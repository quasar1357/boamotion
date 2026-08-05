import numpy as np
import pytest
import tifffile

from boamotion import FrameSequence, load_frames


def write_frames(directory, names, shape=(4, 6), dtype=np.uint16):
    """Write one TIFF per name, each filled with its position in the list."""
    directory.mkdir(parents=True, exist_ok=True)
    for value, name in enumerate(names):
        tifffile.imwrite(directory / name, np.full(shape, value, dtype=dtype))
    return directory


def test_reads_every_frame(tmp_path):
    write_frames(tmp_path, [f"f{i:03d}.tif" for i in range(5)])
    frames = load_frames(tmp_path)
    assert len(frames) == 5
    assert frames.n_frames == 5
    assert frames.shape == (4, 6)
    assert frames.dtype == np.uint16


def test_unpadded_numbers_are_ordered_by_value(tmp_path):
    # Alphabetical order would give 1, 10, 11, 2, ... ImageJ sorts numerically.
    names = [f"frame{i}.tif" for i in [1, 2, 9, 10, 11, 100]]
    write_frames(tmp_path, names)
    frames = load_frames(tmp_path)
    assert [p.name for p in frames.paths] == names
    assert [int(frames[i][0, 0]) for i in range(len(frames))] == list(range(6))


def test_frame_contents_and_negative_indexing(tmp_path):
    write_frames(tmp_path, [f"f{i}.tif" for i in range(4)])
    frames = load_frames(tmp_path)
    assert np.all(frames[2] == 2)
    assert np.all(frames[-1] == 3)


def test_iteration_yields_frames_in_order(tmp_path):
    write_frames(tmp_path, [f"f{i}.tif" for i in range(4)])
    values = [int(frame[0, 0]) for frame in load_frames(tmp_path)]
    assert values == [0, 1, 2, 3]


def test_suffix_matching_is_case_insensitive_and_ignores_other_files(tmp_path):
    write_frames(tmp_path, ["a.tif", "b.TIF", "c.tiff"])
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")
    (tmp_path / "preview.png").write_bytes(b"not a tiff")
    assert len(load_frames(tmp_path)) == 3


def test_repr_is_informative(tmp_path):
    write_frames(tmp_path / "A001", ["a.tif", "b.tif"])
    text = repr(load_frames(tmp_path / "A001"))
    assert "A001" in text
    assert "2 frames" in text


def test_missing_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="no such directory"):
        load_frames(tmp_path / "absent")


def test_file_instead_of_directory_names_the_deferred_formats(tmp_path):
    stack = tmp_path / "stack.tif"
    tifffile.imwrite(stack, np.zeros((2, 4, 6), dtype=np.uint16))
    with pytest.raises(NotADirectoryError, match="TIFF stacks"):
        load_frames(stack)


def test_directory_without_tiffs(tmp_path):
    (tmp_path / "notes.txt").write_text("nothing here", encoding="utf-8")
    with pytest.raises(ValueError, match="no TIFF files"):
        load_frames(tmp_path)


def test_single_frame_is_not_a_recording(tmp_path):
    write_frames(tmp_path, ["only.tif"])
    with pytest.raises(ValueError, match="single frame"):
        load_frames(tmp_path)


def test_mismatched_frame_size_is_reported_with_the_file_name(tmp_path):
    write_frames(tmp_path, ["a.tif", "b.tif"])
    tifffile.imwrite(tmp_path / "c.tif", np.zeros((8, 8), dtype=np.uint16))
    frames = load_frames(tmp_path)
    with pytest.raises(ValueError, match="c.tif"):
        frames[2]


def test_colour_frames_are_rejected(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    for name in ("a.tif", "b.tif"):
        tifffile.imwrite(tmp_path / name, np.zeros((4, 6, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="grayscale"):
        load_frames(tmp_path)


def test_slicing_is_rejected_clearly(tmp_path):
    write_frames(tmp_path, ["a.tif", "b.tif"])
    with pytest.raises(TypeError, match="integer index"):
        load_frames(tmp_path)[0:2]


def test_frames_are_read_lazily(tmp_path):
    # An unreadable file later in the sequence must not break opening the recording,
    # which is only true if frames are read on demand rather than up front.
    write_frames(tmp_path, ["a.tif", "b.tif"])
    (tmp_path / "c.tif").write_bytes(b"not a real tiff")
    frames = load_frames(tmp_path)
    assert len(frames) == 3
    assert np.all(frames[0] == 0)


def test_class_and_function_are_equivalent(tmp_path):
    write_frames(tmp_path, ["a.tif", "b.tif"])
    assert load_frames(tmp_path).paths == FrameSequence(tmp_path).paths


def test_load_reports_the_recording(tmp_path, caplog):
    write_frames(tmp_path, ["a.tif", "b.tif"])
    with caplog.at_level("INFO", logger="boamotion.frames"):
        load_frames(tmp_path)
    assert "2 frames of 6 x 4" in caplog.text
