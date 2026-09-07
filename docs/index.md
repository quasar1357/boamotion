# boamotion

boamotion measures how much muscle tissue moves in a video microscopy recording. It turns a
sequence of frames into a contraction trace over time, finds the individual beats in it, and
measures each one. It is a Python port of the
[MUSCLEMOTION](https://github.com/l-sala/MUSCLEMOTION) ImageJ/FIJI macro, meant to be run
from a notebook or a script rather than a GUI.

**Status: prototype complete, validated against FIJI on a real recording.** With
`legacy=True` a run reproduces the original macro's own output table for table, so the
numbers are the macro's numbers.

## Where to start

- **[Installation](installation.md)** — what you need and how to get it.
- **[Demo](demo.ipynb)** — a complete run, from a recording to the results, in a few cells.
- **[How it works](how-it-works.md)** — what the analysis computes, and what each parameter
  changes.

If you have a folder of frames and want the short version:

```python
from boamotion import Boa

boa = Boa("recordings/A001", framerate=25)
result = boa.run()
result.save("results")
```

## What a run gives you

A `Result` holds the contraction trace, the speed of contraction, the per-beat table, the
reference frame that everything was measured against, and any warnings raised along the
way. Saving it writes those out as text and CSV alongside three figures, in a folder of
their own.

The [demo](demo.ipynb) shows each of these on a small recording that is generated on the
spot, so it runs anywhere without a download.
