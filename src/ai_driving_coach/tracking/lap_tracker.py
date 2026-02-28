from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ai_driving_coach.core.event_bus import EventBus
from ai_driving_coach.core.events import Event
from ai_driving_coach.models.telemetry import TelemetryTick


@dataclass(slots=True)
class LapTrackerState:
    current_lap: Optional[int] = None
    current_sector: Optional[int] = None
    lap_start_session_time: Optional[float] = None


class LapTracker:
    """Detects lap transitions and sector changes from telemetry stream."""

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.state = LapTrackerState()

    def process_tick(self, tick: TelemetryTick) -> None:
        if self.state.current_lap is None:
            self.state.current_lap = tick.lap_count
            self.state.current_sector = tick.sector
            self.state.lap_start_session_time = tick.session_time_s
            self.event_bus.publish(
                Event(
                    name="lap_started",
                    payload={
                        "lap_number": tick.lap_count,
                        "session_time_s": tick.session_time_s,
                        "sector": tick.sector,
                    },
                )
            )
            return

        if tick.lap_count != self.state.current_lap:
            lap_duration = (
                tick.session_time_s - self.state.lap_start_session_time
                if self.state.lap_start_session_time is not None
                else tick.lap_time_s
            )
            finished_lap = self.state.current_lap
            self.event_bus.publish(
                Event(
                    name="lap_finished",
                    payload={
                        "lap_number": finished_lap,
                        "lap_time_s": max(0.0, lap_duration),
                        "session_time_s": tick.session_time_s,
                    },
                )
            )
            self.state.current_lap = tick.lap_count
            self.state.current_sector = tick.sector
            self.state.lap_start_session_time = tick.session_time_s
            self.event_bus.publish(
                Event(
                    name="lap_started",
                    payload={
                        "lap_number": tick.lap_count,
                        "session_time_s": tick.session_time_s,
                        "sector": tick.sector,
                    },
                )
            )
            return

        if tick.sector and tick.sector != self.state.current_sector:
            old_sector = self.state.current_sector
            self.state.current_sector = tick.sector
            self.event_bus.publish(
                Event(
                    name="sector_changed",
                    payload={
                        "lap_number": tick.lap_count,
                        "from_sector": old_sector,
                        "to_sector": tick.sector,
                        "session_time_s": tick.session_time_s,
                    },
                )
            )
