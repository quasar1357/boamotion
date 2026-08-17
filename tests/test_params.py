import pytest
import yaml

from boamotion import Params

# Defaults of the original macro, read from the DEFAULT VALUES block of
# MUSCLEMOTION v1-1beta.ijm. Guards against accidental drift.
MACRO_DEFAULTS = {
    "framerate": 100.0,
    "speed_window": 2,
    "mask_start_frame": 1,
    "mask_end_frame": None,
    "ref_search_start": 1,
    "ref_search_stop": 300,
    "n_low_values": 20,
    "n_unity_values": 10,
    "peak_window": 20,
    "peak_threshold": 30.0,
    "baseline_threshold": 2.0,
    "baseline_n_points": 5,
    "high_freq_baseline": True,
    "percentages": (10, 50, 90),
}


@pytest.mark.parametrize(("name", "expected"), MACRO_DEFAULTS.items())
def test_defaults_match_the_original_macro(name, expected):
    assert getattr(Params(), name) == expected


def test_keywords_override_defaults():
    params = Params(framerate=25, peak_threshold=50, high_freq_baseline=False)
    assert params.framerate == 25
    assert params.peak_threshold == 50
    assert params.high_freq_baseline is False
    assert params.speed_window == 2


def test_sampling_interval():
    assert Params(framerate=25).sampling_interval_ms == 40.0
    assert Params(framerate=100).sampling_interval_ms == 10.0


def test_update_sets_several_at_once_and_validates():
    params = Params()
    assert params.update(framerate=25, percentages=[10, 90]) is params
    assert params.framerate == 25
    assert params.percentages == (10, 90)
    with pytest.raises(ValueError, match="ascending"):
        params.update(percentages=[90, 10])
    with pytest.raises(ValueError, match="unknown setting"):
        params.update(frame_rate=25)


def test_percentages_accept_any_sequence():
    assert Params(percentages=[10, 90]).percentages == (10, 90)


def test_yaml_round_trip(tmp_path):
    original = Params(framerate=25, percentages=[10, 50, 90], reference_frame=57, legacy=False)
    path = original.to_yaml(tmp_path / "params.yaml")
    assert Params.from_yaml(path) == original


def test_yaml_is_readable_and_ordered(tmp_path):
    path = Params(framerate=25).to_yaml(tmp_path / "params.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["framerate"] == 25
    assert data["percentages"] == [10, 50, 90]
    assert list(data)[0] == "framerate"


def test_empty_yaml_gives_defaults(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert Params.from_yaml(path) == Params()


def test_unknown_yaml_key_is_rejected(tmp_path):
    path = tmp_path / "typo.yaml"
    path.write_text("frame_rate: 25\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown parameter"):
        Params.from_yaml(path)


def test_non_mapping_yaml_is_rejected(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- 1\n- 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        Params.from_yaml(path)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"framerate": 0}, "framerate"),
        ({"speed_window": 0}, "speed_window"),
        ({"reference_frame": 0}, "1-based"),
        ({"ref_search_start": 0}, "ref_search_start"),
        ({"ref_search_stop": 1}, "ref_search_stop"),
        ({"n_low_values": 1}, "n_low_values"),
        ({"n_unity_values": 20}, "n_unity_values"),
        ({"mask_start_frame": 0}, "mask_start_frame"),
        ({"mask_end_frame": 1}, "mask_end_frame"),
        ({"peak_window": 1}, "peak_window"),
        ({"peak_threshold": 101}, "peak_threshold"),
        ({"percentages": []}, "at least one level"),
        ({"percentages": [0, 50]}, "1-99"),
        ({"percentages": [90, 10]}, "ascending"),
        ({"percentages": [10, 10]}, "ascending"),
        ({"flank_level_index": 3}, "flank_level_index"),
        ({"flank_level_index": -1}, "flank_level_index"),
        ({"baseline_threshold": -1}, "baseline_threshold"),
        ({"baseline_n_points": 0}, "baseline_n_points"),
    ],
)
def test_invalid_parameters_are_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Params(**kwargs)


def test_validate_catches_changes_made_after_construction():
    params = Params()
    params.framerate = -1
    with pytest.raises(ValueError, match="framerate"):
        params.validate()


def test_reference_frame_defaults_to_automatic():
    assert Params().reference_frame is None
