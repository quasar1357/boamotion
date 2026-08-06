# The original's quirks, in its own code

The last section of [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) describes these quirks in plain
language, and section 3 of [`DECISIONS.md`](DECISIONS.md) records what each means for
results. This file is the working reference behind both: for each one, the actual FIJI
macro source, why it behaves as it does, and what `boamotion` does in either mode.

It is aimed at whoever maintains the port — including us, months from now, trying to
remember why a function has two branches. Line numbers refer to
`MUSCLEMOTION v1-1beta.ijm`.

**The F numbers are shared across all three files**, so any finding can be followed from
one to the next. The nine below are F1 to F9 of the fourteen in `DECISIONS.md` — the ones
that are quirks of the original's implementation.

All nine are implemented. F1 to F7 are corrected by `legacy=False`, and run roughly in the
order the analysis meets them: reference frame, then mask, then transients. F8 and F9 we
reproduce in **both** modes, because they are definitions rather than mistakes and
changing them would silently alter every result.

Three conventions to keep in mind while reading the excerpts. Arrays in the ImageJ macro
language are **0-based**, but stack slices are **1-based**, and the macro mixes the two
freely — which is where several of these come from. `Array.rankPositions(a)` returns the
indices of `a` sorted by value ascending, so `rankPositions(a)[0]` is the position of the
smallest element.

And in the macro language `-` binds **tighter** than `+`, which is not what most languages
do. It is what makes `100-percentages[m]+"-to-"+100-percentages[m]+" transient (ms)"`
produce `90-to-90 transient (ms)` rather than a type error partway through, and equally
what makes the all-`+` expression in F2 print `511` instead of `52`.

