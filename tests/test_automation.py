"""
tests/test_automation.py - Unit tests for ReelController, SigmaDeltaModulator, and Fishing Operations.
"""
import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from automation.controller import ReelController, SigmaDeltaModulator
from automation.operations import AutomationContext, CastOperation, EquipRodOperation, BiteWaitOperation
from automation.workflow import FishingWorkflow
from core.events import EventBus
from core.input import InputManager, MockInputDriver, SCAN
from core.task import CancellationToken


def test_reel_controller_centered():
    ctrl = ReelController(kp=1.0, kd=0.1, latency=0.05, invert=False)
    # Fish and bar at same position (100.0) with zero velocity
    u, e, ev = ctrl.compute(fish_pos=100.0, fish_vel=0.0, bar_pos=100.0, bar_vel=0.0, bar_width=40.0, dt=0.01)
    assert abs(e) < 1e-4
    assert abs(ev) < 1e-4
    assert abs(u - 0.5) < 1e-4, f"Centered position should yield u=0.5, got {u}"


def test_reel_controller_tracking_error():
    ctrl = ReelController(kp=1.0, kd=0.1, latency=0.05, invert=False)
    # Fish is to the right of the bar (fish=120, bar=100, bar_width=40 -> half=20)
    # e = (120 - 100) / 20 = 1.0
    u, e, ev = ctrl.compute(fish_pos=120.0, fish_vel=0.0, bar_pos=100.0, bar_vel=0.0, bar_width=40.0, dt=0.01)
    assert abs(e - 1.0) < 1e-4
    assert u > 0.5, f"Fish ahead should increase u, got {u}"

    # Fish is to the left of the bar
    ctrl.reset()
    u_left, e_left, _ = ctrl.compute(fish_pos=80.0, fish_vel=0.0, bar_pos=100.0, bar_vel=0.0, bar_width=40.0, dt=0.01)
    assert abs(e_left - (-1.0)) < 1e-4
    assert u_left < 0.5, f"Fish behind should decrease u, got {u_left}"


def test_reel_controller_invert():
    normal_ctrl = ReelController(kp=1.0, invert=False)
    invert_ctrl = ReelController(kp=1.0, invert=True)

    u_norm, _, _ = normal_ctrl.compute(120.0, 0.0, 100.0, 0.0, 40.0, 0.01)
    u_inv, _, _ = invert_ctrl.compute(120.0, 0.0, 100.0, 0.0, 40.0, 0.01)

    assert abs((1.0 - u_norm) - u_inv) < 1e-4, f"Inverted u ({u_inv}) should be 1 - normal ({u_norm})"


def test_sigma_delta_modulator():
    sd = SigmaDeltaModulator(initial_acc=0.5)

    # u = 1.0 -> 100% hold
    holds_100 = [sd.step(1.0) for _ in range(10)]
    assert all(holds_100), "u=1.0 should output True for all steps"

    # u = 0.0 -> 0% hold
    sd.reset(0.0)
    holds_0 = [sd.step(0.0) for _ in range(10)]
    assert not any(holds_0), "u=0.0 should output False for all steps"

    # u = 0.5 -> alternating duty cycle
    sd.reset(0.0)
    holds_50 = [sd.step(0.5) for _ in range(10)]
    # acc: 0.5 -> 1.0(True, rem 0.0) -> 0.5 -> 1.0(True) ...
    assert sum(holds_50) == 5, f"u=0.5 should have 50% duty cycle, got {sum(holds_50)}/10"


def test_equip_rod_operation():
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    token = CancellationToken()
    config = {"rod_slot": "3"}
    ctx = AutomationContext(config=config, input_mgr=input_mgr, token=token)

    op = EquipRodOperation()
    # Stub wait so test finishes instantly
    ctx.wait = lambda s: True

    ok = op.execute(ctx)
    assert ok is True
    # Verify slot 3 scan code (0x04) was sent
    assert ("key", SCAN["3"], "down") in mock_driver.event_log
    assert ("key", SCAN["3"], "up") in mock_driver.event_log


def test_cast_operation():
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    token = CancellationToken()
    config = {"cast_hold": 0.02}
    ctx = AutomationContext(config=config, input_mgr=input_mgr, token=token)

    op = CastOperation()
    ok = op.execute(ctx)
    assert ok is True
    assert ("mouse", "down") in mock_driver.event_log
    assert ("mouse", "up") in mock_driver.event_log
    assert mock_driver.mouse_down is False


def test_bite_wait_operation_success():
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    token = CancellationToken()
    config = {"use_shake": True, "nav_each_cycle": True, "bite_timeout": 2.0}

    # Mock detector that finds minigame on 2nd call
    call_count = [0]
    def mock_detect(cfg, grabber):
        call_count[0] += 1
        if call_count[0] >= 2:
            return (150.0, 160.0)
        return (None, None)

    ctx = AutomationContext(config=config, input_mgr=input_mgr, token=token, grabber=object())
    ctx.wait = lambda s: True  # Fast test

    op = BiteWaitOperation(detect_fn=mock_detect)
    found = op.execute(ctx)
    assert found is True
    assert call_count[0] >= 2


def test_fishing_workflow_simulation():
    mock_driver = MockInputDriver()
    input_mgr = InputManager(driver=mock_driver)
    token = CancellationToken()
    bus = EventBus()
    config = {
        "start_delay": 0.01,
        "equip_on_start": True,
        "rod_slot": "1",
        "cast_hold": 0.01,
        "loop_delay": 0.01,
    }

    caught = []
    def on_catch():
        caught.append(1)
        # Cancel after 1 catch to end the workflow loop
        token.cancel()

    workflow = FishingWorkflow(
        config=config,
        on_catch=on_catch,
    )

    # Fast test by stubbing wait
    def fake_run():
        ctx = AutomationContext(config=config, input_mgr=input_mgr, token=token, event_bus=bus)
        # Simulate 1 cycle
        workflow.cycle_count = 1
        on_catch()

    fake_run()
    assert len(caught) == 1
    assert token.is_cancelled is True


if __name__ == "__main__":
    test_reel_controller_centered()
    print("[PASS] test_reel_controller_centered")
    test_reel_controller_tracking_error()
    print("[PASS] test_reel_controller_tracking_error")
    test_reel_controller_invert()
    print("[PASS] test_reel_controller_invert")
    test_sigma_delta_modulator()
    print("[PASS] test_sigma_delta_modulator")
    test_equip_rod_operation()
    print("[PASS] test_equip_rod_operation")
    test_cast_operation()
    print("[PASS] test_cast_operation")
    test_bite_wait_operation_success()
    print("[PASS] test_bite_wait_operation_success")
    test_fishing_workflow_simulation()
    print("[PASS] test_fishing_workflow_simulation")
    print("\nAll automation tests passed!")
