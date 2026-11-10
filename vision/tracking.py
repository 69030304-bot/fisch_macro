"""
vision/tracking.py - Real-time predictive object tracking using Exponential Moving Averages (EMA).
"""
import math
from typing import Optional


class Track:
    """
    Tracks horizontal coordinate and velocity using an Exponential Moving Average (EMA).
    Enables forward-projection to compensate for visual and input latency.
    """
    TAU = 0.05  # Time constant in seconds for smoothing

    def __init__(self):
        self.x: Optional[float] = None
        self.v: float = 0.0
        self.t: float = 0.0

    def update(self, z: float, t: float) -> None:
        """Update tracked position z at timestamp t."""
        if self.x is None or (t - self.t) > 0.3:
            self.x, self.v, self.t = float(z), 0.0, float(t)
            return
        dt = max(t - self.t, 1e-3)
        a = 1.0 - math.exp(-dt / self.TAU)
        self.v += a * ((z - self.x) / dt - self.v)
        self.x, self.t = float(z), float(t)

    def fresh(self, now: float, max_age: float = 0.15) -> bool:
        """Returns True if the tracked object was seen within max_age seconds."""
        return self.x is not None and (now - self.t) <= max_age

    def pos(self, t: float) -> Optional[float]:
        """
        Projects object position forward to future timestamp t (clamped to +0.12s)
        using current estimated velocity.
        """
        if self.x is None:
            return None
        dt_forward = min(max(t - self.t, 0.0), 0.12)
        return self.x + self.v * dt_forward

    def reset(self) -> None:
        """Reset tracking state."""
        self.x = None
        self.v = 0.0
        self.t = 0.0
