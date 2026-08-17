"""The whole analysis in one object.

Every stage already exists as a function that states exactly what it needs. `Boa` does
nothing they do not: it unpacks the settings, calls them in order, and collects what they
produce. Reach for the functions directly whenever you want one stage on its own.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from boamotion.frames import load_frames
from boamotion.params import Params
from boamotion.reference import detect_reference_frame
from boamotion.result import Result
from boamotion.traces import build_motion_pixel_mask, measure_contraction, measure_speed
from boamotion.transients import find_baselines, find_peaks, measure_transients

logger = logging.getLogger(__name__)


class Boa:
    """Measure contraction in a recording.

    >>> boa = Boa("recordings/A001", framerate=25)
    >>> result = boa.run()
    >>> result.save("results")

    Settings can be given as keyword arguments, or as a ready-made `Params`, and can be
    changed with `set_params()` at any time before `run()`.

    Args:
        source: A directory of TIFF frames, or anything indexable that yields 2-D frames,
            such as a `FrameSequence` or a 3-D array.
        params: Settings for the run. Defaults to the original macro's defaults.
        name: What to call the recording in the output. Taken from the path if not given.
        **settings: Individual settings, as an alternative to passing `params`.
    """

    def __init__(
        self, source, *, params: Params | None = None, name: str | None = None, **settings
    ):
        if params is not None and settings:
            raise ValueError(
                "pass either a Params object or individual settings, not both; "
                f"got params and {sorted(settings)}. To start from a Params and adjust "
                "it, call set_params() afterwards"
            )
        self.source = source
        self.params = params if params is not None else Params(**settings)
        self.name = name or _name_of(source)
        self.result: Result | None = None

    def set_params(self, **settings) -> Boa:
        """Change several settings at once, and return self so calls can be chained.

        >>> boa = Boa("recordings/A001")
        >>> boa.set_params(framerate=25, peak_window=16, legacy=False)

        The settings are validated straight away, so a wrong name or value is caught
        here rather than part-way through a run.
        """
        self.params.update(**settings)
        return self

    def run(self) -> Result:
        """Run every stage and return the results, which are also kept on `.result`.

        Everything the run logs is captured and written out with the results, so the
        package's own logger is lowered to INFO for the duration and restored after. If
        you have configured logging yourself and set it higher, you will see those
        messages while a run is in progress.
        """
        self.params.validate()
        recorder = _LogRecorder()
        package = logging.getLogger("boamotion")
        level = package.level
        package.addHandler(recorder)
        if not package.isEnabledFor(logging.INFO):
            package.setLevel(logging.INFO)
        try:
            self.result = self._analyse(recorder)
        finally:
            package.removeHandler(recorder)
            package.setLevel(level)
        return self.result

    def _analyse(self, recorder: _LogRecorder) -> Result:
        params = self.params
        frames = load_frames(self.source) if _is_path(self.source) else self.source
        logger.info("Analysing %s: %d frames at %g fps", self.name, len(frames), params.framerate)

        reference_frame = params.reference_frame or detect_reference_frame(
            frames,
            speed_window=params.speed_window,
            ref_search_start=params.ref_search_start,
            ref_search_stop=params.ref_search_stop,
            n_low_values=params.n_low_values,
            n_unity_values=params.n_unity_values,
            legacy=params.legacy,
        )

        mask = None
        if params.noise_reduction:
            mask = build_motion_pixel_mask(
                frames,
                reference_frame,
                mask_start_frame=params.mask_start_frame,
                mask_end_frame=params.mask_end_frame,
                legacy=params.legacy,
            )

        contraction = measure_contraction(frames, reference_frame, mask=mask, legacy=params.legacy)
        speed = measure_speed(
            frames,
            reference_frame,
            speed_window=params.speed_window,
            mask=mask,
            legacy=params.legacy,
        )
        beats = self._measure_beats(contraction, reference_frame)

        return Result(
            name=self.name,
            params=params,
            reference_frame=reference_frame,
            contraction=contraction,
            speed=speed,
            beats=beats,
            mask=mask,
            warnings=recorder.warnings(),
            log=recorder.lines(),
        )

    def _measure_beats(self, contraction: np.ndarray, reference_frame: int):
        params = self.params
        if not params.transient_analysis:
            logger.info("Transient analysis is off; no beats measured")
            peaks, baselines = np.zeros(0, dtype=int), np.zeros(0)
        else:
            peaks = find_peaks(
                contraction,
                reference_frame=reference_frame,
                peak_window=params.peak_window,
                peak_threshold=params.peak_threshold,
                legacy=params.legacy,
            )
            baselines = find_baselines(
                contraction,
                peaks,
                high_freq_baseline=params.high_freq_baseline,
                baseline_threshold=params.baseline_threshold,
                baseline_n_points=params.baseline_n_points,
                legacy=params.legacy,
            )
        return measure_transients(
            contraction,
            peaks,
            baselines,
            framerate=params.framerate,
            percentages=params.percentages,
            flank_level_index=params.flank_level_index,
        )

    def __repr__(self) -> str:
        state = "not run yet" if self.result is None else f"{self.result.n_beats} beats"
        return f"Boa({self.name!r}, {state})"


class _LogRecorder(logging.Handler):
    """Keeps what a run logged, so the results can carry their own account of it."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def lines(self) -> tuple[str, ...]:
        return tuple(f"{r.levelname}: {r.getMessage()}" for r in self.records)

    def warnings(self) -> tuple[str, ...]:
        """The warnings alone, which is where a setting being changed shows up."""
        return tuple(r.getMessage() for r in self.records if r.levelno >= logging.WARNING)


def _is_path(source) -> bool:
    return isinstance(source, (str, Path))


def _name_of(source) -> str:
    return Path(source).name if _is_path(source) else "recording"
