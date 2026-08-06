"""Quantify muscle contraction from video microscopy.

A Python port of the MUSCLEMOTION ImageJ macro by van Meer, Sala and Burton.

Modules, in the order the analysis uses them:

    params      settings for a run
    frames      reading a recording from disk
    synthetic   a generated recording with known ground truth
    reference   stage 1 - choosing the reference frame
    traces      stages 2 and 3 - pixel mask, contraction and speed
    transients  stage 4 - per-beat measurements
"""

from boamotion.frames import FrameSequence, load_frames
from boamotion.params import Params
from boamotion.reference import detect_reference_frame
from boamotion.synthetic import SyntheticRecording, synthetic_recording
from boamotion.traces import build_motion_pixel_mask, measure_contraction, measure_speed
from boamotion.transients import find_baselines, find_peaks, measure_transients

__version__ = "0.0.1"

__all__ = [
    "FrameSequence",
    "Params",
    "SyntheticRecording",
    "__version__",
    "find_baselines",
    "measure_contraction",
    "detect_reference_frame",
    "find_peaks",
    "load_frames",
    "build_motion_pixel_mask",
    "measure_speed",
    "measure_transients",
    "synthetic_recording",
]
