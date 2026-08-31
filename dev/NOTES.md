# Working notes

Internal notes for developing `boamotion`. The other three documents:

- [`how-it-works.md`](../docs/how-it-works.md) — what the analysis computes and what each
  parameter changes, in plain language. The public description of the method.
- [`DECISIONS.md`](DECISIONS.md) — decisions, open questions and findings to raise with the
  client. Everything client-facing lives there.
- [`LEGACY_MODE.md`](LEGACY_MODE.md) — the original macro's quirks worked through against
  its own source, for whoever maintains the port.

Findings carry an F number that means the same thing in all three.

## Source material

All in the project folder that sits outside this repo,
`OneDrive - Universitaet Bern/MuscleMotion/`. The first five are in its
`MUSCLEMOTION/` subfolder, the last two beside it:

| File                                     | Notes                                                  |
| ---------------------------------------- | ------------------------------------------------------ |
| `MUSCLEMOTION v1-1beta.ijm`              | Authoritative source for the port.                     |
| `MUSCLEMOTION v1.0.ijm`                  | Algorithmically identical to the beta; ignore.         |
| `MUSCLEMOTION User Manual v1.0.pdf`      | 12 pages; rationale and parameter guidance.            |
| `sala-et-al-2017-musclemotion.pdf`       | The paper. Figure S4 covers reference-frame detection. |
| `AChanda_MuscleMotion_version_python.py` | Earlier partial Python attempt; cross-check only.      |
| `MuscleMotion_GUI-with-params.png`       | Client's last-used transient-analysis settings.        |
| `MuscleMotion_Emails.txt`                | Client correspondence and agreed prototype scope.      |

The two `.ijm` versions differ only in 38 lines where array lengths are hoisted into a
temporary before `newArray(...)`. No behavioural difference.

## What the macro computes

Four stages. Everything is measured over the **whole frame** — the macro has no ROI or
cropping anywhere.

**1. Reference frame.** Build a motion trace `speed[i] = mean(|frame[i+speedWindow] - frame[i]|)`,
then plot each value against its successor (a phase-plane). Quiescent frames lie near the
origin (little motion) *and* near the unity line (motion not changing), which separates a
genuinely relaxed frame from a momentary zero-crossing mid-transient. Take the `lowValueN`
points nearest the origin, then the `unitySelectionN` of those nearest the unity line. The
chosen frame is then **removed from the stack** for all later measurements.

**2. Pixel mask** (`pixelsOfInterest`, "noise reduction"). Accumulate a maximum-intensity
projection of `|frame[i] - reference|` over the recording, threshold at `mean + std` of that
projection, binarise to 0/255.

**3. Traces.**

```
contraction[i] = mean( |frame[i] - reference|           * mask )
speed[i]       = mean( |frame[i] - frame[i+speedWindow]| * mask )
```

Both in arbitrary units. Image maths is done in 32-bit float. The mask being 0/255 rather
than 0/1 scales the traces by 255; harmless given the arbitrary units, but must be matched
if we want identical numbers.

**4. Transient analysis.** Sliding-window local-maximum peak finder with an amplitude
threshold; a per-peak baseline (minimum before the peak, or an average of the flattest
points before it); then per requested percentage of the peak-to-baseline amplitude, the
crossing points on both flanks, requiring 3 consecutive points beyond the level to reject
noise. Yields time-to-peak, relaxation time, contraction duration, peak-to-peak time,
amplitudes and percentage transient durations.

## Original outputs (7 files per recording)

`contraction.txt`, `speed-of-contraction.txt` (lower case; two tab-separated columns,
time and value, no header), `Contraction.jpg`, `Speed of contraction.jpg`,
`Comparison calculated (red) and measured (black) speed.jpg`, `Overview-results.txt`
(tab-separated table), `Log_file.txt`. Written to `<saveDir>/<name>-Contr-Results/`.

## Standing implementation constraints

Applied from the start so the cluster route stays open without doing cluster work now:

- The core is a pure function of *(input path, parameters)*, no global state.
- No GUI import anywhere in the analysis path; must run headless.
- Parameters are serializable to a file and dumped alongside every result.
- Frames are streamed, not all loaded (the manual states the macro handles files larger
  than RAM).
- Outputs go to a caller-specified directory.

## Open items

- Waiting on the client's example data (`A001.zip`, TIFF sequence, ~800 frames, 25 fps).
  It was shared as a SharePoint link we have no rights to; access was requested through
  SharePoint, and the client was asked to approve it on 21 August 2026. This is the only
  real blocker — with the recording in hand we can run the FIJI plugin ourselves and diff
  against that, so the client's own results folder is useful but not required.
