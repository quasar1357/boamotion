import numpy as np
import pytest

from boamotion import (
    build_motion_pixel_mask,
    detect_reference_frame,
    load_frames,
    measure_contraction,
    measure_speed,
    synthetic_recording,
)


def frames_with_bright_pixels(spots, shape=(4, 4), value=1000.0):
    """One frame per entry in `spots`, each with the listed pixels lit up."""
    stack = np.zeros((len(spots), *shape), dtype=np.float32)
    for index, pixels in enumerate(spots):
        for row, column in pixels:
            stack[index, row, column] = value
    return stack


def test_mask_covers_the_moving_blob_and_nothing_else():
    recording = synthetic_recording(noise=0.01, seed=0)
    reference = detect_reference_frame(recording.frames, legacy=False)
    mask = build_motion_pixel_mask(recording.frames, reference)
    width = mask.shape[1]
    # The static blob sits in the left quarter, the moving one around x = 52-58.
    assert mask[:, : width // 4].sum() == 0
    assert mask[:, width // 2 :].sum() == mask.sum() > 0


def test_mask_keeps_a_small_fraction_of_the_frame():
    recording = synthetic_recording(noise=0.01, seed=0)
    reference = detect_reference_frame(recording.frames, legacy=False)
    mask = build_motion_pixel_mask(recording.frames, reference)
    assert 0.02 < mask.mean() < 0.25


def test_threshold_is_the_mean_plus_one_standard_deviation():
    # Pins the rule, including ImageJ's n-1 convention for the standard deviation.
    recording = synthetic_recording(noise=0.01, seed=0)
    reference = recording.frames[0].astype(np.float32)
    peak_change = np.zeros(reference.shape, dtype=np.float32)
    for index in range(1, recording.n_frames):
        change = np.abs(recording.frames[index].astype(np.float32) - reference)
        peak_change = np.maximum(peak_change, change)

    threshold = peak_change.mean(dtype=np.float64) + peak_change.std(ddof=1, dtype=np.float64)
    assert np.array_equal(build_motion_pixel_mask(recording.frames, 1), peak_change >= threshold)


def test_a_pixel_that_never_moves_is_dropped():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(0, 0)], [(0, 0)]])
    mask = build_motion_pixel_mask(frames, reference_frame=1)
    assert mask[0, 0]
    assert mask.sum() == 1


def test_end_frame_limits_which_frames_are_accumulated():
    # Frame 3 is the only one lighting up the far corner.
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)], []])
    assert not build_motion_pixel_mask(frames, 1, mask_end_frame=2, legacy=True)[3, 3]
    assert build_motion_pixel_mask(frames, 1, mask_end_frame=2, legacy=False)[3, 3]


def test_legacy_stops_one_frame_early():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)], []])
    assert build_motion_pixel_mask(frames, 1, mask_end_frame=2, legacy=True).sum() == 1
    assert build_motion_pixel_mask(frames, 1, mask_end_frame=2, legacy=False).sum() == 2


def test_start_frame_skips_earlier_frames():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)], []])
    assert not build_motion_pixel_mask(frames, 1, mask_start_frame=2)[0, 0]
    assert build_motion_pixel_mask(frames, 1, mask_start_frame=2)[3, 3]


def test_positions_count_without_the_reference_frame():
    # With frame 2 as reference, position 1 is frame 1 and position 2 is frame 3.
    frames = frames_with_bright_pixels([[(0, 0)], [], [(3, 3)], []])
    mask = build_motion_pixel_mask(frames, reference_frame=2, mask_start_frame=2, mask_end_frame=3)
    assert mask[3, 3]
    assert not mask[0, 0]


def test_reading_from_disk_gives_the_same_mask(tmp_path):
    recording = synthetic_recording(noise=0.01, seed=0)
    on_disk = load_frames(recording.write(tmp_path / "movie"))
    from_memory = build_motion_pixel_mask(recording.frames, 1)
    assert np.array_equal(build_motion_pixel_mask(on_disk, 1), from_memory)


def test_mask_is_reported(caplog):
    recording = synthetic_recording(noise=0.01, seed=0)
    with caplog.at_level("INFO", logger="boamotion.traces"):
        build_motion_pixel_mask(recording.frames, 1)
    assert "Pixel mask keeps" in caplog.text
    assert "from 99 frames" in caplog.text


def test_reference_frame_outside_the_recording():
    frames = frames_with_bright_pixels([[], [(0, 0)]])
    with pytest.raises(ValueError, match="outside the recording"):
        build_motion_pixel_mask(frames, reference_frame=9)


def test_start_frame_must_be_one_based():
    frames = frames_with_bright_pixels([[], [(0, 0)]])
    with pytest.raises(ValueError, match="1-based"):
        build_motion_pixel_mask(frames, 1, mask_start_frame=0)


def test_no_frames_left_to_accumulate():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)]])
    with pytest.raises(ValueError, match="no frames left"):
        build_motion_pixel_mask(frames, 1, mask_start_frame=3, mask_end_frame=2)


def uniform_frames(values, shape=(2, 2)):
    """One frame per value, every pixel set to it, so traces are computable by hand."""
    stack = np.asarray(values, dtype=np.float32).reshape(-1, 1, 1)
    return stack * np.ones((1, *shape), dtype=np.float32)


