# What `legacy=True` reproduces, in the original's own code

`HOW_IT_WORKS.md` describes the original's quirks in plain language and `DECISIONS.md`
records what they mean for results. This file is the working reference behind both: for
each item, the actual FIJI macro source, why it behaves as it does, and what `boamotion`
does in either mode.

It is aimed at whoever maintains the port — including us, months from now, trying to
remember why a function has two branches. Line numbers refer to
`MUSCLEMOTION v1-1beta.ijm`.

Two conventions to keep in mind while reading the excerpts. Arrays in the ImageJ macro
language are **0-based**, but stack slices are **1-based**, and the macro mixes the two
freely — which is where several of these come from. `Array.rankPositions(a)` returns the
indices of `a` sorted by value ascending, so `rankPositions(a)[0]` is the position of the
smallest element.

| | Quirk | Impact | Status |
|---|---|---|---|
| 1 | [The unity-line filter never runs](#1--the-unity-line-filter-never-runs) | significant | ported |
| 2 | [Search start is not added back](#2--the-search-start-is-not-added-back) | minor | ported |
| 3 | [The mask loses its last frame](#3--the-mask-loses-its-last-frame) | minor | ported |
| 4 | [The mask holds 255, not 1](#4--the-mask-holds-255-not-1) | constant factor | ported |
| 5 | [The peak threshold indexes the trace with a frame number](#5--the-peak-threshold-indexes-the-trace-with-a-frame-number) | moderate | step 10 |
| 6 | [A phantom peak when only one is found](#6--a-phantom-peak-when-only-one-is-found) | edge case | step 10 |
| 7 | [The first percentage defines three other measures](#7--the-first-percentage-defines-three-other-measures) | by design | step 10 |

---

## 1 — The unity-line filter never runs

Reference-frame detection, lines 899-921. This is the one that actually matters. See F1.

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

## 2 — The search start is not added back

Same function, lines 859-891 and 923-929. See F2.

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

## 3 — The mask loses its last frame

`pixelsOfInterest`, lines 649-651. Not previously written down anywhere; see F11.

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

## 4 — The mask holds 255, not 1

`pixelsOfInterest` line 674, applied in `getContractionData` line 697. See F9 for the
related point about the average.

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
separate point recorded as F9, and we reproduce it in both modes because it is a design
choice rather than a mistake.

**What boamotion does.** `_mask_weight` multiplies the boolean mask by `255.0` when
`legacy=True` and `1.0` otherwise. `test_legacy_scales_the_trace_by_255` asserts the ratio,
and `test_legacy_changes_nothing_without_a_mask` asserts the flag is inert when there is no
mask to scale.

## 5 — The peak threshold indexes the trace with a frame number

`transientAnalysis`, lines 1009-1011. **Not yet ported — this is step 10.** See F3.

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

**Planned handling.** `legacy=True` reproduces the indexing verbatim; `legacy=False` uses
the trace minimum as the zero point.

## 6 — A phantom peak when only one is found

`transientAnalysis`, lines 1047-1051. **Not yet ported — step 10.** See F4.

```javascript
//fix if maxList is 1 value;
if(maxCount<2){
    print("1 peak: adding false value to facilitate array calculations.");
    maxList=Array.concat(maxList,false);
}
```

**What goes wrong.** `maxList` is built as a bare number when the first peak is found and
only becomes an array on the second (lines 1037-1044), so a single peak leaves a scalar
where the rest of the function expects an array. The fix appends `false`, which the macro
coerces to `0`.

Downstream, `maxList.length` is now 2 and the loops run twice, producing a second result
row for a "peak" at trace position 0, with whatever measurements fall out of it. It affects
short recordings and slowly beating ones — exactly the recordings where a spurious extra
row is most likely to be taken seriously.

**Planned handling.** `legacy=True` emits the phantom row so the result table matches
FIJI's row for row; `legacy=False` returns the single peak alone.

## 7 — The first percentage defines three other measures

`transientAnalysis`, lines 1187-1245. **Not yet ported — step 10.** See F8. Included here
because it looks like a bug and is not.

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

**Planned handling.** Reproduced in both modes, since it is the documented behaviour. We
require `percentages` in ascending order and document the coupling.

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
