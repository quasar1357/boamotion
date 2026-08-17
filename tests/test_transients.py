import logging

import numpy as np
import pytest

from boamotion import (
    build_motion_pixel_mask,
    find_baselines,
    find_peaks,
    measure_contraction,
    measure_transients,
    synthetic_recording,
)


def beat_train(heights=(100.0, 100.0, 100.0, 100.0), period=25, rise=5, fall=8, rest=10.0):
    """A triangular beat train, flat at `rest` between beats. Returns trace and peaks."""
    trace = np.full(len(heights) * period, rest, dtype=float)
    peaks = []
    for beat, amplitude in enumerate(heights):
        peak = beat * period + period // 2
        peaks.append(peak)
        trace[peak] = amplitude
        for step in range(1, rise + 1):
            trace[peak - rise + step - 1] = rest + (amplitude - rest) * step / (rise + 1)
        for step in range(1, fall + 1):
            trace[peak + step] = amplitude - (amplitude - rest) * step / fall
    return trace, peaks


def peak_indices(recording, reference_frame=1):
    """Where the known peaks land in a trace, which omits the reference frame."""
    positions = [i for i in range(recording.n_frames) if i != reference_frame - 1]
    return [positions.index(frame - 1) for frame in recording.peak_frames]


def synthetic_trace():
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = build_motion_pixel_mask(recording.frames, 1)
    return measure_contraction(recording.frames, 1, mask=mask), recording


# --- finding the beats ---------------------------------------------------------------


def test_peaks_are_found_where_the_beats_are():
    trace, peaks = beat_train()
    assert find_peaks(trace, reference_frame=0).tolist() == peaks


def test_peaks_match_the_recording_they_were_built_into():
    trace, recording = synthetic_trace()
    found = find_peaks(trace, reference_frame=0, peak_window=16)
    assert found.tolist() == peak_indices(recording)


def test_a_wobble_below_the_threshold_is_not_a_beat():
    trace, peaks = beat_train()
    trace[3] = 20.0  # a local maximum, but only a ninth of the range above rest
    assert find_peaks(trace, reference_frame=0).tolist() == peaks


def test_a_taller_threshold_drops_the_smaller_beats():
    trace, peaks = beat_train(heights=(100.0, 50.0, 100.0, 100.0))
    assert find_peaks(trace, reference_frame=0).tolist() == peaks
    assert find_peaks(trace, reference_frame=0, peak_threshold=60.0).tolist() == [
        peaks[0],
        peaks[2],
        peaks[3],
    ]


# --- the two ways the peak window is narrower than it reads (F12) ---------------------


def test_the_neighbourhood_reaches_one_point_less_far_than_the_window():
    # With peak_window=20 a candidate is compared against +/- 9, not +/- 10, so a
    # higher point exactly 10 away does not displace it.
    trace = np.zeros(80)
    trace[30], trace[40] = 50.0, 60.0
    assert find_peaks(trace, reference_frame=0).tolist() == [30, 40]

    trace = np.zeros(80)
    trace[30], trace[39] = 50.0, 60.0
    assert find_peaks(trace, reference_frame=0).tolist() == [39]


def test_a_beat_near_the_end_of_the_trace_is_never_examined():
    # The rule of thumb of 0.75 x frames per beat gives 18 here, which loses the fourth
    # beat entirely: it sits within peak_window/2 + 1 of the end of the trace.
    trace, recording = synthetic_trace()
    expected = peak_indices(recording)
    assert find_peaks(trace, reference_frame=0, peak_window=18).tolist() == expected[:-1]
    assert find_peaks(trace, reference_frame=0, peak_window=16).tolist() == expected


# --- the legacy zero level (F3) ------------------------------------------------------


