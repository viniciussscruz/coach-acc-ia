from __future__ import annotations

import math
import mmap
import struct
import time
from dataclasses import dataclass
from typing import Iterator

from ai_driving_coach.models.telemetry import TelemetryTick
from ai_driving_coach.providers.base import TelemetryProvider

_ACC_PHYSICS_MAP_NAME = "Local\\acpmf_physics"
_ACC_GRAPHICS_MAP_NAME = "Local\\acpmf_graphics"
_ACC_STATIC_MAP_NAME = "Local\\acpmf_static"
_ACC_PHYSICS_MAP_SIZE = 800
_ACC_GRAPHICS_MAP_SIZE = 1588
_ACC_STATIC_MAP_SIZE = 784

# Physics map first fields: packetID, gas, brake, fuel, gear, rpm, steerAngle, speedKmh
_PHYSICS_HEAD_STRUCT = struct.Struct("<ifffiiff")


def _read_i32(buffer: bytes, offset: int) -> int:
    return struct.unpack_from("<i", buffer, offset)[0]


def _read_f32(buffer: bytes, offset: int) -> float:
    return struct.unpack_from("<f", buffer, offset)[0]


def _read_f32x4(buffer: bytes, offset: int) -> tuple[float, float, float, float]:
    return struct.unpack_from("<ffff", buffer, offset)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _read_utf16(buffer: bytes, offset: int, wchar_count: int) -> str:
    raw = buffer[offset : offset + (wchar_count * 2)]
    text = raw.decode("utf-16-le", errors="ignore")
    return text.split("\x00", 1)[0].strip()


@dataclass(slots=True)
class _ACCPhysicsSample:
    packet_id: int
    throttle: float
    brake: float
    fuel_l: float
    gear: int
    rpm: int
    steer: float
    speed_kmh: float
    air_temp_c: float
    road_temp_c: float
    tire_pressure_psi: tuple[float, float, float, float]
    tire_core_temp_c: tuple[float, float, float, float]
    brake_temp_c: tuple[float, float, float, float]
    slip_ratio: tuple[float, float, float, float]


@dataclass(slots=True)
class _ACCGraphicsSample:
    packet_id: int
    status: int
    completed_laps: int
    number_of_laps: int
    current_lap_time_ms: int
    session_time_left_s: float
    fuel_per_lap_l: float
    fuel_estimated_laps: float
    normalized_car_position: float
    current_sector_index: int
    is_in_pit: bool
    is_in_pit_lane: bool
    player_world_pos: tuple[float, float, float] | None


@dataclass(slots=True)
class _ACCStaticSample:
    track_name: str
    track_length_m: float
    car_name: str


