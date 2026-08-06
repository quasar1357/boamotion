# Decisions, findings and open questions

Everything worth raising with the client, in one file. Items are numbered so they can be
referenced directly in a meeting. Not everything here is a trade-off — section 3 in
particular is observations about the original macro that the client should know about.

Status of each decision: **taken** (we have decided, client may still object),
**proposed** (our recommendation, awaiting client input) or **open**.

---

## 1. Decisions and trade-offs

### D1 — Licence: GPL-3.0 · *taken, needs confirming*

The original MUSCLEMOTION macro is GPL-3.0. This is a deliberate port written after
reading that source, so an independent-implementation argument would be weak. We therefore
release `boamotion` under GPL-3.0 as well.

**Consequence for the client:** anything distributing this code, or software derived from
it, inherits GPL-3.0 obligations. If the group ever intends commercial use, or embedding
the analysis in a closed pipeline, this needs revisiting — the alternative is asking van
Meer and Sala to relicense. Nothing is public yet, so the decision is still reversible.

### D2 — Name: `boamotion` · *taken*

A boa is a constrictor, which is what the tool measures. `musclemotion`, `myopy` and
`pyomyo` are all taken on PyPI; `pyomyo` in particular is an existing muscle-signal
(EMG armband) package, so reusing it would actively mislead. `cobra` was considered and
rejected because COBRApy is a well-known package in the same scientific-Python space.

### D3 — Faithful port, with the original's quirks reproducible · *proposed*

The prototype's acceptance criterion is "same numbers as FIJI". Several genuine bugs in
the original (section 3) change those numbers. We implement the original behaviour as the
default, behind a single `legacy` switch, with corrected alternatives implemented and
tested alongside.

**Trade-off:** the client gets a demonstrable match against their existing results *and*
an explicit, per-item choice about which bugs to fix — rather than discovering that
numbers changed silently. Cost is a modest amount of extra code and testing.

### D4 — Reimplement the original's algorithms rather than substituting library equivalents · *taken*

Where the macro has a bespoke algorithm (peak detection, baseline finding, flank
crossings), we port it literally instead of calling a standard library function. See F5
for why this matters.

### D5 — No video display; no viewer dependency · *proposed*

The macro runs almost entirely with image windows hidden (`setBatchMode(true)`). FIJI is
used as an image reader, an array-arithmetic engine, a plot renderer and a dialog toolkit
— not as a viewer. The only place a video is genuinely shown is manual reference-frame
selection. Everything else displayed is a static 2-D line plot, which matplotlib covers.

So: no napari, no viewer in the analysis path. Automatic reference-frame detection is the
default and a plain `reference_frame=<n>` parameter lets a user who has already inspected
the movie pass the number directly. This keeps the package runnable headless on a compute
node, which is a hard requirement for the cluster.

**Trade-off:** users who relied on eyeballing the movie lose that step for now. An
interactive picker can be added later (a notebook slider works on the cluster; napari
would be a local-only optional extra).

### D6 — Parameters: one object, settable directly or loaded from a file · *proposed*

A single parameter object carries every setting with the original's defaults. It can be
constructed with keyword arguments, modified attribute by attribute, or loaded from and
saved to a YAML file. Every analysis writes its effective parameters next to the results,
so any output can be reproduced exactly.

**Trade-off:** this replaces the macro's behaviour of remembering the last-used settings
in ImageJ's global preferences, which makes an analysis hard to reproduce months later and
silently couples unrelated runs. Explicit parameter files are more typing and much more
defensible.

### D7 — Whole-frame measurement, with an ROI option planned · *proposed*

The macro measures over the entire frame, so users currently crop in FIJI beforehand to
exclude non-contracting regions. We will offer an explicit region-of-interest parameter
instead (deferred to after the prototype, see section 4). **Question for the client: do
you currently crop before running the macro?** If so this is not optional, it is part of
reproducing their workflow.

### D8 — Small, conservative dependency set · *taken*

`numpy`, `tifffile`, `pandas`, `matplotlib`, `pyyaml`. Notably **not** OpenCV: the earlier
Python attempt pulls in all of OpenCV for one absolute-difference call that numpy performs
natively and identically. Video-format support (AVI) will be an optional extra.