def test_the_legacy_zero_level_can_drop_a_genuine_beat():
    trace, peaks = beat_train(heights=(100.0, 100.0, 50.0, 100.0))

    # Corrected, the zero level is the lowest point of the trace and all four are found.
    assert find_peaks(trace, reference_frame=0, legacy=False).tolist() == peaks

    # The original indexes the trace with the frame number instead. Landing partway up
    # a flank raises the level every beat is judged against, and the small one is lost.
    on_a_flank = peaks[0] - 1
    found = find_peaks(trace, reference_frame=on_a_flank, legacy=True)
    assert found.tolist() == [peaks[0], peaks[1], peaks[3]]


def test_the_two_modes_agree_when_the_reference_lands_on_rest():
    trace, peaks = beat_train()
    assert find_peaks(trace, reference_frame=0, legacy=True).tolist() == peaks
    assert find_peaks(trace, reference_frame=0, legacy=False).tolist() == peaks


# --- reporting and rejection ---------------------------------------------------------


def test_an_odd_window_is_raised_to_the_next_even_one(caplog):
    trace, peaks = beat_train()
    with caplog.at_level(logging.WARNING):
        found = find_peaks(trace, reference_frame=0, peak_window=19)
    assert found.tolist() == find_peaks(trace, reference_frame=0, peak_window=20).tolist()
    assert "raised from 19 to 20" in caplog.text


def test_peaks_are_reported(caplog):
    trace, _ = beat_train()
    with caplog.at_level(logging.INFO):
        find_peaks(trace, reference_frame=0)
    assert "Detected 4 peak(s)" in caplog.text


def test_a_reference_frame_outside_the_trace_is_rejected():
    trace, _ = beat_train()
    with pytest.raises(ValueError, match="outside a trace"):
        find_peaks(trace, reference_frame=len(trace))


def test_a_window_below_two_is_rejected():
    trace, _ = beat_train()
    with pytest.raises(ValueError, match="at least 2"):
        find_peaks(trace, reference_frame=0, peak_window=1)


# --- baselines -----------------------------------------------------------------------


def test_high_frequency_baseline_takes_the_lowest_point_before_the_beat():
    trace, peaks = beat_train()
    trace[peaks[1] - 3] = 4.0  # below the resting level, and inside the search range
    baselines = find_baselines(trace, peaks, high_freq_baseline=True)
    assert baselines.tolist() == [10.0, 4.0, 10.0, 10.0]


def test_a_dip_more_than_halfway_back_belongs_to_no_beat_at_all():
    # Each beat looks back only as far as halfway to the previous one, and no beat
    # looks forward, so the resting points in between are never examined.
    trace, peaks = beat_train()
    halfway = peaks[1] - (peaks[1] - peaks[0]) // 2

    ignored = trace.copy()
    ignored[halfway - 2] = 4.0
    assert find_baselines(ignored, peaks, high_freq_baseline=True).tolist() == [10.0] * 4

    seen = trace.copy()
    seen[halfway + 2] = 4.0
    assert find_baselines(seen, peaks, high_freq_baseline=True).tolist() == [
        10.0,
        4.0,
        10.0,
        10.0,
    ]


def test_flat_baseline_averages_the_quiet_points_before_the_beat():
    trace, peaks = beat_train()
    baselines = find_baselines(trace, peaks, high_freq_baseline=False)
    assert baselines.tolist() == pytest.approx([10.0] * 4)


def test_both_baseline_modes_agree_on_a_flat_rest():
    trace, _ = synthetic_trace()
    peaks = find_peaks(trace, reference_frame=0, peak_window=16)
    lowest = find_baselines(trace, peaks, high_freq_baseline=True)
    flattest = find_baselines(trace, peaks, high_freq_baseline=False)
    assert flattest == pytest.approx(lowest, rel=0.1)


def test_no_peaks_gives_no_baselines():
    trace, _ = beat_train()
    assert find_baselines(trace, []).tolist() == []


def test_baselines_are_reported(caplog):
    trace, peaks = beat_train()
    with caplog.at_level(logging.INFO):
        find_baselines(trace, peaks)
    assert "Baselines for 4 beat(s)" in caplog.text