class ACCSharedMemoryProvider(TelemetryProvider):
    """Reads live telemetry from ACC shared memory maps on Windows."""

    def __init__(self, poll_hz: int = 60, max_idle_seconds: float = 0.0) -> None:
        self.poll_hz = poll_hz
        self.max_idle_seconds = max_idle_seconds
        self._sleep_s = 1.0 / float(max(1, poll_hz))
        self._physics_map: mmap.mmap | None = None
        self._graphics_map: mmap.mmap | None = None
        self._static_map: mmap.mmap | None = None
        self._last_physics_packet_id: int | None = None
        self._last_graphics_packet_id: int | None = None
        self._static_sample = _ACCStaticSample(track_name="", track_length_m=0.0, car_name="")
        self._session_clock_start = 0.0
        self._last_wait_log_at = 0.0
        self._connected = False

    def connect(self) -> None:
        try:
            self._physics_map = mmap.mmap(
                -1,
                _ACC_PHYSICS_MAP_SIZE,
                tagname=_ACC_PHYSICS_MAP_NAME,
                access=mmap.ACCESS_READ,
            )
            self._graphics_map = mmap.mmap(
                -1,
                _ACC_GRAPHICS_MAP_SIZE,
                tagname=_ACC_GRAPHICS_MAP_NAME,
                access=mmap.ACCESS_READ,
            )
            self._static_map = mmap.mmap(
                -1,
                _ACC_STATIC_MAP_SIZE,
                tagname=_ACC_STATIC_MAP_NAME,
                access=mmap.ACCESS_READ,
            )
        except OSError as exc:
            self.close()
            raise RuntimeError(
                "Nao foi possivel abrir shared memory do ACC. "
                "Confirme que o ACC esta aberto e com uma sessao carregada."
            ) from exc

        self._static_sample = self._parse_static(self._static_map[:])
        self._session_clock_start = time.perf_counter()
        self._connected = True

    def stream(self) -> Iterator[TelemetryTick]:
        if not self._connected or self._physics_map is None or self._graphics_map is None or self._static_map is None:
            raise RuntimeError("Provider not connected.")
        idle_started_at = time.perf_counter()

        while True:
            physics_raw = self._physics_map[:]
            graphics_raw = self._graphics_map[:]
            physics = self._parse_physics(physics_raw)
            graphics = self._parse_graphics(graphics_raw)
            if self._static_sample.track_length_m <= 0.0:
                self._static_sample = self._parse_static(self._static_map[:])

            self._last_physics_packet_id = physics.packet_id
            self._last_graphics_packet_id = graphics.packet_id

            # Ignore ACC_OFF state but keep process alive while user enters track.
            if graphics.status == 0:
                now = time.perf_counter()
                if now - self._last_wait_log_at >= 2.0:
                    print(
                        "[ACC] aguardando sessao ativa "
                        f"(status={graphics.status}, laps={graphics.completed_laps}, "
                        f"lap_time_ms={graphics.current_lap_time_ms}, spline={graphics.normalized_car_position:.4f})"
                    )
                    self._last_wait_log_at = now

                if (
                    self.max_idle_seconds > 0.0
                    and (now - idle_started_at) > self.max_idle_seconds
                ):
                    raise RuntimeError(
                        "ACC detectado, mas estado atual permanece OFF. "
                        "Entre na pista ou aumente AIDC_ACC_MAX_IDLE_S."
                    )
                time.sleep(self._sleep_s)
                continue
            idle_started_at = time.perf_counter()

            lap_count = max(1, graphics.completed_laps + 1)
            current_lap_time_s = (
                float(graphics.current_lap_time_ms) / 1000.0
                if 0 <= graphics.current_lap_time_ms < 10_000_000
                else 0.0
            )
            sector = graphics.current_sector_index + 1 if 0 <= graphics.current_sector_index <= 2 else None
            race_total_laps = graphics.number_of_laps if graphics.number_of_laps > 0 else None
            laps_remaining = (
                max(0, graphics.number_of_laps - graphics.completed_laps)
                if race_total_laps is not None
                else None
            )

            fuel_per_lap_l = graphics.fuel_per_lap_l if graphics.fuel_per_lap_l > 0.01 else None
            fuel_estimated_laps = graphics.fuel_estimated_laps if graphics.fuel_estimated_laps > 0.0 else None
            if fuel_estimated_laps is None and fuel_per_lap_l is not None and physics.fuel_l > 0.0:
                fuel_estimated_laps = physics.fuel_l / fuel_per_lap_l
            fuel_will_finish = None
            if laps_remaining is not None and fuel_estimated_laps is not None:
                fuel_will_finish = fuel_estimated_laps + 0.15 >= float(laps_remaining)

            slip_rl = physics.slip_ratio[2]
            slip_rr = physics.slip_ratio[3]
            traction_loss_rear = (
                physics.throttle > 0.60
                and physics.speed_kmh > 40.0
                and (abs(slip_rl) > 0.12 or abs(slip_rr) > 0.12)
            )

            yield TelemetryTick(
                session_time_s=time.perf_counter() - self._session_clock_start,
                lap_count=lap_count,
                lap_time_s=current_lap_time_s,
                normalized_spline_pos=_clamp(graphics.normalized_car_position, 0.0, 1.0),
                speed_kmh=max(0.0, physics.speed_kmh),
                throttle=_clamp(physics.throttle, 0.0, 1.0),
                brake=_clamp(physics.brake, 0.0, 1.0),
                steer=physics.steer,
                steering_angle_deg=physics.steer * (180.0 / math.pi),
                gear=physics.gear,
                rpm=max(0, physics.rpm),
                is_in_pit=graphics.is_in_pit or graphics.is_in_pit_lane,
                sector=sector,
                track_name=self._static_sample.track_name or None,
                track_length_m=self._static_sample.track_length_m if self._static_sample.track_length_m > 0.0 else None,
                car_name=self._static_sample.car_name or None,
                world_pos_x=(graphics.player_world_pos[0] if graphics.player_world_pos is not None else None),
                world_pos_y=(graphics.player_world_pos[1] if graphics.player_world_pos is not None else None),
                world_pos_z=(graphics.player_world_pos[2] if graphics.player_world_pos is not None else None),
                fuel_l=max(0.0, physics.fuel_l),
                fuel_per_lap_l=fuel_per_lap_l,
                fuel_estimated_laps=fuel_estimated_laps,
                race_total_laps=race_total_laps,
                completed_laps=max(0, graphics.completed_laps),
                laps_remaining=laps_remaining,
                fuel_will_finish=fuel_will_finish,
                session_time_left_s=max(0.0, graphics.session_time_left_s),
                air_temp_c=physics.air_temp_c,
                road_temp_c=physics.road_temp_c,
                tire_pressure_fl=physics.tire_pressure_psi[0],
                tire_pressure_fr=physics.tire_pressure_psi[1],
                tire_pressure_rl=physics.tire_pressure_psi[2],
                tire_pressure_rr=physics.tire_pressure_psi[3],
                tire_temp_fl=physics.tire_core_temp_c[0],
                tire_temp_fr=physics.tire_core_temp_c[1],
                tire_temp_rl=physics.tire_core_temp_c[2],
                tire_temp_rr=physics.tire_core_temp_c[3],
                brake_temp_fl=physics.brake_temp_c[0],
                brake_temp_fr=physics.brake_temp_c[1],
                brake_temp_rl=physics.brake_temp_c[2],
                brake_temp_rr=physics.brake_temp_c[3],
                slip_ratio_rl=slip_rl,
                slip_ratio_rr=slip_rr,
                traction_loss_rear=traction_loss_rear,
            )

            time.sleep(self._sleep_s)

    def close(self) -> None:
        if self._physics_map is not None:
            self._physics_map.close()
            self._physics_map = None
        if self._graphics_map is not None:
            self._graphics_map.close()
            self._graphics_map = None
        if self._static_map is not None:
            self._static_map.close()
            self._static_map = None
        self._connected = False
        self._last_physics_packet_id = None
        self._last_graphics_packet_id = None
        self._last_wait_log_at = 0.0
        self._static_sample = _ACCStaticSample(track_name="", track_length_m=0.0, car_name="")

    def _parse_physics(self, raw: bytes) -> _ACCPhysicsSample:
        packet_id, throttle, brake, fuel_l, gear, rpm, steer, speed_kmh = _PHYSICS_HEAD_STRUCT.unpack_from(raw, 0)
        tire_pressure_psi = _read_f32x4(raw, 88)
        tire_core_temp_c = _read_f32x4(raw, 152)
        air_temp_c = _read_f32(raw, 288)
        road_temp_c = _read_f32(raw, 292)
        brake_temp_c = _read_f32x4(raw, 348)
        slip_ratio = _read_f32x4(raw, 640)
        return _ACCPhysicsSample(
            packet_id=packet_id,
            throttle=throttle,
            brake=brake,
            fuel_l=fuel_l,
            gear=gear,
            rpm=rpm,
            steer=steer,
            speed_kmh=speed_kmh,
            air_temp_c=air_temp_c,
            road_temp_c=road_temp_c,
            tire_pressure_psi=tire_pressure_psi,
            tire_core_temp_c=tire_core_temp_c,
            brake_temp_c=brake_temp_c,
            slip_ratio=slip_ratio,
        )

    def _parse_graphics(self, raw: bytes) -> _ACCGraphicsSample:
        # Offsets from official ACC graphics shared memory layout.
        packet_id = _read_i32(raw, 0)
        status = _read_i32(raw, 4)
        completed_laps = _read_i32(raw, 132)
        current_lap_time_ms = _read_i32(raw, 140)
        session_time_left_s = _read_f32(raw, 152)
        is_in_pit = _read_i32(raw, 160) != 0
        current_sector_index = _read_i32(raw, 164)
        number_of_laps = _read_i32(raw, 172)
        normalized_car_position = _read_f32(raw, 248)
        active_cars = max(0, min(60, _read_i32(raw, 252)))
        player_car_id = _read_i32(raw, 1216)
        is_in_pit_lane = _read_i32(raw, 1240) != 0
        fuel_per_lap_l = _read_f32(raw, 1284)
        fuel_estimated_laps = _read_f32(raw, 1412)

        player_world_pos: tuple[float, float, float] | None = None
        if active_cars > 0:
            coord_base = 256
            car_id_base = 976
            player_index = None
            for idx in range(active_cars):
                car_id = _read_i32(raw, car_id_base + idx * 4)
                if car_id == player_car_id:
                    player_index = idx
                    break
            if player_index is not None:
                start = coord_base + (player_index * 12)
                player_world_pos = (
                    _read_f32(raw, start),
                    _read_f32(raw, start + 4),
                    _read_f32(raw, start + 8),
                )

        return _ACCGraphicsSample(
            packet_id=packet_id,
            status=status,
            completed_laps=completed_laps,
            number_of_laps=number_of_laps,
            current_lap_time_ms=current_lap_time_ms,
            session_time_left_s=session_time_left_s,
            fuel_per_lap_l=fuel_per_lap_l,
            fuel_estimated_laps=fuel_estimated_laps,
            normalized_car_position=normalized_car_position,
            current_sector_index=current_sector_index,
            is_in_pit=is_in_pit,
            is_in_pit_lane=is_in_pit_lane,
            player_world_pos=player_world_pos,
        )

    def _parse_static(self, raw: bytes) -> _ACCStaticSample:
        # Based on ACC static map layout.
        car_name = _read_utf16(raw, offset=68, wchar_count=33)
        # track name wchar[33] starts at offset 134.
        track_name = _read_utf16(raw, offset=134, wchar_count=33)
        # trackSplineLength float offset.
        track_length_m = max(0.0, _read_f32(raw, 524))
        return _ACCStaticSample(
            track_name=track_name,
            track_length_m=track_length_m,
            car_name=car_name,
        )
