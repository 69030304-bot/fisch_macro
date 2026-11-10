"""
tests/test_core.py - Unit tests for core package (MacroEngine, StateManager, EventBus, InputManager, CancellationToken).
"""
import sys
import os
import time

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.state import MacroState, StateManager, StateTransitionError
from core.events import EventBus
from core.task import CancellationToken
from core.input import InputManager, MockInputDriver, SCAN
from core.engine import MacroEngine


def test_macro_state_transitions():
    sm = StateManager(MacroState.IDLE)
    assert sm.current_state == MacroState.IDLE
    assert not sm.is_active()

    # Valid transitions
    sm.transition_to(MacroState.STARTING)
    assert sm.current_state == MacroState.STARTING
    assert sm.is_active()

    sm.transition_to(MacroState.RUNNING)
    assert sm.current_state == MacroState.RUNNING
    assert sm.is_active()

    sm.transition_to(MacroState.PAUSED)
    assert sm.current_state == MacroState.PAUSED
    assert sm.is_active()

    sm.transition_to(MacroState.RUNNING)
    assert sm.current_state == MacroState.RUNNING

    sm.transition_to(MacroState.STOPPING)
    assert sm.current_state == MacroState.STOPPING

    sm.transition_to(MacroState.STOPPED)
    assert sm.current_state == MacroState.STOPPED
    assert not sm.is_active()

    sm.transition_to(MacroState.IDLE)
    assert sm.current_state == MacroState.IDLE


def test_invalid_state_transition():
    sm = StateManager(MacroState.IDLE)
    try:
        sm.transition_to(MacroState.STOPPED)
        assert False, "Should not allow IDLE -> STOPPED"
    except StateTransitionError as e:
        assert e.from_state == MacroState.IDLE
        assert e.to_state == MacroState.STOPPED


def test_state_change_listeners():
    sm = StateManager(MacroState.IDLE)
    log = []

    def on_change(old, new):
        log.append((old, new))

    sm.add_listener(on_change)
    sm.transition_to(MacroState.STARTING)
    sm.transition_to(MacroState.RUNNING)

    assert log == [(MacroState.IDLE, MacroState.STARTING), (MacroState.STARTING, MacroState.RUNNING)]

    sm.remove_listener(on_change)
    sm.transition_to(MacroState.STOPPING)
    assert len(log) == 2  # Listener was removed


def test_event_bus():
    bus = EventBus()
    received = []

    def handler_a(data):
        received.append(("a", data))

    def handler_b(data):
        received.append(("b", data))

    bus.subscribe("test_topic", handler_a)
    bus.subscribe("test_topic", handler_b)

    bus.publish("test_topic", "hello")
    assert received == [("a", "hello"), ("b", "hello")]

    bus.unsubscribe("test_topic", handler_a)
    received.clear()
    bus.publish("test_topic", "world")
    assert received == [("b", "world")]


def test_cancellation_token_interruptible_wait():
    token = CancellationToken()
    t0 = time.time()

    # Normal wait
    ok = token.wait(0.05)
    dur = time.time() - t0
    assert ok is True
    assert dur >= 0.04

    # Cancelled wait wakes up immediately
    token.cancel()
    assert token.is_cancelled
    t1 = time.time()
    ok2 = token.wait(2.0)
    dur2 = time.time() - t1
    assert ok2 is False
    assert dur2 < 0.1, f"Wait should have aborted immediately on cancel, took {dur2}s"


def test_cancellation_cleanup_hooks():
    token = CancellationToken()
    cleaned = []

    token.add_cleanup_hook(lambda: cleaned.append(1))
    token.add_cleanup_hook(lambda: cleaned.append(2))

    token.run_cleanup()
    assert cleaned == [1, 2]


def test_input_manager_mock():
    mock_driver = MockInputDriver()
    mgr = InputManager(driver=mock_driver)

    assert mgr.is_mock is True
    assert mgr.cursor_pos() == (100, 100)
    assert not mgr.is_failsafe_triggered()

    # Test mouse button tracking
    mgr.mouse_button(True)
    assert mock_driver.mouse_down is True
    mgr.mouse_button(False)
    assert mock_driver.mouse_down is False

    # Test key event tracking
    mgr.key_event(SCAN["1"], up=False)
    assert SCAN["1"] in mock_driver.held_keys
    mgr.key_event(SCAN["1"], up=True)
    assert SCAN["1"] not in mock_driver.held_keys

    # Test failsafe detection
    mock_driver.set_cursor_pos(0, 0)
    assert mgr.is_failsafe_triggered() is True

    # Test release_all guarantee
    mgr.mouse_button(True)
    mgr.key_event(SCAN["enter"], up=False)
    assert mock_driver.mouse_down is True
    assert SCAN["enter"] in mock_driver.held_keys

    mgr.release_all()
    assert mock_driver.mouse_down is False
    assert len(mock_driver.held_keys) == 0


def test_macro_engine_lifecycle():
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    bus = EventBus()
    sm = StateManager()
    engine = MacroEngine(state_manager=sm, event_bus=bus, input_mgr=input_mgr)

    started_flag = []

    def task(token, inp, events):
        started_flag.append("started")
        inp.mouse_button(True)
        # Wait up to 5 seconds or until cancelled
        token.wait(5.0)

    # Start engine
    ok = engine.start(task)
    assert ok is True

    time.sleep(0.05)
    assert engine.is_running is True
    assert started_flag == ["started"]
    assert mock_driver.mouse_down is True

    # Prevent duplicate start
    duplicate_ok = engine.start(task)
    assert duplicate_ok is False

    # Stop engine
    engine.stop()
    time.sleep(0.1)

    assert engine.current_state in (MacroState.STOPPING, MacroState.STOPPED)
    # Guaranteed input cleanup
    assert mock_driver.mouse_down is False


def test_macro_engine_emergency_stop():
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    bus = EventBus()
    engine = MacroEngine(input_mgr=input_mgr, event_bus=bus)

    def task(token, inp, events):
        inp.mouse_button(True)
        token.wait(5.0)

    engine.start(task)
    time.sleep(0.05)
    assert mock_driver.mouse_down is True

    engine.emergency_stop()
    time.sleep(0.05)
    assert mock_driver.mouse_down is False


if __name__ == "__main__":
    test_macro_state_transitions()
    print("[PASS] test_macro_state_transitions")
    test_invalid_state_transition()
    print("[PASS] test_invalid_state_transition")
    test_state_change_listeners()
    print("[PASS] test_state_change_listeners")
    test_event_bus()
    print("[PASS] test_event_bus")
    test_cancellation_token_interruptible_wait()
    print("[PASS] test_cancellation_token_interruptible_wait")
    test_cancellation_cleanup_hooks()
    print("[PASS] test_cancellation_cleanup_hooks")
    test_input_manager_mock()
    print("[PASS] test_input_manager_mock")
    test_macro_engine_lifecycle()
    print("[PASS] test_macro_engine_lifecycle")
    test_macro_engine_emergency_stop()
    print("[PASS] test_macro_engine_emergency_stop")
    print("\nAll core tests passed successfully!")
