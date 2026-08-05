"""Quantify muscle contraction from video microscopy.

A Python port of the MUSCLEMOTION ImageJ macro by van Meer, Sala and Burton.

Modules, in the order the analysis uses them:

    params      settings for a run
    frames      reading a recording from disk
    synthetic   a generated recording with known ground truth
    reference   stage 1 - choosing the reference frame
    traces      stages 2 and 3 - pixel mask, contraction and speed
"""

from boamotion.frames import FrameSequence, load_frames
from boamotion.params import Params
from boamotion.reference import detect_reference_frame
from boamotion.synthetic import SyntheticRecording, synthetic_recording
from boamotion.traces import contraction_trace, motion_pixel_mask, speed_trace

__version__ = "0.0.1"

__all__ = [
    "FrameSequence",
    "Params",
    "SyntheticRecording",
    "__version__",
    "contraction_trace",
    "detect_reference_frame",
    "load_frames",
    "motion_pixel_mask",
    "speed_trace",
    "synthetic_recording",
]
