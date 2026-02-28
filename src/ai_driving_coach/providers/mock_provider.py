from __future__ import annotations

import math
from typing import Iterator

from ai_driving_coach.models.telemetry import TelemetryTick
from ai_driving_coach.providers.base import TelemetryProvider


class MockTelemetryProvider(TelemetryProvider):
    """Deterministic synthetic laps to test the full pipeline."""

    def __init__(self, tick_rate_hz: int = 20, lap_time_s: float = 95.0) -> None:
        self.tick_rate_hz = tick_rate_hz
        self.lap_time_s = lap_time_s
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def stream(self) -> Iterator[TelemetryTick]:
        if not self._connected:
            raise RuntimeError("Provider not connected.")

        dt = 1.0 / float(self.tick_rate_hz)
        session_time = 0.0
        lap_count = 1
        lap_time = 0.0
        sectors = (0.333, 0.666, 1.0)
        race_total_laps = 20
        fuel_l = 65.0
        fuel_per_lap_l = 2.65
        fuel_rate_per_s = fuel_per_lap_l / self.lap_time_s

        while True:
            normalized_pos = lap_time / self.lap_time_s
            if normalized_pos >= 1.0:
                lap_count += 1
                lap_time = 0.0
                normalized_pos = 0.0

            corner_phase = math.sin(2.0 * math.pi * normalized_pos * 6.0)
            speed = 165.0 - max(0.0, corner_phase) * 85.0
            brake = max(0.0, corner_phase)
            throttle = max(0.0, -corner_phase)
            steer = math.sin(2.0 * math.pi * normalized_pos * 6.0 + 0.5) * 0.6
            gear = max(2, min(6, int(speed // 30)))
            rpm = int(3000 + speed * 45)
            sector = 1 if normalized_pos < sectors[0] else 2 if normalized_pos < sectors[1] else 3
            theta = 2.0 * math.pi * normalized_pos
            world_x = math.cos(theta) * 1000.0
            world_z = math.sin(theta) * 800.0
            air_temp_c = 23.0 + math.sin(session_time * 0.01) * 1.2
            road_temp_c = 31.0 + math.sin(session_time * 0.008) * 2.3
            tire_temp_fl = 82.0 + abs(math.sin(theta * 1.2)) * 8.5
            tire_temp_fr = 83.0 + abs(math.sin(theta * 1.1 + 0.2)) * 8.2
            tire_temp_rl = 84.0 + abs(math.sin(theta * 1.0 + 0.8)) * 9.0
            tire_temp_rr = 84.0 + abs(math.sin(theta * 1.0 + 1.0)) * 9.3
            tire_pressure_fl = 27.4 + math.sin(theta * 0.8) * 0.4
            tire_pressure_fr = 27.5 + math.sin(theta * 0.8 + 0.2) * 0.4
            tire_pressure_rl = 27.2 + math.sin(theta * 0.8 + 0.9) * 0.5
            tire_pressure_rr = 27.3 + math.sin(theta * 0.8 + 1.1) * 0.5
            brake_temp_base = 420.0 + brake * 290.0
            brake_temp_fl = brake_temp_base + abs(steer) * 35.0
            brake_temp_fr = brake_temp_base + abs(steer) * 30.0
            brake_temp_rl = 300.0 + brake * 210.0
            brake_temp_rr = 300.0 + brake * 205.0
            slip_ratio_rl = throttle * 0.15 * math.sin(theta * 2.5 + 0.4)
            slip_ratio_rr = throttle * 0.15 * math.sin(theta * 2.5 + 1.0)
            traction_loss_rear = throttle > 0.6 and (abs(slip_ratio_rl) > 0.10 or abs(slip_ratio_rr) > 0.10)
            completed_laps = max(0, lap_count - 1)
            laps_remaining = max(0, race_total_laps - completed_laps)
            fuel_estimated_laps = fuel_l / fuel_per_lap_l if fuel_per_lap_l > 0.0 else None
            fuel_will_finish = fuel_estimated_laps is not None and fuel_estimated_laps + 0.15 >= laps_remaining

            yield TelemetryTick(
                session_time_s=session_time,
                lap_count=lap_count,
                lap_time_s=lap_time,
                normalized_spline_pos=normalized_pos,
                speed_kmh=speed,
                throttle=throttle,
                brake=brake,
                steer=steer,
                steering_angle_deg=steer * (180.0 / math.pi),
                gear=gear,
                rpm=rpm,
                is_in_pit=False,
                sector=sector,
                track_name="spa",
                track_length_m=7004.0,
                car_name="bmw_m4_gt3",
                world_pos_x=world_x,
                world_pos_y=0.0,
                world_pos_z=world_z,
                fuel_l=max(0.0, fuel_l),
                fuel_per_lap_l=fuel_per_lap_l,
                fuel_estimated_laps=fuel_estimated_laps,
                race_total_laps=race_total_laps,
                completed_laps=completed_laps,
                laps_remaining=laps_remaining,
                fuel_will_finish=fuel_will_finish,
                session_time_left_s=max(0.0, (race_total_laps * self.lap_time_s) - session_time),
                air_temp_c=air_temp_c,
                road_temp_c=road_temp_c,
                tire_pressure_fl=tire_pressure_fl,
                tire_pressure_fr=tire_pressure_fr,
                tire_pressure_rl=tire_pressure_rl,
                tire_pressure_rr=tire_pressure_rr,
                tire_temp_fl=tire_temp_fl,
                tire_temp_fr=tire_temp_fr,
                tire_temp_rl=tire_temp_rl,
                tire_temp_rr=tire_temp_rr,
                brake_temp_fl=brake_temp_fl,
                brake_temp_fr=brake_temp_fr,
                brake_temp_rl=brake_temp_rl,
                brake_temp_rr=brake_temp_rr,
                slip_ratio_rl=slip_ratio_rl,
                slip_ratio_rr=slip_ratio_rr,
                traction_loss_rear=traction_loss_rear,
            )

            session_time += dt
            lap_time += dt
            fuel_l -= fuel_rate_per_s * dt

    def close(self) -> None:
        self._connected = False
