"""
automation/workflow.py - High-level Fishing Automation Workflow.

Coordinates the sequential fishing cycle:
Countdown -> Equip -> [Cast -> Wait for Bite -> Reel Minigame -> Rest] (Repeat)
"""
import time
from typing import Any, Callable, Dict, Optional

from automation.operations import (
    AutomationContext,
    BiteWaitOperation,
    CastOperation,
    EquipRodOperation,
    ReelOperation,
)
from core.events import EventBus
from core.input import InputManager
from core.task import CancellationToken


class FishingWorkflow:
    """Orchestrates the complete cyclic auto-fishing workflow."""

    def __init__(
        self,
        config: Dict[str, Any],
        operations: Optional[Dict[str, Any]] = None,
        on_catch: Optional[Callable[[], None]] = None,
        on_finish: Optional[Callable[[], None]] = None,
    ):
        self.config = config
        self.operations = operations or {}
        self.on_catch = on_catch
        self.on_finish = on_finish
        self.cycle_count = 0
        self.current_phase = "idle"

    def run(self, token: CancellationToken, input_mgr: InputManager, event_bus: EventBus) -> None:
        """Executes the fishing cycle loop until cancelled or stopped."""
        grabber = self.operations.get("grabber")
        log_fn = lambda msg: event_bus.publish("log", msg)

        ctx = AutomationContext(
            config=self.config,
            input_mgr=input_mgr,
            token=token,
            event_bus=event_bus,
            grabber=grabber,
            log_fn=log_fn,
        )

        try:
            # Phase: Countdown start delay
            start_delay = float(self.config.get("start_delay", 5))
            ctx.log(f"Starting in {start_delay:.0f}s - Switch to Roblox window")
            self.current_phase = "start"
            ctx.set_status("นับถอยหลัง... คลิกกลับไปหน้าเกม")
            event_bus.publish("phase_changed", "start")

            if not ctx.wait(start_delay):
                return

            # Phase: Equip rod once on startup
            if self.config.get("equip_on_start", True) and not token.is_cancelled:
                equip_op = self.operations.get("equip") or EquipRodOperation()
                equip_op.execute(ctx)

            cast_op = self.operations.get("cast") or CastOperation()
            bite_op = self.operations.get("bite")
            reel_op = self.operations.get("reel")

            # Main fishing workflow loop
            while not token.is_cancelled:
                self.cycle_count += 1
                event_bus.publish("cycle_changed", self.cycle_count)
                ctx.log(f"--- Cycle #{self.cycle_count} ---")

                # Step 1: Cast rod
                self.current_phase = "cast"
                event_bus.publish("phase_changed", "cast")
                cast_ok = cast_op.execute(ctx)
                if token.is_cancelled or not cast_ok:
                    break

                # Step 2: Wait for bite / Shake
                self.current_phase = "wait"
                event_bus.publish("phase_changed", "wait")
                bite_detected = False
                if bite_op:
                    bite_detected = bite_op.execute(ctx)
                else:
                    # Minimal wait if bite operation not provided
                    bite_detected = ctx.wait(2.0)

                if token.is_cancelled:
                    break

                # Step 3: Reel minigame
                if bite_detected:
                    ctx.log("Minigame detected! Reeling fish...")
                    self.current_phase = "reel"
                    event_bus.publish("phase_changed", "reel")

                    if reel_op:
                        dur, fps = reel_op.execute(ctx)
                        ctx.log(f"Minigame completed ({dur:.1f}s, avg {fps:.0f} fps)")
                    else:
                        ctx.wait(3.0)

                    if self.on_catch:
                        self.on_catch()
                    event_bus.publish("catch", self.cycle_count)

                elif not token.is_cancelled:
                    ctx.log("No bite detected within timeout. Resetting cycle.")

                # Step 4: Rest before next cycle
                self.current_phase = "rest"
                ctx.set_status("พักก่อนเหวี่ยงรอบถัดไป")
                event_bus.publish("phase_changed", "rest")
                loop_delay = float(self.config.get("loop_delay", 2.0))
                if not ctx.wait(loop_delay):
                    break

        except Exception as e:
            ctx.log(f"Workflow error: {e}")
            event_bus.publish("error", str(e))
        finally:
            input_mgr.release_all()
            self.current_phase = "idle"
            ctx.set_status("")
            event_bus.publish("phase_changed", "idle")
            if self.on_finish:
                self.on_finish()
