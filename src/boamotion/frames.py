"""Reading recordings frame by frame.

Only a directory of single-page TIFF files is supported; the other formats the original
macro accepts (TIFF stacks, PNG sequences, uncompressed AVI) are not implemented yet.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import tifffile

logger = logging.getLogger(__name__)

TIFF_SUFFIXES = (".tif", ".tiff")


def _natural_key(path: Path) -> tuple[object, ...]:
    """Sort key that orders embedded numbers by value, so frame9 precedes frame10."""
    parts = re.split(r"(\d+)", path.name)
    return tuple(int(p) if p.isdigit() else p.lower() for p in parts)


class FrameSequence:
    """A recording stored as one TIFF file per frame, read on demand.

    Frames are ordered the way ImageJ's image sequence importer orders them: numbers
    embedded in the file names are compared by value, not as text. Frames are read from
    disk as they are requested, so memory use does not grow with the length of the
    recording.
    """

    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.paths = tuple(sorted(_find_tiffs(self.directory), key=_natural_key))

        if not self.paths:
            raise ValueError(
                f"no TIFF files in {self.directory}. Expected one file per frame with a "
                f"{' or '.join(TIFF_SUFFIXES)} suffix"
            )
        if len(self.paths) < 2:
            raise ValueError(
                f"{self.directory} holds a single frame; a recording of at least 2 frames "
                f"is required"
            )

        first = self._read(self.paths[0])
        self.shape: tuple[int, int] = first.shape
        self.dtype: np.dtype = first.dtype

        logger.info(
            "Loaded %d frames of %d x %d (%s) from %s",
            len(self.paths),
            self.shape[1],
            self.shape[0],
            self.dtype,
            self.directory.name,
        )

    @property
    def n_frames(self) -> int:
        """Number of frames in the recording."""
        return len(self.paths)

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, index: int) -> np.ndarray:
        """Return one frame, in the file's own dtype. Negative indices count from the end."""
        if not isinstance(index, (int, np.integer)):
            raise TypeError(
                f"frames are selected one at a time by integer index, got {type(index).__name__}"
            )
        frame = self._read(self.paths[index])
        if frame.shape != self.shape:
            raise ValueError(
                f"{self.paths[index].name} is {frame.shape[1]} x {frame.shape[0]}, but the "
                f"recording is {self.shape[1]} x {self.shape[0]}; all frames must match"
            )
        return frame

    def __iter__(self) -> Iterator[np.ndarray]:
        for i in range(len(self)):
            yield self[i]

    def __repr__(self) -> str:
        return (
            f"FrameSequence({self.directory.name!r}, {len(self)} frames, "
            f"{self.shape[1]} x {self.shape[0]}, {self.dtype})"
        )

    @staticmethod
    def _read(path: Path) -> np.ndarray:
        frame = tifffile.imread(path)
        if frame.ndim != 2:
            raise ValueError(
                f"{path.name} has shape {frame.shape}; only single-channel (grayscale) "
                f"frames are supported. Convert colour recordings to grayscale first"
            )
        return frame


def _find_tiffs(directory: Path) -> list[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"no such directory: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(
            f"{directory} is a file. Only a directory holding one TIFF per frame is "
            f"supported; TIFF stacks, PNG sequences and AVI are not implemented yet"
        )
    return [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in TIFF_SUFFIXES]


def load_frames(path: str | Path) -> FrameSequence:
    """Open a recording. Currently a directory holding one TIFF file per frame."""
    return FrameSequence(path)
