"""
vision/capture.py - Screen capture drivers and adapters.

Provides:
- MssScreenGrabber: Fast multi-monitor screen capture via mss
- PilScreenGrabber: Fallback screen capture via PIL.ImageGrab
- MockScreenGrabber: Synthetic frame buffer injection for tests
- ScreenGrabber (Grabber): Unified capture adapter with automatic fallback
"""
from typing import List, Optional, Tuple
import numpy as np

try:
    import mss
except ImportError:
    mss = None

from PIL import ImageGrab


class BaseScreenGrabber:
    """Interface for screen capture drivers."""

    def grab(self, region: Tuple[int, int, int, int], stride: int = 1) -> np.ndarray:
        """
        Captures a rectangular region [x, y, width, height] and returns
        a NumPy array of shape (height // stride, width, 3) in int16 RGB format.
        """
        raise NotImplementedError


class MssScreenGrabber(BaseScreenGrabber):
    """High-speed screen capture driver using mss."""

    def __init__(self):
        self._sct = None
        if mss is not None:
            try:
                self._sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
            except Exception:
                self._sct = None

    @property
    def is_available(self) -> bool:
        return self._sct is not None

    def grab(self, region: Tuple[int, int, int, int], stride: int = 1) -> np.ndarray:
        if not self._sct:
            raise RuntimeError("mss capture driver is not available")
        x, y, w, h = region
        shot = self._sct.grab({"left": int(x), "top": int(y), "width": int(w), "height": int(h)})
        # Convert BGRA to RGB and slice stride rows
        return np.asarray(shot)[::stride, :, 2::-1].astype(np.int16)


class PilScreenGrabber(BaseScreenGrabber):
    """Fallback screen capture driver using PIL.ImageGrab."""

    def grab(self, region: Tuple[int, int, int, int], stride: int = 1) -> np.ndarray:
        x, y, w, h = region
        img = ImageGrab.grab(bbox=(int(x), int(y), int(x + w), int(y + h)), all_screens=True).convert("RGB")
        return np.asarray(img)[::stride].astype(np.int16)


class MockScreenGrabber(BaseScreenGrabber):
    """Mock screen capture driver returning preconfigured or blank frames for testing."""

    def __init__(self, frame: Optional[np.ndarray] = None):
        self.frame = frame

    def set_frame(self, frame: np.ndarray) -> None:
        self.frame = frame

    def grab(self, region: Tuple[int, int, int, int], stride: int = 1) -> np.ndarray:
        if self.frame is not None:
            return self.frame[::stride].astype(np.int16)
        x, y, w, h = region
        # Return blank zero array matching requested dimensions
        rows = max(1, h // stride)
        return np.zeros((rows, int(w), 3), dtype=np.int16)


class ScreenGrabber(BaseScreenGrabber):
    """
    Unified screen capture manager.
    Attempts high-speed mss capture first; seamlessly falls back to PIL ImageGrab.
    """

    def __init__(self):
        self._mss: Optional[MssScreenGrabber] = None
        self._pil = PilScreenGrabber()
        try:
            mss_driver = MssScreenGrabber()
            if mss_driver.is_available:
                self._mss = mss_driver
        except Exception:
            self._mss = None

    @property
    def sct(self):
        """Backwards compatibility property exposing mss handle."""
        return self._mss._sct if self._mss else None

    def grab(self, region: Tuple[int, int, int, int], stride: int = 1) -> np.ndarray:
        if self._mss:
            try:
                return self._mss.grab(region, stride)
            except Exception:
                self._mss = None  # Fallback to PIL if mss fails at runtime
        return self._pil.grab(region, stride)


# Aliased for 100% backwards compatibility with existing fisch_macro.py
Grabber = ScreenGrabber
