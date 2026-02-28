from __future__ import annotations

import os
from pathlib import Path

from ai_driving_coach.app import CoachingApp
from ai_driving_coach.config import AppConfig
from ai_driving_coach.runtime_logging import configure_runtime_log


def main() -> None:
    log_file = Path(os.getenv("AIDC_LOG_FILE", "logs/aidc.log").strip() or "logs/aidc.log")
    log_path = configure_runtime_log(log_file)
    provider_mode = os.getenv("AIDC_PROVIDER", "mock").strip().lower()
    acc_poll_hz = int(os.getenv("AIDC_ACC_POLL_HZ", "60"))
    acc_max_idle_seconds = float(os.getenv("AIDC_ACC_MAX_IDLE_S", "0"))
    replay_file = os.getenv("AIDC_REPLAY_FILE", "").strip()
    replay_speed = float(os.getenv("AIDC_REPLAY_SPEED", "1.0"))
    tick_limit = int(os.getenv("AIDC_TICK_LIMIT", "0"))
    capture_heartbeat = os.getenv("AIDC_CAPTURE_HEARTBEAT", "0") != "0"
    capture_heartbeat_every_ticks = int(os.getenv("AIDC_CAPTURE_HEARTBEAT_EVERY", "120"))
    baseline_mode = os.getenv("AIDC_BASELINE_MODE", "session_best").strip().lower()
    reference_features_path = os.getenv("AIDC_REFERENCE_FEATURES_PATH", "").strip()
    fallback_track_length_m = float(os.getenv("AIDC_TRACK_LENGTH_M", "0"))
    overlay_enabled = os.getenv("AIDC_OVERLAY", "1") != "0"
    overlay_x = int(os.getenv("AIDC_OVERLAY_X", "24"))
    overlay_y = int(os.getenv("AIDC_OVERLAY_Y", "24"))
    overlay_width = int(os.getenv("AIDC_OVERLAY_W", "520"))
    overlay_height = int(os.getenv("AIDC_OVERLAY_H", "190"))
    overlay_hint_seconds = float(os.getenv("AIDC_OVERLAY_HINT_SECONDS", "3.0"))
    enable_dashboard = os.getenv("AIDC_DASHBOARD", "1") != "0"
    dashboard_host = os.getenv("AIDC_DASHBOARD_HOST", "127.0.0.1")
    dashboard_port = int(os.getenv("AIDC_DASHBOARD_PORT", "8765"))
    persist_raw_ticks = os.getenv("AIDC_PERSIST_RAW_TICKS", "1") != "0"
    persist_parquet = os.getenv("AIDC_PERSIST_PARQUET", "1") != "0"
    benchmark_db_path = os.getenv("AIDC_BENCHMARK_DB", "data/benchmarks/accsetups.sqlite").strip()
    benchmark_condition = os.getenv("AIDC_BENCHMARK_CONDITION", "overall").strip().lower()

    print(
        f"[BOOT] provider={provider_mode} "
        f"tick_limit={tick_limit} acc_poll_hz={acc_poll_hz} "
        f"acc_max_idle_s={acc_max_idle_seconds:.1f} "
        f"capture_heartbeat={capture_heartbeat} every={capture_heartbeat_every_ticks} "
        f"baseline={baseline_mode} overlay={overlay_enabled} "
        f"dashboard={enable_dashboard}@{dashboard_host}:{dashboard_port} "
        f"benchmark={benchmark_condition} "
        f"log_file={log_path}"
    )
    app = CoachingApp(
        AppConfig(
            provider_mode=provider_mode,
            acc_poll_hz=acc_poll_hz,
            acc_max_idle_seconds=acc_max_idle_seconds,
            replay_file=replay_file,
            replay_speed=replay_speed,
            tick_limit=tick_limit,
            capture_heartbeat=capture_heartbeat,
            capture_heartbeat_every_ticks=capture_heartbeat_every_ticks,
            baseline_mode=baseline_mode,
            reference_features_path=reference_features_path,
            fallback_track_length_m=fallback_track_length_m,
            overlay_enabled=overlay_enabled,
            overlay_x=overlay_x,
            overlay_y=overlay_y,
            overlay_width=overlay_width,
            overlay_height=overlay_height,
            overlay_hint_seconds=overlay_hint_seconds,
            enable_dashboard=enable_dashboard,
            dashboard_host=dashboard_host,
            dashboard_port=dashboard_port,
            persist_raw_ticks=persist_raw_ticks,
            persist_parquet=persist_parquet,
            benchmark_db_path=Path(benchmark_db_path),
            benchmark_condition=benchmark_condition,
        )
    )
    app.run()


if __name__ == "__main__":
    main()
