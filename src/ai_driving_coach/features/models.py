from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional


@dataclass(slots=True)
class CornerFeature:
    lap_number: int
    corner_index: int
    brake_start_point: float
    turn_in_point: float
    apex_point: float
    brake_peak: float
    brake_duration: float
    min_speed: float
    throttle_on_point: float
    exit_stabilization_point: float
    time_to_full_throttle: float
    exit_speed: float
    track_name: Optional[str] = None
    track_length_m: Optional[float] = None

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
