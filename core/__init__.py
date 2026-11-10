"""
core package - Macro Engine, State Management, Event Bus, and Input Abstraction.
"""
from core.state import MacroState, StateManager, StateTransitionError
from core.events import EventBus, default_bus
from core.task import CancellationToken
from core.input import InputManager, input_manager, mouse_button, key_event, tap, cursor_pos, SCAN
from core.engine import MacroEngine

__all__ = [
    "MacroState",
    "StateManager",
    "StateTransitionError",
    "EventBus",
    "default_bus",
    "CancellationToken",
    "InputManager",
    "input_manager",
    "mouse_button",
    "key_event",
    "tap",
    "cursor_pos",
    "SCAN",
    "MacroEngine",
]
