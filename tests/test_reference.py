import numpy as np
import pytest

from boamotion import detect_reference_frame, load_frames, synthetic_recording
from boamotion.reference import _motion_trace, _select_legacy

# Motion values used by the hand-built recording below. Pair (0.3, 0.31) is the
# stable quiet point; pair (0.1, 0.2) is quieter still but changing fast.
MOTION = [9.0, 0.1, 0.2, 5.0, 0.3, 0.31, 5.0, 5.0]

# The same, but with frames that do not move at all, so their unity distance is 0/0.
STILL_MOTION = [9.0, 0.0, 0.0, 0.0, 0.0, 7.0, 6.0, 5.0]


def constant_frames(motion):
    """Uniform frames whose brightness steps by the given amounts.

    Every frame is a single constant value, so with speed_window=1 the motion trace
    is exactly `motion` and the selection can be reasoned about by hand.
    """
    values = np.concatenate([[0.0], np.cumsum(motion)])
    return values.astype(np.float32).reshape(-1, 1, 1)


def detect(frames, **kwargs):
    settings = {"speed_window": 1, "ref_search_start": 1, "ref_search_stop": 8}
    settings.update(kwargs)
    return detect_reference_frame(frames, **settings)


def test_corrected_picks_the_stable_quiet_point():
    # Pair index 3 is quiet and steady; the corrected method maps it to frame 5.
    assert detect(constant_frames(MOTION), n_low_values=3, n_unity_values=2, legacy=False) == 5


def test_legacy_picks_a_point_that_is_not_quiet_at_all():
    # The unfilled entry of the unity array wins, so selection falls back to the
    # n_low_values-th quietest point - here one with 20x the motion of the answer.
    assert detect(constant_frames(MOTION), n_low_values=3, n_unity_values=2, legacy=True) == 2


def test_legacy_lets_the_unfilled_entry_beat_a_motionless_pair():
    # A pair that does not move gives 0/0, which ImageJ leaves NaN and ranks last, so
    # the unfilled entry still wins and the answer is the n_low_values-th quietest.
    frames = constant_frames(STILL_MOTION)
    assert detect(frames, n_low_values=3, n_unity_values=2, legacy=True) == 3


def test_corrected_treats_a_motionless_pair_as_exactly_on_the_unity_line():
    frames = constant_frames(STILL_MOTION)
    assert detect(frames, n_low_values=3, n_unity_values=2, legacy=False) == 2


def test_corrected_result_does_not_depend_on_where_the_search_starts():
    frames = constant_frames(MOTION)
    from_first = detect(frames, ref_search_start=1, n_low_values=2, n_unity_values=2, legacy=False)
    from_third = detect(frames, ref_search_start=3, n_low_values=2, n_unity_values=2, legacy=False)
    assert from_first == from_third == 5


def test_legacy_result_moves_when_the_search_starts_elsewhere():
    # The original maps the chosen point back to a frame number without accounting
    # for ref_search_start, so the same physical frame is reported differently.
    frames = constant_frames(MOTION)
    assert detect(frames, ref_search_start=1, n_low_values=2, n_unity_values=2, legacy=True) == 4
    assert detect(frames, ref_search_start=3, n_low_values=2, n_unity_values=2, legacy=True) == 1


@pytest.mark.parametrize("n_low_values", [5, 10, 20, 30])
def test_legacy_selection_is_decided_by_the_radius_ranking_alone(n_low_values):
    # Demonstrates the inert stability test: the answer is always the
    # n_low_values-th quietest candidate, whatever the unity distances are.
    recording = synthetic_recording(noise=0.01, seed=0)
    window = _motion_trace(recording.frames, 2, 97)[1:97]
    quietest = np.argsort(np.hypot(window[:-1], window[1:]), kind="stable")
    assert _select_legacy(window, n_low_values, 10) == quietest[n_low_values - 1]


@pytest.mark.parametrize("n_unity_values", [2, 5, 10, 15])
def test_n_unity_values_has_no_effect_in_legacy_mode(n_unity_values):
    recording = synthetic_recording(noise=0.01, seed=0)
    frame = detect_reference_frame(recording.frames, n_unity_values=n_unity_values, legacy=True)
    assert frame == 6


@pytest.mark.parametrize("legacy", [True, False])
def test_both_modes_land_on_a_resting_frame(legacy):
    recording = synthetic_recording(noise=0.01, seed=0)
    frame = detect_reference_frame(recording.frames, legacy=legacy)
    assert frame in recording.rest_frames


def test_reading_from_disk_gives_the_same_answer(tmp_path):
    recording = synthetic_recording(noise=0.01, seed=0)
    on_disk = load_frames(recording.write(tmp_path / "movie"))
    assert detect_reference_frame(on_disk) == detect_reference_frame(recording.frames)


def test_search_range_is_fitted_to_a_short_recording(caplog):
    recording = synthetic_recording(noise=0.01, seed=0)
    with caplog.at_level("WARNING", logger="boamotion.reference"):
        detect_reference_frame(recording.frames, ref_search_stop=300)
    assert "ref_search_stop reduced from 300 to 97" in caplog.text


def test_selection_sizes_are_fitted_to_the_candidates(caplog):
    recording = synthetic_recording(noise=0.01, seed=0)
    with caplog.at_level("WARNING", logger="boamotion.reference"):
        detect_reference_frame(recording.frames, n_low_values=5, n_unity_values=10)
    assert "n_unity_values reduced from 10 to 4" in caplog.text


def test_the_chosen_frame_is_reported(caplog):
    recording = synthetic_recording(noise=0.01, seed=0)
    with caplog.at_level("INFO", logger="boamotion.reference"):
        frame = detect_reference_frame(recording.frames)
    assert f"Reference frame: {frame}" in caplog.text


def test_recording_too_short_to_search():
    frames = np.zeros((5, 2, 2), dtype=np.float32)
    with pytest.raises(ValueError, match="usable point"):
        detect_reference_frame(frames)


def test_recording_far_too_short():
    frames = np.zeros((3, 2, 2), dtype=np.float32)
    with pytest.raises(ValueError, match="nothing to search"):
        detect_reference_frame(frames)


def test_motion_trace_measures_across_the_speed_window():
    frames = constant_frames([1.0, 2.0, 3.0, 4.0])
    # Values are 0, 1, 3, 6, 10; two frames apart the differences are 3 and 5.
    assert _motion_trace(frames, 2, 3).tolist() == [3.0, 5.0, 7.0]
