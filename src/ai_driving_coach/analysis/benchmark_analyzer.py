from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai_driving_coach.benchmarks.models import BenchmarkReference
from ai_driving_coach.benchmarks.repository import BenchmarkRepository


@dataclass(slots=True)
class BenchmarkLapResult:
    lap_number: int
    lap_time_s: float
    reference_lap_time_s: float
    gap_s: float
    gap_percent: float
    scope: str
    reference: BenchmarkReference


class BenchmarkAnalyzer:
    """Tracks session context and compares laps against external benchmark references."""

    def __init__(self, repository: BenchmarkRepository, condition: str = "overall") -> None:
        self.repository = repository
        self.condition = condition
        self.current_reference: Optional[BenchmarkReference] = None
        self._context_key: tuple[str, str, str] | None = None

    def update_context(self, track_name: str | None, car_name: str | None) -> Optional[BenchmarkReference]:
        key = ((track_name or "").strip(), (car_name or "").strip(), self.condition)
        if self._context_key == key:
            return self.current_reference
        self._context_key = key
        self.current_reference = self.repository.find_reference(
            track_name=track_name,
            car_name=car_name,
            condition=self.condition,
        )
        return self.current_reference

    def compare_lap(
        self,
        lap_number: int,
        lap_time_s: float,
        track_name: str | None,
        car_name: str | None,
    ) -> Optional[BenchmarkLapResult]:
        reference = self.update_context(track_name=track_name, car_name=car_name)
        if reference is None:
            return None
        gap = lap_time_s - reference.lap_time_s
        gap_percent = 0.0
        if reference.lap_time_s > 0.0:
            gap_percent = (gap / reference.lap_time_s) * 100.0
        return BenchmarkLapResult(
            lap_number=lap_number,
            lap_time_s=lap_time_s,
            reference_lap_time_s=reference.lap_time_s,
            gap_s=gap,
            gap_percent=gap_percent,
            scope=reference.scope,
            reference=reference,
        )

