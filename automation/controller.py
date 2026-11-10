"""
automation/controller.py - Control algorithms for reel minigame.

Extracts and isolates the PD controller with integral accumulator and
sigma-delta pulse modulation from the legacy bot thread.
"""
from typing import Optional, Tuple


class ReelController:
    """
    Computes normalized control signal u in [0.0, 1.0] from fish and bar positions.

    Parameters:
    - kp: Proportional gain (responsiveness to tracking error)
    - kd: Derivative gain (damping based on relative velocity)
    - latency: Estimated visual and network delay in seconds
    - invert: Inverts control direction if enabled
    """

    def __init__(self, kp: float = 1.0, kd: float = 0.10, latency: float = 0.05, invert: bool = False):
        self.kp = float(kp)
        self.kd = float(kd)
        self.latency = float(latency)
        self.invert = bool(invert)
        self.integ = 0.0

    def reset(self) -> None:
        """Reset internal integral state."""
        self.integ = 0.0

    def compute(
        self,
        fish_pos: float,
        fish_vel: float,
        bar_pos: float,
        bar_vel: float,
        bar_width: Optional[float],
        dt: float,
    ) -> Tuple[float, float, float]:
        """
        Calculates control signal u, position error e, and velocity error ev.
        Returns: (u, e, ev)
        - u: Control effort clamped to [0.0, 1.0]
        - e: Normalized position error (+1.0 = fish is at the right edge of the bar)
        - ev: Normalized velocity error
        """
        half = max(8.0, (bar_width or 30.0) / 2.0)
        e = (fish_pos - bar_pos) / half
        ev = (fish_vel - bar_vel) / half

        if abs(e) < 0.8:
            self.integ = min(0.3, max(-0.3, self.integ + 0.3 * e * dt))

        u = min(1.0, max(0.0, 0.5 + self.kp * e + self.kd * ev + self.integ))
        if self.invert:
            u = 1.0 - u

        return u, e, ev


class SigmaDeltaModulator:
    """
    Sigma-Delta accumulator converting a continuous signal u in [0.0, 1.0]
    into discrete high-frequency pulses (True=Hold, False=Release).
    """

    def __init__(self, initial_acc: float = 0.5):
        self.acc = float(initial_acc)

    def reset(self, initial_acc: float = 0.5) -> None:
        self.acc = float(initial_acc)

    def step(self, u: float) -> bool:
        """
        Updates accumulator with signal u and returns binary hold state.
        Higher u values yield higher duty cycles.
        """
        self.acc += min(1.0, max(0.0, u))
        if self.acc >= 1.0:
            self.acc -= 1.0
            return True
        return False