# --- a lone peak loses its baseline (F4) ---------------------------------------------


def test_a_lone_peak_gets_a_zero_baseline_in_legacy_mode():
    trace, _ = synthetic_trace()
    trace = trace[:40]
    peak = find_peaks(trace, reference_frame=0, peak_window=16)
    assert len(peak) == 1

    # The appended phantom peak reverses the range the steepest rise is measured over,
    # leaving it at zero, so no point can count as flat and the average is empty.
    assert find_baselines(trace, peak, high_freq_baseline=False, legacy=True).tolist() == [0.0]

    # Corrected, the lone beat is simply the first beat, and its baseline is a genuine
    # resting value rather than zero.
    rest = trace[: peak[0] - 5]
    corrected = find_baselines(trace, peak, high_freq_baseline=False, legacy=False)
    assert rest.min() <= corrected[0] <= rest.max()


def test_a_lone_peak_is_unaffected_in_the_high_frequency_mode():
    trace, _ = synthetic_trace()
    trace = trace[:40]
    peak = find_peaks(trace, reference_frame=0, peak_window=16)
    for legacy in (True, False):
        baseline = find_baselines(trace, peak, high_freq_baseline=True, legacy=legacy)
        assert baseline[0] == pytest.approx(trace[: peak[0]].min())


# --- a baseline shortage narrows every later beat (F13) ------------------------------


def drifting_rest_train():
    """Two beats. The second rests on a gentle staircase, so how many points are
    averaged changes the answer. Returns a trace whose first beat has no flat points
    at all, and an otherwise identical one whose first beat rests quietly."""
    trace, peaks = beat_train(heights=(100.0, 100.0), period=40)
    first, second = peaks

    for step, j in enumerate(range(second - 15, second - 5)):
        trace[j] = 10.0 + 0.1 * step
    calm = trace.copy()

    # Everything before the first beat now alternates by more than the flatness
    # threshold, so that beat offers nothing to average.
    for j in range(first):
        trace[j] = 10.0 + 5.0 * (j % 2)
    return trace, calm, peaks


def test_a_baseline_shortage_narrows_every_later_beat():
    noisy, calm, peaks = drifting_rest_train()
    narrowed = find_baselines(noisy, peaks, high_freq_baseline=False, legacy=True)
    intact = find_baselines(calm, peaks, high_freq_baseline=False, legacy=True)

    # No flat points before the first beat, so its own baseline collapses to zero.
    assert narrowed[0] == 0.0
    assert intact[0] != 0.0

    # The second beat is identical in both traces, yet its baseline differs: the
    # shortage assigned to the parameter itself, so fewer points are averaged from
    # here on, and those reach less far back down the staircase.
    assert narrowed[1] != pytest.approx(intact[1])
    assert narrowed[1] > intact[1]


def test_the_shortage_is_confined_to_its_own_beat_when_corrected():
    noisy, calm, peaks = drifting_rest_train()
    narrowed = find_baselines(noisy, peaks, high_freq_baseline=False, legacy=False)
    intact = find_baselines(calm, peaks, high_freq_baseline=False, legacy=False)
    assert narrowed[1] == pytest.approx(intact[1])


def test_the_shortage_warning_names_the_beat_that_caused_it(caplog):
    noisy, _, peaks = drifting_rest_train()
    with caplog.at_level(logging.WARNING):
        find_baselines(noisy, peaks, high_freq_baseline=False, legacy=True)
    assert "before peak 0" in caplog.text


# --- measuring each beat -------------------------------------------------------------


def test_a_beat_train_is_measured_as_it_was_built():
    # framerate=100 gives a 10 ms interval, so every figure below is frames x 10.
    trace, peaks = beat_train()
    table = measure_transients(trace, peaks, [10.0] * 4)

    first = table.loc[1]
    assert first["peak_position"] == 12
    assert first["baseline"] == 10.0
    assert first["peak_amplitude"] == 100.0
    assert first["contraction_amplitude"] == 90.0
    assert first["time_to_peak_ms"] == 60.0
    assert first["relaxation_time_ms"] == 80.0
    assert first["contraction_duration_ms"] == 140.0
    assert first["transient_10pct_ms"] == 140.0
    assert first["transient_50pct_ms"] == 90.0
    assert first["transient_90pct_ms"] == 20.0


