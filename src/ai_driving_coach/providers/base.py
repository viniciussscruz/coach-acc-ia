from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator

from ai_driving_coach.models.telemetry import TelemetryTick


class TelemetryProvider(ABC):
    """Telemetry source abstraction (ACC shared memory, mock, replay, etc)."""

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def stream(self) -> Iterator[TelemetryTick]:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

