"""
core/input.py - Hardware Input Layer with Platform Abstraction & Failsafe.

Provides:
- Win32 SendInput driver on Windows.
- Safe MockInputDriver on non-Windows/test environments.
- High-level InputManager with guaranteed release_all cleanup and failsafe check.
"""
import ctypes
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

SCAN = {
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06, "6": 0x07,
    "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B, "\\": 0x2B, "enter": 0x1C,
}

IS_WINDOWS = sys.platform == "win32" and hasattr(ctypes, "windll")


# ---------------------------------------------------------------- Windows Win32 Driver
if IS_WINDOWS:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    user32 = ctypes.windll.user32
    PUL = ctypes.POINTER(ctypes.c_ulong)

    class KeyBdInput(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_short),
            ("wParamH", ctypes.c_ushort),
        ]

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class Input_I(ctypes.Union):
        _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class BaseInputDriver:
    """Interface for input hardware simulation."""
    def send_key_event(self, scan_code: int, up: bool = False) -> None:
        raise NotImplementedError

    def send_mouse_button(self, down: bool) -> None:
        raise NotImplementedError

    def get_cursor_pos(self) -> Tuple[int, int]:
        raise NotImplementedError


class Win32InputDriver(BaseInputDriver):
    """Direct Windows user32 SendInput driver."""

    def _send(self, inp: Any) -> None:
        user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))

    def send_key_event(self, scan_code: int, up: bool = False) -> None:
        extra = ctypes.c_ulong(0)
        ii = Input_I()
        ii.ki = KeyBdInput(0, scan_code, 0x0008 | (0x0002 if up else 0), 0, ctypes.pointer(extra))
        self._send(Input(1, ii))

    def send_mouse_button(self, down: bool) -> None:
        extra = ctypes.c_ulong(0)
        ii = Input_I()
        ii.mi = MouseInput(0, 0, 0, 0x0002 if down else 0x0004, 0, ctypes.pointer(extra))
        self._send(Input(0, ii))

    def get_cursor_pos(self) -> Tuple[int, int]:
        p = POINT()
        user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y


class MockInputDriver(BaseInputDriver):
    """Safe mock input driver for headless unit tests and non-Windows systems."""

    def __init__(self):
        self.mouse_down: bool = False
        self.held_keys: set[int] = set()
        self.cursor_pos: Tuple[int, int] = (100, 100)
        self.event_log: List[Tuple[str, Any]] = []

    def send_key_event(self, scan_code: int, up: bool = False) -> None:
        if up:
            self.held_keys.discard(scan_code)
        else:
            self.held_keys.add(scan_code)
        self.event_log.append(("key", scan_code, "up" if up else "down"))

    def send_mouse_button(self, down: bool) -> None:
        self.mouse_down = down
        self.event_log.append(("mouse", "down" if down else "up"))

    def get_cursor_pos(self) -> Tuple[int, int]:
        return self.cursor_pos

    def set_cursor_pos(self, x: int, y: int) -> None:
        self.cursor_pos = (x, y)


class InputManager:
    """Manages input execution, held button state tracking, and failsafe detection."""

    def __init__(self, driver: Optional[BaseInputDriver] = None):
        if driver is not None:
            self.driver = driver
        elif IS_WINDOWS:
            self.driver = Win32InputDriver()
        else:
            self.driver = MockInputDriver()

        self._mouse_held = False
        self._held_scans: set[int] = set()

    @property
    def is_mock(self) -> bool:
        return isinstance(self.driver, MockInputDriver)

    def mouse_button(self, down: bool) -> None:
        """Press or release the left mouse button with state tracking."""
        if down != self._mouse_held:
            self.driver.send_mouse_button(down)
            self._mouse_held = down

    def key_event(self, scan_code: int, up: bool = False) -> None:
        """Send a keyboard event with tracking."""
        self.driver.send_key_event(scan_code, up=up)
        if up:
            self._held_scans.discard(scan_code)
        else:
            self._held_scans.add(scan_code)

    def tap(self, name: str, hold: float = 0.04) -> None:
        """Tap a key by name (e.g. '1', 'enter', '\\')."""
        scan = SCAN.get(name)
        if scan is None:
            return
        self.key_event(scan, up=False)
        time.sleep(hold)
        self.key_event(scan, up=True)

    def cursor_pos(self) -> Tuple[int, int]:
        return self.driver.get_cursor_pos()

    def is_failsafe_triggered(self) -> bool:
        """Returns True if the mouse is placed at the top-left (0, 0) emergency abort corner."""
        try:
            return self.cursor_pos() == (0, 0)
        except Exception:
            return False

    def release_all(self) -> None:
        """Safety guarantee: release all currently held mouse buttons and keys."""
        if self._mouse_held:
            try:
                self.driver.send_mouse_button(False)
            except Exception:
                pass
            self._mouse_held = False

        for scan in list(self._held_scans):
            try:
                self.driver.send_key_event(scan, up=True)
            except Exception:
                pass
        self._held_scans.clear()


# Default singleton input manager
input_manager = InputManager()

# Standalone helper functions preserving exact backwards compatibility
def mouse_button(down: bool) -> None:
    input_manager.mouse_button(down)

def key_event(scan: int, up: bool = False) -> None:
    input_manager.key_event(scan, up=up)

def tap(name: str, hold: float = 0.04) -> None:
    input_manager.tap(name, hold=hold)

def cursor_pos() -> Tuple[int, int]:
    return input_manager.cursor_pos()