### D9 — Parallelism across recordings, not within one · *proposed*

For cluster use, one recording per SLURM array task is simpler, more robust and scales
better than threading inside a single analysis. The core therefore stays single-threaded.

**Trade-off:** a single very long recording will not go faster on more cores. Given the
macro currently opens and closes an ImageJ window per frame, and the Python equivalent is
a couple of array passes, we expect a large speedup regardless; per-recording parallelism
would be premature optimisation.

### D10 — Outputs: original format plus a machine-readable one · *proposed*

We reproduce the original's seven output files and their names, so results can be diffed
directly against FIJI output, and additionally write a tidy CSV and the parameter dump.

### D11 — Frame numbers are 1-based · *proposed*

Every parameter that refers to a frame (`reference_frame`, `ref_search_start`,
`mask_start_frame`, …) counts from 1, matching FIJI and the manual. Internally the code
converts to Python's 0-based indexing.

**Trade-off:** this is mildly unusual for Python, where counting from 0 is the norm. We
chose it because the alternative guarantees off-by-one confusion at exactly the moment it
hurts most — when comparing our output against FIJI's, or when a user reads a frame number
off a FIJI window and types it in. A frame number now means the same thing in both tools.

### D12 — Parameter names follow Python conventions · *taken*

`speedWindow` becomes `speed_window`, `PeakDetectionWindow` becomes `peak_window`, and so
on. The original macro name is documented alongside each parameter so the two can be
cross-referenced. Keeping the original spellings would have mixed old and new naming in
the same namespace and made a later rename harder to carry out safely.

### D13 — Analysis functions take explicit keyword arguments, not the `Params` object · *taken*

`detect_reference_frame(frames, *, speed_window=2, ...)` rather than
`detect_reference_frame(frames, params)`. Each function then states exactly what it
depends on and can be used without knowing about our configuration object. The
user-facing class unpacks `Params` into these calls.

**Trade-off:** defaults are written twice, so they could drift apart. A test introspects
every function's signature and asserts each default equals the matching `Params` field,
which turns drift into a CI failure rather than a silent inconsistency.

### D14 — The user-facing class is called `Boa` · *taken*

`Boa("recordings/A001", framerate=25).run()`. Short, memorable, and unambiguous inside a
package called `boamotion`. `Recording` was rejected because `FrameSequence` and
`SyntheticRecording` already occupy that concept.

---

## 2. Open questions for the client

- **Q1 — Frame rate.** The example recording is 25 fps. The MUSCLEMOTION manual requires
  60–75 fps minimum, and the macro itself prints `WARNING: Recorded framerate is low`
  below 50 fps. At 25 fps the timing resolution is 40 ms per frame, which meaningfully
  limits the precision of time-to-peak and relaxation time. Is 25 fps the standard for
  this assay, and are the temporal parameters being used quantitatively? (Amplitude
  measures are much less affected than timing measures.)
- **Q2 — Demo data.** The manual describes a `demo/` folder containing `demo_stack.tif`
  and a `demo_results/` folder with correct reference outputs. It is *not* in the public
  GitHub repository. Does your FIJI installation have it? It would let us validate against
  known-good numbers immediately.
- **Q3 — Settings.** The screenshot shows only the third wizard dialog. What did you select
  in the first one — specifically Gaussian blur, noise reduction, and reference-frame
  detection? We are currently assuming the defaults (blur off, noise reduction on,
  automatic reference frame).
- **Q4 — Cropping.** See D7.
- **Q5 — Scope.** "Runs on the SLURM cluster" was the original motivation, but batch
  processing and performance work are in the Outlook list, not the prototype. Worth
  confirming this is understood, since it is the one place where the stated prototype and
  the original project goal diverge.

---

## 3. Findings about the original macro

Observations from reading `MUSCLEMOTION v1-1beta.ijm`. These are not criticisms of the
science — the tool is well designed and widely used — but they affect what "identical
results" means, so the client should see them.

Each item below states the consequence. For the original source behind it, and the
mechanism worked through line by line, see [`LEGACY_MODE.md`](LEGACY_MODE.md).

### F1 — The automatic reference-frame selection does not do what it documents · *significant*

