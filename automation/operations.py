"""
automation/operations.py - Independent, testable fishing operations.

Contains:
- EquipRodOperation: Initial rod selection
- CastOperation: Timed mouse casting
- BiteWaitOperation: Shake prompts and visual bite detection
- ReelOperation: Minigame visual tracking and control loop
"""
import csv
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from automation.controller import ReelController, SigmaDeltaModulator
from core.events import EventBus
from core.input import InputManager
from core.task import CancellationToken


class AutomationContext:
    """Shared execution context passed to automation operations."""

    def __init__(
        self,
        config: Dict[str, Any],
        input_mgr: InputManager,
        token: CancellationToken,
        event_bus: Optional[EventBus] = None,
        grabber: Optional[Any] = None,
        log_fn: Optional[Callable[[str], None]] = None,
        status_fn: Optional[Callable[[str], None]] = None,
    ):
        self.config = config
        self.input_mgr = input_mgr
        self.token = token
        self.event_bus = event_bus
        self.grabber = grabber
        self._log_fn = log_fn
        self._status_fn = status_fn
        self.live_status: str = ""

    def log(self, message: str) -> None:
        if self._log_fn:
            self._log_fn(message)
        if self.event_bus:
            self.event_bus.publish("log", message)

    def set_status(self, text: str) -> None:
        self.live_status = text
        if self._status_fn:
            self._status_fn(text)
        if self.event_bus:
            self.event_bus.publish("status", text)

    def check_failsafe(self) -> bool:
        if self.input_mgr.is_failsafe_triggered():
            self.log("FAILSAFE: Mouse at top-left corner (0, 0). Emergency stop.")
            self.token.emergency_stop()
            self.input_mgr.release_all()
            return True
        return False

    def wait(self, seconds: float) -> bool:
        """Interruptible wait with periodic failsafe checks."""
        end_time = time.time() + seconds
        while not self.token.is_cancelled and time.time() < end_time:
            chunk = min(0.05, max(0.0, end_time - time.time()))
            if not self.token.wait(chunk):
                return False
            if self.check_failsafe():
                return False
        return not self.token.is_cancelled


class EquipRodOperation:
    """Equips the rod in the designated hotbar slot once on macro startup."""

    def execute(self, ctx: AutomationContext) -> bool:
        slot = str(ctx.config.get("rod_slot", "1"))
        ctx.log(f"Pressing slot {slot} to equip rod")
        ctx.input_mgr.tap(slot)
        return ctx.wait(0.8)


class CastOperation:
    """Performs rod casting by holding left mouse button for cast_hold seconds."""

    def execute(self, ctx: AutomationContext) -> bool:
        ctx.set_status("เหวี่ยงเบ็ด")
        cast_hold = float(ctx.config.get("cast_hold", 1.0))
        ctx.log("เหวี่ยงเบ็ด")

        ctx.input_mgr.mouse_button(True)
        try:
            ok = ctx.wait(cast_hold)
        finally:
            ctx.input_mgr.mouse_button(False)

        return ok and not ctx.token.is_cancelled


class BiteWaitOperation:
    r"""
    Waits for a fish bite:
    - Periodically taps Enter for Shake minigames.
    - Optionally toggles UI navigation (\) to trigger shake prompts.
    - Polls visual detector for minigame bar/fish appearance.
    """

    def __init__(self, detect_fn: Callable[[Dict[str, Any], Any], Tuple[Optional[float], Optional[float]]]):
        self.detect_fn = detect_fn

    def execute(self, ctx: AutomationContext) -> bool:
        cfg = ctx.config
        ctx.set_status("รอปลากิน / กด Shake")
        use_shake = bool(cfg.get("use_shake", True))
        nav_each_cycle = bool(cfg.get("nav_each_cycle", True))
        timeout = float(cfg.get("bite_timeout", 25.0))

        nav_active = use_shake and nav_each_cycle
        found_minigame = False

        if nav_active:
            if not ctx.wait(0.3):
                return False
            ctx.input_mgr.tap("\\")

        try:
            start_time = time.time()
            while not ctx.token.is_cancelled and (time.time() - start_time) < timeout:
                if use_shake:
                    ctx.input_mgr.tap("enter")

                if ctx.grabber and self.detect_fn:
                    fish, bar = self.detect_fn(cfg, ctx.grabber)
                    if fish is not None and bar is not None:
                        found_minigame = True
                        break

                if not ctx.wait(0.1):
                    break
        finally:
            if nav_active:
                ctx.input_mgr.tap("\\")
                ctx.wait(0.15)

        return found_minigame


