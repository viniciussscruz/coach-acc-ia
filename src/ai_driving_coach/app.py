from __future__ import annotations

import time
from dataclasses import dataclass

from ai_driving_coach.analysis.benchmark_analyzer import BenchmarkAnalyzer
from ai_driving_coach.analysis.session_timing import SessionTimingAnalyzer
from ai_driving_coach.analysis.post_lap_analyzer import PostLapAnalyzer
from ai_driving_coach.benchmarks.repository import BenchmarkRepository
from ai_driving_coach.coaching.realtime_coach import CoachMessage, RealtimeCoach
from ai_driving_coach.config import AppConfig
from ai_driving_coach.core.event_bus import EventBus
from ai_driving_coach.core.events import Event
from ai_driving_coach.dashboard.server import DashboardServer
from ai_driving_coach.dashboard.state import DashboardState
from ai_driving_coach.features.extractor import FeatureExtractor
from ai_driving_coach.features.models import CornerFeature
from ai_driving_coach.overlay.window import CoachOverlayWindow, OverlayPayload
from ai_driving_coach.providers.acc_shared_memory import ACCSharedMemoryProvider
from ai_driving_coach.providers.base import TelemetryProvider
from ai_driving_coach.providers.mock_provider import MockTelemetryProvider
from ai_driving_coach.providers.replay_provider import ReplayTelemetryProvider
from ai_driving_coach.reference.repository import ReferenceLapRepository
from ai_driving_coach.storage.persistence import SessionPersistence
from ai_driving_coach.storage.tick_recorder import TickRecorder
from ai_driving_coach.tracking.lap_tracker import LapTracker


