"""Quantify muscle contraction from video microscopy.

A Python port of the MUSCLEMOTION ImageJ macro by van Meer, Sala and Burton.
"""

from boamotion.frames import FrameSequence, load_frames
from boamotion.params import Params

__version__ = "0.0.1"

__all__ = ["FrameSequence", "Params", "__version__", "load_frames"]
