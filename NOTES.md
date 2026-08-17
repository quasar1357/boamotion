# Working notes

Internal notes for developing `boamotion`. The other three documents:

- [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) — what the analysis computes and what each parameter
  changes, in plain language. The public description of the method.
- [`DECISIONS.md`](DECISIONS.md) — decisions, open questions and findings to raise with the
  client. Everything client-facing lives there.
- [`LEGACY_MODE.md`](LEGACY_MODE.md) — the original macro's quirks worked through against
  its own source, for whoever maintains the port.

Findings carry an F number that means the same thing in all three.

## Source material

All under `../` (the folder containing this repo):

| File | Notes |
|---|---|
| `MUSCLEMOTION v1-1beta.ijm` | Authoritative source for the port. |
| `MUSCLEMOTION v1.0.ijm` | Algorithmically identical to the beta; ignore. |
| `MUSCLEMOTION User Manual v1.0.pdf` | 12 pages; rationale and parameter guidance. |
| `sala-et-al-2017-musclemotion.pdf` | The paper. Figure S4 covers reference-frame detection. |
| `AChanda_MuscleMotion_version_python.py` | Earlier partial Python attempt; cross-check only. |
| `MuscleMotion_GUI-with-params.png` | Client's last-used transient-analysis settings. |
| `MuscleMotion_Emails.txt` | Client correspondence and agreed prototype scope. |

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
  (step 17) — noise reduction and a manually chosen reference frame are already settings.

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

| | Step | |
|---|---|---|
| **A** | 1 Repo, licence, NOTES, DECISIONS | done |
| | 2 Packaging, src layout, ruff | done |
| | 3 GitHub Actions CI | done |
| **B** | 4 `Params` | done |
| | 5 TIFF sequence loader | done |
| | 6 Synthetic recording | done |
| **C** | 7 `detect_reference_frame` | done |
| | 8 `build_motion_pixel_mask` | done |
| | 9 `measure_contraction`, `measure_speed` | done |
| | 10a `find_peaks` and `find_baselines` | done |
| | 10b `measure_transients` — levels, flank crossings, per-beat table | done |
| **D** | 11 `Result` object and the output files | done |
| | 12 The three figures | done |
| | 13 `Boa`, the user-facing class, and logging | done |
| **E** | 14 Validation against FIJI output | **next**, needs data |
| | 15 Example notebook on the client's recording | needs data |
| | — prototype complete — | |
| **F** | 16 Other input formats: TIFF stacks, PNG, AVI | |
| | 17 Gaussian blur, ROI, interactive reference picking | |
| | 18 Batch driver and CLI | |
| | 19 SLURM array job | |
| | 20 Performance work, if profiling justifies it | |
| | 21 The original's other contraction-figure markers, per D15 | |

Every module the prototype needs now exists. What remains is validation against real
output, which is blocked on the client's data.

## Check these first against real FIJI output

Step 14 has no data yet, and parts of the output format are inferred rather than
observed. These are the places a diff would fail first, in the order worth checking:

1. **The percentage column names.** We write `<100-p>-to-<100-p> transient (ms)`, which
   assumes the macro language binds `-` tighter than `+`. Any other precedence makes that
   expression a type error, and the CD90 convention says the result should be `90-to-90`,
   so this is the only reading that works — but it is inference, not observation.
2. **The `Overview-results.txt` layout.** We write a row-number column headed with a single
   space, rows numbered from 1, tab separated. That is what ImageJ's *Save As Results* is
   understood to produce; the exact header cell and number formatting are unverified.
3. **Missing measurements as `0`** (F16). We assume `setResult` with `false` stores the
   number zero.
4. **Number formatting** in all three text files — decimal places, and whether ImageJ
   writes integers without a decimal point.

## Where each finding lives

`DECISIONS.md` says what each finding is and `LEGACY_MODE.md` shows the original source.
This says which code it touches. Two things are being tracked at once, so they get their
own columns: whether we **correct** it, and whether it is **written** yet.

| F | Where | Correct it? | Written |
|---|---|---|---|
| F1 | `reference.py` — `_select_legacy` vs `_select` | yes | step 7 |
| F2 | `reference.py` — the frame mapping in `detect_reference_frame` | yes | step 7 |
| F3 | `traces.py` — `_frames_to_use` | yes | step 8 |
| F4 | `traces.py` — `_mask_weight` | yes | step 9 |
| F5 | `transients.py` — `_zero_level` | yes | step 10a |
| F6 | `transients.py` — `_range_positions` | yes | step 10a |
| F7 | `transients.py` — `_legacy_flat_average` | yes | step 10a |
| F8 | `transients.py` — `_dominates_neighbours` | no | step 10a |
| F9 | `transients.py` — `measure_transients` | no | step 10b |
| F10 | no code; it is the reasoning behind D4 | no | — |
| F11 | `result.py` — the output column names | no | **step 11** |
| F12 | `params.py` — superseded by `Params` and YAML, per D6 | no | step 4 |
| F13 | `traces.py` — `_mean_change` averages the whole frame | no | step 9 |
| F14 | `result.py` — `time_ms`, and the figures drawn on it | no | steps 11 and 12 |
| F15 | `result.py` — `original_headers` | yes | step 11 |
| F16 | `result.py` — `_write_overview` | yes | step 11 |
| F17 | `result.py` — `file_names` | yes | steps 11 and 12 |
| F22 | `result.py` — `comparison_curves` | yes | step 12 |
| F18 | `traces.py` — the fixed `mean + std` threshold | no | step 8 |
| F19 | `transients.py` — the fixed three-point test in `_crossing_before` | no | step 10b |
| F20 | `traces.py` — `_frames_without_reference` | no | step 9 |
| F21 | `transients.py` — `find_peaks` | no | step 10a |

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

## Notebooks

Notebooks are committed **with** their outputs, so the figures are visible on GitHub
without running anything. The cost is that outputs go stale silently when the code
changes, and that diffs are large. Re-run a notebook end to end before committing changes
that affect it.

## The conda environment

`environment.yml` is deliberately thin: conda provides only the interpreter, pip and
`ipykernel`, and every actual dependency comes from `pyproject.toml` via `pip install -e
.[dev]`. That keeps `pyproject.toml` the single source of truth, so the two files cannot
drift apart.

Plain `pip install -e .[dev]` into a venv works just as well — all dependencies ship
universal wheels and need no compiler. The conda file exists because that is the workflow
here, and because non-Python binaries (ffmpeg, if AVI support lands) install more cleanly
through conda.