@dataclass
class CoachingApp:
    config: AppConfig

    def __post_init__(self) -> None:
        self._tick_counter = 0
        self._capture_announced = False
        self._latest_hint_text = "Sem nova dica"
        self._latest_hint_level = "info"
        self._hint_updated_at = 0.0
        self._hint_visible_seconds = max(0.0, self.config.overlay_hint_seconds)
        self._fuel_alert_active = False
        self._fuel_alert_threshold_laps = 5.0
        self._fuel_alert_refresh_s = 12.0
        self._last_fuel_alert_emit = 0.0
        self._last_track_name = "-"
        self._last_track_length_m = 0.0
        self._last_car_name = "-"
        self.event_bus = EventBus()
        self.provider = self._build_provider()
        self.lap_tracker = LapTracker(self.event_bus)
        self.feature_extractor = FeatureExtractor(self.event_bus)
        self.realtime_coach = RealtimeCoach()
        self.post_lap_analyzer = PostLapAnalyzer()
        self.session_timing = SessionTimingAnalyzer()
        self.persistence = SessionPersistence(self.config.output_dir)
        self.tick_recorder = TickRecorder(self.config.output_dir)
        self.reference_repo = ReferenceLapRepository()
        self.benchmark_repo = BenchmarkRepository(self.config.benchmark_db_path)
        self.benchmark_analyzer = BenchmarkAnalyzer(
            repository=self.benchmark_repo,
            condition=self.config.benchmark_condition,
        )
        self.dashboard_state, self.dashboard_server = self._build_dashboard()
        self.dashboard_state.update_timing(self.session_timing.snapshot())
        self.dashboard_state.set_benchmark_reference(None)
        self.overlay = self._build_overlay()
        self._load_external_baseline()
        self._register_handlers()

    def run(self) -> None:
        self.dashboard_state.set_status("starting")
        if self.dashboard_server is not None:
            try:
                self.dashboard_server.start()
                print(f"[DASH] running at {self.dashboard_server.url}")
            except OSError as exc:
                print(f"[DASH] failed to start dashboard: {exc}")
                self.dashboard_server = None
        if self.overlay is not None:
            try:
                self.overlay.start()
                print("[OVERLAY] running (top-most window).")
            except Exception as exc:  # noqa: BLE001
                print(f"[OVERLAY] failed to start: {exc}")
                self.overlay = None
        self.provider.connect()
        self.dashboard_state.set_status("running")
        try:
            for i, tick in enumerate(self.provider.stream(), start=1):
                self.event_bus.publish(Event(name="tick", payload={"tick": tick}))
                if self.config.tick_limit > 0 and i >= self.config.tick_limit:
                    print(f"[RUN] tick_limit atingido ({self.config.tick_limit}). Encerrando captura.")
                    break
        finally:
            self.dashboard_state.set_status("stopped")
            if self.config.persist_raw_ticks:
                for lap_number, csv_path, parquet_path in self.tick_recorder.flush_all(
                    persist_parquet=self.config.persist_parquet
                ):
                    if csv_path is not None:
                        print(f"[PERSIST] Pending lap {lap_number} ticks CSV saved: {csv_path}")
                    if parquet_path is not None:
                        print(f"[PERSIST] Pending lap {lap_number} ticks Parquet saved: {parquet_path}")
            self.provider.close()
            if self.dashboard_server is not None:
                self.dashboard_server.stop()
            if self.overlay is not None:
                self.overlay.stop()

    def _build_provider(self) -> TelemetryProvider:
        provider_mode = self.config.provider_mode.strip().lower()
        if provider_mode == "mock":
            return MockTelemetryProvider()
        if provider_mode == "acc":
            return ACCSharedMemoryProvider(
                poll_hz=self.config.acc_poll_hz,
                max_idle_seconds=self.config.acc_max_idle_seconds,
            )
        if provider_mode == "replay":
            return ReplayTelemetryProvider(
                replay_file=self.config.replay_file,
                speed=self.config.replay_speed,
            )
        raise RuntimeError(f"Provider mode invalido: {self.config.provider_mode}")

    def _register_handlers(self) -> None:
        self.event_bus.subscribe("tick", self._on_tick)
        self.event_bus.subscribe("lap_started", self._on_lap_started)
        self.event_bus.subscribe("sector_changed", self._on_sector_changed)
        self.event_bus.subscribe("lap_finished", self._on_lap_finished)
        self.event_bus.subscribe("corner_feature_completed", self._on_corner_feature_completed)

    def _build_dashboard(self) -> tuple[DashboardState, DashboardServer | None]:
        provider_name = self.config.provider_mode.strip().lower()
        config_view = {
            "provider": provider_name,
            "tick_limit": self.config.tick_limit,
            "acc_poll_hz": self.config.acc_poll_hz,
            "acc_max_idle_seconds": self.config.acc_max_idle_seconds,
            "replay_file": self.config.replay_file,
            "replay_speed": self.config.replay_speed,
            "capture_heartbeat": self.config.capture_heartbeat,
            "capture_heartbeat_every_ticks": self.config.capture_heartbeat_every_ticks,
            "baseline_mode": self.config.baseline_mode,
            "reference_features_path": self.config.reference_features_path,
            "fallback_track_length_m": self.config.fallback_track_length_m,
            "persist_parquet": self.config.persist_parquet,
            "persist_raw_ticks": self.config.persist_raw_ticks,
            "output_dir": str(self.config.output_dir),
            "overlay_enabled": self.config.overlay_enabled,
            "overlay_x": self.config.overlay_x,
            "overlay_y": self.config.overlay_y,
            "overlay_width": self.config.overlay_width,
            "overlay_height": self.config.overlay_height,
            "overlay_hint_seconds": self.config.overlay_hint_seconds,
            "dashboard_enabled": self.config.enable_dashboard,
            "dashboard_host": self.config.dashboard_host,
            "dashboard_port": self.config.dashboard_port,
            "benchmark_db_path": str(self.config.benchmark_db_path),
            "benchmark_condition": self.config.benchmark_condition,
            "benchmark_entries": self.benchmark_repo.count_entries(),
        }
        state = DashboardState(provider_name=provider_name, config_view=config_view)
        if not self.config.enable_dashboard:
            return state, None
        server = DashboardServer(
            state=state,
            host=self.config.dashboard_host,
            port=self.config.dashboard_port,
        )
        return state, server

    def _build_overlay(self) -> CoachOverlayWindow | None:
        if not self.config.overlay_enabled:
            return None
        return CoachOverlayWindow(
            x=self.config.overlay_x,
            y=self.config.overlay_y,
            width=self.config.overlay_width,
            height=self.config.overlay_height,
        )

    def _load_external_baseline(self) -> None:
        if self.config.baseline_mode != "external":
            return
        if not self.config.reference_features_path:
            print("[BASELINE] external mode ativo, mas AIDC_REFERENCE_FEATURES_PATH vazio.")
            self.config.baseline_mode = "session_best"
            return
        try:
            reference = self.reference_repo.load_features(self.config.reference_features_path)
        except RuntimeError as exc:
            print(f"[BASELINE] erro ao carregar referencia externa: {exc}")
            self.config.baseline_mode = "session_best"
            return
        track_length = 0.0
        if reference.features and reference.features[0].track_length_m:
            track_length = float(reference.features[0].track_length_m)
        self.realtime_coach.set_baseline(
            features=reference.features,
            label=f"external:{reference.source_path}",
            track_length_m=track_length,
        )
        print(f"[BASELINE] referencia externa carregada: {reference.source_path}")

    def _push_overlay(self, tick, steer_deg: float) -> None:
        if self.overlay is None:
            return
        hint_text = self._latest_hint_text
        hint_level = self._latest_hint_level

        # Keep last message visible for 2 seconds, then clear until next hint.
        if self._hint_visible_seconds > 0.0 and self._hint_updated_at > 0.0:
            if (time.monotonic() - self._hint_updated_at) > self._hint_visible_seconds:
                hint_text = "Sem nova dica"
                hint_level = "info"

        payload = OverlayPayload(
            status=self.dashboard_state.status,
            provider=self.config.provider_mode,
            lap=tick.lap_count,
            sector=tick.sector or 0,
            speed_kmh=tick.speed_kmh,
            throttle=tick.throttle,
            brake=tick.brake,
            steer=tick.steer,
            steering_angle_deg=steer_deg,
            spline=tick.normalized_spline_pos,
            latest_hint=hint_text,
            hint_level=hint_level,
            baseline_label=self.realtime_coach.baseline_label,
            track_name=self._last_track_name,
            track_length_m=self._last_track_length_m,
            fuel_l=tick.fuel_l,
            fuel_estimated_laps=tick.fuel_estimated_laps,
            laps_remaining=tick.laps_remaining,
            fuel_will_finish=tick.fuel_will_finish,
            road_temp_c=tick.road_temp_c,
            air_temp_c=tick.air_temp_c,
            traction_loss_rear=bool(tick.traction_loss_rear) if tick.traction_loss_rear is not None else False,
            tires={
                "FL": {
                    "pressure": tick.tire_pressure_fl,
                    "temp": tick.tire_temp_fl,
                    "brake_temp": tick.brake_temp_fl,
                },
                "FR": {
                    "pressure": tick.tire_pressure_fr,
                    "temp": tick.tire_temp_fr,
                    "brake_temp": tick.brake_temp_fr,
                },
                "RL": {
                    "pressure": tick.tire_pressure_rl,
                    "temp": tick.tire_temp_rl,
                    "brake_temp": tick.brake_temp_rl,
                    "slip_ratio": tick.slip_ratio_rl,
                },
                "RR": {
                    "pressure": tick.tire_pressure_rr,
                    "temp": tick.tire_temp_rr,
                    "brake_temp": tick.brake_temp_rr,
                    "slip_ratio": tick.slip_ratio_rr,
                },
            },
        )
        self.overlay.push(payload)

    def _on_tick(self, event: Event) -> None:
        tick = event.payload["tick"]
        self._tick_counter += 1
        self.dashboard_state.update_tick(tick, self._tick_counter)
        if self.config.persist_raw_ticks:
            self.tick_recorder.record(tick)

        if tick.track_name:
            self._last_track_name = tick.track_name
        if tick.car_name:
            self._last_car_name = tick.car_name
        if tick.track_length_m and tick.track_length_m > 0.0:
            self._last_track_length_m = tick.track_length_m
        elif self._last_track_length_m <= 0.0 and self.config.fallback_track_length_m > 0.0:
            self._last_track_length_m = self.config.fallback_track_length_m

        benchmark_reference = self.benchmark_analyzer.update_context(
            track_name=self._last_track_name if self._last_track_name != "-" else tick.track_name,
            car_name=self._last_car_name if self._last_car_name != "-" else tick.car_name,
        )
        self.dashboard_state.set_benchmark_reference(benchmark_reference)
        self._handle_fuel_alerts(tick)

        if self.config.capture_heartbeat:
            if not self._capture_announced:
                self._capture_announced = True
                print(
                    "[CAPTURE] first_tick "
                    f"lap={tick.lap_count} sector={tick.sector} "
                    f"spline={tick.normalized_spline_pos:.4f} "
                    f"speed={tick.speed_kmh:.1f}kmh throttle={tick.throttle:.2f} brake={tick.brake:.2f} "
                    f"steer={tick.steer:+.3f} steer_deg={self._resolve_steer_deg(tick):+.1f}"
                )
            elif self._tick_counter % max(1, self.config.capture_heartbeat_every_ticks) == 0:
                print(
                    "[CAPTURE] heartbeat "
                    f"tick={self._tick_counter} lap={tick.lap_count} sector={tick.sector} "
                    f"lap_time={tick.lap_time_s:.2f}s spline={tick.normalized_spline_pos:.4f} "
                    f"speed={tick.speed_kmh:.1f}kmh throttle={tick.throttle:.2f} brake={tick.brake:.2f} "
                    f"steer={tick.steer:+.3f} steer_deg={self._resolve_steer_deg(tick):+.1f}"
                )
                print(
                    "[VEH] "
                    f"fuel={self._fmt_f(tick.fuel_l, 1)}L est={self._fmt_f(tick.fuel_estimated_laps, 2)}laps "
                    f"left={self._fmt_i(tick.laps_remaining)} give={self._fmt_bool(tick.fuel_will_finish)} "
                    f"road={self._fmt_f(tick.road_temp_c, 1)}C air={self._fmt_f(tick.air_temp_c, 1)}C "
                    f"detrac={self._fmt_bool(tick.traction_loss_rear)} "
                    f"FL(p={self._fmt_f(tick.tire_pressure_fl, 2)} t={self._fmt_f(tick.tire_temp_fl, 1)} b={self._fmt_f(tick.brake_temp_fl, 0)}) "
                    f"FR(p={self._fmt_f(tick.tire_pressure_fr, 2)} t={self._fmt_f(tick.tire_temp_fr, 1)} b={self._fmt_f(tick.brake_temp_fr, 0)}) "
                    f"RL(p={self._fmt_f(tick.tire_pressure_rl, 2)} t={self._fmt_f(tick.tire_temp_rl, 1)} b={self._fmt_f(tick.brake_temp_rl, 0)}) "
                    f"RR(p={self._fmt_f(tick.tire_pressure_rr, 2)} t={self._fmt_f(tick.tire_temp_rr, 1)} b={self._fmt_f(tick.brake_temp_rr, 0)})"
                )

        self._push_overlay(tick=tick, steer_deg=self._resolve_steer_deg(tick))
        self.lap_tracker.process_tick(tick)
        self.feature_extractor.process_tick(tick)

    def _resolve_steer_deg(self, tick) -> float:
        if tick.steering_angle_deg is not None:
            return float(tick.steering_angle_deg)
        return float(tick.steer) * (180.0 / 3.141592653589793)

    def _fmt_f(self, value, digits: int) -> str:
        if value is None:
            return "-"
        return f"{float(value):.{digits}f}"

    def _fmt_i(self, value) -> str:
        if value is None:
            return "-"
        return str(int(value))

    def _fmt_bool(self, value) -> str:
        if value is None:
            return "-"
        return "sim" if bool(value) else "nao"

    def _on_lap_started(self, event: Event) -> None:
        lap_number = int(event.payload["lap_number"])
        session_time_s = float(event.payload["session_time_s"])
        sector = int(event.payload.get("sector") or 1)
        self.session_timing.on_lap_started(lap_number, session_time_s, sector=sector)
        self.dashboard_state.update_timing(self.session_timing.snapshot())

    def _on_sector_changed(self, event: Event) -> None:
        from_sector = event.payload.get("from_sector")
        to_sector = event.payload.get("to_sector")
        session_time_s = float(event.payload["session_time_s"])
        self.session_timing.on_sector_changed(from_sector, to_sector, session_time_s)
        self.dashboard_state.update_timing(self.session_timing.snapshot())

    def _on_corner_feature_completed(self, event: Event) -> None:
        data = event.payload["feature"]
        feature = CornerFeature(**data)
        if feature.track_name is None and self._last_track_name != "-":
            feature.track_name = self._last_track_name
        if (feature.track_length_m is None or feature.track_length_m <= 0.0) and self._last_track_length_m > 0.0:
            feature.track_length_m = self._last_track_length_m

        message = self.realtime_coach.evaluate_corner(feature)
        if message:
            print(
                f"[RT][Lap {message.lap_number:03d} C{message.corner_index:02d}] "
                f"[{message.severity}] {message.text}"
            )
            self._publish_hint_message(message)

    def _on_lap_finished(self, event: Event) -> None:
        lap_number = int(event.payload["lap_number"])
        lap_time_s = float(event.payload["lap_time_s"])
        session_time_s = float(event.payload.get("session_time_s", 0.0))

        timing = self.session_timing.on_lap_finished(
            lap_number=lap_number,
            lap_time_s=lap_time_s,
            session_time_s=session_time_s,
        )
        self.dashboard_state.update_timing(self.session_timing.snapshot())

        self.feature_extractor.finalize_lap(lap_number)
        lap_features = self.feature_extractor.get_lap_features(lap_number)

        ticks_csv = ticks_parquet = None
        if self.config.persist_raw_ticks:
            ticks_csv, ticks_parquet = self.tick_recorder.flush_lap(lap_number, persist_parquet=self.config.persist_parquet)
            if ticks_csv is not None:
                print(f"[PERSIST] Ticks CSV saved: {ticks_csv}")
            if ticks_parquet is not None:
                print(f"[PERSIST] Ticks Parquet saved: {ticks_parquet}")

        csv_file = self.persistence.save_lap_features_csv(lap_number, lap_features)
        print(f"[PERSIST] Features CSV saved: {csv_file}")
        if self.config.persist_parquet:
            parquet_file = self.persistence.save_lap_features_parquet(lap_number, lap_features)
            print(f"[PERSIST] Features Parquet saved: {parquet_file}")

        result = self.post_lap_analyzer.register_lap(lap_number, lap_time_s, lap_features)
        print(
            f"[LAP {lap_number:03d}] time={lap_time_s:.3f}s "
            f"delta_best={result.delta_to_best_lap_s:+.3f}s best={result.is_best_lap}"
        )
        for line in result.summary:
            print(f"[POST] {line}")
        self.dashboard_state.add_lap_result(
            lap_number=lap_number,
            lap_time_s=lap_time_s,
            is_best_lap=result.is_best_lap,
            delta_to_best_lap_s=result.delta_to_best_lap_s,
            summary=result.summary,
            features_count=len(lap_features),
        )
        benchmark_result = self.benchmark_analyzer.compare_lap(
            lap_number=lap_number,
            lap_time_s=lap_time_s,
            track_name=self._last_track_name if self._last_track_name != "-" else None,
            car_name=self._last_car_name if self._last_car_name != "-" else None,
        )
        if benchmark_result is not None:
            self.dashboard_state.set_lap_benchmark_data(
                lap_number=lap_number,
                benchmark_gap_s=benchmark_result.gap_s,
                benchmark_percent=benchmark_result.gap_percent,
                benchmark_scope=benchmark_result.scope,
                benchmark_reference_lap_s=benchmark_result.reference_lap_time_s,
            )
            self.dashboard_state.set_benchmark_reference(benchmark_result.reference)
            print(
                f"[BENCH][LAP {lap_number:03d}] "
                f"ref={benchmark_result.reference.lap_time_s:.3f}s "
                f"gap={benchmark_result.gap_s:+.3f}s "
                f"({benchmark_result.gap_percent:+.2f}%) scope={benchmark_result.scope}"
            )

        self.dashboard_state.set_lap_sector_data(
            lap_number=lap_number,
            sectors=timing.sectors,
            sector_deltas_to_best=timing.sector_deltas_to_best,
            theoretical_best_s=timing.theoretical_best_s,
        )

        if self.config.baseline_mode == "session_best" and result.is_best_lap:
            self.realtime_coach.update_best_lap(
                lap_features,
                track_length_m=self._last_track_length_m,
            )
            print("[BASELINE] session best updated.")

    def _publish_hint_message(self, message: CoachMessage, overlay_text: str | None = None) -> None:
        self.dashboard_state.add_coach_message(message)
        self._latest_hint_text = overlay_text or message.text
        self._latest_hint_level = message.severity
        self._hint_updated_at = time.monotonic()

    def _resolve_fuel_laps_remaining(self, tick) -> float | None:
        candidates: list[float] = []
        if tick.fuel_estimated_laps is not None:
            candidates.append(float(tick.fuel_estimated_laps))
        if tick.laps_remaining is not None:
            candidates.append(float(tick.laps_remaining))
        if not candidates:
            return None
        return min(candidates)

    def _handle_fuel_alerts(self, tick) -> None:
        fuel_laps = self._resolve_fuel_laps_remaining(tick)
        if fuel_laps is None:
            return

        now = time.monotonic()
        is_low = fuel_laps <= self._fuel_alert_threshold_laps
        lap_number = int(tick.lap_count)

        if is_low and not self._fuel_alert_active:
            self._fuel_alert_active = True
            self._last_fuel_alert_emit = now
            self._publish_hint_message(
                CoachMessage(
                    lap_number=lap_number,
                    corner_index=0,
                    text=f"Combustivel baixo: {fuel_laps:.1f} voltas.",
                    severity="critical",
                    category="fuel",
                ),
                overlay_text=f"Combustivel baixo: {fuel_laps:.1f} voltas.",
            )
            return

        if is_low and self._fuel_alert_active and (now - self._last_fuel_alert_emit) >= self._fuel_alert_refresh_s:
            self._last_fuel_alert_emit = now
            self._publish_hint_message(
                CoachMessage(
                    lap_number=lap_number,
                    corner_index=0,
                    text=f"Combustivel baixo: {fuel_laps:.1f} voltas.",
                    severity="critical",
                    category="fuel",
                ),
                overlay_text=f"Combustivel baixo: {fuel_laps:.1f} voltas.",
            )
            return

        if not is_low and self._fuel_alert_active:
            self._fuel_alert_active = False
            self._last_fuel_alert_emit = now
            self._publish_hint_message(
                CoachMessage(
                    lap_number=lap_number,
                    corner_index=0,
                    text=f"Combustivel normalizado: {fuel_laps:.1f} voltas.",
                    severity="info",
                    category="fuel",
                ),
                overlay_text=f"Combustivel normalizado: {fuel_laps:.1f} voltas.",
            )
