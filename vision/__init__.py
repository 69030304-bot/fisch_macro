"""
vision package - High-performance screen capture, color segmentation, and predictive tracking.
"""
from vision.capture import (
    BaseScreenGrabber,
    MssScreenGrabber,
    PilScreenGrabber,
    MockScreenGrabber,
    ScreenGrabber,
    Grabber,
)
from vision.detection import (
    BAR_GAP,
    FISH_GAP,
    color_mask,
    runs_of,
    choose,
    analyze,
    measure,
    centers,
    row_stride,
    detect,
)
from vision.tracking import Track

__all__ = [
    "BaseScreenGrabber",
    "MssScreenGrabber",
    "PilScreenGrabber",
    "MockScreenGrabber",
    "ScreenGrabber",
    "Grabber",
    "BAR_GAP",
    "FISH_GAP",
    "color_mask",
    "runs_of",
    "choose",
    "analyze",
    "measure",
    "centers",
    "row_stride",
    "detect",
    "Track",
]