def peak_indices(recording, reference_frame=1):
    """Where the known peaks land in a trace, which omits the reference frame."""
    positions = [i for i in range(recording.n_frames) if i != reference_frame - 1]
    return [positions.index(frame - 1) for frame in recording.peak_frames]


def test_contraction_is_computed_by_hand():
    frames = uniform_frames([0, 10, 20, 5])
    assert measure_contraction(frames, 1).tolist() == [10.0, 20.0, 5.0]


def test_speed_compares_each_frame_with_a_later_one():
    frames = uniform_frames([0, 10, 20, 5])
    assert measure_speed(frames, 1, speed_window=1).tolist() == [10.0, 15.0]


def test_the_reference_frame_is_left_out():
    # With frame 2 as reference, the trace measures frames 1, 3 and 4 against it.
    frames = uniform_frames([0, 10, 20, 5])
    assert measure_contraction(frames, 2).tolist() == [10.0, 10.0, 5.0]


def test_trace_lengths():
    recording = synthetic_recording(noise=0.01, seed=0)
    assert len(measure_contraction(recording.frames, 1)) == recording.n_frames - 1
    assert len(measure_speed(recording.frames, 1, speed_window=2)) == recording.n_frames - 3


def test_contraction_peaks_where_the_recording_was_built_to_peak():
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = build_motion_pixel_mask(recording.frames, 1)
    trace = measure_contraction(recording.frames, 1, mask=mask)
    for expected in peak_indices(recording):
        nearby = trace[expected - 5 : expected + 6]
        assert int(np.argmax(nearby)) == 5


def test_speed_dips_at_peak_contraction_and_rises_on_both_flanks():
    # An absolute difference is always positive, so one beat gives two speed humps:
    # one contracting, one relaxing, with a standstill between them.
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = build_motion_pixel_mask(recording.frames, 1)
    speed = measure_speed(recording.frames, 1, speed_window=2, mask=mask)
    for peak in peak_indices(recording):
        standstill = peak - 1  # speed_window=2 straddles the peak
        assert speed[standstill] < speed[standstill - 3]
        assert speed[standstill] < speed[standstill + 5]


def test_legacy_scales_the_trace_by_255():
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = build_motion_pixel_mask(recording.frames, 1)
    legacy = measure_contraction(recording.frames, 1, mask=mask, legacy=True)
    corrected = measure_contraction(recording.frames, 1, mask=mask, legacy=False)
    assert np.allclose(legacy, corrected * 255.0)


def test_legacy_changes_nothing_without_a_mask():
    recording = synthetic_recording(noise=0.01, seed=0)
    assert np.array_equal(
        measure_contraction(recording.frames, 1, legacy=True),
        measure_contraction(recording.frames, 1, legacy=False),
    )


def test_masking_lifts_the_trace_clear_of_the_noise_floor():
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = build_motion_pixel_mask(recording.frames, 1)
    rest = np.array(peak_indices(recording)) - 10
    peak = np.array(peak_indices(recording))

    whole = measure_contraction(recording.frames, 1)
    kept = measure_contraction(recording.frames, 1, mask=mask)
    assert whole[rest].mean() / whole[peak].mean() > 0.15
    assert kept[rest].mean() / kept[peak].mean() < 0.06


def test_a_wider_speed_window_measures_more_motion():
    # More happens between frames further apart, so the trace spans a wider range.
    # Only up to a point: past roughly a quarter of a beat it saturates and degrades.
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = build_motion_pixel_mask(recording.frames, 1)
    narrow = measure_speed(recording.frames, 1, speed_window=1, mask=mask)
    wide = measure_speed(recording.frames, 1, speed_window=4, mask=mask)
    assert np.ptp(wide) > 2 * np.ptp(narrow)


def test_traces_from_disk_match_those_from_memory(tmp_path):
    recording = synthetic_recording(noise=0.01, seed=0)
    on_disk = load_frames(recording.write(tmp_path / "movie"))
    assert np.allclose(measure_contraction(on_disk, 1), measure_contraction(recording.frames, 1))
    assert np.allclose(measure_speed(on_disk, 1), measure_speed(recording.frames, 1))


def test_traces_are_reported(caplog):
    recording = synthetic_recording(noise=0.01, seed=0)
    with caplog.at_level("INFO", logger="boamotion.traces"):
        measure_contraction(recording.frames, 1)
        measure_speed(recording.frames, 1)
    assert "Contraction trace: 99 points" in caplog.text
    assert "Speed trace: 97 points" in caplog.text


def test_mask_of_the_wrong_size_is_rejected():
    frames = uniform_frames([0, 10, 20])
    with pytest.raises(ValueError, match="mask is"):
        measure_contraction(frames, 1, mask=np.ones((5, 5), dtype=bool))


def test_speed_window_must_fit_the_recording():
    frames = uniform_frames([0, 10, 20])
    with pytest.raises(ValueError, match="nothing to measure"):
        measure_speed(frames, 1, speed_window=5)


def test_speed_window_must_be_positive():
    frames = uniform_frames([0, 10, 20])
    with pytest.raises(ValueError, match="at least 1 frame"):
        measure_speed(frames, 1, speed_window=0)
