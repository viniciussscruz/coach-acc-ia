from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ai_driving_coach.core.event_bus import EventBus
from ai_driving_coach.core.events import Event
from ai_driving_coach.features.models import CornerFeature
from ai_driving_coach.models.telemetry import TelemetryTick


@dataclass(slots=True)
class CornerCaptureState:
    in_corner: bool = False
    lap_number: int = 0
    corner_index: int = 0
    start_time_s: float = 0.0
    brake_start_point: float = 0.0
    turn_in_point: float = 0.0
    apex_point: float = 0.0
    brake_peak: float = 0.0
    min_speed: float = 999.0
    throttle_on_point: float = 0.0
    throttle_on_time_s: float = 0.0
    full_throttle_time_s: Optional[float] = None
    exit_stabilization_point: float = 0.0
    exit_speed: float = 0.0
    track_name: Optional[str] = None
    track_length_m: Optional[float] = None


class FeatureExtractor:
    """Extracts corner-level metrics from telemetry ticks."""

    def __init__(
        self,
        event_bus: EventBus,
        brake_threshold: float = 0.15,
        throttle_threshold: float = 0.20,
        full_throttle_threshold: float = 0.95,
        turn_in_steer_threshold: float = 0.12,
        stabilize_steer_threshold: float = 0.10,
    ) -> None:
        self.event_bus = event_bus
        self.brake_threshold = brake_threshold
        self.throttle_threshold = throttle_threshold
        self.full_throttle_threshold = full_throttle_threshold
        self.turn_in_steer_threshold = turn_in_steer_threshold
        self.stabilize_steer_threshold = stabilize_steer_threshold
        self._state = CornerCaptureState()
        self._lap_features: Dict[int, List[CornerFeature]] = {}

    def process_tick(self, tick: TelemetryTick) -> None:
        if tick.lap_count not in self._lap_features:
            self._lap_features[tick.lap_count] = []

        if (not self._state.in_corner) and tick.brake >= self.brake_threshold:
            self._start_corner(tick)
            return

        if not self._state.in_corner:
            return

        self._state.brake_peak = max(self._state.brake_peak, tick.brake)
        if tick.speed_kmh <= self._state.min_speed:
            self._state.min_speed = tick.speed_kmh
            self._state.apex_point = tick.normalized_spline_pos
        self._state.exit_speed = tick.speed_kmh

        if self._state.turn_in_point == 0.0 and abs(tick.steer) >= self.turn_in_steer_threshold:
            self._state.turn_in_point = tick.normalized_spline_pos

        if self._state.throttle_on_time_s == 0.0 and tick.throttle >= self.throttle_threshold:
            self._state.throttle_on_time_s = tick.session_time_s
            self._state.throttle_on_point = tick.normalized_spline_pos

        if (
            self._state.throttle_on_time_s > 0.0
            and self._state.full_throttle_time_s is None
            and tick.throttle >= self.full_throttle_threshold
        ):
            self._state.full_throttle_time_s = tick.session_time_s

        if (
            self._state.exit_stabilization_point == 0.0
            and self._state.throttle_on_time_s > 0.0
            and tick.brake <= 0.05
            and abs(tick.steer) <= self.stabilize_steer_threshold
        ):
            self._state.exit_stabilization_point = tick.normalized_spline_pos

        # Corner considered complete after throttle returns and brake is fully released.
        if (
            self._state.throttle_on_time_s > 0.0
            and tick.throttle >= self.throttle_threshold
            and tick.brake <= 0.05
            and tick.speed_kmh >= self._state.min_speed + 12.0
        ):
            self._finalize_corner(tick)

    def finalize_lap(self, lap_number: int) -> None:
        # If a corner is still open at lap end, close it with available data.
        if self._state.in_corner and self._state.lap_number == lap_number:
            fake_tick = TelemetryTick(
                session_time_s=self._state.start_time_s,
                lap_count=lap_number,
                lap_time_s=0.0,
                normalized_spline_pos=1.0,
                speed_kmh=self._state.exit_speed,
                throttle=0.0,
                brake=0.0,
                steer=0.0,
                gear=0,
                rpm=0,
            )
            self._finalize_corner(fake_tick)

        self.event_bus.publish(
            Event(
                name="lap_features_ready",
                payload={
                    "lap_number": lap_number,
                    "features": [feature.to_dict() for feature in self._lap_features.get(lap_number, [])],
                },
            )
        )

    def get_lap_features(self, lap_number: int) -> List[CornerFeature]:
        return list(self._lap_features.get(lap_number, []))

    def _start_corner(self, tick: TelemetryTick) -> None:
        next_corner_index = len(self._lap_features[tick.lap_count]) + 1
        self._state = CornerCaptureState(
            in_corner=True,
            lap_number=tick.lap_count,
            corner_index=next_corner_index,
            start_time_s=tick.session_time_s,
            brake_start_point=tick.normalized_spline_pos,
            turn_in_point=tick.normalized_spline_pos,
            apex_point=tick.normalized_spline_pos,
            brake_peak=tick.brake,
            min_speed=tick.speed_kmh,
            exit_speed=tick.speed_kmh,
            track_name=tick.track_name,
            track_length_m=tick.track_length_m,
        )

    def _finalize_corner(self, tick: TelemetryTick) -> None:
        if not self._state.in_corner:
            return
        brake_duration = max(0.0, tick.session_time_s - self._state.start_time_s)
        full_throttle_time = self._state.full_throttle_time_s or tick.session_time_s
        throttle_reference_time = self._state.throttle_on_time_s or tick.session_time_s
        time_to_full_throttle = max(0.0, full_throttle_time - throttle_reference_time)

        feature = CornerFeature(
            lap_number=self._state.lap_number,
            corner_index=self._state.corner_index,
            brake_start_point=self._state.brake_start_point,
            turn_in_point=self._state.turn_in_point or self._state.brake_start_point,
            apex_point=self._state.apex_point or tick.normalized_spline_pos,
            brake_peak=self._state.brake_peak,
            brake_duration=brake_duration,
            min_speed=self._state.min_speed,
            throttle_on_point=self._state.throttle_on_point or tick.normalized_spline_pos,
            exit_stabilization_point=self._state.exit_stabilization_point or tick.normalized_spline_pos,
            time_to_full_throttle=time_to_full_throttle,
            exit_speed=self._state.exit_speed,
            track_name=self._state.track_name,
            track_length_m=self._state.track_length_m,
        )
        self._lap_features.setdefault(feature.lap_number, []).append(feature)

        self.event_bus.publish(
            Event(
                name="corner_feature_completed",
                payload={"lap_number": feature.lap_number, "feature": feature.to_dict()},
            )
        )

        self._state = CornerCaptureState()
