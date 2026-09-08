"""A synthetic beating recording with known ground truth.

Used to test the analysis against known answers, and as a stand-in for the demo dataset
the MUSCLEMOTION manual describes, which its public repository does not include.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import tifffile

logger = logging.getLogger(__name__)


@dataclass
class SyntheticRecording:
    """A generated recording together with the truth used to build it.

    Frame numbers are 1-based, matching the rest of the package.

    Attributes:
        frames: The recording, shaped (n_frames, height, width).
        peak_frames: Frames of maximum displacement, one per beat.
        rest_frames: Frames where the tissue is completely still.
        framerate: Frames per second the recording is meant to represent.
        frames_per_beat: Length of one beat cycle, in frames.
    """

    frames: np.ndarray
    peak_frames: tuple[int, ...]
    rest_frames: tuple[int, ...]
    framerate: float
    frames_per_beat: int

    @property
    def n_frames(self) -> int:
        """Number of frames in the recording."""
        return len(self.frames)

    @property
    def beat_interval_ms(self) -> float:
        """Time between consecutive peaks, in milliseconds."""
        return self.frames_per_beat * 1000.0 / self.framerate

    def write(self, directory: str | Path) -> Path:
        """Write the recording as one TIFF per frame and return the directory."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for i, frame in enumerate(self.frames, start=1):
            tifffile.imwrite(directory / f"frame_{i:04d}.tif", frame)
        logger.info("Wrote %d synthetic frames to %s", self.n_frames, directory)
        return directory

    def __repr__(self) -> str:
        return (
            f"SyntheticRecording({self.n_frames} frames, "
            f"{self.frames.shape[2]} x {self.frames.shape[1]}, "
            f"{len(self.peak_frames)} beats at {self.framerate} fps)"
        )


def _beat_profile(at_rest: int, rising: int, falling: int) -> np.ndarray:
    """Displacement over one beat, from 0 at rest to exactly 1 at the peak."""
    rise = 0.5 * (1 - np.cos(np.pi * np.arange(1, rising + 1) / rising))
    fall = 0.5 * (1 + np.cos(np.pi * np.arange(1, falling + 1) / falling))
    return np.concatenate([np.zeros(at_rest), rise, fall])


def _blob(shape: tuple[int, int], x: float, y: float, sigma: float) -> np.ndarray:
    rows, cols = np.ogrid[: shape[0], : shape[1]]
    return np.exp(-((cols - x) ** 2 + (rows - y) ** 2) / (2 * sigma**2))


def synthetic_recording(
    n_beats: int = 4,
    frames_at_rest: int = 10,
    frames_rising: int = 6,
    frames_falling: int = 9,
    shape: tuple[int, int] = (64, 80),
    displacement: float = 6.0,
    noise: float = 0.0,
    framerate: float = 25.0,
    dtype: type = np.uint16,
    seed: int = 0,
) -> SyntheticRecording:
    """Generate a beating recording whose peaks and rest periods are known exactly.

    A bright blob shifts sideways and returns, once per beat, next to a second blob
    that never moves. The static blob gives the pixel mask something to exclude and
    the background something other than noise.

    Args:
        n_beats: Number of contraction cycles.
        frames_at_rest: Still frames before each contraction.
        frames_rising: Frames taken to reach full displacement.
        frames_falling: Frames taken to return to rest.
        shape: Frame size as (height, width).
        displacement: How far the moving blob travels, in pixels.
        noise: Gaussian noise, as a fraction of full brightness.
        framerate: Frames per second the recording represents.
        dtype: Integer type of the frames, as a microscope would deliver.
        seed: Seed for the noise, so recordings are reproducible.
    """
    if n_beats < 1:
        raise ValueError(f"n_beats must be at least 1, got {n_beats}")
    if min(frames_at_rest, frames_rising, frames_falling) < 1:
        raise ValueError("each beat needs at least one frame at rest, rising and falling")

    profile = np.tile(_beat_profile(frames_at_rest, frames_rising, frames_falling), n_beats)
    frames_per_beat = frames_at_rest + frames_rising + frames_falling

    height, width = shape
    static = 0.6 * _blob(shape, x=width * 0.2, y=height * 0.5, sigma=min(shape) / 12)
    rng = np.random.default_rng(seed)
    full_scale = float(np.iinfo(dtype).max) * 0.8

    stack = np.empty((len(profile), height, width), dtype=dtype)
    for i, offset in enumerate(profile):
        image = static + _blob(
            shape,
            x=width * 0.65 + displacement * offset,
            y=height * 0.5,
            sigma=min(shape) / 10,
        )
        if noise:
            image = image + rng.normal(0.0, noise, shape)
        stack[i] = np.clip(image, 0.0, 1.0) * full_scale

    peak_frames = tuple(
        beat * frames_per_beat + frames_at_rest + frames_rising for beat in range(n_beats)
    )
    rest_frames = tuple(
        beat * frames_per_beat + i for beat in range(n_beats) for i in range(1, frames_at_rest + 1)
    )
    return SyntheticRecording(
        frames=stack,
        peak_frames=peak_frames,
        rest_frames=rest_frames,
        framerate=framerate,
        frames_per_beat=frames_per_beat,
    )
