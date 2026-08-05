"""Stage 1: choosing the reference frame.

The frame every other frame is measured against. See HOW_IT_WORKS.md for the idea
behind the phase-plane method and for what `legacy` changes.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


def detect_reference_frame(
    frames,
    *,
    speed_window: int = 2,
    ref_search_start: int = 1,
    ref_search_stop: int = 300,
    n_low_values: int = 20,
    n_unity_values: int = 10,
    legacy: bool = True,
) -> int:
    """Find the frame in which the tissue is most at rest, and return its 1-based number.

    Motion is measured between frames `speed_window` apart, then each motion value is
    paired with the next one. Points near the origin are quiet; points near the unity
    line are quiet *and staying quiet*, which is what separates true rest from the
    momentary standstill at the top of a beat.

    Args:
        frames: Anything indexable that yields 2-D frames, such as a FrameSequence.
        speed_window: Frame gap used to measure motion.
        ref_search_start: First frame of the search range, 1-based.
        ref_search_stop: Last frame of the search range, 1-based.
        n_low_values: How many quietest candidates to shortlist.
        n_unity_values: How many of those survive the stability test.
        legacy: Reproduce the original macro, in which the stability test has no effect
            and the resulting frame number is one too low.
    """
    n_frames = len(frames)
    ref_search_stop = _fit_search_range(n_frames, speed_window, ref_search_start, ref_search_stop)

    motion = _motion_trace(frames, speed_window, ref_search_stop)
    window = motion[ref_search_start:ref_search_stop]

    n_pairs = len(window) - 1
    if n_pairs < 2:
        raise ValueError(
            f"only {n_pairs} usable point(s) between frames {ref_search_start} and "
            f"{ref_search_stop}; widen the search range or use a longer recording"
        )
    n_low_values, n_unity_values = _fit_selection_sizes(n_pairs, n_low_values, n_unity_values)

    if legacy:
        index = _select_legacy(window, n_low_values, n_unity_values)
        frame = index + 1
    else:
        index = _select(window, n_low_values, n_unity_values)
        frame = index + ref_search_start + 1

    logger.info(
        "Reference frame: %d (searched frames %d-%d)", frame, ref_search_start, ref_search_stop
    )
    return frame


def _fit_search_range(n_frames: int, speed_window: int, start: int, stop: int) -> int:
    """Shrink the search range to what the recording can support, as the original does."""
    if stop >= n_frames:
        fitted = n_frames - speed_window - 1
        logger.warning(
            "ref_search_stop reduced from %d to %d: the recording has %d frames",
            stop,
            fitted,
            n_frames,
        )
        stop = fitted
    if stop <= start:
        raise ValueError(
            f"nothing to search between frames {start} and {stop}; the recording has "
            f"{n_frames} frames, so lower ref_search_start"
        )
    return stop


def _fit_selection_sizes(n_pairs: int, n_low_values: int, n_unity_values: int) -> tuple[int, int]:
    if n_low_values > n_pairs:
        logger.warning(
            "n_low_values reduced from %d to %d: only that many candidates exist",
            n_low_values,
            n_pairs,
        )
        n_low_values = n_pairs
    if n_unity_values >= n_low_values:
        logger.warning(
            "n_unity_values reduced from %d to %d, one below n_low_values",
            n_unity_values,
            n_low_values - 1,
        )
        n_unity_values = n_low_values - 1
    return n_low_values, max(n_unity_values, 1)


def _motion_trace(frames, speed_window: int, count: int) -> np.ndarray:
    """Mean absolute difference between frames `speed_window` apart, for the first `count`."""
    recent: deque[np.ndarray] = deque(maxlen=speed_window + 1)
    values = np.empty(count, dtype=np.float64)
    for i in range(count + speed_window):
        recent.append(np.asarray(frames[i], dtype=np.float32))
        if len(recent) == speed_window + 1:
            values[i - speed_window] = np.abs(recent[0] - recent[-1]).mean(dtype=np.float64)
    return values


def _unity_distance(motion: np.ndarray, shifted: np.ndarray) -> np.ndarray:
    """How far each pair sits from the unity line, where consecutive motion is equal."""
    with np.errstate(divide="ignore", invalid="ignore"):
        distance = np.abs(motion / shifted - 1.0)
    # 0/0 means both frames were perfectly still, which is exactly on the unity line.
    return np.nan_to_num(distance, nan=0.0, posinf=np.inf, neginf=np.inf)


def _select(window: np.ndarray, n_low_values: int, n_unity_values: int) -> int:
    """The method as documented: quietest points, then the most stable among them."""
    motion, shifted = window[:-1], window[1:]
    radius = np.hypot(motion, shifted)

    quietest = np.argsort(radius, kind="stable")[:n_low_values]
    unity = _unity_distance(motion[quietest], shifted[quietest])
    finalists = quietest[np.argsort(unity, kind="stable")[:n_unity_values]]

    unity = _unity_distance(motion[finalists], shifted[finalists])
    return int(finalists[np.argmin(motion[finalists] * shifted[finalists] * unity)])


def _select_legacy(window: np.ndarray, n_low_values: int, n_unity_values: int) -> int:
    """The original, transcribed loop for loop so its behaviour is visible.

    Both loops stop one iteration short of their array, which is what makes the
    stability test inert: the unfilled last entry stays 0 and always wins.
    """
    motion, shifted = window[:-1], window[1:]
    radius = np.hypot(motion, shifted)
    quietest = np.argsort(radius, kind="stable")

    unity = np.zeros(n_low_values)
    for d in range(n_low_values - 1):
        index = quietest[d]
        unity[d] = _unity_distance(motion[index], shifted[index])

    ranked = np.argsort(unity, kind="stable")
    best_index, best_score = None, None
    for d in range(min(n_unity_values, n_low_values) - 1):
        index = quietest[ranked[d]]
        score = motion[index] * shifted[index] * unity[ranked[d]]
        if best_score is None or score < best_score:
            best_index, best_score = index, score

    # The original leaves this undefined; falling back keeps a valid answer.
    return int(quietest[ranked[0]] if best_index is None else best_index)