| F | Quirk | Impact | Implemented in |
|---|---|---|---|
| F1 | [The unity-line filter never runs](#f1--the-unity-line-filter-never-runs) | significant | `reference.py` `_select_legacy` |
| F2 | [The search start is not added back](#f2--the-search-start-is-not-added-back) | minor | `reference.py` `detect_reference_frame` |
| F3 | [The mask loses its last frame](#f3--the-mask-loses-its-last-frame) | minor | `traces.py` `_frames_to_use` |
| F4 | [The mask holds 255, not 1](#f4--the-mask-holds-255-not-1) | constant factor | `traces.py` `_mask_weight` |
| F5 | [The peak threshold indexes the trace with a frame number](#f5--the-peak-threshold-indexes-the-trace-with-a-frame-number) | moderate | `transients.py` `_zero_level` |
| F6 | [A single detected peak loses its baseline](#f6--a-single-detected-peak-loses-its-baseline) | edge case | `transients.py` `_range_positions` |
| F7 | [A baseline shortage narrows every later beat](#f7--a-baseline-shortage-narrows-every-later-beat) | moderate | `transients.py` `_legacy_flat_average` |
| F8 | [The peak window is a frame narrower than it reads](#f8--the-peak-window-is-a-frame-narrower-than-it-reads) | minor | `transients.py` `_dominates_neighbours` |
| F9 | [The first percentage defines three other measures](#f9--the-first-percentage-defines-three-other-measures) | by design | `transients.py` `measure_transients` |

---

## F1 — The unity-line filter never runs

Reference-frame detection, lines 899-921. This is the one that actually matters.

```javascript
indicesVal=Array.rankPositions(radianPoints);   // candidates, quietest first
low=0;
unitySelection=newArray(lowValueN);             // lowValueN entries, all zero
for(d=0;d<lowValueN-1;d++){                     // (a) fills only lowValueN-1 of them
    index=indicesVal[d];
    unitySelection[d]=abs((speedY[index]/speedYshift[index])-1);
}

//check which [unitySelectionN] of the unitySelection is smallest
indicesUni=Array.rankPositions(unitySelection); // (b) the untouched 0 sorts first
for(d=0;d<unitySelectionN-1;d++){               // (c) also one short
    indexTrans=indicesUni[d];
    index=indicesVal[indexTrans];
    lowValue=(speedY[index]*speedYshift[index])*unitySelection[indexTrans];
    if(d==0){
        low=lowValue;                           // (d) d==0 wins unconditionally
        lowIndex=index;
    }
    else if(low>lowValue){                      // (e) strict, so 0 is never displaced
        low=lowValue;
        lowIndex=index;
    }
}
```

**What goes wrong.** `newArray(n)` in the macro language zero-fills. At (a) the loop runs
`d = 0 … lowValueN-2`, so `unitySelection[lowValueN-1]` is never assigned and stays `0`.
Every genuine unity distance is a non-negative `abs(...)`, so at (b) that leftover zero
ranks first and `indicesUni[0] == lowValueN-1`.

The first pass through the second loop therefore lands on it, and (d) takes it
unconditionally. Its score at that point is `speedY * speedYshift * 0`, which is exactly
`0` — the smallest value the score can take. Because (e) compares strictly, nothing later
can displace it.

**The consequence.** `lowIndex` is always `indicesVal[lowValueN-1]`: the **`lowValueN`-th
quietest** candidate, not the quietest, and not the steadiest. The stability test — the
part of the method the paper's Figure S4 is about, and the only part that distinguishes
true rest from a momentary standstill at the top of a beat — contributes nothing.
`unitySelectionN` is inert, which (c) would have crippled anyway.

Worth stressing that the *method* is sound; only this implementation of it is not. And it
usually still returns something reasonable, because a recording with a decent rest phase
holds many near-identical quiet frames, which is very likely why it went unnoticed.

**What boamotion does.** `reference.py` has both. `_select_legacy` is transcribed loop for
loop, zero-fill and all, so the mechanism stays visible rather than being asserted in a
comment. `_select` is the method as documented: shortlist by distance from the origin,
then by distance from the unity line, then score.

`test_reference.py` pins the mechanism rather than a number:
`test_legacy_selection_is_decided_by_the_radius_ranking_alone` sweeps `n_low_values` and
asserts the answer is always the `n_low_values`-th quietest, and
`test_n_unity_values_has_no_effect_in_legacy_mode` sweeps the parameter that is supposed
to matter and asserts it changes nothing.

On a recording built so that the right answer is unambiguous, the corrected method picks
the quiet, steady point while the original picks one with about **twelve times** as much
motion.

## F2 — The search start is not added back

Same function, lines 859-891 and 923-929.

```javascript
speedY=newArray(autoDetectStop-autoDetectStart+1);
...                                             // filled from slice 1 upward
speedY=Array.slice(speedY,autoDetectStart,autoDetectStop);
```

```javascript
setSlice((lowIndex+1));
print("Automatic detected reference frame: frame "+lowIndex+1);
referenceFrameSlice=lowIndex+1;
```

**What goes wrong.** The motion trace is built starting at slice 1, then sliced from
`autoDetectStart`, so `lowIndex` is a position *within the search window*. Converting it
back to a slice number adds only the 1 that turns a 0-based array index into a 1-based
slice — never `autoDetectStart` itself.

With the default `autoDetectStart = 1` the reported frame is one too low. Any larger value
shifts it further, by exactly that amount, which means the parameter was effectively
unusable: narrowing the search moved the answer.

(The `print` on the preceding line has a second, harmless bug — string concatenation binds
left to right, so it prints `511` rather than `52`. Cosmetic, log only.)

**What boamotion does.** `detect_reference_frame` maps the winning index to a frame with
`index + 1` when `legacy=True` and `index + ref_search_start + 1` otherwise.
`test_corrected_result_does_not_depend_on_where_the_search_starts` asserts the corrected
version returns the same physical frame from three different search starts;
`test_legacy_result_moves_when_the_search_starts_elsewhere` asserts the original's does
not.

## F3 — The mask loses its last frame

`pixelsOfInterest`, lines 649-651.

```javascript
if(MPendRange==-1){MPendRange=slices;}
else if(MPendRange>slices){MPendRange=slices;}
for(lfhIndex=MPstartRange;lfhIndex<MPendRange;lfhIndex++){
```

**What goes wrong.** The bound is strict, so frame `MPendRange` itself never contributes to
the maximum-intensity projection.

With the default `-1` this is invisible, and that is worth understanding rather than
assuming. `slices` is captured before the reference frame is deleted from the stack, so the
stack being iterated holds `slices-1` frames; the loop covering `1 … slices-1` therefore
covers all of them exactly. The off-by-one only bites when a user **sets** an end frame, at
which point the last frame they asked for is silently excluded.

**What boamotion does.** `_frames_to_use` uses `end - 1` when `legacy=True` and `end`
otherwise, and does nothing differently when `mask_end_frame` is `None` — matching the
above. `test_legacy_stops_one_frame_early` pins it.

Small in effect: one frame out of hundreds, contributing to a pixel-wise maximum that is
then thresholded. It matters only if that particular frame held the largest excursion.

## F4 — The mask holds 255, not 1

`pixelsOfInterest` line 674, applied in `getContractionData` line 697. See also F13, a
separate point about the average that follows.

```javascript
setThreshold(lucaVar, max);
run("Make Binary");
```

```javascript
if(maxProject==true){
    imageCalculator("Multiply create 32-bit stack", "Result of subtractTemp","maxProjectStack");
}
getStatistics(LFHnothing, LFHmean, LFHmin, LFHmax, LFHstdDev);
```

**What happens.** `Make Binary` produces an 8-bit mask of 0 and 255, and the difference
image is multiplied by it directly rather than by a 0/1 indicator. Every masked trace is
therefore scaled by 255.

This is not really a bug — the units are arbitrary — but it must be reproduced exactly to
match the original's numbers, and it is a trap for anyone comparing a masked run against an
unmasked one and expecting the amplitudes to be commensurable.

Note also that `getStatistics` runs on the multiplied image, whose mean is taken over the
**whole frame** with excluded pixels counted as zero, not over the kept pixels. That is the
separate point recorded as F13, and we reproduce it in both modes because it is a design
choice rather than a mistake.

**What boamotion does.** `_mask_weight` multiplies the boolean mask by `255.0` when
`legacy=True` and `1.0` otherwise. `test_legacy_scales_the_trace_by_255` asserts the ratio,
and `test_legacy_changes_nothing_without_a_mask` asserts the flag is inert when there is no
mask to scale.

## F5 — The peak threshold indexes the trace with a frame number

`transientAnalysis`, lines 1009-1011.

```javascript
perc100=yValues[maxMin[yValues.length-1]];
perc0=yValues[referenceFrameSlice];
peakThresholdValue=(peakThreshold/100)*(perc100-perc0);
```

**What goes wrong.** `perc100` is correct: the largest value in the trace. `perc0` is meant
to be the baseline, near zero — but `yValues` is the **contraction trace** and
`referenceFrameSlice` is a **frame number**. Indexing one with the other is a category
error; the value that comes out is an arbitrary sample of the trace.

It usually passes unnoticed because the reference frame is typically near the start of the
recording, where the trace is genuinely near baseline. If the reference frame number
happens to land on or near a peak, the threshold shifts by a large fraction of the
amplitude and peaks are wrongly admitted or dropped.

The compounding detail: the reference frame has been removed from the trace by this point,
so the index does not even refer to the frame it names.

**What boamotion does.** `_zero_level` reproduces the indexing when `legacy=True` and
takes the trace minimum otherwise. `test_the_legacy_zero_level_can_drop_a_genuine_beat`
builds a train with one smaller beat and shows the original losing it while the
corrected version keeps it.

## F6 — A single detected peak loses its baseline

`transientAnalysis`, lines 1047-1051.

```javascript
//fix if maxList is 1 value;
if(maxCount<2){
    print("1 peak: adding false value to facilitate array calculations.");
    maxList=Array.concat(maxList,false);
}
```

**Why it is there.** `maxList` is assigned a bare number for the first peak and only becomes
an array on the second (lines 1037-1044), so a single peak leaves a scalar where the rest of
the function expects an array. Appending `false`, which the macro coerces to `0`, makes it
an array again.

**What goes wrong.** `maxCount` stays 1 while `maxList.length` becomes 2, and the function
uses the two interchangeably. Everything that writes a result row is bounded by `maxCount`
(lines 1172 and 1262), so **no spurious row is produced** — but everything that derives a
range from the *next* peak uses `maxList`, and the next peak is now at position 0, so those
ranges come out negative:

```javascript
rangeSpeedMax=round((maxList[j+1]-maxList[j])/4);          // negative
if(maxList[j]-(rangeSpeedMax)>0 && maxList[j]+rangeSpeedMax<yValues.length){
    findMax=0;
    for(b=maxList[j]-rangeSpeedMax;b<maxList[j]+rangeSpeedMax-1;b++){   // start > end
        ...
    speedMaxValueList[j]=findMax;                          // assignment is inside the loop
    }
}
```

The guard passes, but the loop's start already exceeds its end, so it never iterates — and
because the assignment sits *inside* it, `speedMaxValueList[0]` is never written and keeps
its zero-fill. That value is the beat's steepest rise, and the flat-baseline mode scales its
threshold by it:

```javascript
baselineThresholdValue=(baselineThreshold/100)*speedMaxValueList[countPeakRegion];  // 0
if((abs(yValues[j+1]-yValues[j])<baselineThresholdValue) && ...)                    // never true
```

No point can be strictly below zero, so no baseline points are collected and the baseline is
reported as `0`. The contraction amplitude for that beat is then its raw height rather than
its height above rest.

`high_freq_baseline = True` takes a minimum instead and is unaffected. The flank search is
also widened, since `peakToPeakDistance` becomes negative and only its absolute value is
used.

**What boamotion does.** `_range_positions` appends the phantom zero when `legacy=True`
and exactly one peak was found, so `_steepest_rise` reverses just as the original does.
`test_a_lone_peak_gets_a_zero_baseline_in_legacy_mode` asserts the resulting baseline is
`0.0` and that the corrected mode returns a genuine resting value;
`test_a_lone_peak_is_unaffected_in_the_high_frequency_mode` pins the other half.

## F7 — A baseline shortage narrows every later beat

`transientAnalysis`, lines 1139-1167.

```javascript
if(regionBaselineValues.length>baselineNumberOfPoints){
    startF=regionBaselineValues.length-baselineNumberOfPoints;
}
else{
    startF=0;
    baselineNumberOfPoints=regionBaselineValues.length;    // (a) global, and permanent
    print("WARNING: Not enough baseline values at peak "+countPeakRegion+" ...");
}
if(regionBaselineValues.length>1){
    ...                                                    // sum the last startF..end
}
else{
    sumBaselineValues=0;                                   // (b) a single point is discarded
}
minValueList[countPeakRegion]=sumBaselineValues/baselineNumberOfPoints;
```

**What goes wrong, twice.** At (a) `baselineNumberOfPoints` is the global parameter itself,
not a local copy. One beat with too few flat points permanently lowers it for every
*subsequent* beat in the recording, and it only ever ratchets downward. A single noisy beat
early in a recording can therefore reduce the whole recording's baselines to an average of
one or two points. The warning printed names the beat that triggered it but not the beats it
goes on to affect.

At (b) the array is initialised as `newArray(1)`, so "one qualifying point" and "no
qualifying points at all" are indistinguishable — both have length 1. The branch discards
both, yielding a baseline of `0 / baselineNumberOfPoints = 0`. So a beat with exactly one
flat point gets a zero baseline rather than that point's value.

**What boamotion does.** `_legacy_flat_average` carries the narrowed count from beat to
beat and discards a lone point; the corrected path keeps `baseline_n_points` per beat,
uses a single qualifying point when that is all there is, and falls back to the lowest
point in the search range when there are none.
`test_a_baseline_shortage_narrows_every_later_beat` measures the same second beat against
two traces differing only in the first, and gets 10.8 against 10.6.

## F8 — The peak window is a frame narrower than it reads

`transientAnalysis`, lines 1021-1027.

```javascript
for(u=PeakDetectionWindow/2;u<yValues.length-1-PeakDetectionWindow/2;u++){
    if((yValues[u]-perc0)>peakThresholdValue){
        for(r=1;r<PeakDetectionWindow/2;r++){
            if(yValues[u-r]>yValues[u] || yValues[u+r]>yValues[u]){
                noMax=true;
```

**What happens.** The inner bound is strict, so with the default window of 20 a candidate is
compared against its neighbours at `±1 … ±9` — a 19-point neighbourhood, not 20 or 21. A
peak exactly 10 points from a higher one is therefore admitted.

This is a definition detail rather than a mistake; "a window of 20 frames" centred on a point
is inherently ambiguous. It is recorded because it must be matched exactly to reproduce the
original's peak list, and because the obvious reading of the parameter is off by one.

The outer bound has a firmer consequence: candidates in the first `peak_window/2` points, or
the last `peak_window/2 + 1`, are never examined. A beat at the very start of a recording is
invisible to the detector.

**What boamotion does.** `_dominates_neighbours` compares the slice
`[position - half + 1, position + half)`, matching the original in both modes: this is
the definition of the parameter, and changing it would alter every peak list.
`test_the_neighbourhood_reaches_one_point_less_far_than_the_window` shows a higher point
10 away failing to displace a candidate where one 9 away succeeds, and
`test_a_beat_near_the_end_of_the_trace_is_never_examined` shows the textbook window of
18 losing the fourth beat of our synthetic recording.

## F9 — The first percentage defines three other measures

`transientAnalysis`, lines 1187-1245. Included here because it looks like a bug and
is not.

```javascript
for(m=0;m<percentageLevels.length;m++){
    ...
    for(l=maxList[c];l>minBorder;l--){
        if(yValues[l]<percentageLevels[m] && yValues[l-1]<percentageLevels[m] && yValues[l-2]<percentageLevels[m]){
            percentageDataDown[m]=l;
            if(m==0){
                lowDown=l;          // the first level, and only the first, is kept
            }
            l=minBorder;            // "break", by assigning past the loop bound
        }
    }
    ...
}
...
contractionTime=abs((maxList[c]-lowDown)*samplingTime);
relaxationTime=abs((maxList[c]-lowUp)*samplingTime);
transientDuration=abs((lowUp-lowDown)*samplingTime);
```

**What happens.** The percentage levels look like an independent list of extra outputs, but
`m==0` also sets `lowDown` and `lowUp`, and those define time-to-peak, relaxation time and
contraction duration. With the usual list starting at 10%, contraction duration is measured
10% above baseline — which the hard-coded column name at line 1243 does say. Deselecting
10% would silently redefine three headline measures while leaving that column name intact.

Two things in the excerpt are idiom rather than error, and are worth recognising so they
are not "fixed" during the port. Assigning `l=minBorder` is how the macro language breaks
out of a loop. And the `three consecutive points below the level` test is a deliberate
noise guard, not an off-by-one.

**What boamotion does.** `measure_transients` reproduces the coupling in both modes and
requires `percentages` to ascend, which `Params` already enforced.
`test_the_first_percentage_defines_the_headline_measures` asserts that contraction duration
always equals the transient at the first level, and that starting the list at 50% instead
of 10% changes all three headline measures.

Requiring ascending order also disarms a second problem in this loop. The
`percentageDataDown` and `percentageDataUp` arrays are allocated once, before the peak
loop, and never reset between beats, so a level with no crossing for this beat silently
keeps the crossing found for the previous one. It is unreachable in practice: the
durations are only computed when the *first* level found both its crossings, and the first
level is the lowest, which is the hardest to reach — any level above it crosses nearer the
peak. So if the first level is found, all of them are. We therefore do not reproduce the
stale value, and there is nothing to correct.

---

## Divergences we accept

Places where we knowingly do not match the original bit for bit, in either mode.

**Ties in the ranking.** `Array.rankPositions` does not specify how equal values are
ordered. We use `np.argsort(kind="stable")`, which keeps the earlier index first. Exact
ties in a mean-of-absolute-differences over a whole frame need identical frames, so this
should not arise with real camera noise.

**`0/0` in the unity distance.** Two perfectly identical consecutive motion values give
`0/0`, which is `NaN` in the macro and would propagate unpredictably through
`rankPositions`. We map it to `0` — a pair with no motion at all sits exactly on the unity
line, which is the sensible reading. Again, only reachable with noise-free frames, which is
to say with synthetic recordings rather than real ones.

**Gaussian blur** is not implemented (deferred, see `DECISIONS.md` section 4). It appears
in most of the excerpts above and is skipped when reading them.