def test_the_table_has_one_row_per_beat_numbered_from_one():
    trace, peaks = beat_train()
    table = measure_transients(trace, peaks, [10.0] * 4)
    assert table.index.tolist() == [1, 2, 3, 4]
    assert table.index.name == "beat"


def test_durations_shrink_as_the_level_rises():
    trace, peaks = beat_train()
    table = measure_transients(trace, peaks, [10.0] * 4, percentages=(10, 50, 90))
    at = [table.loc[1, f"transient_{p}pct_ms"] for p in (10, 50, 90)]
    assert at[0] > at[1] > at[2]


def test_peak_to_peak_time_matches_the_beat_period():
    trace, recording = synthetic_trace()
    peaks = find_peaks(trace, reference_frame=0, peak_window=16)
    table = measure_transients(
        trace, peaks, find_baselines(trace, peaks), framerate=recording.framerate
    )
    expected = recording.frames_per_beat * 1000.0 / recording.framerate
    assert table["peak_to_peak_ms"].dropna().tolist() == pytest.approx([expected] * 3)


def test_the_first_beat_has_no_peak_to_peak_time():
    trace, peaks = beat_train()
    table = measure_transients(trace, peaks, [10.0] * 4)
    assert np.isnan(table.loc[1, "peak_to_peak_ms"])
    assert not np.isnan(table.loc[2, "peak_to_peak_ms"])


def test_times_scale_with_the_framerate():
    trace, peaks = beat_train()
    slow = measure_transients(trace, peaks, [10.0] * 4, framerate=100.0)
    fast = measure_transients(trace, peaks, [10.0] * 4, framerate=200.0)
    assert fast["contraction_duration_ms"].tolist() == pytest.approx(
        (slow["contraction_duration_ms"] / 2).tolist()
    )
    assert fast["contraction_amplitude"].tolist() == slow["contraction_amplitude"].tolist()


def test_amplitude_is_measured_above_the_baseline_it_is_given():
    trace, peaks = beat_train()
    table = measure_transients(trace, peaks, [40.0] * 4)
    assert table["contraction_amplitude"].tolist() == [60.0] * 4
    assert table["peak_amplitude"].tolist() == [100.0] * 4


# --- one percentage defines three other measures (F9) --------------------------------


def test_the_first_percentage_defines_the_headline_measures():
    trace, peaks = beat_train()
    at_10 = measure_transients(trace, peaks, [10.0] * 4, percentages=(10, 50))
    at_50 = measure_transients(trace, peaks, [10.0] * 4, percentages=(50, 90))

    # Contraction duration is always the transient at the *first* level ...
    assert at_10.loc[1, "contraction_duration_ms"] == at_10.loc[1, "transient_10pct_ms"]
    assert at_50.loc[1, "contraction_duration_ms"] == at_50.loc[1, "transient_50pct_ms"]

    # ... so dropping the lowest level silently redefines three headline measures.
    assert at_50.loc[1, "contraction_duration_ms"] != at_10.loc[1, "contraction_duration_ms"]
    assert at_50.loc[1, "time_to_peak_ms"] != at_10.loc[1, "time_to_peak_ms"]
    assert at_50.loc[1, "relaxation_time_ms"] != at_10.loc[1, "relaxation_time_ms"]


