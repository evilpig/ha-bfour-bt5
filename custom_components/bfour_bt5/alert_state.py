"""Pure per-probe alert state; targets are stored in Celsius."""
from dataclasses import dataclass
import math


@dataclass
class ProbeAlerts:
    target_c: float = 60.0
    armed: bool = False
    armed_at: float | None = None
    last_valid_at: float | None = None
    current_c: float | None = None
    target_reached: bool = False
    stale: bool = False

    def evaluate(self, now, stale_seconds):
        if not self.armed:
            self.target_reached = False
            self.stale = False
            return
        baseline = max(self.armed_at if self.armed_at is not None else now,
                       self.last_valid_at if self.last_valid_at is not None else 0)
        self.stale = now - baseline >= stale_seconds
        if (not self.stale and self.current_c is not None and self.last_valid_at is not None
                and now - self.last_valid_at < stale_seconds and self.current_c >= self.target_c):
            self.target_reached = True

    def record(self, value, now, stale_seconds):
        self.current_c = value
        if value is not None:
            self.last_valid_at = now
        self.evaluate(now, stale_seconds)

    def set_armed(self, armed, now, stale_seconds):
        if armed and not self.armed:
            self.armed_at = now
            self.target_reached = False
        self.armed = armed
        self.evaluate(now, stale_seconds)

    def set_target(self, value, now, stale_seconds):
        if not math.isfinite(value) or not 0 <= value <= 300:
            raise ValueError("Target must be between 0 and 300 Celsius")
        self.target_c = value
        self.target_reached = False
        self.evaluate(now, stale_seconds)

    def serialize(self):
        return {key: getattr(self, key) for key in (
            "target_c", "armed", "armed_at", "last_valid_at", "target_reached"
        )}

    @classmethod
    def restore(cls, data):
        target = data.get("target_c", 60.0)
        if not isinstance(target, (int, float)) or not math.isfinite(target) or not 0 <= target <= 300:
            target = 60.0
        def timestamp(key):
            value = data.get(key)
            return value if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None
        return cls(target_c=target, armed=data.get("armed") is True,
                   armed_at=timestamp("armed_at"), last_valid_at=timestamp("last_valid_at"),
                   target_reached=data.get("target_reached") is True)
