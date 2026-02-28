from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from ai_driving_coach.models.telemetry import TelemetryTick


@dataclass(slots=True)
class Event:
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TickEvent(Event):
    tick: TelemetryTick = field(default_factory=lambda: TelemetryTick(0.0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0, 0))

    def __init__(self, tick: TelemetryTick):
        super().__init__(name="tick", payload={"tick": tick})
        self.tick = tick

