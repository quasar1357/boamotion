"""Stage 4: finding the beats in a contraction trace, and the level each rises from.

Positions here are indices into the trace, which holds one point fewer than the
recording because the reference frame has been removed. See LEGACY_MODE.md for the
original's behaviour that `legacy` reproduces.
"""

from __future__ import annotations

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


def find_peaks(
    trace,
    *,
    reference_frame: int,
    peak_window: int = 20,
    peak_threshold: float = 30.0,
    legacy: bool = True,
) -> np.ndarray:
    """Find the beats: local maxima that also clear a height threshold.

    A point is a peak when nothing close to it is higher, and when it rises far enough
    above the trace's zero level. Note that "close to it" reaches one point less far
    than `peak_window` suggests, and that the two ends of the trace are never examined.

    Args:
        trace: The contraction trace.
        reference_frame: Only used for the legacy zero level, which indexes the trace
            with this frame number.
        peak_window: Width of the neighbourhood a peak has to dominate, in points.
        peak_threshold: How far a peak must rise, as a percent of the trace's range.
        legacy: Reproduce the original macro, which takes its zero level from an
            arbitrary sample of the trace rather than from its lowest point.

    Returns:
        The positions of the detected peaks, in ascending order.
    """
    trace = np.asarray(trace, dtype=np.float64)
    half = _even_window(peak_window) // 2
    zero = _zero_level(trace, reference_frame, legacy)
    threshold = (peak_threshold / 100.0) * (trace.max() - zero)

    # The bounds leave the first `half` and last `half + 1` points unexamined.
    peaks = [
        position
        for position in range(half, len(trace) - 1 - half)
        if trace[position] - zero > threshold and _dominates_neighbours(trace, position, half)
    ]

    logger.info("Detected %d peak(s) rising above %.4g", len(peaks), zero + threshold)
    return np.array(peaks, dtype=int)


def beat_baselines(
    trace,
    peaks,
    *,
    high_freq_baseline: bool = True,
    baseline_threshold: float = 2.0,
    baseline_n_points: int = 5,
    legacy: bool = True,
) -> np.ndarray:
    """Find the resting level each beat is measured from, one value per peak.

    Each beat looks backwards over the half of the gap to the previous peak. The
    high-frequency method takes the lowest point there, which needs no rest period;
    the other averages the flattest points, which is steadier but does.

    Args:
        trace: The contraction trace.
        peaks: Peak positions, as returned by `find_peaks`.
        high_freq_baseline: Take the lowest point rather than averaging flat ones.
        baseline_threshold: How flat counts as flat, as a percent of the beat's
            steepest rise. Ignored when `high_freq_baseline` is set.
        baseline_n_points: How many flat points to average. Ignored likewise.
        legacy: Reproduce the original macro, in which too few flat points at one beat
            permanently narrows every later beat, a lone flat point is discarded, and a
            single detected peak ends up with a baseline of zero.

    Returns:
        One baseline value per peak, in the same order.
    """
    trace = np.asarray(trace, dtype=np.float64)
    peaks = np.asarray(peaks, dtype=int)
    if len(peaks) == 0:
        return np.zeros(0)

    positions = _range_positions(peaks, legacy)
    if high_freq_baseline:
        baselines = [_lowest_before(trace, positions, k) for k in range(len(positions))]
    else:
        baselines = _flat_baselines(trace, positions, baseline_threshold, baseline_n_points, legacy)

    baselines = np.array(baselines[: len(peaks)], dtype=np.float64)
    logger.info(
        "Baselines for %d beat(s): %.4g to %.4g", len(baselines), baselines.min(), baselines.max()
    )
    return baselines


def _even_window(peak_window: int) -> int:
    """The original rounds an odd window up, and says so."""
    if peak_window < 2:
        raise ValueError(f"peak_window must be at least 2, not {peak_window}")
    if peak_window % 2 == 0:
        return peak_window
    logger.warning(
        "peak_window raised from %d to %d, as it must be even", peak_window, peak_window + 1
    )
    return peak_window + 1


def _zero_level(trace: np.ndarray, reference_frame: int, legacy: bool) -> float:
    """The level the peak threshold is measured from.

    The original indexes the trace with a frame number, which reads a more or less
    arbitrary sample; corrected, the zero level is the lowest point of the trace.
    """
    if not legacy:
        return float(trace.min())
    if not 0 <= reference_frame < len(trace):
        raise ValueError(
            f"reference frame {reference_frame} is outside a trace of {len(trace)} points; "
            "the legacy zero level indexes the trace with the frame number"
        )
    return float(trace[reference_frame])


