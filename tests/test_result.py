import dataclasses
import logging
from pathlib import Path

import numpy as np
import pytest

from boamotion import (
    Params,
    Result,
    build_motion_pixel_mask,
    find_baselines,
    find_peaks,
    measure_contraction,
    measure_speed,
    measure_transients,
    synthetic_recording,
)
from boamotion.result import original_headers


def analysed(**overrides) -> Result:
    """A complete run over the synthetic recording, ready to be written out."""
    recording = synthetic_recording(noise=0.01, seed=0)
    params = Params(framerate=recording.framerate, peak_window=16, **overrides)
    mask = build_motion_pixel_mask(recording.frames, 1, legacy=params.legacy)
    contraction = measure_contraction(recording.frames, 1, mask=mask, legacy=params.legacy)
    speed = measure_speed(recording.frames, 1, mask=mask, legacy=params.legacy)
    peaks = find_peaks(
        contraction,
        reference_frame=0,
        peak_window=params.peak_window,
        peak_threshold=params.peak_threshold,
        legacy=params.legacy,
    )
    baselines = find_baselines(contraction, peaks, legacy=params.legacy)
    beats = measure_transients(
        contraction, peaks, baselines, framerate=params.framerate, percentages=params.percentages
    )
    return Result(
        name="A001",
        params=params,
        reference_frame=1,
        contraction=contraction,
        speed=speed,
        beats=beats,
        mask=mask,
    )


def written(tmp_path, **overrides):
    result = analysed(**overrides)
    return result, result.save(tmp_path)


# --- what the object holds -----------------------------------------------------------


def test_the_time_axis_adds_one_interval_per_point():
    result = analysed()
    step = result.params.sampling_interval_ms
    assert result.time_ms[0] == 0.0
    assert np.allclose(np.diff(result.time_ms), step)
    assert len(result.time_ms) == len(result.contraction)


def test_the_speed_axis_also_starts_at_zero_but_is_shorter():
    result = analysed()
    assert result.speed_time_ms[0] == 0.0
    assert len(result.speed_time_ms) == len(result.speed) < len(result.time_ms)


def test_calculated_speed_matches_the_measured_trace_in_length():
    result = analysed()
    assert len(result.calculated_speed) == len(result.speed)
    assert (result.calculated_speed >= 0).all()


def test_the_repr_says_what_the_run_was():
    text = repr(analysed())
    assert "A001" in text and "4 beats" in text and "masked" in text


def test_a_result_cannot_be_edited_after_the_fact():
    result = analysed()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.reference_frame = 7


# --- the original's column names -----------------------------------------------------


def test_percentage_columns_use_the_cd90_convention():
    headers = original_headers(Params(percentages=(10, 50, 90)))
    assert headers["transient_10pct_ms"] == "90-to-90 transient (ms)"
    assert headers["transient_90pct_ms"] == "10-to-10 transient (ms)"


def test_the_duration_header_is_hard_coded_to_ten_percent_in_legacy_mode():
    legacy = original_headers(Params(percentages=(20, 50), legacy=True))
    assert legacy["contraction_duration_ms"] == "Contraction duration [10% above baseline] (ms)"

    corrected = original_headers(Params(percentages=(20, 50), legacy=False))
    assert corrected["contraction_duration_ms"] == "Contraction duration [20% above baseline] (ms)"


def test_the_headers_are_in_the_order_the_macro_writes_them():
    order = list(original_headers(Params(percentages=(10, 50))))
    assert order == [
        "contraction_duration_ms",
        "time_to_peak_ms",
        "relaxation_time_ms",
        "transient_10pct_ms",
        "transient_50pct_ms",
        "peak_to_peak_ms",
        "baseline",
        "peak_amplitude",
        "contraction_amplitude",
    ]


# --- the files ------------------------------------------------------------------------


def test_every_expected_file_is_written(tmp_path):
    _, target = written(tmp_path)
    assert target.name == "A001-Contr-Results"
    assert sorted(p.name for p in target.iterdir()) == [
        "Comparison calculated (red) and measured (black) speed.jpg",
        "Contraction.jpg",
        "Log_file.txt",
        "Overview-results.txt",
        "Speed of contraction.jpg",
        "beats.csv",
        "contraction.txt",
        "parameters.yaml",
        "run-summary.txt",
        "speed-of-contraction.txt",
    ]


