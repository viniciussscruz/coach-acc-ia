from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Deque, Dict, List

from ai_driving_coach.benchmarks.models import BenchmarkReference
from ai_driving_coach.coaching.realtime_coach import CoachMessage
from ai_driving_coach.models.telemetry import TelemetryTick


@dataclass(slots=True)
class DashboardState:
    provider_name: str
    config_view: Dict[str, Any]
    started_at: float = field(default_factory=time.time)
    status: str = "booting"
    tick_count: int = 0
    last_tick: Dict[str, Any] = field(default_factory=dict)
    track_progress: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=15000))
    timing: Dict[str, Any] = field(default_factory=dict)
    benchmark_reference: Dict[str, Any] = field(default_factory=dict)
    recent_laps: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=12))
    recent_messages: Deque[Dict[str, Any]] = field(default_factory=lambda: deque(maxlen=30))
    _lock: Lock = field(default_factory=Lock)

    def set_status(self, status: str) -> None:
        with self._lock:
            self.status = status

    def update_tick(self, tick: TelemetryTick, tick_count: int) -> None:
        with self._lock:
            previous_track = self.last_tick.get("track_name")
            if previous_track and tick.track_name and previous_track != tick.track_name:
                self.track_progress.clear()
            self.tick_count = tick_count
            self.last_tick = {
                "session_time_s": round(tick.session_time_s, 3),
                "lap_count": tick.lap_count,
                "lap_time_s": round(tick.lap_time_s, 3),
                "sector": tick.sector,
                "spline": round(tick.normalized_spline_pos, 5),
                "speed_kmh": round(tick.speed_kmh, 2),
                "throttle": round(tick.throttle, 3),
                "brake": round(tick.brake, 3),
                "steer": round(tick.steer, 3),
                "steering_angle_deg": round(tick.steering_angle_deg, 2) if tick.steering_angle_deg is not None else None,
                "gear": tick.gear,
                "rpm": tick.rpm,
                "is_in_pit": tick.is_in_pit,
                "track_name": tick.track_name,
                "track_length_m": tick.track_length_m,
                "car_name": tick.car_name,
                "world_pos_x": tick.world_pos_x,
                "world_pos_z": tick.world_pos_z,
                "fuel_l": round(tick.fuel_l, 2) if tick.fuel_l is not None else None,
                "fuel_estimated_laps": (
                    round(tick.fuel_estimated_laps, 2) if tick.fuel_estimated_laps is not None else None
                ),
                "laps_remaining": tick.laps_remaining,
                "fuel_will_finish": tick.fuel_will_finish,
            }
            self.track_progress.append(
                {
                    "spline": round(tick.normalized_spline_pos, 5),
                    "speed_kmh": round(tick.speed_kmh, 2),
                    "sector": tick.sector,
                    "world_x": round(tick.world_pos_x, 3) if tick.world_pos_x is not None else None,
                    "world_z": round(tick.world_pos_z, 3) if tick.world_pos_z is not None else None,
                }
            )

    def update_timing(self, timing_snapshot: Dict[str, Any]) -> None:
        with self._lock:
            self.timing = dict(timing_snapshot)

    def set_benchmark_reference(self, reference: BenchmarkReference | None) -> None:
        with self._lock:
            if reference is None:
                self.benchmark_reference = {}
                return
            self.benchmark_reference = {
                "track_slug": reference.track_slug,
                "track_name": reference.track_name,
                "car_slug": reference.car_slug,
                "car_name": reference.car_name,
                "car_class": reference.car_class,
                "condition": reference.condition,
                "lap_time_s": round(reference.lap_time_s, 3),
                "lap_time_text": reference.lap_time_text,
                "source_url": reference.source_url,
                "scope": reference.scope,
                "requested_condition": reference.requested_condition,
            }

    def add_coach_message(self, message: CoachMessage) -> None:
        with self._lock:
            self.recent_messages.appendleft(
                {
                    "lap_number": message.lap_number,
                    "corner_index": message.corner_index,
                    "text": message.text,
                    "severity": message.severity,
                    "category": message.category,
                    "ts": round(time.time() - self.started_at, 2),
                }
            )

    def add_lap_result(
        self,
        lap_number: int,
        lap_time_s: float,
        is_best_lap: bool,
        delta_to_best_lap_s: float,
        summary: List[str],
        features_count: int,
        track_name: str | None = None,
        car_name: str | None = None,
    ) -> None:
        with self._lock:
            self.recent_laps.appendleft(
                {
                    "lap_number": lap_number,
                    "lap_time_s": round(lap_time_s, 3),
                    "is_best_lap": is_best_lap,
                    "delta_to_best_lap_s": round(delta_to_best_lap_s, 3),
                    "summary": list(summary),
                    "features_count": features_count,
                    "track_name": track_name,
                    "car_name": car_name,
                }
            )

    def set_lap_sector_data(
        self,
        lap_number: int,
        sectors: Dict[int, float],
        sector_deltas_to_best: Dict[int, float],
        theoretical_best_s: float | None,
    ) -> None:
        with self._lock:
            for item in self.recent_laps:
                if item.get("lap_number") == lap_number:
                    item["sectors"] = {int(k): round(v, 3) for k, v in sectors.items()}
                    item["sector_deltas_to_best"] = {
                        int(k): round(v, 3) for k, v in sector_deltas_to_best.items()
                    }
                    item["theoretical_best_s"] = (
                        round(theoretical_best_s, 3) if theoretical_best_s is not None else None
                    )
                    break

    def set_lap_benchmark_data(
        self,
        lap_number: int,
        benchmark_gap_s: float,
        benchmark_percent: float,
        benchmark_scope: str,
        benchmark_reference_lap_s: float,
    ) -> None:
        with self._lock:
            for item in self.recent_laps:
                if item.get("lap_number") == lap_number:
                    item["benchmark_gap_s"] = round(benchmark_gap_s, 3)
                    item["benchmark_percent"] = round(benchmark_percent, 2)
                    item["benchmark_scope"] = benchmark_scope
                    item["benchmark_reference_lap_s"] = round(benchmark_reference_lap_s, 3)
                    break

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "provider": self.provider_name,
                "uptime_s": round(time.time() - self.started_at, 2),
                "tick_count": self.tick_count,
                "last_tick": dict(self.last_tick),
                "track_progress": list(self.track_progress),
                "timing": dict(self.timing),
                "benchmark_reference": dict(self.benchmark_reference),
                "recent_laps": list(self.recent_laps),
                "recent_messages": list(self.recent_messages),
                "config": dict(self.config_view),
            }
