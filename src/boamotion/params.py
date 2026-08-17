"""Analysis parameters.

Field names follow Python conventions; the name used in the original MUSCLEMOTION
macro is given in brackets so the two can be cross-referenced.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PERCENTAGES = (10, 50, 90)


@dataclass
class Params:
    """Settings for one contraction analysis.

    All frame numbers are 1-based, matching FIJI and the MUSCLEMOTION manual, so a
    frame number means the same thing in both tools.

    Recording:
        framerate: Frames per second of the recording [recordedFramerate].
        speed_window: Frame shift used for the speed trace [speedWindow].

    Reference frame:
        reference_frame: Frame to measure against, or None to detect it automatically
            [referenceFrameSlice / autodetectReferenceFrame].
        ref_search_start: First frame considered during detection [autoDetectStart].
        ref_search_stop: Last frame considered during detection [autoDetectStop].
        n_low_values: How many quietest candidate frames to keep [lowValueN].
        n_unity_values: How many of those to keep after the stability test
            [unitySelectionN].

    Noise reduction:
        noise_reduction: Restrict the measurement to pixels that actually move
            [SNRimprovement / maxProject].
        mask_start_frame: First frame used to build the mask [MPstartRange].
        mask_end_frame: Last frame used to build the mask, or None for all
            [MPendRange].

    Transient analysis:
        transient_analysis: Detect peaks and measure them
            [automaticTransientDetection].
        peak_window: Expected peak width; roughly 0.75 x frames per beat
            [PeakDetectionWindow].
        peak_threshold: Minimum peak height as a percentage of the full range
            [peakThreshold].
        percentages: Amplitude levels, in percent above baseline, at which transient
            durations are measured [percentages]. Must be ascending.
        flank_level_index: Which of those levels defines the flanks, as an index into
            `percentages`. Its two crossings give time-to-peak, relaxation time and
            contraction duration. The original always uses the first, which is the
            default here.
        baseline_threshold: Flatness tolerance for baseline detection, in percent
            [baselineThreshold].
        baseline_n_points: Frames averaged to give the baseline [baselineNumberOfPoints].
        high_freq_baseline: Take the minimum before each peak as the baseline instead
            of averaging. For fast beating, where diastole is short
            [highFreqBaselineDetection].

    Compatibility:
        legacy: Reproduce the original macro's behaviour, including its known bugs.
            See DECISIONS.md for what changes when this is False.
    """

    # Recording
    framerate: float = 100.0
    speed_window: int = 2

    # Reference frame
    reference_frame: int | None = None
    ref_search_start: int = 1
    ref_search_stop: int = 300
    n_low_values: int = 20
    n_unity_values: int = 10

    # Noise reduction
    noise_reduction: bool = True
    mask_start_frame: int = 1
    mask_end_frame: int | None = None

    # Transient analysis
    transient_analysis: bool = True
    peak_window: int = 20
    peak_threshold: float = 30.0
    percentages: tuple[int, ...] = DEFAULT_PERCENTAGES
    flank_level_index: int = 0
    baseline_threshold: float = 2.0
    baseline_n_points: int = 5
    high_freq_baseline: bool = True

    # Compatibility
    legacy: bool = True

    def __post_init__(self) -> None:
        self.percentages = tuple(self.percentages)
        self.validate()

    def update(self, **settings) -> Params:
        """Change several settings at once, and return self so calls can be chained.

        Unknown names are rejected rather than quietly added, which a plain attribute
        assignment cannot do.
        """
        unknown = sorted(set(settings) - {field.name for field in fields(self)})
        if unknown:
            raise ValueError(f"unknown setting(s) {unknown}; see Params for what exists")
        for name, value in settings.items():
            setattr(self, name, value)
        self.percentages = tuple(self.percentages)
        self.validate()
        return self

    @property
    def sampling_interval_ms(self) -> float:
        """Time between consecutive frames, in milliseconds."""
        return 1000.0 / self.framerate

    def validate(self) -> None:
        """Raise ValueError on the first inconsistent parameter.

        Called on construction, and again before an analysis runs so that attributes
        changed afterwards are still checked.
        """
        if self.framerate <= 0:
            raise ValueError(f"framerate must be positive, got {self.framerate}")
        if self.speed_window < 1:
            raise ValueError(f"speed_window must be at least 1 frame, got {self.speed_window}")

        if self.reference_frame is not None and self.reference_frame < 1:
            raise ValueError(
                f"reference_frame is 1-based and must be at least 1, "
                f"got {self.reference_frame} (use None to detect it automatically)"
            )
        if self.ref_search_start < 1:
            raise ValueError(
                f"ref_search_start is 1-based and must be at least 1, got {self.ref_search_start}"
            )
        if self.ref_search_stop <= self.ref_search_start:
            raise ValueError(
                f"ref_search_stop ({self.ref_search_stop}) must be greater than "
                f"ref_search_start ({self.ref_search_start})"
            )
        if self.n_low_values < 2:
            raise ValueError(f"n_low_values must be at least 2, got {self.n_low_values}")
        if not 1 <= self.n_unity_values < self.n_low_values:
            raise ValueError(
                f"n_unity_values must be at least 1 and below n_low_values "
                f"({self.n_low_values}), got {self.n_unity_values}"
            )

        if self.mask_start_frame < 1:
            raise ValueError(
                f"mask_start_frame is 1-based and must be at least 1, got {self.mask_start_frame}"
            )
        if self.mask_end_frame is not None and self.mask_end_frame <= self.mask_start_frame:
            raise ValueError(
                f"mask_end_frame ({self.mask_end_frame}) must be greater than "
                f"mask_start_frame ({self.mask_start_frame}), or None for all frames"
            )

        if self.peak_window < 2:
            raise ValueError(f"peak_window must be at least 2 frames, got {self.peak_window}")
        if not 0 <= self.peak_threshold <= 100:
            raise ValueError(
                f"peak_threshold is a percentage and must be in 0-100, got {self.peak_threshold}"
            )
        if not self.percentages:
            raise ValueError("percentages must contain at least one level")
        if any(not 1 <= p <= 99 for p in self.percentages):
            raise ValueError(f"percentages must all be in 1-99, got {self.percentages}")
        if list(self.percentages) != sorted(set(self.percentages)):
            raise ValueError(
                f"percentages must be ascending and free of duplicates, got {self.percentages}"
            )
        if not 0 <= self.flank_level_index < len(self.percentages):
            raise ValueError(
                f"flank_level_index must select one of the {len(self.percentages)} "
                f"percentages, got {self.flank_level_index}"
            )
        if not 0 <= self.baseline_threshold <= 100:
            raise ValueError(
                f"baseline_threshold is a percentage and must be in 0-100, "
                f"got {self.baseline_threshold}"
            )
        if self.baseline_n_points < 1:
            raise ValueError(f"baseline_n_points must be at least 1, got {self.baseline_n_points}")

    def to_dict(self) -> dict[str, Any]:
        """Return the parameters as plain Python types, suitable for YAML or JSON."""
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = list(value) if isinstance(value, tuple) else value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Params:
        """Build parameters from a mapping, rejecting unknown keys."""
        known = {f.name for f in fields(cls)}
        unknown = set(data) - known
        if unknown:
            raise ValueError(
                f"unknown parameter(s): {', '.join(sorted(unknown))}. "
                f"Valid names are: {', '.join(sorted(known))}"
            )
        return cls(**data)

    def to_yaml(self, path: str | Path) -> Path:
        """Write the parameters to a YAML file and return its path."""
        path = Path(path)
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(self.to_dict(), fh, sort_keys=False, default_flow_style=False)
        return path

    @classmethod
    def from_yaml(cls, path: str | Path) -> Params:
        """Read parameters from a YAML file."""
        path = Path(path)
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ValueError(f"{path} must contain a mapping of parameter names to values")
        return cls.from_dict(data)