def test_corrected_names_are_lower_case_throughout(tmp_path):
    _, target = written(tmp_path, legacy=False)
    assert target.name == "A001-results"
    assert sorted(p.name for p in target.iterdir()) == [
        "beats.csv",
        "contraction.png",
        "contraction.txt",
        "log.txt",
        "overview-results.txt",
        "parameters.yaml",
        "run-summary.txt",
        "speed-comparison.png",
        "speed-of-contraction.png",
        "speed-of-contraction.txt",
    ]


def test_no_output_name_contains_a_space_or_bracket(tmp_path):
    _, target = written(tmp_path, legacy=False)
    for path in [target, *target.iterdir()]:
        assert not set(path.name) & set(" ()")


def test_the_trace_file_is_time_and_value_without_a_header(tmp_path):
    result, target = written(tmp_path)
    lines = (target / "contraction.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(result.contraction)

    first = lines[0].split("\t")
    assert len(first) == 2
    assert float(first[0]) == 0.0
    assert float(first[1]) == pytest.approx(result.contraction[0])

    second = lines[1].split("\t")
    assert float(second[0]) == pytest.approx(result.params.sampling_interval_ms)


def test_the_speed_file_is_shorter_than_the_contraction_file(tmp_path):
    _, target = written(tmp_path)
    contraction = (target / "contraction.txt").read_text(encoding="utf-8").splitlines()
    speed = (target / "speed-of-contraction.txt").read_text(encoding="utf-8").splitlines()
    assert len(speed) < len(contraction)


def test_the_overview_uses_the_original_headers_and_numbers_rows_from_one(tmp_path):
    result, target = written(tmp_path)
    lines = (target / "Overview-results.txt").read_text(encoding="utf-8").splitlines()

    header = lines[0].split("\t")
    assert header[0] == " "
    assert header[1] == "Contraction duration [10% above baseline] (ms)"
    assert "90-to-90 transient (ms)" in header
    assert len(lines) == result.n_beats + 1
    assert lines[1].split("\t")[0] == "1"


def test_our_own_columns_stay_out_of_the_original_file(tmp_path):
    _, target = written(tmp_path)
    header = (target / "Overview-results.txt").read_text(encoding="utf-8").splitlines()[0]
    assert "peak_position" not in header
    assert "peak_time_ms" not in header


def test_the_tidy_csv_keeps_our_own_names(tmp_path):
    _, target = written(tmp_path)
    header = (target / "beats.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "contraction_amplitude" in header
    assert "peak_position" in header


def test_the_parameters_can_be_loaded_back(tmp_path):
    result, target = written(tmp_path)
    assert Params.from_yaml(target / "parameters.yaml") == result.params


# --- a missing measurement is written as zero in legacy mode --------------------------


def test_missing_measurements_are_written_as_zero_in_legacy_mode(tmp_path):
    result, target = written(tmp_path, legacy=True)
    assert result.beats["relaxation_time_ms"].isna().any()  # the last beat, near the end

    rows = (target / "Overview-results.txt").read_text(encoding="utf-8").splitlines()[1:]
    last = rows[-1].split("\t")
    assert "" not in last
    assert float(last[3]) == 0.0  # relaxation time, reported as a real measurement


def test_missing_measurements_are_left_empty_when_corrected(tmp_path):
    _, target = written(tmp_path, legacy=False)
    rows = (target / "overview-results.txt").read_text(encoding="utf-8").splitlines()[1:]
    assert any(cell == "" for cell in rows[-1].split("\t"))


# --- never overwriting ----------------------------------------------------------------


def test_an_existing_folder_is_never_overwritten(tmp_path):
    result = analysed()
    first = result.save(tmp_path)
    second = result.save(tmp_path)
    third = result.save(tmp_path)

    assert first.name == "A001-Contr-Results"
    assert second.name == "A001-Contr-Results-1"
    assert third.name == "A001-Contr-Results-2"
    assert first.exists() and second.exists()


# --- the run summary ------------------------------------------------------------------


def test_the_summary_records_what_actually_happened(tmp_path):
    _, target = written(tmp_path)
    text = (target / "run-summary.txt").read_text(encoding="utf-8")
    assert "reference frame: 1" in text
    assert "beats detected: 4" in text
    assert "% of the frame" in text


def test_adjustments_are_recorded_when_the_analysis_had_to_change_something(tmp_path):
    result = analysed()
    adjusted = Result(
        name=result.name,
        params=result.params,
        reference_frame=result.reference_frame,
        contraction=result.contraction,
        speed=result.speed,
        beats=result.beats,
        mask=result.mask,
        warnings=("n_low_values reduced from 20 to 15",),
    )
    text = (adjusted.save(tmp_path) / "run-summary.txt").read_text(encoding="utf-8")
    assert "warnings from this run" in text
    assert "n_low_values reduced from 20 to 15" in text


def test_no_adjustments_means_no_such_section(tmp_path):
    _, target = written(tmp_path)
    assert "warnings from this run" not in (target / "run-summary.txt").read_text(encoding="utf-8")


def test_writing_is_reported(tmp_path, caplog):
    result = analysed()
    with caplog.at_level(logging.INFO):
        result.save(tmp_path)
    assert "Wrote 10 files" in caplog.text


# --- the three figures ----------------------------------------------------------------


def test_each_figure_is_drawn_with_the_expected_axes():
    result = analysed()
    for figure, ylabel in (
        (result.plot_contraction(), "Contraction (a.u.)"),
        (result.plot_speed(), "Speed of contraction (a.u.)"),
        (result.plot_speed_comparison(), "Normalized contraction speed (a.u.)"),
    ):
        ax = figure.axes[0]
        assert ax.get_xlabel() == "Time (ms)"
        assert ax.get_ylabel() == ylabel


def test_the_contraction_figure_marks_every_beat():
    result = analysed()
    ax = result.plot_contraction().axes[0]
    # one trace line, then a marker line per beat
    assert len(ax.lines) == 1 + result.n_beats
    assert len(ax.collections) == result.n_beats  # the baseline-to-peak bars


def test_the_comparison_figure_draws_both_curves():
    result = analysed()
    ax = result.plot_speed_comparison().axes[0]
    assert [line.get_label() for line in ax.lines] == ["measured", "calculated"]


def test_both_comparison_curves_are_scaled_to_the_same_range():
    _, measured, calculated = analysed(legacy=False).comparison_curves()
    for curve in (measured, calculated):
        assert curve.min() >= 0.0
        assert curve.max() == pytest.approx(1.0)


def test_the_comparison_curves_are_one_point_shorter_than_the_speed_trace():
    result = analysed()
    times, measured, calculated = result.comparison_curves()
    assert len(times) == len(measured) == len(calculated) == len(result.speed) - 1


def test_legacy_leaves_both_comparison_curves_at_zero(tmp_path):
    # The original's normalising loop stops one short, so the last point of each curve
    # keeps the zero it was allocated with, and the plot ends in a drop to the axis.
    _, legacy_measured, legacy_calculated = analysed(legacy=True).comparison_curves()
    assert legacy_measured[-1] == 0.0
    assert legacy_calculated[-1] == 0.0

    _, measured, calculated = analysed(legacy=False).comparison_curves()
    assert measured[-1] > 0.0 or calculated[-1] > 0.0


def test_the_figures_are_written_as_real_images(tmp_path):
    _, target = written(tmp_path, legacy=False)
    for name in ("contraction.png", "speed-of-contraction.png", "speed-comparison.png"):
        assert (target / name).stat().st_size > 1000


def test_the_library_never_reaches_for_pyplot():
    # Figures are built from matplotlib's Figure directly, so nothing in the analysis
    # path depends on a backend being available. That is what keeps it headless.
    import boamotion

    package = Path(boamotion.__file__).parent
    imports = ("import matplotlib.pyplot", "from matplotlib import pyplot")
    offenders = [
        path.name
        for path in package.glob("*.py")
        if any(line in path.read_text(encoding="utf-8") for line in imports)
    ]
    assert offenders == []
