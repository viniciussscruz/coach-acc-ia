from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class TelemetryTick:
    """Single telemetry sample consumed by the pipeline."""

    session_time_s: float
    lap_count: int
    lap_time_s: float
    normalized_spline_pos: float
    speed_kmh: float
    throttle: float
    brake: float
    steer: float
    gear: int
    rpm: int
    steering_angle_deg: Optional[float] = None
    is_in_pit: bool = False
    sector: Optional[int] = None
    track_name: Optional[str] = None
    track_length_m: Optional[float] = None
    car_name: Optional[str] = None
    world_pos_x: Optional[float] = None
    world_pos_y: Optional[float] = None
    world_pos_z: Optional[float] = None
    fuel_l: Optional[float] = None
    fuel_per_lap_l: Optional[float] = None
    fuel_estimated_laps: Optional[float] = None
    race_total_laps: Optional[int] = None
    completed_laps: Optional[int] = None
    laps_remaining: Optional[int] = None
    fuel_will_finish: Optional[bool] = None
    session_time_left_s: Optional[float] = None
    air_temp_c: Optional[float] = None
    road_temp_c: Optional[float] = None
    tire_pressure_fl: Optional[float] = None
    tire_pressure_fr: Optional[float] = None
    tire_pressure_rl: Optional[float] = None
    tire_pressure_rr: Optional[float] = None
    tire_temp_fl: Optional[float] = None
    tire_temp_fr: Optional[float] = None
    tire_temp_rl: Optional[float] = None
    tire_temp_rr: Optional[float] = None
    brake_temp_fl: Optional[float] = None
    brake_temp_fr: Optional[float] = None
    brake_temp_rl: Optional[float] = None
    brake_temp_rr: Optional[float] = None
    slip_ratio_rl: Optional[float] = None
    slip_ratio_rr: Optional[float] = None
    traction_loss_rear: Optional[bool] = None
