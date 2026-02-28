from __future__ import annotations

import csv
import math
import time
from pathlib import Path
from typing import Iterator, List

import pyarrow.parquet as pq

from ai_driving_coach.models.telemetry import TelemetryTick
from ai_driving_coach.providers.base import TelemetryProvider


def _to_bool(raw: str) -> bool:
    return str(raw).strip().lower() in {"1", "true", "yes", "y"}


def _opt_float(raw: object) -> float | None:
    if raw in (None, "", "None"):
        return None
    return float(raw)


def _opt_int(raw: object) -> int | None:
    if raw in (None, "", "None"):
        return None
    return int(raw)


def _opt_bool(raw: object) -> bool | None:
    if raw in (None, "", "None"):
        return None
    if isinstance(raw, bool):
        return raw
    return _to_bool(str(raw))


class ReplayTelemetryProvider(TelemetryProvider):
    """Plays back telemetry ticks from CSV/Parquet files."""

    def __init__(self, replay_file: str, speed: float = 1.0) -> None:
        self.replay_file = replay_file
        self.speed = max(0.0, speed)
        self._connected = False
        self._ticks: List[TelemetryTick] = []

    def connect(self) -> None:
        file_path = Path(self.replay_file)
        if not self.replay_file:
            raise RuntimeError("AIDC_REPLAY_FILE nao informado.")
        if not file_path.exists():
            raise RuntimeError(f"Replay file nao encontrado: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".csv":
            self._ticks = self._load_csv(file_path)
        elif ext in {".parquet", ".pq"}:
            self._ticks = self._load_parquet(file_path)
        else:
            raise RuntimeError("Replay file invalido. Use .csv ou .parquet.")

        if not self._ticks:
            raise RuntimeError("Replay file vazio.")
        self._connected = True

    def stream(self) -> Iterator[TelemetryTick]:
        if not self._connected:
            raise RuntimeError("Provider not connected.")

        previous_time = self._ticks[0].session_time_s
        for tick in self._ticks:
            if self.speed > 0.0:
                delta = max(0.0, tick.session_time_s - previous_time)
                sleep_s = delta / self.speed
                if sleep_s > 0.0:
                    time.sleep(sleep_s)
            previous_time = tick.session_time_s
            yield tick

    def close(self) -> None:
        self._connected = False
        self._ticks = []

    def _load_csv(self, file_path: Path) -> List[TelemetryTick]:
        ticks: List[TelemetryTick] = []
        with file_path.open("r", newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                steer = float(row["steer"])
                steering_angle_deg = (
                    float(row["steering_angle_deg"])
                    if row.get("steering_angle_deg") not in (None, "", "None")
                    else steer * (180.0 / math.pi)
                )
                ticks.append(
                    TelemetryTick(
                        session_time_s=float(row["session_time_s"]),
                        lap_count=int(row["lap_count"]),
                        lap_time_s=float(row["lap_time_s"]),
                        normalized_spline_pos=float(row["normalized_spline_pos"]),
                        speed_kmh=float(row["speed_kmh"]),
                        throttle=float(row["throttle"]),
                        brake=float(row["brake"]),
                        steer=steer,
                        gear=int(row["gear"]),
                        rpm=int(row["rpm"]),
                        steering_angle_deg=steering_angle_deg,
                        is_in_pit=_to_bool(row.get("is_in_pit", "0")),
                        sector=int(row["sector"]) if row.get("sector") not in (None, "", "None") else None,
                        track_name=(row.get("track_name") or None),
                        track_length_m=(
                            float(row["track_length_m"])
                            if row.get("track_length_m") not in (None, "", "None")
                            else None
                        ),
                        car_name=(row.get("car_name") or None),
                        world_pos_x=(
                            float(row["world_pos_x"])
                            if row.get("world_pos_x") not in (None, "", "None")
                            else None
                        ),
                        world_pos_y=(
                            float(row["world_pos_y"])
                            if row.get("world_pos_y") not in (None, "", "None")
                            else None
                        ),
                        world_pos_z=(
                            float(row["world_pos_z"])
                            if row.get("world_pos_z") not in (None, "", "None")
                            else None
                        ),
                        fuel_l=_opt_float(row.get("fuel_l")),
                        fuel_per_lap_l=_opt_float(row.get("fuel_per_lap_l")),
                        fuel_estimated_laps=_opt_float(row.get("fuel_estimated_laps")),
                        race_total_laps=_opt_int(row.get("race_total_laps")),
                        completed_laps=_opt_int(row.get("completed_laps")),
                        laps_remaining=_opt_int(row.get("laps_remaining")),
                        fuel_will_finish=_opt_bool(row.get("fuel_will_finish")),
                        session_time_left_s=_opt_float(row.get("session_time_left_s")),
                        air_temp_c=_opt_float(row.get("air_temp_c")),
                        road_temp_c=_opt_float(row.get("road_temp_c")),
                        tire_pressure_fl=_opt_float(row.get("tire_pressure_fl")),
                        tire_pressure_fr=_opt_float(row.get("tire_pressure_fr")),
                        tire_pressure_rl=_opt_float(row.get("tire_pressure_rl")),
                        tire_pressure_rr=_opt_float(row.get("tire_pressure_rr")),
                        tire_temp_fl=_opt_float(row.get("tire_temp_fl")),
                        tire_temp_fr=_opt_float(row.get("tire_temp_fr")),
                        tire_temp_rl=_opt_float(row.get("tire_temp_rl")),
                        tire_temp_rr=_opt_float(row.get("tire_temp_rr")),
                        brake_temp_fl=_opt_float(row.get("brake_temp_fl")),
                        brake_temp_fr=_opt_float(row.get("brake_temp_fr")),
                        brake_temp_rl=_opt_float(row.get("brake_temp_rl")),
                        brake_temp_rr=_opt_float(row.get("brake_temp_rr")),
                        slip_ratio_rl=_opt_float(row.get("slip_ratio_rl")),
                        slip_ratio_rr=_opt_float(row.get("slip_ratio_rr")),
                        traction_loss_rear=_opt_bool(row.get("traction_loss_rear")),
                    )
                )
        return ticks

    def _load_parquet(self, file_path: Path) -> List[TelemetryTick]:
        table = pq.read_table(file_path)
        rows = table.to_pylist()
        ticks: List[TelemetryTick] = []
        for row in rows:
            steer = float(row["steer"])
            steering_angle_deg = (
                float(row["steering_angle_deg"])
                if row.get("steering_angle_deg") is not None
                else steer * (180.0 / math.pi)
            )
            ticks.append(
                TelemetryTick(
                    session_time_s=float(row["session_time_s"]),
                    lap_count=int(row["lap_count"]),
                    lap_time_s=float(row["lap_time_s"]),
                    normalized_spline_pos=float(row["normalized_spline_pos"]),
                    speed_kmh=float(row["speed_kmh"]),
                    throttle=float(row["throttle"]),
                    brake=float(row["brake"]),
                    steer=steer,
                    gear=int(row["gear"]),
                    rpm=int(row["rpm"]),
                    steering_angle_deg=steering_angle_deg,
                    is_in_pit=bool(row.get("is_in_pit", False)),
                    sector=int(row["sector"]) if row.get("sector") is not None else None,
                    track_name=(row.get("track_name") or None),
                    track_length_m=(
                        float(row["track_length_m"]) if row.get("track_length_m") is not None else None
                    ),
                    car_name=(row.get("car_name") or None),
                    world_pos_x=(float(row["world_pos_x"]) if row.get("world_pos_x") is not None else None),
                    world_pos_y=(float(row["world_pos_y"]) if row.get("world_pos_y") is not None else None),
                    world_pos_z=(float(row["world_pos_z"]) if row.get("world_pos_z") is not None else None),
                    fuel_l=_opt_float(row.get("fuel_l")),
                    fuel_per_lap_l=_opt_float(row.get("fuel_per_lap_l")),
                    fuel_estimated_laps=_opt_float(row.get("fuel_estimated_laps")),
                    race_total_laps=_opt_int(row.get("race_total_laps")),
                    completed_laps=_opt_int(row.get("completed_laps")),
                    laps_remaining=_opt_int(row.get("laps_remaining")),
                    fuel_will_finish=_opt_bool(row.get("fuel_will_finish")),
                    session_time_left_s=_opt_float(row.get("session_time_left_s")),
                    air_temp_c=_opt_float(row.get("air_temp_c")),
                    road_temp_c=_opt_float(row.get("road_temp_c")),
                    tire_pressure_fl=_opt_float(row.get("tire_pressure_fl")),
                    tire_pressure_fr=_opt_float(row.get("tire_pressure_fr")),
                    tire_pressure_rl=_opt_float(row.get("tire_pressure_rl")),
                    tire_pressure_rr=_opt_float(row.get("tire_pressure_rr")),
                    tire_temp_fl=_opt_float(row.get("tire_temp_fl")),
                    tire_temp_fr=_opt_float(row.get("tire_temp_fr")),
                    tire_temp_rl=_opt_float(row.get("tire_temp_rl")),
                    tire_temp_rr=_opt_float(row.get("tire_temp_rr")),
                    brake_temp_fl=_opt_float(row.get("brake_temp_fl")),
                    brake_temp_fr=_opt_float(row.get("brake_temp_fr")),
                    brake_temp_rl=_opt_float(row.get("brake_temp_rl")),
                    brake_temp_rr=_opt_float(row.get("brake_temp_rr")),
                    slip_ratio_rl=_opt_float(row.get("slip_ratio_rl")),
                    slip_ratio_rr=_opt_float(row.get("slip_ratio_rr")),
                    traction_loss_rear=_opt_bool(row.get("traction_loss_rear")),
                )
            )
        return ticks
