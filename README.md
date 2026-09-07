# boamotion

[![CI](https://github.com/quasar1357/boamotion/actions/workflows/ci.yml/badge.svg)](https://github.com/quasar1357/boamotion/actions/workflows/ci.yml)

A Python reimplementation of [MUSCLEMOTION](https://github.com/l-sala/MUSCLEMOTION), the
ImageJ/FIJI macro that quantifies muscle contraction from video microscopy.

The goal is to reproduce the original tool's analysis faithfully while making it usable
from a notebook or a script, without FIJI and without a GUI.

**Status: prototype complete, validated against FIJI on a real recording.** Every stage of
the analysis is implemented and tested. On a recording analysed with MUSCLEMOTION in FIJI, a
`legacy=True` run reproduces that output exactly — the same reference frame, the same
beats, and an identical results table; the traces differ only by the order float32
accumulates in.

## Getting started

```bash
pip install "boamotion @ git+https://github.com/quasar1357/boamotion.git"
```

```python
from boamotion import Boa

boa = Boa("recordings/A001", framerate=25)
result = boa.run()

result.beats              # one row per beat, with its amplitudes and durations
result.plot_contraction()
result.save("results")    # traces, table, figures and a log, in a folder of their own
```

[`docs/installation.md`](docs/installation.md) covers conda and editable installs, and
[`docs/demo.ipynb`](docs/demo.ipynb) runs the whole analysis end to end.

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

- [`index.md`](docs/index.md) — what BoaMotion is and where to start.
- [`installation.md`](docs/installation.md) — what you need and how to get it.
- [`demo.ipynb`](docs/demo.ipynb) — running BoaMotion end to end.
- [`how-it-works.md`](docs/how-it-works.md) — what the analysis computes and what each
  parameter changes.

How it was built, in [`dev/`](dev):

- [`DECISIONS.md`](dev/DECISIONS.md) — design decisions, the questions still open, and
  the findings about the original macro.
- [`LEGACY_MODE.md`](dev/LEGACY_MODE.md) — the original macro's quirks worked through
  against its own source, and what each `legacy` branch does.
- [`NOTES.md`](dev/NOTES.md) — working notes on the original macro and this port.
- [`BUILDING_BLOCKS.ipynb`](dev/BUILDING_BLOCKS.ipynb) — the analysis stage by stage.

Checked against the original in [`validation/`](validation), where a `legacy=True` run is
diffed against the output the macro itself produced.

## Origin and licence

Ported from MUSCLEMOTION by BJ van Meer, L Sala and FL Burton (Leiden University Medical
Center / University of Glasgow, 2017), published as Sala & van Meer et al.,
*Circulation Research* 122(3):e5–e16, 2018, doi:10.1161/CIRCRESAHA.117.312067.

The original is GPL-3.0; this port is GPL-3.0 as well. See [`LICENSE`](LICENSE) and the
licence note in [`DECISIONS.md`](dev/DECISIONS.md).
