"""Stages 2 and 3: the pixel mask, and the contraction and speed traces.

Everything here works on the recording *after the reference frame has been removed*,
which is what the original macro measures. Frame positions below therefore count
within that shortened recording.
"""

from __future__ import annotations

import logging

import numpy as np

logger = logging.getLogger(__name__)


def pixel_mask(
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


def _frames_to_use(
    n_frames: int,
    reference_frame: int,
    start: int,
    end: int | None,
    legacy: bool,
) -> list[int]:
    """Positions of the frames to accumulate, as 0-based indices into the recording."""
    if not 1 <= reference_frame <= n_frames:
        raise ValueError(
            f"reference_frame {reference_frame} is outside the recording, which has "
            f"{n_frames} frames"
        )
    if start < 1:
        raise ValueError(f"mask_start_frame is 1-based and must be at least 1, got {start}")

    without_reference = [i for i in range(n_frames) if i != reference_frame - 1]
    # The original's loop stops before its end frame instead of including it.
    last = len(without_reference) if end is None else (end - 1 if legacy else end)
    selected = without_reference[start - 1 : last]

    if not selected:
        raise ValueError(
            f"no frames left to build the mask from between {start} and {end}; the "
            f"recording has {n_frames} frames"
        )
    return selected
