import numpy as np
import pytest

from boamotion import detect_reference_frame, load_frames, pixel_mask, synthetic_recording


def frames_with_bright_pixels(spots, shape=(4, 4), value=1000.0):
    """One frame per entry in `spots`, each with the listed pixels lit up."""
    stack = np.zeros((len(spots), *shape), dtype=np.float32)
    for index, pixels in enumerate(spots):
        for row, column in pixels:
            stack[index, row, column] = value
    return stack


def masked_trace(recording, reference_frame, mask=None):
    reference = recording.frames[reference_frame - 1].astype(np.float32)
    changes = (np.abs(frame.astype(np.float32) - reference) for frame in recording.frames)
    return np.array(
        [change[mask].mean() if mask is not None else change.mean() for change in changes]
    )


def test_mask_covers_the_moving_blob_and_nothing_else():
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = pixel_mask(recording.frames, detect_reference_frame(recording.frames, legacy=False))
    width = mask.shape[1]
    # The static blob sits in the left quarter, the moving one around x = 52-58.
    assert mask[:, : width // 4].sum() == 0
    assert mask[:, width // 2 :].sum() == mask.sum() > 0


def test_mask_keeps_a_small_fraction_of_the_frame():
    recording = synthetic_recording(noise=0.01, seed=0)
    mask = pixel_mask(recording.frames, detect_reference_frame(recording.frames, legacy=False))
    assert 0.02 < mask.mean() < 0.25


def test_mask_lifts_the_signal_clear_of_the_noise_floor():
    # The point of the mask: background pixels never move but still average in noise.
    recording = synthetic_recording(noise=0.01, seed=0)
    reference = detect_reference_frame(recording.frames, legacy=False)
    mask = pixel_mask(recording.frames, reference)

    rest = np.array(recording.rest_frames) - 1
    peak = np.array(recording.peak_frames) - 1
    whole = masked_trace(recording, reference)
    kept = masked_trace(recording, reference, mask)

    assert whole[rest].mean() / whole[peak].mean() > 0.15
    assert kept[rest].mean() / kept[peak].mean() < 0.06


def test_threshold_is_the_mean_plus_one_standard_deviation():
    # Pins the rule, including ImageJ's n-1 convention for the standard deviation.
    recording = synthetic_recording(noise=0.01, seed=0)
    reference = recording.frames[0].astype(np.float32)
    peak_change = np.zeros(reference.shape, dtype=np.float32)
    for index in range(1, recording.n_frames):
        change = np.abs(recording.frames[index].astype(np.float32) - reference)
        peak_change = np.maximum(peak_change, change)

    threshold = peak_change.mean(dtype=np.float64) + peak_change.std(ddof=1, dtype=np.float64)
    assert np.array_equal(pixel_mask(recording.frames, 1), peak_change >= threshold)


def test_a_pixel_that_never_moves_is_dropped():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(0, 0)], [(0, 0)]])
    mask = pixel_mask(frames, reference_frame=1)
    assert mask[0, 0]
    assert mask.sum() == 1


def test_end_frame_limits_which_frames_are_accumulated():
    # Frame 3 is the only one lighting up the far corner.
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)], []])
    assert not pixel_mask(frames, 1, mask_end_frame=2, legacy=True)[3, 3]
    assert pixel_mask(frames, 1, mask_end_frame=2, legacy=False)[3, 3]


def test_legacy_stops_one_frame_early():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)], []])
    assert pixel_mask(frames, 1, mask_end_frame=2, legacy=True).sum() == 1
    assert pixel_mask(frames, 1, mask_end_frame=2, legacy=False).sum() == 2


def test_start_frame_skips_earlier_frames():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)], []])
    assert not pixel_mask(frames, 1, mask_start_frame=2)[0, 0]
    assert pixel_mask(frames, 1, mask_start_frame=2)[3, 3]


def test_positions_count_without_the_reference_frame():
    # With frame 2 as reference, position 1 is frame 1 and position 2 is frame 3.
    frames = frames_with_bright_pixels([[(0, 0)], [], [(3, 3)], []])
    mask = pixel_mask(frames, reference_frame=2, mask_start_frame=2, mask_end_frame=3)
    assert mask[3, 3]
    assert not mask[0, 0]


def test_reading_from_disk_gives_the_same_mask(tmp_path):
    recording = synthetic_recording(noise=0.01, seed=0)
    on_disk = load_frames(recording.write(tmp_path / "movie"))
    assert np.array_equal(pixel_mask(on_disk, 1), pixel_mask(recording.frames, 1))


def test_mask_is_reported(caplog):
    recording = synthetic_recording(noise=0.01, seed=0)
    with caplog.at_level("INFO", logger="boamotion.traces"):
        pixel_mask(recording.frames, 1)
    assert "Pixel mask keeps" in caplog.text
    assert "from 99 frames" in caplog.text


def test_reference_frame_outside_the_recording():
    frames = frames_with_bright_pixels([[], [(0, 0)]])
    with pytest.raises(ValueError, match="outside the recording"):
        pixel_mask(frames, reference_frame=9)


def test_start_frame_must_be_one_based():
    frames = frames_with_bright_pixels([[], [(0, 0)]])
    with pytest.raises(ValueError, match="1-based"):
        pixel_mask(frames, 1, mask_start_frame=0)


def test_no_frames_left_to_accumulate():
    frames = frames_with_bright_pixels([[], [(0, 0)], [(3, 3)]])
    with pytest.raises(ValueError, match="no frames left"):
        pixel_mask(frames, 1, mask_start_frame=3, mask_end_frame=2)
