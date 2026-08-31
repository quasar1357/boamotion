import numpy as np
import pytest

from boamotion import load_frames, synthetic_recording


def naive_contraction(frames, reference):
    """The core measurement, written independently of the package, for cross-checking."""
    ref = frames[reference - 1].astype(np.float32)
    return np.array([np.abs(frame.astype(np.float32) - ref).mean() for frame in frames])


def test_default_recording_is_one_second_per_beat_at_25_fps():
    rec = synthetic_recording()
    assert rec.n_frames == 100
    assert rec.frames_per_beat == 25
    assert rec.beat_interval_ms == 1000.0
    assert len(rec.peak_frames) == 4


def test_shape_and_dtype():
    rec = synthetic_recording(shape=(32, 48), dtype=np.uint8)
    assert rec.frames.shape == (100, 32, 48)
    assert rec.frames.dtype == np.uint8


def test_peaks_and_rest_frames_do_not_overlap():
    rec = synthetic_recording()
    assert set(rec.peak_frames).isdisjoint(rec.rest_frames)
    assert rec.peak_frames == (16, 41, 66, 91)


def test_rest_frames_are_identical_without_noise():
    rec = synthetic_recording()
    first = rec.frames[rec.rest_frames[0] - 1]
    for frame in rec.rest_frames:
        assert np.array_equal(rec.frames[frame - 1], first)


def assert_each_beat_peaks_where_it_was_built(rec):
    """Distance from the resting frame is largest exactly where the ground truth says."""
    trace = naive_contraction(rec.frames, reference=rec.rest_frames[0])
    for beat, peak in enumerate(rec.peak_frames):
        beat_slice = trace[beat * rec.frames_per_beat : (beat + 1) * rec.frames_per_beat]
        assert np.argmax(beat_slice) + beat * rec.frames_per_beat + 1 == peak


def test_the_blob_is_furthest_from_rest_at_each_peak():
    # The whole analysis rests on this.
    assert_each_beat_peaks_where_it_was_built(synthetic_recording())


def test_trace_returns_to_zero_at_rest():
    rec = synthetic_recording()
    trace = naive_contraction(rec.frames, reference=rec.rest_frames[0])
    assert trace[np.array(rec.rest_frames) - 1].max() == 0.0
    assert trace[np.array(rec.peak_frames) - 1].min() > 0.0


def test_noise_is_reproducible_and_seed_dependent():
    a = synthetic_recording(noise=0.02, seed=1)
    b = synthetic_recording(noise=0.02, seed=1)
    c = synthetic_recording(noise=0.02, seed=2)
    assert np.array_equal(a.frames, b.frames)
    assert not np.array_equal(a.frames, c.frames)


def test_noise_does_not_move_the_peaks():
    assert_each_beat_peaks_where_it_was_built(synthetic_recording(noise=0.01, seed=3))


def test_nothing_clips():
    rec = synthetic_recording(noise=0.02, seed=4)
    assert rec.frames.max() < np.iinfo(np.uint16).max


def test_static_blob_stays_put_while_the_other_moves():
    rec = synthetic_recording()
    rest = rec.frames[rec.rest_frames[0] - 1].astype(np.float32)
    peak = rec.frames[rec.peak_frames[0] - 1].astype(np.float32)
    change = np.abs(peak - rest)
    width = change.shape[1]
    # Gaussian tails never reach exactly zero, so compare magnitudes rather than
    # asserting the static side is untouched.
    assert change[:, : width // 4].max() < 0.01 * change.max()


def test_writes_frames_that_the_loader_reads_back(tmp_path):
    rec = synthetic_recording(n_beats=2)
    directory = rec.write(tmp_path / "movie")
    frames = load_frames(directory)
    assert len(frames) == rec.n_frames
    assert np.array_equal(frames[0], rec.frames[0])
    assert np.array_equal(frames[-1], rec.frames[-1])


def test_beat_count_and_lengths_are_configurable():
    rec = synthetic_recording(n_beats=3, frames_at_rest=4, frames_rising=3, frames_falling=5)
    assert rec.frames_per_beat == 12
    assert rec.n_frames == 36
    assert rec.peak_frames == (7, 19, 31)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"n_beats": 0}, "n_beats"),
        ({"frames_rising": 0}, "at least one frame"),
    ],
)
def test_invalid_arguments_are_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        synthetic_recording(**kwargs)


def test_repr_is_informative():
    assert "4 beats" in repr(synthetic_recording())
