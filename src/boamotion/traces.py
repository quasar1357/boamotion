"""Stages 2 and 3: the pixel mask, and the contraction and speed traces.

Everything here works on the recording *after the reference frame has been removed*,
which is what the original macro measures. Frame positions below therefore count
within that shortened recording.
"""

from __future__ import annotations

import logging
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


def motion_pixel_mask(
    frames,
    reference_frame: int,
    *,
    mask_start_frame: int = 1,
    mask_end_frame: int | None = None,
    legacy: bool = True,
) -> np.ndarray:
    """Find the pixels that move enough to be worth measuring.

    Accumulates the largest change each pixel ever shows against the reference frame,
    then keeps whatever exceeds the mean plus one standard deviation of that map.
    Pixels that never move contribute only noise to a whole-frame average, so
    excluding them lifts the signal well clear of the noise floor.

    Args:
        frames: Anything indexable that yields 2-D frames, such as a FrameSequence.
        reference_frame: Which frame to measure against, 1-based.
        mask_start_frame: First frame to accumulate, counting without the reference.
        mask_end_frame: Last frame to accumulate, or None for all of them.
        legacy: Reproduce the original macro, which stops one frame before
            `mask_end_frame` rather than including it.

    Returns:
        A boolean array the size of one frame, True where the pixel is kept.
    """
    selected = _frames_to_use(
        len(frames), reference_frame, mask_start_frame, mask_end_frame, legacy
    )
    reference = np.asarray(frames[reference_frame - 1], dtype=np.float32)

    peak_change = np.zeros(reference.shape, dtype=np.float32)
    for position in selected:
        change = np.abs(np.asarray(frames[position], dtype=np.float32) - reference)
        np.maximum(peak_change, change, out=peak_change)

    # ImageJ's standard deviation divides by n-1, so ddof=1 rather than numpy's default.
    threshold = peak_change.mean(dtype=np.float64) + peak_change.std(ddof=1, dtype=np.float64)
    mask = peak_change >= threshold

    logger.info(
        "Pixel mask keeps %d of %d pixels (%.1f%%) from %d frames",
        mask.sum(),
        mask.size,
        100.0 * mask.mean(),
        len(selected),
    )
    return mask


def contraction_trace(
    frames,
    reference_frame: int,
    *,
    mask: np.ndarray | None = None,
    legacy: bool = True,
) -> np.ndarray:
    """Measure how far each frame is from rest, one value per frame.

    Every frame except the reference is compared against it, and the mean absolute
    difference is one point of the trace. This is the contraction waveform; its units
    are arbitrary.

    The mean is taken over the *whole* frame with masked-out pixels counting as zero,
    not over the kept pixels alone, matching the original. Amplitudes therefore scale
    with how much of the frame the mask keeps.

    Args:
        frames: Anything indexable that yields 2-D frames, such as a FrameSequence.
        reference_frame: The frame at rest, 1-based.
        mask: Boolean mask from motion_pixel_mask, or None to use every pixel.
        legacy: Reproduce the original macro, which weights kept pixels by 255
            rather than 1. That scales the whole trace by a constant.
    """
    positions = _frames_without_reference(len(frames), reference_frame)
    reference = np.asarray(frames[reference_frame - 1], dtype=np.float32)
    weight = _mask_weight(mask, reference.shape, legacy)

    values = np.empty(len(positions), dtype=np.float64)
    for index, position in enumerate(positions):
        values[index] = _mean_change(
            np.asarray(frames[position], dtype=np.float32), reference, weight
        )

    _report("Contraction", values, mask)
    return values


def speed_trace(
    frames,
    reference_frame: int,
    *,
    speed_window: int = 2,
    mask: np.ndarray | None = None,
    legacy: bool = True,
) -> np.ndarray:
    """Measure how fast the image is changing, one value per frame.

    Same measurement as the contraction trace, but each frame is compared against one
    `speed_window` frames later instead of against a fixed reference. Because the
    difference is absolute the result is always positive, so a single beat produces two
    humps: one while contracting, one while relaxing, with a dip between them where the
    tissue is momentarily still.

    The trace is `speed_window` points shorter than the contraction trace, since the
    last frames have no partner to be compared against.
    """
    positions = _frames_without_reference(len(frames), reference_frame)
    if speed_window < 1:
        raise ValueError(f"speed_window must be at least 1 frame, got {speed_window}")
    if len(positions) <= speed_window:
        raise ValueError(
            f"speed_window of {speed_window} leaves nothing to measure in a recording "
            f"of {len(frames)} frames"
        )

    shape = np.asarray(frames[positions[0]]).shape
    weight = _mask_weight(mask, shape, legacy)

    recent: deque[np.ndarray] = deque(maxlen=speed_window + 1)
    values = np.empty(len(positions) - speed_window, dtype=np.float64)
    for index, position in enumerate(positions):
        recent.append(np.asarray(frames[position], dtype=np.float32))
        if len(recent) == speed_window + 1:
            values[index - speed_window] = _mean_change(recent[0], recent[-1], weight)

    _report("Speed", values, mask)
    return values


def _frames_without_reference(n_frames: int, reference_frame: int) -> list[int]:
    """Positions of the analysed frames, as 0-based indices into the recording."""
    if not 1 <= reference_frame <= n_frames:
        raise ValueError(
            f"reference_frame {reference_frame} is outside the recording, which has "
            f"{n_frames} frames"
        )
    return [i for i in range(n_frames) if i != reference_frame - 1]


def _mask_weight(mask: np.ndarray | None, shape, legacy: bool) -> np.ndarray | None:
    """Per-pixel multiplier. The original's binary mask holds 255, not 1."""
    if mask is None:
        return None
    if mask.shape != shape:
        raise ValueError(f"mask is {mask.shape} but the frames are {shape}")
    return mask.astype(np.float32) * (255.0 if legacy else 1.0)


def _mean_change(frame: np.ndarray, other: np.ndarray, weight: np.ndarray | None) -> float:
    """Mean absolute difference over the whole frame, masked pixels counting as zero."""
    change = np.abs(frame - other)
    if weight is not None:
        change = change * weight
    return float(change.mean(dtype=np.float64))


def _report(name: str, values: np.ndarray, mask: np.ndarray | None) -> None:
    logger.info(
        "%s trace: %d points, %.1f to %.1f (%s)",
        name,
        len(values),
        values.min(),
        values.max(),
        "masked" if mask is not None else "whole frame",
    )


def _frames_to_use(
    n_frames: int,
    reference_frame: int,
    start: int,
    end: int | None,
    legacy: bool,
) -> list[int]:
    """Positions of the frames to accumulate, as 0-based indices into the recording."""
    if start < 1:
        raise ValueError(f"mask_start_frame is 1-based and must be at least 1, got {start}")

    without_reference = _frames_without_reference(n_frames, reference_frame)
    # The original's loop stops before its end frame instead of including it.
    last = len(without_reference) if end is None else (end - 1 if legacy else end)
    selected = without_reference[start - 1 : last]

    if not selected:
        raise ValueError(
            f"no frames left to build the mask from between {start} and {end}; the "
            f"recording has {n_frames} frames"
        )
    return selected
