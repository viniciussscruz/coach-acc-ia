from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Dict, List, Optional

from ai_driving_coach.features.models import CornerFeature


@dataclass(slots=True)
class LapAnalysisResult:
    lap_number: int
    is_best_lap: bool
    delta_to_best_lap_s: float
    summary: List[str] = field(default_factory=list)


class PostLapAnalyzer:
    """Compares current lap features to best lap in session."""

    def __init__(self) -> None:
        self.best_lap_number: Optional[int] = None
        self.best_lap_time_s: Optional[float] = None
        self.features_by_lap: Dict[int, List[CornerFeature]] = {}

    def register_lap(self, lap_number: int, lap_time_s: float, features: List[CornerFeature]) -> LapAnalysisResult:
        self.features_by_lap[lap_number] = features

        is_best = self.best_lap_time_s is None or lap_time_s < self.best_lap_time_s
        if is_best:
            self.best_lap_time_s = lap_time_s
            self.best_lap_number = lap_number

        delta = 0.0 if self.best_lap_time_s is None else lap_time_s - self.best_lap_time_s
        summary = self._build_summary(lap_number, features)
        return LapAnalysisResult(
            lap_number=lap_number,
            is_best_lap=is_best,
            delta_to_best_lap_s=delta,
            summary=summary,
        )

    def get_best_lap_features(self) -> List[CornerFeature]:
        if self.best_lap_number is None:
            return []
        return self.features_by_lap.get(self.best_lap_number, [])

    def _build_summary(self, lap_number: int, current: List[CornerFeature]) -> List[str]:
        if self.best_lap_number is None or self.best_lap_number == lap_number:
            return ["Volta de referencia atualizada."]

        baseline = self.features_by_lap.get(self.best_lap_number, [])
        if not baseline or not current:
            return ["Dados insuficientes para comparacao."]

        baseline_by_corner = {f.corner_index: f for f in baseline}
        matched = [f for f in current if f.corner_index in baseline_by_corner]
        if not matched:
            return ["Sem curvas comparaveis nesta volta."]

        exit_delta = mean(
            f.exit_speed - baseline_by_corner[f.corner_index].exit_speed for f in matched
        )
        throttle_delta = mean(
            f.time_to_full_throttle - baseline_by_corner[f.corner_index].time_to_full_throttle
            for f in matched
        )
        brake_point_delta = mean(
            f.brake_start_point - baseline_by_corner[f.corner_index].brake_start_point for f in matched
        )
        turn_in_delta = mean(
            f.turn_in_point - baseline_by_corner[f.corner_index].turn_in_point for f in matched
        )
        apex_delta = mean(
            f.apex_point - baseline_by_corner[f.corner_index].apex_point for f in matched
        )

        lines = [f"Delta medio de velocidade de saida: {exit_delta:+.2f} km/h."]
        lines.append(f"Delta medio de tempo ate full throttle: {throttle_delta:+.2f} s.")
        lines.append(f"Delta medio de ponto de freada: {brake_point_delta:+.4f} spline.")
        lines.append(f"Delta medio de turn-in: {turn_in_delta:+.4f} spline.")
        lines.append(f"Delta medio de apex: {apex_delta:+.4f} spline.")
        return lines