def _dominates_neighbours(trace: np.ndarray, position: int, half_window: int) -> bool:
    """Whether a point is the highest nearby.

    The original compares out to `half_window - 1` on each side, one point short of
    what the parameter names, so the neighbourhood is `peak_window - 1` wide.
    """
    neighbours = trace[position - half_window + 1 : position + half_window]
    return bool(trace[position] >= neighbours.max())


def _range_positions(peaks: np.ndarray, legacy: bool) -> np.ndarray:
    """The peak list as the original's range arithmetic sees it.

    A single peak leaves a bare number where an array is expected, so the original
    appends a zero. Every range then measured against that "next peak" comes out
    negative, which is what zeroes the beat's steepest rise.
    """
    if legacy and len(peaks) == 1:
        return np.append(peaks, 0)
    return peaks


def _search_start(positions: np.ndarray, k: int) -> int:
    """Where to start looking back for a baseline: halfway to the previous peak."""
    if k == 0:
        return 0
    return int(positions[k] - _round_half_up((positions[k] - positions[k - 1]) / 2))


def _lowest_before(trace: np.ndarray, positions: np.ndarray, k: int) -> float:
    """The smallest value between the previous peak and this one, the peak included."""
    peak = int(positions[k])
    return float(np.min(trace[_search_start(positions, k) : peak], initial=trace[peak]))


def _steepest_rise(trace: np.ndarray, positions: np.ndarray, k: int) -> float:
    """The largest rise between neighbouring points around a peak.

    This sets the scale for what counts as flat. The radius comes from the gap to the
    *next* peak, which is what a phantom peak at position zero reverses.
    """
    peak = int(positions[k])
    if k == len(positions) - 1:
        gap = peak - positions[k - 1] if len(positions) > 1 else peak
    else:
        gap = positions[k + 1] - peak

    radius = _round_half_up(gap / 4)
    start, stop = peak - radius, peak + radius
    if start <= 0 or stop >= len(trace) or start >= stop:
        return 0.0
    return float(np.diff(trace[start:stop]).max(initial=0.0))


def _flat_points(
    trace: np.ndarray, start: int, peak: int, threshold: float, ceiling: float
) -> list[float]:
    """The values before a peak that barely change and sit low enough to be rest."""
    last = min(peak, len(trace) - 1)
    return [
        float(trace[j])
        for j in range(max(start, 0), last)
        if abs(trace[j + 1] - trace[j]) < threshold and trace[j] < ceiling
    ]


def _flat_baselines(
    trace: np.ndarray,
    positions: np.ndarray,
    baseline_threshold: float,
    baseline_n_points: int,
    legacy: bool,
) -> list[float]:
    ceiling = float(trace.mean()) * 1.5
    n_points = baseline_n_points
    baselines = []

    for k in range(len(positions)):
        peak = int(positions[k])
        start = _search_start(positions, k)
        threshold = (baseline_threshold / 100.0) * _steepest_rise(trace, positions, k)
        flat = _flat_points(trace, start, peak, threshold, ceiling)

        if legacy:
            baseline, n_points = _legacy_flat_average(flat, n_points, k)
        else:
            fallback = _lowest_before(trace, positions, k)
            baseline = float(np.mean(flat[-baseline_n_points:])) if flat else fallback
            if not flat:
                logger.warning("No flat points before peak %d; using the lowest point instead", k)
        baselines.append(baseline)

    return baselines


def _legacy_flat_average(flat: list[float], n_points: int, k: int) -> tuple[float, int]:
    """The original's averaging, including the two ways it can return zero.

    Its array of flat values is created one element long and zero-filled, so no points
    and one point are indistinguishable and both give a baseline of zero. A shortage
    also assigns to the parameter itself, narrowing every later beat.
    """
    length = max(len(flat), 1)
    if length > n_points:
        kept = flat[-n_points:]
    else:
        kept = flat
        n_points = length
        logger.warning(
            "Only %d flat point(s) before peak %d; averaging %d point(s) from here on",
            len(flat),
            k,
            n_points,
        )

    total = math.fsum(kept) if length > 1 else 0.0
    return total / n_points, n_points


def _round_half_up(value: float) -> int:
    """ImageJ rounds a half upward; numpy rounds it to even."""
    return math.floor(value + 0.5)
