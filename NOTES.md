# Working notes

Internal notes for developing `boamotion`. Client-facing material lives in
[`DECISIONS.md`](DECISIONS.md).

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
| `Emails.txt` | Client correspondence and agreed prototype scope. |

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

`Contraction.txt`, `Speed-of-contraction.txt`, `Contraction.jpg`, `Speed of contraction.jpg`,
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
- Waiting on the `demo/` folder with `demo_stack.tif` and reference outputs, if the client
  has it — it is *not* in the public GitHub repo.
- The client's dialog-1 answers (frame rate aside) are unknown; the screenshot only shows
  the third dialog. Assuming defaults: no Gaussian blur, noise reduction on, automatic
  reference frame.

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

One small, reviewable commit per step; notebook updates get their own commit.

| | Step | |
|---|---|---|
| **A** | 1 Repo, licence, NOTES, DECISIONS | done |
| | 2 Packaging, src layout, ruff | done |
| | 3 GitHub Actions CI | done |
| **B** | 4 `Params` | done |
| | 5 TIFF sequence loader | done |
| | 6 Synthetic recording | done |
| **C** | 7 `detect_reference_frame` | done |
| | 8 `motion_pixel_mask` | done |
| | 9 `contraction_trace`, `speed_trace` | done |
| | 10 `analyse_transients` — peaks, baselines, per-beat measures | **next** |
| **D** | 11 `Result` object and the seven output files | |
| | 12 The three figures | |
| | 13 `Boa`, the user-facing class, and logging | |
| **E** | 14 Validation against FIJI output | needs data |
| | 15 Example notebook on the client's recording | needs data |
| | — prototype complete — | |
| **F** | 16 Other input formats: TIFF stacks, PNG, AVI | |
| | 17 Gaussian blur, ROI, interactive reference picking | |
| | 18 Batch driver and CLI | |
| | 19 SLURM array job | |
| | 20 Performance work, if profiling justifies it | |

Modules still to come: `transients.py` (step 10), `result.py` (11 and 12), `analysis.py` (13).

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