- Waiting on the `demo/` folder with `demo_stack.tif` and reference outputs, if the client
  has it — it is *not* in the public GitHub repo. It would validate against the authors'
  own reference numbers rather than a run of our own.
- The client's dialog-1 answers are unknown, but they do not decide the diff: both sides
  can simply be run with the same settings. What was asked instead is whether Gaussian
  blur or cropping are part of their routine, since those two alone are unimplemented
  (step 18) — noise reduction and a manually chosen reference frame are already settings.

## Frame ordering in image sequences

The manual says image sequences are "ordered alphabetically", but the macro opens them
with ImageJ's `sort` option, which sorts numbers embedded in file names *by value*. The
two disagree whenever frame numbers are not zero-padded: alphabetically `frame10.tif`
comes before `frame2.tif`. We follow the macro, not the manual, since that is what
actually produced the client's existing results.

Harmless for zero-padded names, which is probably what the client has — but getting it
wrong would silently scramble the frame order and corrupt every measurement, so it is
worth the explicit test.

## Plan and progress

One reviewable commit per step, grouping what belongs together. Notebook updates are
usually their own commit, except when a code change forces them — a rename has to carry
the notebook with it or the repo is inconsistent at that commit.

|       | Step                                                                                      |                                    |
| ----- | ----------------------------------------------------------------------------------------- | ---------------------------------- |
| **A** | 1 Repo, licence, NOTES, DECISIONS                                                         | done                               |
|       | 2 Packaging, src layout, ruff                                                             | done                               |
|       | 3 GitHub Actions CI                                                                       | done                               |
| **B** | 4 `Params`                                                                                | done                               |
|       | 5 TIFF sequence loader                                                                    | done                               |
|       | 6 Synthetic recording                                                                     | done                               |
| **C** | 7 `detect_reference_frame`                                                                | done                               |
|       | 8 `build_motion_pixel_mask`                                                               | done                               |
|       | 9 `measure_contraction`, `measure_speed`                                                  | done                               |
|       | 10a `find_peaks` and `find_baselines`                                                     | done                               |
|       | 10b `measure_transients` — levels, flank crossings, per-beat table                        | done                               |
| **D** | 11 `Result` object and the output files                                                   | done                               |
|       | 12 The three figures                                                                      | done                               |
|       | 13 `Boa`, the user-facing class, and logging                                              | done                               |
| **E** | 14 Validation against FIJI output, and the `validation/` tooling for it                   | synthetic done, real data pending  |
|       | 15 Example notebook on the client's recording                                             | needs data (prepared on synthetic) |
|       | 16 Minimal docs overhaul: `docs/index.md`, installation, one pass over the four documents |                                    |
|       | — prototype complete —                                                                    |                                    |
| **F** | 17 Other input formats: TIFF stacks, PNG, AVI                                             |                                    |
|       | 18 Gaussian blur, ROI, interactive reference picking                                      |                                    |
|       | 19 Batch driver and CLI                                                                   |                                    |
|       | 20 SLURM array job                                                                        |                                    |
|       | 21 Performance work, if profiling justifies it                                            |                                    |
|       | 22 The original's other contraction-figure markers, per D15                               |                                    |
|       | 23 Finalise the docs: build the book, per the scheme below                                |                                    |

Every module the prototype needs now exists. What remains is step 16 and validation
against real output, and only the second of those is blocked on the client's data.

The docs are split across two steps on purpose. Step 16 is what the prototype owes a
reader — the folders are already in place, so it is filling the gaps and reading the four
documents through once. Step 23 is the book, and it comes last because a build is only
worth wiring up once the thing it documents has stopped moving.

## What the FIJI comparisons established

The macro has been run in FIJI twice, both times with the defaults, 25 fps and
`PeakDetectionWindow=16`, and its output kept beside the input in
`../synthetic_blobs_dataset-results/`:

- **26 August 2026**, on a noise-free recording, in `26-08-26_Fiji_default_NOISELESS/`.
- **31 August 2026**, on `synthetic_recording(noise=0.01, seed=0)`, in
  `26-08-31_Fiji_default/`. That recording is now `synthetic_blobs_dataset/` and the
  standard one everywhere. The demo and `BUILDING_BLOCKS.ipynb` already used it, and a
  noise-free recording cannot exercise the baseline logic at all.

Running `boamotion` with `legacy=True` on the same folder agrees in both cases:

