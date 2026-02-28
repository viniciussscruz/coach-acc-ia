from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ai_driving_coach.features.models import CornerFeature


@dataclass(slots=True)
class CoachMessage:
    lap_number: int
    corner_index: int
    text: str
    severity: str = "info"
    category: str = "general"


class RealtimeCoach:
    """Rule-based realtime coach using corner baseline comparison."""

    def __init__(self) -> None:
        self.best_lap_features: Dict[int, CornerFeature] = {}
        self.current_messages: List[CoachMessage] = []
        self.baseline_label: str = "session_best"
        self.track_length_m: float = 0.0

    def set_baseline(self, features: List[CornerFeature], label: str, track_length_m: float = 0.0) -> None:
        self.best_lap_features = {f.corner_index: f for f in features}
        self.baseline_label = label
        self.track_length_m = max(0.0, track_length_m)

    def update_best_lap(self, features: List[CornerFeature], track_length_m: float = 0.0) -> None:
        self.set_baseline(features=features, label="session_best", track_length_m=track_length_m)

    def evaluate_corner(self, feature: CornerFeature) -> Optional[CoachMessage]:
        baseline = self.best_lap_features.get(feature.corner_index)
        if baseline is None:
            return None

        track_length_m = self._resolve_track_length(feature, baseline)
        brake_delta_m = self._delta_m(feature.brake_start_point - baseline.brake_start_point, track_length_m)
        turn_in_delta_m = self._delta_m(feature.turn_in_point - baseline.turn_in_point, track_length_m)
        apex_delta_m = self._delta_m(feature.apex_point - baseline.apex_point, track_length_m)
        throttle_delta_m = self._delta_m(feature.throttle_on_point - baseline.throttle_on_point, track_length_m)

        if brake_delta_m <= -6.0:
            return self._push(feature, "Freou cedo.", "warn", "brake")
        if brake_delta_m >= 6.0:
            return self._push(feature, "Freou tarde.", "critical", "brake")

        if feature.min_speed < baseline.min_speed - 3.0:
            return self._push(feature, "Entrada de curva lenta.", "warn", "entry")

        if turn_in_delta_m <= -4.0:
            return self._push(feature, "Entrada antecipada.", "warn", "turn_in")
        if turn_in_delta_m >= 4.0:
            return self._push(feature, "Entrada tardia.", "warn", "turn_in")

        if apex_delta_m <= -3.0:
            return self._push(feature, "Apex antecipado.", "warn", "apex")
        if apex_delta_m >= 3.0:
            return self._push(feature, "Apex atrasado.", "warn", "apex")

        if throttle_delta_m >= 5.0:
            return self._push(feature, "Acelerou tarde.", "warn", "throttle")
        if feature.time_to_full_throttle > baseline.time_to_full_throttle + 0.25:
            return self._push(feature, "Aceleracao lenta na saida.", "warn", "throttle")
        if feature.exit_speed < baseline.exit_speed - 3.5:
            return self._push(feature, "Saida de curva lenta.", "warn", "exit")
        return None

    def _push(self, feature: CornerFeature, text: str, severity: str, category: str) -> CoachMessage:
        message = CoachMessage(
            lap_number=feature.lap_number,
            corner_index=feature.corner_index,
            text=text,
            severity=severity,
            category=category,
        )
        self.current_messages.append(message)
        return message

    def _resolve_track_length(self, feature: CornerFeature, baseline: CornerFeature) -> float:
        if feature.track_length_m and feature.track_length_m > 0.0:
            return feature.track_length_m
        if baseline.track_length_m and baseline.track_length_m > 0.0:
            return baseline.track_length_m
        return self.track_length_m

    def _delta_m(self, delta_spline: float, track_length_m: float) -> float:
        if track_length_m <= 0.0:
            return delta_spline * 100.0
        return delta_spline * track_length_m