def test_the_flank_level_can_be_moved_off_the_first_percentage():
    trace, peaks = beat_train()
    first = measure_transients(trace, peaks, [10.0] * 4, percentages=(10, 50))
    second = measure_transients(trace, peaks, [10.0] * 4, percentages=(10, 50), flank_level_index=1)

    assert second.loc[1, "contraction_duration_ms"] == second.loc[1, "transient_50pct_ms"]
    assert second.loc[1, "time_to_peak_ms"] < first.loc[1, "time_to_peak_ms"]

    # Only the headline measures move; the per-level durations are unchanged.
    for level in (10, 50):
        column = f"transient_{level}pct_ms"
        assert second[column].tolist() == first[column].tolist()


def test_a_flank_level_outside_the_percentages_is_rejected():
    trace, peaks = beat_train()
    with pytest.raises(ValueError, match="flank_level_index"):
        measure_transients(trace, peaks, [10.0] * 4, percentages=(10, 50), flank_level_index=2)


def test_levels_that_do_not_ascend_are_rejected():
    trace, peaks = beat_train()
    with pytest.raises(ValueError, match="ascending"):
        measure_transients(trace, peaks, [10.0] * 4, percentages=(90, 10))
    with pytest.raises(ValueError, match="ascending"):
        measure_transients(trace, peaks, [10.0] * 4, percentages=(10, 10))


# --- the three-point noise guard -----------------------------------------------------


def test_a_single_point_below_the_level_is_not_a_crossing():
    trace, peaks = beat_train()
    plain = measure_transients(trace, peaks, [10.0] * 4)

    dipped = trace.copy()
    dipped[peaks[0] - 2] = 5.0  # one sample far below the 10% level, mid-flank
    table = measure_transients(dipped, peaks, [10.0] * 4)
    assert table.loc[1, "time_to_peak_ms"] == plain.loc[1, "time_to_peak_ms"]


def test_three_points_below_the_level_are_a_crossing():
    trace, peaks = beat_train()
    plain = measure_transients(trace, peaks, [10.0] * 4)

    dipped = trace.copy()
    dipped[peaks[0] - 3 : peaks[0]] = 5.0
    table = measure_transients(dipped, peaks, [10.0] * 4)
    assert table.loc[1, "time_to_peak_ms"] < plain.loc[1, "time_to_peak_ms"]


# --- beats the search range cannot reach ---------------------------------------------


def test_a_beat_too_near_the_end_loses_its_falling_measures(caplog):
    # The search stops three points short of the end so the noise guard can look
    # ahead, so the last beat of this recording has no crossing on the way down.
    trace, _ = synthetic_trace()
    peaks = find_peaks(trace, reference_frame=0, peak_window=16)
    with caplog.at_level(logging.WARNING):
        table = measure_transients(trace, peaks, find_baselines(trace, peaks))

    last = table.loc[4]
    assert np.isnan(last["relaxation_time_ms"])
    assert np.isnan(last["contraction_duration_ms"])
    assert all(np.isnan(last[f"transient_{p}pct_ms"]) for p in (10, 50, 90))

    # What does not depend on that flank is still reported.
    assert not np.isnan(last["time_to_peak_ms"])
    assert last["contraction_amplitude"] > 0
    assert "falling flank of beat 4" in caplog.text


# --- rejection and edge cases --------------------------------------------------------


def test_no_peaks_gives_an_empty_table_with_the_right_columns():
    trace, _ = beat_train()
    table = measure_transients(trace, [], [])
    assert len(table) == 0
    assert "contraction_amplitude" in table.columns
    assert "transient_90pct_ms" in table.columns


def test_peaks_and_baselines_must_match():
    trace, peaks = beat_train()
    with pytest.raises(ValueError, match="they must match"):
        measure_transients(trace, peaks, [10.0, 10.0])


def test_a_lone_beat_is_measured_against_everything_before_it():
    trace, peaks = beat_train()
    lone = measure_transients(trace, peaks[:1], [10.0])
    assert lone.loc[1, "contraction_duration_ms"] == pytest.approx(
        measure_transients(trace, peaks, [10.0] * 4).loc[1, "contraction_duration_ms"]
    )
    assert np.isnan(lone.loc[1, "peak_to_peak_ms"])
