"""
core/engine.py - Core Macro Execution Engine.

Responsible for:
- Macro lifecycle control (start, stop, pause, resume, emergency stop).
- State transition management.
- Duplicate task prevention.
- Safe task cancellation.
- Guaranteed input cleanup.
- Event broadcasting.
"""
import sys
import threading
import time
from typing import Any, Callable, Dict, Optional

from core.events import EventBus, default_bus
from core.input import InputManager, input_manager
from core.state import MacroState, StateManager
from core.task import CancellationToken


class MacroEngine:
    """Core automation engine managing background task execution and lifecycle."""

    def __init__(
        self,
        state_manager: Optional[StateManager] = None,
        event_bus: Optional[EventBus] = None,
        input_mgr: Optional[InputManager] = None,
    ):
        self.state_manager = state_manager or StateManager()
        self.event_bus = event_bus or default_bus
        self.input_manager = input_mgr or input_manager

        self._worker_thread: Optional[threading.Thread] = None
        self._cancellation_token: Optional[CancellationToken] = None
        self._lock = threading.RLock()
        self._thread_name = "FischMacroWorker"

    @property
    def current_state(self) -> MacroState:
        return self.state_manager.current_state

    @property
    def is_running(self) -> bool:
        return self.state_manager.is_state(MacroState.RUNNING)

    @property
    def is_active(self) -> bool:
        return self.state_manager.is_active()

    def start(self, task_factory: Callable[[CancellationToken, InputManager, EventBus], None]) -> bool:
        """
        Start the automation engine.
        task_factory is a callable taking (token, input_mgr, event_bus).
        Prevents duplicate execution if already running or starting.
        """
        with self._lock:
            if self.state_manager.is_active():
                self.event_bus.publish("log", "[MacroEngine] Warning: Task is already running.")
                return False

            self.state_manager.transition_to(MacroState.STARTING)
            self._cancellation_token = CancellationToken()

            def runner():
                token = self._cancellation_token
                try:
                    # Windows precision timer setup if available
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            ctypes.windll.winmm.timeBeginPeriod(1)
                        except Exception:
                            pass

                    self.state_manager.transition_to(MacroState.RUNNING)
                    self.event_bus.publish("state_changed", MacroState.RUNNING)

                    # Execute the task
                    task_factory(token, self.input_manager, self.event_bus)

                except Exception as exc:
                    self.event_bus.publish("log", f"[MacroEngine] Error in worker task: {exc}")
                    self.event_bus.publish("error", str(exc))
                    try:
                        self.state_manager.transition_to(MacroState.ERROR)
                    except Exception:
                        pass
                finally:
                    # Guarantee input cleanup and Windows timer restore
                    self.input_manager.release_all()
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            ctypes.windll.winmm.timeEndPeriod(1)
                        except Exception:
                            pass

                    if token:
                        token.run_cleanup()

                    with self._lock:
                        if not self.state_manager.is_state(MacroState.ERROR):
                            try:
                                self.state_manager.transition_to(MacroState.STOPPED)
                            except Exception:
                                pass
                        self.event_bus.publish("state_changed", self.state_manager.current_state)
                        self._worker_thread = None

            self._worker_thread = threading.Thread(target=runner, name=self._thread_name, daemon=True)
            self._worker_thread.start()
            return True

    def stop(self) -> None:
        """Cooperative stop of the automation engine."""
        with self._lock:
            if not self.state_manager.is_active():
                return
            try:
                self.state_manager.transition_to(MacroState.STOPPING)
            except Exception:
                pass

            if self._cancellation_token:
                self._cancellation_token.cancel()

        # Immediate input release
        self.input_manager.release_all()

    def emergency_stop(self) -> None:
        """Emergency stop with immediate input release and priority cancellation."""
        with self._lock:
            try:
                self.state_manager.transition_to(MacroState.STOPPING)
            except Exception:
                pass

            if self._cancellation_token:
                self._cancellation_token.emergency_stop()

        self.input_manager.release_all()
        self.event_bus.publish("log", "[MacroEngine] EMERGENCY STOP ACTIVATED")

    def pause(self) -> None:
        """Pause the automation task."""
        with self._lock:
            if self.state_manager.is_state(MacroState.RUNNING):
                self.state_manager.transition_to(MacroState.PAUSED)
                if self._cancellation_token:
                    self._cancellation_token.pause()
                self.input_manager.release_all()
                self.event_bus.publish("state_changed", MacroState.PAUSED)

    def resume(self) -> None:
        """Resume a paused automation task."""
        with self._lock:
            if self.state_manager.is_state(MacroState.PAUSED):
                self.state_manager.transition_to(MacroState.RUNNING)
                if self._cancellation_token:
                    self._cancellation_token.resume()
                self.event_bus.publish("state_changed", MacroState.RUNNING)