class ReelOperation:
    """
    Executes the active reeling minigame control loop:
    - Real-time predictive tracking (EMA Track) of fish and bar positions.
    - PD error computation via ReelController.
    - Sigma-Delta high-frequency mouse modulation at ~6ms control intervals.
    - Post-run telemetry trace writing to fisch_trace.csv.
    """

    def __init__(
        self,
        measure_fn: Callable[..., Tuple[Any, Any]],
        track_factory: Callable[[], Any],
        row_stride_fn: Callable[[List[int]], int],
        trace_file: Optional[str] = None,
    ):
        self.measure_fn = measure_fn
        self.track_factory = track_factory
        self.row_stride_fn = row_stride_fn
        self.trace_file = trace_file

    def execute(self, ctx: AutomationContext) -> Tuple[float, float]:
        cfg = ctx.config
        ctx.set_status("กำลังดึงปลา")
        region = cfg["region"]
        stride = self.row_stride_fn(region)
        timeout = float(cfg.get("reel_timeout", 40.0))

        controller = ReelController(
            kp=cfg.get("kp", 1.0),
            kd=cfg.get("kd", 0.10),
            latency=cfg.get("latency", 0.05),
            invert=cfg.get("invert", False),
        )
        modulator = SigmaDeltaModulator(initial_acc=0.5)

        ft = self.track_factory()
        bt = self.track_factory()
        bar_w: Optional[float] = None

        trace_data: List[Tuple[float, float, float, float, float, int]] = []
        t0 = time.perf_counter()
        last_fish_seen = last_ctrl = fps_t = t0
        frames = fps_n = 0
        fps = 0.0
        u = 0.5

        try:
            while not ctx.token.is_cancelled and (time.perf_counter() - t0) < timeout:
                arr = ctx.grabber.grab(region, stride) if ctx.grabber else None
                now = time.perf_counter()
                frames += 1
                fps_n += 1

                if arr is not None:
                    f, b = self.measure_fn(arr, cfg, ft.pos(now), bt.pos(now))
                    if f:
                        ft.update(f[2], now)
                        last_fish_seen = now
                    elif now - last_fish_seen > 0.7:
                        # Fish not detected for 0.7s indicates minigame concluded
                        break

                    if b:
                        bt.update((b[0] + b[1]) / 2.0, now)
                        w = b[1] - b[0] + 1
                        bar_w = w if bar_w is None else 0.9 * bar_w + 0.1 * w

                # Control cycle executed at ~6ms intervals
                if now - last_ctrl >= 0.006:
                    dt = now - last_ctrl
                    last_ctrl = now

                    if ft.fresh(now) and bt.fresh(now):
                        tp = now + controller.latency
                        fp, bp = ft.pos(tp), bt.pos(tp)

                        u, e, ev = controller.compute(fp, ft.v, bp, bt.v, bar_w, dt)
                        hold = modulator.step(u)
                        ctx.input_mgr.mouse_button(hold)

                        if cfg.get("trace"):
                            trace_data.append((
                                round(now - t0, 4),
                                round(ft.x or 0.0, 1),
                                round(bt.x or 0.0, 1),
                                round(bar_w or 0.0, 1),
                                round(u, 3),
                                int(hold),
                            ))

                        if frames % 8 == 0:
                            ctx.set_status(f"ปลา {fp:.0f}  แถบ {bp:.0f}  กว้าง {bar_w or 0:.0f}  u={u:.2f}  {fps:.0f} fps")

                    elif not bt.fresh(now):
                        # Release mouse if reel bar visual is lost to prevent runaway reeling
                        ctx.input_mgr.mouse_button(False)

                if fps_n >= 40:
                    fps = fps_n / max(now - fps_t, 1e-6)
                    fps_t, fps_n = now, 0

                if frames % 25 == 0:
                    if ctx.check_failsafe():
                        break

                time.sleep(0.001)

        finally:
            ctx.input_mgr.mouse_button(False)

        dur = time.perf_counter() - t0
        avg_fps = frames / max(dur, 1e-6)

        if cfg.get("trace") and trace_data and self.trace_file:
            try:
                with open(self.trace_file, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["t", "fish_x", "bar_x", "bar_w", "u", "hold"])
                    writer.writerows(trace_data)
            except Exception as e:
                ctx.log(f"Failed to write trace: {e}")

        ctx.set_status("")
        return dur, avg_fps
