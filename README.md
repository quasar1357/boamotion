# boamotion

[![CI](https://github.com/quasar1357/boamotion/actions/workflows/ci.yml/badge.svg)](https://github.com/quasar1357/boamotion/actions/workflows/ci.yml)

A Python reimplementation of [MUSCLEMOTION](https://github.com/l-sala/MUSCLEMOTION), the
ImageJ/FIJI macro that quantifies muscle contraction from video microscopy.

The goal is to reproduce the original tool's analysis faithfully while making it usable
from a notebook or a script, without FIJI and without a GUI.

**Status: prototype complete, not yet validated.** Every stage of the analysis is
implemented and tested, and a run produces the same set of output files as the original.
It has not yet been checked against real FIJI output on a real recording, so the numbers
should not be relied on.

## Development setup

```bash
conda env create -f environment.yml
conda activate boamotion
pytest
```

The environment carries only Python, pip and `ipykernel`; the dependencies themselves come
from `pyproject.toml`. A virtual environment works equally well: `pip install -e ".[dev]"`.

## Project files

How to use it, in [`docs/`](docs):

- [`how-it-works.md`](docs/how-it-works.md) — what the analysis computes and what each
  parameter changes.
- [`demo.ipynb`](docs/demo.ipynb) — running BoaMotion end to end.

How it was built, in [`dev/`](dev):

- [`DECISIONS.md`](dev/DECISIONS.md) — design decisions, open questions and findings to
  discuss with the client.
- [`LEGACY_MODE.md`](dev/LEGACY_MODE.md) — the original macro's quirks worked through
  against its own source, and what each `legacy` branch does.
- [`NOTES.md`](dev/NOTES.md) — working notes on the original macro and this port.
- [`BUILDING_BLOCKS.ipynb`](dev/BUILDING_BLOCKS.ipynb) — the analysis stage by stage.

- [`validation/`](validation) — checking a `legacy=True` run against the output the
  original macro itself produced.

## Origin and licence

Ported from MUSCLEMOTION by BJ van Meer, L Sala and FL Burton (Leiden University Medical
Center / University of Glasgow, 2017), published as Sala & van Meer et al.,
*Circulation Research* 122(3):e5–e16, 2018, doi:10.1161/CIRCRESAHA.117.312067.

The original is GPL-3.0; this port is GPL-3.0 as well. See [`LICENSE`](LICENSE) and the
licence note in [`DECISIONS.md`](dev/DECISIONS.md).
