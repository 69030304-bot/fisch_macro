"""
core/task.py - Cooperative Task Cancellation & Interruptible Lifecycle Management.

Supports:
- Clean cancellation (cooperative interruptible wait).
- Immediate emergency stop prioritization.
- Pause and resume coordination.
- Registered cleanup hooks.
"""
import threading
import time
from typing import Callable, List, Optional


class CancellationToken:
    """Manages cooperative cancellation, pause/resume, and emergency stops."""

    def __init__(self):
        self._cancel_event = threading.Event()
        self._emergency_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Unpaused by default (set = running, clear = paused)
        self._lock = threading.Lock()
        self._cleanup_hooks: List[Callable[[], None]] = []

    def cancel(self) -> None:
        """Signal cooperative cancellation."""
        self._cancel_event.set()

    def emergency_stop(self) -> None:
        """Signal highest-priority emergency abort."""
        self._emergency_event.set()
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def is_emergency(self) -> bool:
        return self._emergency_event.is_set()

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def pause(self) -> None:
        """Pause the automation task."""
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume the automation task."""
        self._pause_event.set()

    def wait(self, timeout: float, step: float = 0.05) -> bool:
        """
        Interruptible sleep.
        Returns True if the full timeout elapsed without cancellation.
        Returns False immediately if cancelled or emergency stopped.
        """
        if self.is_cancelled:
            return False

        end_time = time.time() + timeout
        while time.time() < end_time:
            if self.is_cancelled:
                return False
            # Check if paused and wait until resumed or cancelled
            if not self._pause_event.is_set():
                while not self._pause_event.is_set():
                    if self.is_cancelled:
                        return False
                    self._pause_event.wait(timeout=0.05)

            remaining = end_time - time.time()
            if remaining <= 0:
                break
            sleep_chunk = min(remaining, step)
            # Use cancel_event.wait to wake up instantly on cancel
            if self._cancel_event.wait(timeout=sleep_chunk):
                return False
        return not self.is_cancelled

    def add_cleanup_hook(self, hook: Callable[[], None]) -> None:
        """Register a cleanup hook to run on stop/cleanup."""
        with self._lock:
            if hook not in self._cleanup_hooks:
                self._cleanup_hooks.append(hook)

    def run_cleanup(self) -> None:
        """Execute all registered cleanup hooks safely."""
        with self._lock:
            hooks = list(self._cleanup_hooks)
        for hook in hooks:
            try:
                hook()
            except Exception:
                pass
