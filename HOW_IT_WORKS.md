# How boamotion measures contraction

This is our own description of the method, written from the original MUSCLEMOTION macro
source. It explains what the analysis does, what each parameter changes, and where the
original implementation behaves differently from how it is described.

For the science behind the method, see Sala & van Meer et al., *Circulation Research*
122(3):e5–e16, 2018 (doi:10.1161/CIRCRESAHA.117.312067).

## The one idea everything rests on

Take a video of beating muscle. Pick one frame in which the tissue is at **rest** — the
reference frame. For every other frame, compare it to the reference pixel by pixel:
subtract, and take the absolute value. Where nothing moved the difference is near zero
(black); where something moved it is large (bright). Then average that difference image
over all pixels, giving one number per frame:

```
contraction[i] = mean( | frame[i] - reference | )
```

Plotted against time, those numbers are the contraction trace.

The crucial thing to internalise is that **this tracks nothing**. It does not know where
the tissue is, which direction it moved, or how far. It answers only one question: how
different does this frame look from rest? More movement, bigger number. Three consequences
follow, and they explain most of what comes later.

- **The units are arbitrary.** There is no calibration to microns or to force. Peaks can
  be compared within a recording, but comparing absolute amplitudes between recordings is
  only meaningful when illumination, focus and field of view are identical. Amplitude
  scales roughly linearly with lamp brightness.
- **Contraction and relaxation are indistinguishable.** Because the difference is
  absolute, both read as "far from rest", so one beat produces one hump rather than an
  up-and-down excursion.
- **Anything that changes pixel brightness looks like contraction.** Flickering
  illumination, focus drift or a drifting bubble are not distinguishable from movement.

## Stage 1: choosing the reference frame

The reference frame is the zero point of the entire measurement, and the single most
consequential input. Choose a frame from the middle of a contraction and everything
distorts: true rest now looks far from the reference and appears as a peak, while the real
peak may look closer to it. The trace can end up inverted or double-humped.

**Automatic detection.** First a *motion* signal is built: how much the image changed
between frame `i` and frame `i + speed_window`. Call it `v[i]`. It is large while the
tissue moves and near zero while it is still.

Rather than simply taking the smallest `v`, the method plots `v[i]` against `v[i+1]`, so
each point represents one frame paired with the next. Three situations then separate
cleanly:

- **Mid-contraction.** `v` is large, so the point sits far from the origin.
- **At the turning point of a beat.** Motion is momentarily zero but picks up again
  immediately, so `v[i]` is small while `v[i+1]` is large. The point lies near an axis but
  well off the diagonal.
- **Genuine rest.** Motion is small and *stays* small, so `v[i] ~ v[i+1] ~ 0`. The point
  is near the origin **and** on the diagonal.

The algorithm therefore shortlists the `n_low_values` points nearest the origin, then
keeps the `n_unity_values` of those nearest the diagonal. That second filter is what
separates true rest from a momentary standstill at the top of a beat.

| Parameter | Effect |
|---|---|
| `reference_frame` | Set a frame number to skip detection and use that frame. |
| `ref_search_start`, `ref_search_stop` | Restrict which part of the recording is searched, for instance to skip a start with focus drift or settling illumination. |
| `n_low_values` | How many quiet candidates to shortlist. Too few risks missing the real rest frames; too many admits noisy candidates. |
| `n_unity_values` | How many of those survive the stability test. |

Detection is least reliable when contraction is very symmetric — when the tissue spends as
long contracting as resting, there is no clearly quiet region to find. Check the reference
frame whenever beating is fast.

## Stage 2: the pixel mask

The trace averages over *every* pixel. If the tissue occupies a tenth of the field, the
remaining pixels contribute only camera noise, diluting the signal roughly tenfold. The
mask addresses this:

1. For each frame, compute `|frame - reference|`.
2. Keep a running pixel-wise **maximum** across the recording, giving a map of the most
   each pixel ever changed.
3. Threshold that map at `mean + 1 standard deviation`.
4. The result is a binary mask; the traces then count only the pixels inside it.

| Parameter | Effect |
|---|---|
| `noise_reduction` | Whether to build and apply the mask. On by default. |
| `mask_start_frame`, `mask_end_frame` | Which frames contribute to the mask, for instance to exclude a stimulation artefact. |

Two things follow. Enabling the mask **changes absolute amplitudes**, so masked and
unmasked numbers are not comparable. And because the mask is built from differences
against the reference frame, a poor reference frame degrades the mask as well — the two
errors compound.

## Stage 3: the two traces

```
contraction[i] = mean( | frame[i] - reference |             * mask )   <- fixed reference
speed[i]       = mean( | frame[i] - frame[i+speed_window] | * mask )   <- moving reference
```

The only difference is what each frame is compared against. A fixed reference measures
**displacement from rest**, producing the contraction waveform. A reference that moves
along with the frame measures **how fast the image is changing**, producing something
close to the derivative.