- **The reference frame, the peaks and the beat count are identical** — frame 54 and peaks
  15, 40, 64, 89 without noise, frame 6 and peaks 14, 39, 64, 89 with it. Four beats
  either way, and the `autoDetectStop` clamp to 97 matches too.
- **`Overview-results.txt` is byte-identical**, all four beats and all ten columns. That
  became literally true only with the line-ending fix: pandas pinned LF for this one file,
  while ImageJ and everything else we write follow the platform.
- **The traces agree to 4e-8 relative**, which is float32 accumulation order. That is the
  floor; text comparison of the trace files is not meaningful, so a diff has to parse them
  and compare with a tolerance (F26).

Three of the four things this section previously listed as inferred are now observed. The
layout of `Overview-results.txt` is settled by F23 and F24 — no header row, no row-number
column, peak-to-peak time last. Missing measurements really are written as `0` (F16), on
the fourth beat, whose falling crossing the macro also failed to find. Number formatting is
settled by F26.

What is still unobserved:

1. **The percentage column names.** `<100-p>-to-<100-p> transient (ms)` remains inference,
   and this run could not test it: the macro never writes headers, so the string exists
   only in the Results window. It matters only for `legacy=False`, which writes headers of
   its own.
2. **A recording that is not synthetic.** The noisy run does exercise the baseline logic
   (F6, F7), which the noise-free one could not, but every beat here is still identical
   and the noise is uniform. The client's A001 is the test that counts.

## Where each finding lives

`DECISIONS.md` says what each finding is and `LEGACY_MODE.md` shows the original source.
This says which code it touches. Two things are being tracked at once, so they get their
own columns: whether we **correct** it, and whether it is **written** yet.

| F   | Where                                                              | Correct it? | Written         |
| --- | ------------------------------------------------------------------ | ----------- | --------------- |
| F1  | `reference.py` — `_select_legacy` vs `_select`                     | yes         | step 7          |
| F2  | `reference.py` — the frame mapping in `detect_reference_frame`     | yes         | step 7          |
| F3  | `traces.py` — `_frames_to_use`                                     | yes         | step 8          |
| F4  | `traces.py` — `_mask_weight`                                       | yes         | step 9          |
| F5  | `transients.py` — `_zero_level`                                    | yes         | step 10a        |
| F6  | `transients.py` — `_range_positions`                               | yes         | step 10a        |
| F7  | `transients.py` — `_legacy_flat_average`                           | yes         | step 10a        |
| F8  | `transients.py` — `_dominates_neighbours`                          | no          | step 10a        |
| F9  | `transients.py` — `measure_transients`                             | no          | step 10b        |
| F10 | no code; it is the reasoning behind D4                             | no          | —               |
| F11 | `result.py` — the output column names                              | no          | **step 11**     |
| F12 | `params.py` — superseded by `Params` and YAML, per D6              | no          | step 4          |
| F13 | `traces.py` — `_mean_change` averages the whole frame              | no          | step 9          |
| F14 | `result.py` — `time_ms`, and the figures drawn on it               | no          | steps 11 and 12 |
| F15 | `result.py` — `original_headers`                                   | yes         | step 11         |
| F16 | `result.py` — `_write_overview`                                    | yes         | step 11         |
| F17 | `result.py` — `file_names`                                         | yes         | steps 11 and 12 |
| F22 | `result.py` — `comparison_curves`                                  | yes         | step 12         |
| F23 | `result.py` — `_write_overview`                                    | yes         | step 14         |
| F26 | `result.py` — `_imagej_number`                                     | yes         | step 14         |
| F24 | `result.py` — `ORIGINAL_HEADERS`                                   | no          | step 14         |
| F25 | no code; the macro couples drawing to measuring, we do not         | no          | —               |
| F18 | `traces.py` — the fixed `mean + std` threshold                     | no          | step 8          |
| F19 | `transients.py` — the fixed three-point test in `_crossing_before` | no          | step 10b        |
| F20 | `traces.py` — `_frames_without_reference`                          | no          | step 9          |
| F21 | `transients.py` — `find_peaks`                                     | no          | step 10a        |

Two traps in reading this. "We do not correct it" does not mean there is nothing to write:
F11 and F14 are behaviours we deliberately copy, and copying them is still work. And a
finding's `legacy` branch sits in exactly one helper — F6 for instance branches only in
`_range_positions`, even though the damage surfaces in `_steepest_rise`.

**To do at the final overhaul:** renumber and regroup all the findings once the picture is
complete. The F1-F9 boundary in particular is drawn where it is only because those are the
ones read line by line so far — F13 and F14 are implementation details too, and F14 will
likely earn its own `LEGACY_MODE.md` section once the figures are written in step 12.

