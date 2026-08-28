import numpy as np
import pytest

from compare_macro_utils import compare_results_files, load_macro_log

# Trimmed from the log FIJI wrote for the synthetic recording on 26 August 2026, keeping
# one line of every shape the parser has to handle.
VERSION_LINE = "Algorithm tool version number: 1.0\n"

SAMPLE_LOG = """Log started...
Date: 26-7-2026
Time: 16:37:5
***
Algorithm tool version number: 1.0
recordedFramerate: 25
speedWindow: 2
maxProject: 1
MPendRange: -1
***autodetectReferenceFrame parameters
*lowValueN: 20
*autoDetectStop: 300
***
manualReferenceFrame: 0\tNOTE:overruled if autodetectReferenceFrame is true
***automaticTransientDetection parameters
*PeakDetectionWindow: 16
*percentages:\x20
10, 50, 90
*guassianBlur10: No
***
100 and name: C:\\recordings\\frame_0001.tif
\x20
----------------- Evaluating file:frame_0001 -----------------
WARNING: Recorded framerate is low
WARNING: autoDetectStop set to 97 since it should be smaller than stack number (100)
Automatic detected reference frame: frame 54
lowUp false at peak: 4
Peaks detected at points (frames):
15, 40, 64, 89
Warning: it seems like your Contraction plot is clipping!
Elapsed time (ms): 1431
----------------- Evaluation finished -----------------
"""


@pytest.fixture
def log(tmp_path):
    path = tmp_path / "Log_file.txt"
    path.write_text(SAMPLE_LOG, encoding="utf-8")
    return load_macro_log(path)


def test_the_checkpoints_a_wrong_result_shows_up_in_first(log):
    assert log["reference_frame"] == 54
    assert log["peaks"] == (15, 40, 64, 89)


def test_the_run_identifies_itself(log):
    assert log["recording"] == "frame_0001"
    assert log["version"] == "1.0"
    assert log["elapsed_ms"] == 1431


def test_the_percentages_come_from_the_line_below_their_heading(log):
    assert log["percentages"] == (10, 50, 90)


def test_both_spellings_of_warning_are_collected(log):
    assert len(log["warnings"]) == 3
    assert "Recorded framerate is low" in log["warnings"][0]
    assert log["warnings"][-1].startswith("Warning:")


def test_settings_are_converted_to_numbers_where_they_are_numbers(log):
    assert log["settings"]["recordedFramerate"] == 25
    assert log["settings"]["MPendRange"] == -1
    assert log["settings"]["guassianBlur10"] == "No"


def test_a_setting_keeps_only_its_value_when_a_note_follows(log):
    assert log["settings"]["manualReferenceFrame"] == 0


def test_what_is_not_a_setting_stays_out(log):
    for name in ("Date", "Time", "WARNING", "Warning", "percentages"):
        assert name not in log["settings"]


def test_a_failed_falling_flank_is_reported_as_the_beat_it_belongs_to(log):
    assert log["unmeasured_flanks"] == {"rising": (), "falling": (4,)}


def written_log(tmp_path, body: str):
    """A log holding `body`, headed by the version line the parser insists on."""
    path = tmp_path / "Log_file.txt"
    path.write_text(VERSION_LINE + body, encoding="utf-8")
    return load_macro_log(path)


def test_a_failed_rising_flank_is_moved_to_the_same_convention(tmp_path):
    # The macro prints the loop counter here and the counter plus one for the other
    # flank, so both messages below mean the third beat.
    body = "lowDown false at peak: 2\nlowUp false at peak: 3\n"
    assert written_log(tmp_path, body)["unmeasured_flanks"] == {"rising": (3,), "falling": (3,)}


def test_a_manually_chosen_reference_frame_is_read_too(tmp_path):
    body = "Manual selected reference frame: frame 12\n"
    assert written_log(tmp_path, body)["reference_frame"] == 12


def test_a_log_of_ours_is_refused_rather_than_read_as_an_empty_one(tmp_path):
    path = tmp_path / "log.txt"
    path.write_text("INFO: Reference frame: 54 (searched frames 1-97)\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not look like a MUSCLEMOTION log"):
        load_macro_log(path)


def test_a_log_that_states_nothing_else_gives_empty_answers(tmp_path):
    log = written_log(tmp_path, "")
    assert log["reference_frame"] is None
    assert log["peaks"] == ()
    assert log["warnings"] == ()
    assert log["unmeasured_flanks"] == {"rising": (), "falling": ()}


def test_tables_of_different_shape_are_reported_as_incomparable():
    """A missing beat changes the row count, and no threshold can bridge that."""
    macro = np.zeros((4, 3))
    ours = np.zeros((3, 3))

    assert compare_results_files(macro, ours) == (None, None, None)


def test_tables_that_agree_to_float32_noise_still_count_as_agreeing():
    macro = np.array([[1000.0, 2000.0]])
    ours = macro + 1e-5

    worst, relative, verdict = compare_results_files(macro, ours)

    assert verdict == "OK"
    assert relative < 1e-6
    assert worst == pytest.approx(1e-5)


def test_a_real_disagreement_is_reported_as_a_difference():
    macro = np.array([[1000.0, 2000.0]])
    ours = np.array([[1000.0, 2500.0]])

    _, _, verdict = compare_results_files(macro, ours)

    assert verdict == "DIFF"
