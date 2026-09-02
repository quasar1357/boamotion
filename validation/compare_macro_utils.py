"""Checking a `legacy=True` run against the output the original macro produced.

The macro's own files are the only reference for whether the port agrees with it, and
`Result.save` writes the same names, so a comparison is folder against folder. This
module holds what reads the original side; the comparisons themselves join it here.

Everything here exists only to serve `legacy=True`, so it is scoped to go in the same
move the legacy mode does, rather than being carried over to corrected runs.

Only the log needs real parsing. It is the one file that states the reference frame and
the peak positions, which are what a wrong result shows up in first.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np

# The timestamp names the file that collects the differences. It is set once at import,
# so every call of one session appends to the same file rather than starting a new one.
TIMESTAMP = datetime.now().strftime("%y%m%d-%H%M%S")

# Written once per run, outside the block of settings.
_RECORDING = re.compile(r"-+ Evaluating file:(.+?) -+")
_VERSION = re.compile(r"Algorithm tool version number: (.+)")
_REFERENCE_FRAME = re.compile(r"reference frame: frame (\d+)")
_ELAPSED_MS = re.compile(r"Elapsed time \(ms\): (\d+)")

# A setting is `name: value`, optionally starred, and sometimes trailed by a note.
_SETTING = re.compile(r"^\*?([A-Za-z][A-Za-z0-9]*): ?(.*)$")

# The macro numbers the same beat differently depending on which flank failed: the
# rising one prints the loop counter, the falling one prints it plus one.
_FLANK_FAILURE = re.compile(r"low(Down|Up) false at peak: (\d+)")

_PEAKS_FOLLOW = "Peaks detected at points (frames):"
_PERCENTAGES_FOLLOW = "*percentages:"
# Lines that read like a setting but are not one: the timestamps, the warnings, and
# percentages, whose values are on the following line and have their own key.
_NOT_SETTINGS = ("Date", "Time", "WARNING", "Warning", "percentages")


def load_macro_log(path) -> dict:
    """Read the macro's `Log_file.txt` and return what a comparison needs from it.

    The keys are `recording`, `version`, `reference_frame`, `peaks`, `percentages`,
    `unmeasured_flanks`, `warnings`, `settings` and `elapsed_ms`. Beat numbers are
    1-based, matching our own tables rather than the macro's two conventions.

    Anything the log does not state comes back as None, or empty for the collections.
    Batch runs write several evaluations into one file; this reads the first.

    Raises:
        ValueError: if the file is not one of the macro's logs. Our own log looks
            similar enough that it would be read as an almost empty one.
    """
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    version = _first(_VERSION, lines)
    if version is None:
        raise ValueError(
            f"{path} does not look like a MUSCLEMOTION log: no version line. A run of "
            "our own reports all of this on its Result rather than in its log."
        )

    log = {
        "recording": _first(_RECORDING, lines),
        "version": version,
        "reference_frame": _int_or_none(_first(_REFERENCE_FRAME, lines)),
        "peaks": _numbers_after(_PEAKS_FOLLOW, lines),
        "percentages": _numbers_after(_PERCENTAGES_FOLLOW, lines),
        "unmeasured_flanks": _flank_failures(lines),
        "warnings": tuple(line for line in lines if line.lower().startswith("warning")),
        "settings": _settings(lines),
        "elapsed_ms": _int_or_none(_first(_ELAPSED_MS, lines)),
    }
    return log


def _first(pattern: re.Pattern, lines) -> str | None:
    """The first capture of `pattern` anywhere in the log."""
    for line in lines:
        found = pattern.search(line)
        if found:
            return found.group(1).strip()
    return None


def _numbers_after(header: str, lines) -> tuple[int, ...]:
    """The comma-separated numbers the macro prints on the line after `header`."""
    for position, line in enumerate(lines[:-1]):
        if line.strip() == header:
            return tuple(int(value) for value in lines[position + 1].split(",") if value.strip())
    return ()


def _flank_failures(lines) -> dict[str, tuple[int, ...]]:
    """Which beats lost which flank, as 1-based beat numbers.

    Only the rising list is complete. The macro prints `lowUp false` inside the branch
    where the rising flank was found, so a beat that lost both is reported as a rising
    failure alone and the log never states its falling verdict.
    """
    failures: dict[str, list[int]] = {"rising": [], "falling": []}
    for line in lines:
        found = _FLANK_FAILURE.search(line)
        if not found:
            continue
        # The rising message prints the loop counter, the falling one prints it plus one.
        flank = "rising" if found.group(1) == "Down" else "falling"
        beat = int(found.group(2)) + (1 if flank == "rising" else 0)
        failures[flank].append(beat)
    return {flank: tuple(beats) for flank, beats in failures.items()}


def _settings(lines) -> dict[str, object]:
    """Every `name: value` line the macro writes, with the numbers converted."""
    settings: dict[str, object] = {}
    for line in lines:
        found = _SETTING.match(line)
        if not found or found.group(1) in _NOT_SETTINGS:
            continue
        # Some lines trail an explanatory note after a tab.
        settings[found.group(1)] = _as_number(found.group(2).split("\t")[0].strip())
    return settings


def _as_number(text: str):
    """The value as an int or float where it is one, and as text where it is not."""
    for convert in (int, float):
        try:
            return convert(text)
        except ValueError:
            continue
    return text


def _int_or_none(text: str | None) -> int | None:
    return None if text is None else int(text)


def write_or_print(*text, file_dir=None, also_print=True):
    """Print the report, and write it to `file_dir` as well where one is given.

    Pass `also_print=False` for a long report that would only clutter the notebook.
    """
    if also_print:
        print(*text)
    if file_dir is not None:
        with open(f"{file_dir}/{TIMESTAMP}_diff.txt", "a", encoding="utf-8") as f:
            full_string = " ".join(str(t) for t in text) + "\n"
            if full_string.startswith("==="):
                full_string = "\n\n" + full_string
            f.write(full_string)


def compare_results_files(macro, ours, rel_thresh=1e-6):
    """How far two of the output tables sit apart, taken column by column.

    Float32 accumulates in a different order here than in ImageJ, so the tables agree to
    about 1e-8 rather than exactly. `rel_thresh` is what still counts as agreement.

    Each column is normalised by its own largest value. The tables mix milliseconds with
    amplitudes, and one scale for the whole file would let a small column hide behind a
    large one. Returns the worst column, as `(worst, relative, verdict, column)`.

    Returns four Nones where the shapes differ, which no threshold can bridge.
    """
    if macro.shape != ours.shape:
        return None, None, None, None

    gaps = []
    for column in range(macro.shape[1]):
        worst = np.nanmax(np.abs(macro[:, column] - ours[:, column]))
        gaps.append((worst / (np.nanmax(np.abs(macro[:, column])) or 1.0), worst, column))

    # On a tie, and so on a file that agrees exactly, name the first column.
    relative, worst, column = max(gaps, key=lambda gap: (gap[0], gap[1], -gap[2]))
    verdict = "OK" if relative < rel_thresh else "DIFF"
    return worst, relative, verdict, column