## Marking the `legacy` branches

Every line that passes `legacy` down or branches on it carries a one-line note saying what
the original does differently, so the effect is visible at the call site rather than only
in the helper that implements it:

```python
# legacy: a lone peak gains a phantom neighbour at zero, which zeroes its baseline
positions = _range_positions(peaks, legacy)
```

Prefix the note with `legacy:` where the line merely passes the flag on. Inside an
`if legacy:` block the prefix is redundant, so drop it. Keep new branches to the same rule.

## ImageJ numerical conventions

Two places where the obvious numpy default differs from ImageJ:

- **Standard deviation.** ImageJ divides by n-1, numpy by n. We pass `ddof=1`. Negligible
  over a whole frame, but it is part of the mask threshold.
- **Precision.** Image arithmetic in float32, matching ImageJ's 32-bit images; means
  accumulate in float64, matching its double-precision statistics.

## The documentation scheme, for the final overhaul

Decided ahead of writing the demo notebook, so the notebook is written into a system
rather than retrofitted later. The folders and the moves are done; the book itself is
not built yet, and the tooling below is a preference rather than a commitment.

The split is not user versus developer but **how to use it** versus **how it was built**.
That keeps `DECISIONS.md` where it belongs: the client reads it as a stakeholder in the
build, not as a contributor.

```
README.md         landing: intro, install, one snippet, links out
mkdocs.yml        not written yet
docs/             the book, published; lowercase names become URLs
  index.md  installation.md  demo.ipynb  how-it-works.md
dev/              the build record; keeps its current names
  DECISIONS.md  LEGACY_MODE.md  NOTES.md  BUILDING_BLOCKS.ipynb
validation/       stays put, a check rather than a document
```

`notebooks/` is gone; only the untracked scratch notebook still sits there. The chapter
order is `index`, `installation`, `demo`, `how-it-works`.

- **Folders carry the flag, not filename prefixes.** `docs_`/`dev_` would fight the
  conventions GitHub and the tooling already recognise, and the parent folder says it.
- **MkDocs with Material, `mkdocs-jupyter` and `mkdocstrings`.** Sphinx is more machinery
  than nine modules justify.
- **`mkdocs-jupyter` renders a notebook as a page**, so the demo notebook *is* the "How to
  run" chapter rather than being summarised into one. No second source to drift.
- **`mkdocstrings` settles the parameter question**: descriptions live only in the `Params`
  docstrings and the book renders them. Turning those docstrings into publishable prose
  is part of building the documentation, not something to do piecemeal beforehand.
- **The demo comes before the explanation.** Install, run, then understand: someone who
  has a result in front of them reads `how-it-works` better, and someone who has not will
  skip it either way.
- **Only the user book is built.** The `dev/` files stay plain markdown, read on GitHub.
  They are read by three people and change every session, so a second nav is maintenance
  without a reader. Adding a "Development" section to the same book later is a few lines
  of `mkdocs.yml`, so nothing is foreclosed.
- **The demo runs on `synthetic.py`**, which needs no data, so CI can execute it and catch
  a stale demo. No other notebook has that property.
- `NOTES.md` moves into `dev/` as a plan file rather than a document; if `dev/` is ever
  built, it stays out of the nav.
- The README links rather than summarises, except where a summary is three sentences that
  will not drift.

## Notebooks

Notebooks are committed **with** their outputs, so the figures are visible on GitHub
without running anything. The cost is that outputs go stale silently when the code
changes, and that diffs are large. Re-run a notebook end to end before committing changes
that affect it.

**To do:** have CI execute `docs/demo.ipynb` and fail on an error, so a stale notebook is
caught rather than noticed. `nbclient` is already in the `dev` extra for it; `ipykernel`
would have to join it, since CI installs `.[dev]` only. Such a check would have caught
`BUILDING_BLOCKS.ipynb` printing a `legacy` default and a parameter list that had both
moved on.

## The conda environment

`environment.yml` is deliberately thin: conda provides only the interpreter, pip and
`ipykernel`, and every actual dependency comes from `pyproject.toml` via `pip install -e
.[dev]`. That keeps `pyproject.toml` the single source of truth, so the two files cannot
drift apart.

Plain `pip install -e .[dev]` into a venv works just as well — all dependencies ship
universal wheels and need no compiler. The conda file exists because that is the workflow
here, and because non-Python binaries (ffmpeg, if AVI support lands) install more cleanly
through conda.
