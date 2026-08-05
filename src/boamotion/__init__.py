"""Quantify muscle contraction from video microscopy.

A Python port of the MUSCLEMOTION ImageJ macro by van Meer, Sala and Burton.

Modules, in the order the analysis uses them:

    params      settings for a run
    frames      reading a recording from disk
    synthetic   a generated recording with known ground truth
    reference   stage 1 - choosing the reference frame
"""

from boamotion.frames import FrameSequence, load_frames
from boamotion.params import Params
from boamotion.reference import detect_reference_frame
from boamotion.synthetic import SyntheticRecording, synthetic_recording

__version__ = "0.0.1"

__all__ = [
    "FrameSequence",
    "Params",
    "SyntheticRecording",
    "__version__",
    "detect_reference_frame",
    "load_frames",
    "synthetic_recording",
]
