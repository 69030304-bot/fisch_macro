"""
core/state.py - Thread-safe state management for Fisch Macro Engine.

Enforces state transitions for macro lifecycle:
  IDLE -> STARTING -> RUNNING -> PAUSED -> RUNNING -> STOPPING -> STOPPED -> IDLE
                                              |
                                              +-> ERROR -> IDLE
"""
from enum import Enum, auto
import threading
from typing import Callable, List, Optional, Set


class MacroState(Enum):
    IDLE = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()

    def __str__(self) -> str:
        return self.name


class StateTransitionError(Exception):
    """Raised when an invalid macro state transition is attempted."""
    def __init__(self, from_state: MacroState, to_state: MacroState, message: Optional[str] = None):
        super().__init__(message or f"Invalid state transition from {from_state} to {to_state}")
        self.from_state = from_state
        self.to_state = to_state


class StateManager:
    """Thread-safe state manager for the macro automation engine."""

    # Explicit allowable state transitions
    _VALID_TRANSITIONS: dict[MacroState, Set[MacroState]] = {
        MacroState.IDLE: {MacroState.STARTING, MacroState.ERROR},
        MacroState.STARTING: {MacroState.RUNNING, MacroState.STOPPING, MacroState.STOPPED, MacroState.ERROR},
        MacroState.RUNNING: {MacroState.PAUSED, MacroState.STOPPING, MacroState.STOPPED, MacroState.ERROR},
        MacroState.PAUSED: {MacroState.RUNNING, MacroState.STOPPING, MacroState.STOPPED, MacroState.ERROR},
        MacroState.STOPPING: {MacroState.STOPPED, MacroState.ERROR},
        MacroState.STOPPED: {MacroState.IDLE, MacroState.STARTING, MacroState.ERROR},
        MacroState.ERROR: {MacroState.IDLE, MacroState.STARTING, MacroState.STOPPED},
    }

    def __init__(self, initial_state: MacroState = MacroState.IDLE):
        self._lock = threading.RLock()
        self._current_state = initial_state
        self._listeners: List[Callable[[MacroState, MacroState], None]] = []

    @property
    def current_state(self) -> MacroState:
        with self._lock:
            return self._current_state

    def is_state(self, *states: MacroState) -> bool:
        with self._lock:
            return self._current_state in states

    def is_active(self) -> bool:
        """Returns True if the engine is starting, running, or paused."""
        return self.is_state(MacroState.STARTING, MacroState.RUNNING, MacroState.PAUSED)

    def transition_to(self, new_state: MacroState, error_message: Optional[str] = None) -> bool:
        """
        Transition to a new state if valid.
        Invokes all registered state change listeners.
        Returns True on successful transition; raises StateTransitionError if invalid.
        """
        callbacks_to_invoke = []
        old_state = MacroState.IDLE

        with self._lock:
            if self._current_state == new_state:
                return True

            allowed = self._VALID_TRANSITIONS.get(self._current_state, set())
            if new_state not in allowed:
                raise StateTransitionError(self._current_state, new_state, error_message)

            old_state = self._current_state
            self._current_state = new_state
            callbacks_to_invoke = list(self._listeners)

        # Invoke callbacks outside the lock to avoid deadlocks
        for callback in callbacks_to_invoke:
            try:
                callback(old_state, new_state)
            except Exception:
                pass

        return True

    def add_listener(self, listener: Callable[[MacroState, MacroState], None]) -> None:
        """Register a callback for state changes: callback(old_state, new_state)"""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[MacroState, MacroState], None]) -> None:
        """Unregister a state change callback."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)
