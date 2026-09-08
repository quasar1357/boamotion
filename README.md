# boamotion

[![CI](https://github.com/quasar1357/boamotion/actions/workflows/ci.yml/badge.svg)](https://github.com/quasar1357/boamotion/actions/workflows/ci.yml)

BoaMotion measures how strongly and how quickly muscle tissue contracts, from a video
microscopy recording of it beating. It needs no markers and no segmentation: every frame is
compared against a still one, the difference becomes a contraction trace, and each beat in
that trace is found and measured.

It is a Python reimplementation of
[MUSCLEMOTION](https://github.com/l-sala/MUSCLEMOTION), the ImageJ/FIJI macro that does the
same, and reproduces the original tool's analysis faithfully while making it usable from a
notebook, a script or a compute cluster — without FIJI and without a GUI.

**Status: prototype complete, validated against FIJI on a real recording.** Every stage of
the analysis is implemented and tested. On a recording analysed with MUSCLEMOTION in FIJI, a
`legacy=True` run reproduces that output exactly — the same reference frame, the same
beats, and an identical results table; the traces differ only by the order float32
accumulates in.

## Getting started

```bash
pip install git+https://github.com/quasar1357/boamotion.git
```

```python
from boamotion import Boa

boa = Boa("recordings/A001", framerate=25)
result = boa.run()

result.beats  # one row per beat, with its amplitudes and durations
result.plot_contraction()
result.save("results")  # traces, table, figures and a log, in a folder of their own
```

## Documentation

- [`docs/index.md`](docs/index.md) — what BoaMotion is and where to start.
- [`docs/installation.md`](docs/installation.md) — what you need and how to get it,
  including conda and editable installs.
- [`docs/demo.ipynb`](docs/demo.ipynb) — a whole analysis end to end, in a few cells.
- [`docs/how-it-works.md`](docs/how-it-works.md) — what the analysis computes and what each
  parameter changes.

## Development

```bash
conda env create -f environment.yml
conda activate boamotion
pytest
```

The environment carries only Python, pip and `ipykernel`; the dependencies themselves come
from `pyproject.toml`. A virtual environment works equally well: `pip install -e ".[dev]"`.

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
*Circulation Research* 122(3):e5–e16, 2018, doi:10.1161/CIRCRESAHA.117.312067. See
[`CITATION.cff`](CITATION.cff) for how to cite both.

This is an independent reimplementation, not the authors' own continuation of
MUSCLEMOTION. Luca Sala consented to its release in September 2026.

Copyright © 2026 Roman Schwob. The original is GPL-3.0 and so is this port: see
[`LICENSE`](LICENSE) and the licence note in [`DECISIONS.md`](dev/DECISIONS.md).