One detail worth having in mind: the speed trace is also an absolute difference, so it is
always positive. Each beat therefore produces **two** speed humps — one while contracting,
one while relaxing — separated by a dip at peak contraction, where the tissue is
momentarily stationary. This is why the analysis also plots the measured speed against the
numerically differentiated contraction trace: when the measurement behaves linearly the
two curves overlap, and a visible divergence is a warning that something is wrong.

| Parameter | Effect |
|---|---|
| `framerate` | Converts frame numbers to time, each frame spanning `1000/framerate` ms. It changes no shape, but every millisecond output scales linearly with it, so a wrong value silently corrupts all timing results. |
| `speed_window` | Frame gap used for the speed trace. Larger values smooth the curve but blur events in time and reduce their amplitude. Around 2-5 frames per 100 fps is a reasonable starting point. |

At low frame rates a `speed_window` of 2 can already span a substantial fraction of a beat,
so it is worth checking against the beat duration rather than using the default blindly.

## Stage 4: transient analysis

With a trace in hand, the analysis extracts per-beat measurements.

**Finding peaks.** A frame counts as a peak when it is the highest value within a window
of plus or minus `peak_window`/2 frames, and when it rises above `peak_threshold` percent
of the trace's full range.

| Parameter | Effect |
|---|---|
| `peak_window` | Too small and noise spikes register as peaks; too large and real beats merge or are missed. A useful rule of thumb is about 0.75 x frames per beat. |
| `peak_threshold` | Height filter, as a percentage of the full range. Raising it rejects small wobbles. |

**Finding each beat's baseline**, the resting level from which amplitude is measured. Two
strategies are available:

- `high_freq_baseline = True` takes the **minimum** value between the previous peak and
  the current one. Robust when the tissue barely rests between beats, which is why it
  suits high beating frequencies.
- `high_freq_baseline = False` looks backwards from the peak for stretches where the curve
  is **flat** — where the frame-to-frame change falls below `baseline_threshold` percent
  of that beat's own steepest rise — and averages the last `baseline_n_points` of them.
  More resistant to noise, but it needs a genuine rest period to work with.

A `baseline_threshold` set too low leaves too few qualifying points; set too high, it
averages in points that are not really baseline. A larger `baseline_n_points` smooths the
baseline but reaches further back in time.

**The measurements.** Amplitude is `peak - baseline`. For each level in `percentages` the
analysis computes `baseline + p% * amplitude` and locates where the curve crosses that
level on the way up and again on the way down, requiring **three consecutive points**
beyond the level so that a single noisy sample cannot trigger a crossing. The time between
the two crossings is the transient duration at that level.

Two naming points. A level of `p` percent is reported as the `(100-p)`-to-`(100-p)`
transient, so the 10% level appears as "90-to-90" — the CD90 convention, measuring
duration at 90% relaxation. And the **first** percentage in the list does double duty: its
crossings also define time-to-peak, relaxation time and contraction duration.

## What `legacy=True` reproduces

MUSCLEMOTION is a well-designed and widely used tool, and the items below are not a
criticism of the science. They are implementation details we had to decide how to handle
in order to reproduce its output faithfully. With `legacy=True`, boamotion behaves as the
original does; with `legacy=False` each is corrected. They are ordered by how much they can
move the resulting numbers.

**1. The unity-line filter never runs.** In the reference-frame detection, the array
holding the unity-line scores is allocated with `n_low_values` entries but the loop that
fills it stops one short, leaving the final entry at zero. Every real score is positive, so
that leftover zero always wins the minimisation that follows. The effect is that
`n_unity_values` has no influence and the stability test — the discriminating part of the
method — is skipped. What is actually selected is the `n_low_values`-th closest point to
the origin rather than the closest. Recordings with a long rest phase contain many
near-identical quiet frames, so the result is usually still reasonable, which is likely why
this went unnoticed; but it is fragile in exactly the fast, symmetric case where the method
is already known to struggle.

**2. The peak threshold uses an arbitrary reference value.** The threshold is computed
relative to `trace[reference_frame_number]`, indexing the contraction *trace* with a
*frame number*. The intent is that the baseline is near zero, and since the trace usually
is near zero early on the result is often acceptable. If the reference frame number
happens to fall on or near a peak, however, the threshold shifts and peaks are wrongly
admitted or dropped.

**3. A one-frame offset** in the reference-frame search: the motion trace is computed
relative to `ref_search_start` but then sliced with absolute indices.

**4. A phantom peak when only one is detected.** If exactly one peak is found, a literal
`false` (evaluating to 0) is appended to the peak list so that later array arithmetic
works. This produces a second peak at frame 0 with meaningless measurements attached. It
affects short or slowly beating recordings.

**5. The first percentage silently defines three other measures**, as described above.
This only matters when the lowest level is deselected, at which point time-to-peak and
relaxation time change meaning without warning.

**6. The mask holds 0 and 255 rather than 0 and 1.** The trace multiplies by the mask
directly, so all amplitudes are scaled by 255. Harmless given arbitrary units, but it must
be reproduced to match the original's numbers.

In practice items 1 and 2 can genuinely change results, item 3 shifts them slightly, item 4
affects edge cases only, item 5 depends on settings, and item 6 is a constant factor.
