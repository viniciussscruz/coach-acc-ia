from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(slots=True)
class LapTimingData:
    lap_number: int
    lap_time_s: float
    sectors: Dict[int, float] = field(default_factory=dict)
    is_best_lap: bool = False
    delta_to_best_lap_s: float = 0.0
    theoretical_best_s: Optional[float] = None
    sector_deltas_to_best: Dict[int, float] = field(default_factory=dict)


class SessionTimingAnalyzer:
    """Tracks lap and sector performance over a session."""

    def __init__(self) -> None:
        self.current_lap_number: Optional[int] = None
        self.current_lap_start_s: Optional[float] = None
        self.current_sector: Optional[int] = None
        self.current_sector_start_s: Optional[float] = None
        self.current_sector_times: Dict[int, float] = {}

        self.best_lap_time_s: Optional[float] = None
        self.best_lap_number: Optional[int] = None
        self.best_sector_times: Dict[int, float] = {}

        self.last_lap_timing: Optional[LapTimingData] = None

    def on_lap_started(self, lap_number: int, session_time_s: float, sector: int = 1) -> None:
        self.current_lap_number = lap_number
        self.current_lap_start_s = session_time_s
        self.current_sector = max(1, min(3, sector))
        self.current_sector_start_s = session_time_s
        self.current_sector_times = {}

    def on_sector_changed(self, from_sector: Optional[int], to_sector: Optional[int], session_time_s: float) -> None:
        if from_sector is None:
            self.current_sector = to_sector
            self.current_sector_start_s = session_time_s
            return
        if self.current_sector_start_s is None:
            self.current_sector_start_s = session_time_s
            self.current_sector = to_sector
            return

        sector_time = max(0.0, session_time_s - self.current_sector_start_s)
        self.current_sector_times[from_sector] = sector_time
        self._update_best_sector(from_sector, sector_time)

        self.current_sector = to_sector
        self.current_sector_start_s = session_time_s

    def on_lap_finished(self, lap_number: int, lap_time_s: float, session_time_s: float) -> LapTimingData:
        sectors = dict(self.current_sector_times)

        # Close open sector (typically sector 3) at lap finish.
        if self.current_sector is not None and self.current_sector_start_s is not None:
            if self.current_sector not in sectors:
                sector_time = max(0.0, session_time_s - self.current_sector_start_s)
                sectors[self.current_sector] = sector_time
                self._update_best_sector(self.current_sector, sector_time)

        is_best_lap = self.best_lap_time_s is None or lap_time_s < self.best_lap_time_s
        if is_best_lap:
            self.best_lap_time_s = lap_time_s
            self.best_lap_number = lap_number

        delta_to_best = 0.0 if self.best_lap_time_s is None else lap_time_s - self.best_lap_time_s
        theoretical_best = None
        if all(s in self.best_sector_times for s in (1, 2, 3)):
            theoretical_best = self.best_sector_times[1] + self.best_sector_times[2] + self.best_sector_times[3]

        sector_deltas_to_best: Dict[int, float] = {}
        for sector in (1, 2, 3):
            if sector in sectors and sector in self.best_sector_times:
                sector_deltas_to_best[sector] = sectors[sector] - self.best_sector_times[sector]

        timing = LapTimingData(
            lap_number=lap_number,
            lap_time_s=lap_time_s,
            sectors=sectors,
            is_best_lap=is_best_lap,
            delta_to_best_lap_s=delta_to_best,
            theoretical_best_s=theoretical_best,
            sector_deltas_to_best=sector_deltas_to_best,
        )
        self.last_lap_timing = timing
        return timing

    def snapshot(self) -> Dict[str, object]:
        return {
            "current_lap_number": self.current_lap_number,
            "current_sector": self.current_sector,
            "current_sector_times": dict(self.current_sector_times),
            "best_lap_time_s": self.best_lap_time_s,
            "best_lap_number": self.best_lap_number,
            "best_sector_times": dict(self.best_sector_times),
            "theoretical_best_s": (
                self.best_sector_times[1] + self.best_sector_times[2] + self.best_sector_times[3]
                if all(s in self.best_sector_times for s in (1, 2, 3))
                else None
            ),
            "last_lap_timing": self._timing_to_dict(self.last_lap_timing),
        }

    def _update_best_sector(self, sector: int, sector_time: float) -> None:
        current_best = self.best_sector_times.get(sector)
        if current_best is None or sector_time < current_best:
            self.best_sector_times[sector] = sector_time

    def _timing_to_dict(self, timing: Optional[LapTimingData]) -> Optional[Dict[str, object]]:
        if timing is None:
            return None
        return {
            "lap_number": timing.lap_number,
            "lap_time_s": timing.lap_time_s,
            "sectors": dict(timing.sectors),
            "is_best_lap": timing.is_best_lap,
            "delta_to_best_lap_s": timing.delta_to_best_lap_s,
            "theoretical_best_s": timing.theoretical_best_s,
            "sector_deltas_to_best": dict(timing.sector_deltas_to_best),
        }
