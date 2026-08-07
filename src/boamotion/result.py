"""Collecting a finished analysis, and writing it out.

The original macro's output files are reproduced by name and by format, so its results
and ours can be diffed directly. Three of the seven are figures, which arrive in step 12,
and the log file follows the logging in step 13.

Alongside them we write the effective parameters and a tidy CSV, which the original has
no equivalent of. Those use our own column names; the reproduced files use the original's.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from boamotion.params import Params

logger = logging.getLogger(__name__)

# The original's Results table, in the order the macro fills the columns.
ORIGINAL_HEADERS = {
    "contraction_duration_ms": "Contraction duration [{first}% above baseline] (ms)",
    "time_to_peak_ms": "Time-to-peak (ms)",
    "relaxation_time_ms": "Relaxation Time (ms)",
    "_percentages_here": None,
    "peak_to_peak_ms": "Peak-to-peak time (ms)",
    "baseline": "Baseline value (a.u.)",
    "peak_amplitude": "Peak amplitude (a.u.)",
    "contraction_amplitude": "Contraction amplitude (a.u.)",
}


@dataclass(frozen=True)
class Result:
    """Everything one analysis produced, and the settings that produced it.

    The pieces are kept together because writing the files, drawing the figures and
    reproducing the run all need the same set, and separating them lets them drift.

    Attributes:
        name: The recording's name, which the output directory is named after.
        params: The settings used. Written out so the run can be repeated exactly.
        reference_frame: The frame everything was measured against, 1-based.
        contraction: The contraction trace, one point per analysed frame.
        speed: The speed trace, shorter by `speed_window` points.
        beats: One row per detected beat, as `measure_transients` returns it.
        mask: The pixel mask used, or None if the whole frame was measured.
        adjustments: Settings the analysis had to change to fit the recording, as the
            messages it logged. Empty when everything was used as asked for.
    """

    name: str
    params: Params
    reference_frame: int
    contraction: np.ndarray
    speed: np.ndarray
    beats: pd.DataFrame
    mask: np.ndarray | None = None
    adjustments: tuple[str, ...] = field(default=())

    @property
    def time_ms(self) -> np.ndarray:
        """Time axis for the contraction trace.

        One sampling interval per point, as the original does. The reference frame was
        removed, so every point after it sits one frame earlier than it really was.
        """
        return np.arange(len(self.contraction)) * self.params.sampling_interval_ms

    @property
    def speed_time_ms(self) -> np.ndarray:
        """Time axis for the speed trace, which also starts at zero."""
        return np.arange(len(self.speed)) * self.params.sampling_interval_ms

    @property
    def calculated_speed(self) -> np.ndarray:
        """The contraction trace differentiated, for comparison against measured speed.

        Where the measurement behaves linearly the two agree; a visible divergence is a
        warning that something is wrong.
        """
        return np.abs(np.diff(self.contraction))[: len(self.speed)]

    @property
    def n_beats(self) -> int:
        return len(self.beats)

    def save(self, directory) -> Path:
        """Write the results into a new folder under `directory`, and return its path.

        An existing folder is never overwritten; a numbered one is made alongside it,
        as the original does.
        """
        # legacy: the original's own file and folder names, mixed case and all
        names = file_names(self.params.legacy)
        target = _new_directory(Path(directory), self.name, names["folder"])
        target.mkdir(parents=True)

        _write_trace(target / names["contraction"], self.time_ms, self.contraction)
        _write_trace(target / names["speed"], self.speed_time_ms, self.speed)
        _write_overview(target / names["overview"], self.beats, self.params)

        self.params.to_yaml(target / "parameters.yaml")
        self.beats.to_csv(target / "beats.csv")
        _write_summary(target / "run-summary.txt", self)

        logger.info("Wrote %d files to %s", len(list(target.iterdir())), target)
        return target

    def __repr__(self) -> str:
        return (
            f"Result({self.name!r}: {len(self.contraction)} points, "
            f"reference frame {self.reference_frame}, {self.n_beats} beats, "
            f"{'masked' if self.mask is not None else 'whole frame'})"
        )


def original_headers(params: Params) -> dict[str, str]:
    """Map our column names onto the original's, in the order the macro writes them.

    The macro hard-codes "10% above baseline" whatever the first percentage actually is,
    so the header can disagree with the number beneath it.
    """
    # legacy: the header says 10% even when the level used is not 10%
    first = 10 if params.legacy else params.percentages[0]
    headers = {}
    for column, template in ORIGINAL_HEADERS.items():
        if column == "_percentages_here":
            for level in params.percentages:
                headers[f"transient_{level}pct_ms"] = (
                    f"{100 - level}-to-{100 - level} transient (ms)"
                )
        else:
            headers[column] = template.format(first=first)
    return headers


def file_names(legacy: bool) -> dict[str, str]:
    """What the output files are called.

    The original mixes conventions — lower-case text files, capitalised images, spaces
    and brackets in one of them, and a folder called `-Contr-Results`. Spaces and
    brackets in particular are awkward from a shell, which matters on a cluster. With
    `legacy=False` the names are lower case and hyphenated throughout.
    """
    if legacy:
        return {
            "folder": "-Contr-Results",
            "contraction": "contraction.txt",
            "speed": "speed-of-contraction.txt",
            "overview": "Overview-results.txt",
        }
    return {
        "folder": "-results",
        "contraction": "contraction.txt",
        "speed": "speed-of-contraction.txt",
        "overview": "overview-results.txt",
    }


def _new_directory(parent: Path, name: str, suffix: str) -> Path:
    """The first free `<name><suffix>` folder, numbered if earlier ones exist."""
    base = parent / f"{name}{suffix}"
    if not base.exists():
        return base
    version = 1
    while (parent / f"{base.name}-{version}").exists():
        version += 1
    return parent / f"{base.name}-{version}"


def _write_trace(path: Path, times: np.ndarray, values: np.ndarray) -> None:
    """Two tab-separated columns, no header, as the original writes them."""
    lines = (f"{time}\t{value}" for time, value in zip(times, values, strict=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_overview(path: Path, beats: pd.DataFrame, params: Params) -> None:
    """The original's Results table: our columns renamed, ours alone dropped."""
    headers = original_headers(params)
    table = beats.reindex(columns=list(headers)).rename(columns=headers)

    # legacy: a measurement that was never found is written as 0, which reads as a real
    # value; corrected, it is left empty so a reader can tell the two apart.
    if params.legacy:
        table = table.fillna(0)

    table.index = pd.RangeIndex(1, len(table) + 1)
    table.to_csv(path, sep="\t", index_label=" ", lineterminator="\n")


def _write_summary(path: Path, result: Result) -> None:
    """What actually happened, as opposed to what was asked for."""
    coverage = "none" if result.mask is None else f"{100 * result.mask.mean():.1f}% of the frame"
    lines = [
        f"recording: {result.name}",
        f"reference frame: {result.reference_frame}",
        f"trace points: {len(result.contraction)}",
        f"speed points: {len(result.speed)}",
        f"beats detected: {result.n_beats}",
        f"pixel mask: {coverage}",
    ]
    if result.adjustments:
        lines += ["", "settings the analysis had to change:"]
        lines += [f"  - {message}" for message in result.adjustments]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