The method is meant to find frames that are both quiet and stable (near the origin *and*
near the unity line in the phase-plane). In the code the `unitySelection` array is
allocated with `lowValueN` entries but the loop that fills it stops one short, leaving the
final entry at zero. Because every candidate value is non-negative, that leftover zero
always wins the subsequent minimisation and is never displaced.

**Effect:** the unity-line refinement has no influence at all, and the `unitySelectionN`
parameter does nothing. The method reduces to "take the `lowValueN`-th point closest to
the origin". This is the most consequential finding here, because the reference frame sets
the baseline of the entire contraction trace.

**Now confirmed in code.** On a recording constructed so the right answer is unambiguous,
the corrected method picks the quiet, steady point while the original picks one with
about twelve times as much motion. On our synthetic recording both still land on a
resting frame, but on different ones. Tests pin the mechanism: the original's answer is
always the `lowValueN`-th quietest candidate whatever the stability scores are, and
`unitySelectionN` provably changes nothing.

### F2 — One-frame offset in the same routine · *minor*

The motion trace is computed relative to `autoDetectStart` but then sliced with absolute
indices, so the chosen point is mapped back to a frame number without accounting for where
the search began.

**Observable consequence:** the corrected version reports the same physical frame no matter
where the search window starts, while the original's answer moves with `autoDetectStart`.
With the default of 1 the reported frame is one too low. A larger value shifts it further,
which also means `autoDetectStart` was effectively unusable in the original.

### F3 — The peak threshold uses an arbitrary trace sample · *moderate*

The global peak-amplitude threshold takes its zero point from `yValues[referenceFrameSlice]`
— indexing the *contraction trace* with a *frame number*. The intent is "the baseline is
near zero", but the value actually used is an arbitrary sample of the trace.

### F4 — A single detected peak loses its baseline · *edge case*

If the detector finds exactly one peak, the code appends a literal `false` (i.e. 0) to the
peak list to make later array arithmetic work. The result table is written per *detected*
peak, so no spurious row appears — but several quantities are derived from the distance
between neighbouring peaks, and the appended zero makes the real peak look as though it has
a neighbour at position 0. That distance comes out negative, a loop that should locate the
beat's steepest rise never runs, and in the flat-baseline mode the resulting threshold of
zero admits no baseline points at all.

**Consequence:** with `high_freq_baseline = False`, the single beat's baseline is reported
as 0 and its contraction amplitude therefore equals the raw peak height rather than the
height above rest. The flank crossings are also searched over a wider range than intended.
With `high_freq_baseline = True` the baseline is unaffected. Relevant to short or slowly
beating recordings, and to any recording where the peak threshold admits only one beat.

### F5 — Why the earlier Python attempt gave different results

The client's colleague attributed the discrepancy to OpenCV versus FIJI arithmetic. That
is almost certainly not the cause — `cv2.absdiff` on 32-bit floats is identical to numpy's
subtraction. The real differences are that three algorithms were replaced rather than
ported: reference-frame selection uses "quietest consecutive frame difference" instead of
the phase-plane method; peak detection uses `scipy.signal.find_peaks` with a prominence
criterion instead of the macro's sliding-window-and-threshold rule; and flank crossings
use a different rule than the macro's "three consecutive points beyond the level". The
reference frame is also never removed from the stack, which the macro does. This is the
direct justification for D4.

### F6 — Column naming convention

Percentage output columns are named by `100 - percentage`, so selecting 10% produces a
column called "90-to-90 transient (ms)". Confusing at first sight, but it matches the CD90
convention used in the field. We will keep it and document it.

### F7 — Settings are stored in ImageJ's global preferences

The macro remembers the last-used settings across sessions in ImageJ's preference store.
Convenient, but it means an analysis cannot be reproduced from its outputs alone, and
settings leak between unrelated projects. See D6.

---

### F8 — The first selected percentage silently defines three other measures

The chosen percentage levels look like an independent list of extra outputs, but the
*first* one does more: its crossing points on the two flanks are what "time-to-peak",
"relaxation time" and "contraction duration" are measured from. With the usual selection
starting at 10%, contraction duration is therefore measured 10% above baseline — which the
column name does say — but deselecting 10% would silently change the definition of three
headline measures. We keep the behaviour, require the levels to be given in ascending
order, and document it.

