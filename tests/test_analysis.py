import logging

import numpy as np
import pytest

from boamotion import Boa, Params, Result, synthetic_recording


def recording():
    return synthetic_recording(noise=0.01, seed=0)


def boa(**settings):
    rec = recording()
    settings.setdefault("framerate", rec.framerate)
    settings.setdefault("peak_window", 16)
    return Boa(rec.frames, **settings), rec


# --- the shortest thing that works ----------------------------------------------------


def test_a_run_produces_a_result_with_every_piece_filled_in():
    analyser, rec = boa()
    result = analyser.run()

    assert isinstance(result, Result)
    assert result.reference_frame in range(1, rec.n_frames + 1)
    assert len(result.contraction) == rec.n_frames - 1
    assert len(result.speed) == rec.n_frames - 3
    assert result.mask is not None
    assert result.n_beats == 4


def test_the_result_is_kept_on_the_object():
    analyser, _ = boa()
    assert analyser.result is None
    assert analyser.run() is analyser.result


def test_the_repr_says_whether_it_has_run():
    analyser, _ = boa()
    assert "not run yet" in repr(analyser)
    analyser.run()
    assert "4 beats" in repr(analyser)


def test_settings_can_be_given_as_a_params_object():
    rec = recording()
    params = Params(framerate=rec.framerate, peak_window=16)
    assert Boa(rec.frames, params=params).run().params is params


def test_settings_can_be_changed_between_runs():
    analyser, _ = boa()
    assert analyser.run().n_beats == 4

    # A wider window puts the last beat inside the detector's blind spot (F8).
    analyser.params.peak_window = 18
    assert analyser.run().n_beats == 3


def test_set_params_changes_several_settings_and_chains():
    analyser, rec = boa()
    assert analyser.set_params(peak_window=18, legacy=False).run().n_beats == 3
    assert analyser.params.peak_window == 18
    assert analyser.params.legacy is False
    assert analyser.params.framerate == rec.framerate  # the rest is untouched


def test_set_params_rejects_a_name_that_is_not_a_setting():
    analyser, _ = boa()
    with pytest.raises(ValueError, match="unknown setting"):
        analyser.set_params(frame_rate=25.0)
    assert not hasattr(analyser.params, "frame_rate")


def test_params_and_loose_settings_together_are_rejected():
    with pytest.raises(ValueError, match="not both"):
        Boa(recording().frames, params=Params(), framerate=25.0)


def test_an_invalid_setting_is_caught_before_any_work_is_done():
    analyser, _ = boa()
    analyser.params.framerate = -1.0
    with pytest.raises(ValueError, match="framerate"):
        analyser.run()


# --- naming ---------------------------------------------------------------------------


def test_a_directory_gives_its_name_to_the_run(tmp_path):
    folder = recording().write(tmp_path / "A001")
    assert Boa(folder).name == "A001"


def test_frames_in_memory_get_a_neutral_name():
    assert boa()[0].name == "recording"


def test_the_name_can_be_set_explicitly():
    assert boa(name="dish-3")[0].name == "dish-3"


# --- reading from disk matches reading from memory ------------------------------------


def test_a_run_from_disk_matches_a_run_from_memory(tmp_path):
    rec = recording()
    folder = rec.write(tmp_path / "A001")

    from_memory = Boa(rec.frames, framerate=rec.framerate, peak_window=16).run()
    from_disk = Boa(folder, framerate=rec.framerate, peak_window=16).run()

    assert from_disk.reference_frame == from_memory.reference_frame
    assert np.allclose(from_disk.contraction, from_memory.contraction)
    assert from_disk.beats.equals(from_memory.beats)


# --- the switches that turn stages off -------------------------------------------------


def test_noise_reduction_off_measures_the_whole_frame():
    result = boa(noise_reduction=False)[0].run()
    assert result.mask is None
    assert result.n_beats == 4


def test_transient_analysis_off_gives_an_empty_table_with_the_right_columns():
    result = boa(transient_analysis=False)[0].run()
    assert result.n_beats == 0
    assert "contraction_amplitude" in result.beats.columns
    assert len(result.contraction) > 0  # the traces are still measured


def test_a_reference_frame_given_directly_skips_detection(caplog):
    analyser, _ = boa(reference_frame=3)
    with caplog.at_level(logging.INFO):
        result = analyser.run()
    assert result.reference_frame == 3
    assert "Reference frame:" not in caplog.text


def test_legacy_and_corrected_runs_differ():
    legacy = boa(legacy=True)[0].run()
    corrected = boa(legacy=False)[0].run()
    assert legacy.reference_frame != corrected.reference_frame
    assert not np.allclose(legacy.contraction, corrected.contraction)


# --- what the run recorded about itself -----------------------------------------------


def test_the_log_covers_every_stage():
    result = boa()[0].run()
    joined = "\n".join(result.log)
    for stage in ("Analysing", "Reference frame", "Pixel mask", "Contraction trace", "Speed trace"):
        assert stage in joined


def test_warnings_are_kept_apart_from_the_rest_of_the_log():
    result = boa()[0].run()
    assert result.warnings
    assert all(any(w in line for line in result.log) for w in result.warnings)
    assert len(result.warnings) < len(result.log)


def test_a_setting_the_recording_forced_us_to_change_is_recorded():
    # The default search range of 300 frames cannot fit a 100-frame recording.
    result = boa()[0].run()
    assert any("ref_search_stop reduced" in message for message in result.warnings)


def test_the_package_logger_is_left_as_it_was_found():
    package = logging.getLogger("boamotion")
    before = package.level
    boa()[0].run()
    assert package.level == before
    assert not any(type(h).__name__ == "_LogRecorder" for h in package.handlers)


# --- the whole way through to files ----------------------------------------------------


def test_a_run_can_be_saved_and_reloaded(tmp_path):
    result = boa(legacy=False)[0].run()
    target = result.save(tmp_path)

    assert Params.from_yaml(target / "parameters.yaml") == result.params
    assert (target / "log.txt").read_text(encoding="utf-8").count("\n") == len(result.log)
    assert "ref_search_stop reduced" in (target / "run-summary.txt").read_text(encoding="utf-8")