### F9 — Masked amplitudes depend on how much of the frame the mask keeps

The mask is applied by multiplying the difference image, but the average that follows is
taken over the *whole* frame rather than over the kept pixels. A mask covering a tenth of
the frame therefore produces amplitudes roughly a tenth of the average change in the
moving region.

**Consequence:** contraction amplitudes are not comparable between recordings whose masks
differ in coverage — the same tissue filling less of the field reads as a smaller
contraction. Timing measures are unaffected. This is design rather than a bug, so we
reproduce it in both modes.

### F10 — The time axis closes the gap left by the reference frame

The reference frame is removed from the stack before measuring, so the traces hold one
point fewer than the recording. The two trace points either side of it are still adjacent
in the trace but two sampling intervals apart in the recording — with frame 5 as
reference, trace points 3 and 4 are frames 4 and 6. The time axis adds one interval per
point regardless, so that step is drawn half its true length.

**Consequence:** every point after the reference frame is placed one frame too early.
Durations measured between two points are unaffected, since the shift cancels; absolute
peak times after the reference are off by one frame. Small, and smaller still because the
reference is usually near the start of the recording.

### F11 — An explicitly set mask end frame excludes itself · *minor*

The loop building the pixel mask stops one frame before the end frame it is given, so that
frame does not contribute. With the default setting ("use the whole recording") this is
invisible, because the count it compares against was taken before the reference frame was
removed and the two off-by-ones cancel exactly. It only takes effect when a user sets an
end frame deliberately — for instance to exclude a stimulation artefact — and then the last
frame they asked for is silently left out.

**Consequence:** negligible in practice. One frame among hundreds, contributing to a
pixel-wise maximum that is subsequently thresholded; it changes the mask only if that frame
happened to hold a pixel's largest excursion. Recorded for completeness.

### F12 — The peak detection window is one frame narrower than it reads · *minor*

A candidate is compared against its neighbours out to `peak_window/2 - 1` on each side, so
the default of 20 examines a 19-point neighbourhood. A peak exactly 10 points away from a
higher one is admitted. This is a definition detail rather than a mistake — "a window of 20
frames" centred on a point is inherently ambiguous — but it is worth knowing when choosing
the parameter, and we reproduce it exactly in both modes because changing it would alter
every peak list.

A firmer consequence of the same loop: candidates within `peak_window/2` of the start of the
trace, or `peak_window/2 + 1` of its end, are never examined at all. **A beat at the very
start of a recording cannot be detected.** With the default that is the first ten points.

### F13 — One beat with too few baseline points narrows all the later ones · *moderate*

This applies only to the flat-baseline mode (`high_freq_baseline = False`). When a beat does
not offer enough flat points to average, the macro reduces the number of points to average —
but it assigns to the parameter itself rather than to a per-beat copy. Every subsequent beat
in that recording then uses the reduced number, and the value only ever ratchets downward.
One noisy beat early on can leave the rest of the recording with baselines averaged over one
or two points.

A second, related detail: a beat offering exactly one qualifying point is treated as
offering none, and its baseline is reported as 0.

**Consequence:** baselines, and therefore contraction amplitudes, depend on the order the
beats are processed in, and a single bad beat degrades the beats after it but not before it.
The printed warning names the beat that triggered the reduction but not the ones it affects.
`high_freq_baseline = True`, which we believe is the client's setting, is unaffected — worth
confirming (see Q3).

---

## 4. Deferred — after the prototype

Agreed as out of prototype scope, listed so nothing is lost:

- Input formats other than a TIFF image sequence directory (TIFF stacks, PNG sequences,
  uncompressed AVI).
- Gaussian blur preprocessing (only relevant for samples with highly repetitive
  structures, such as adult cardiomyocytes).
- Region-of-interest / cropping parameter (D7).
- Interactive reference-frame selection (D5).
- Batch processing over directories, and the command-line interface.
- SLURM / cluster integration.
- Performance work: chunked or parallel reading, and any per-recording parallelism (D9).
- Drift and artefact correction.
- User documentation.
