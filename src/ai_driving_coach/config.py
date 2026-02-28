from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    provider_mode: str = "mock"  # mock | acc | replay
    acc_poll_hz: int = 60
    acc_max_idle_seconds: float = 0.0
    replay_file: str = ""
    replay_speed: float = 1.0
    tick_limit: int = 0
    capture_heartbeat: bool = True
    capture_heartbeat_every_ticks: int = 120
    baseline_mode: str = "session_best"  # session_best | external
    reference_features_path: str = ""
    fallback_track_length_m: float = 0.0
    overlay_enabled: bool = True
    overlay_x: int = 24
    overlay_y: int = 24
    overlay_width: int = 520
    overlay_height: int = 190
    overlay_hint_seconds: float = 3.0
    enable_dashboard: bool = True
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8765
    persist_raw_ticks: bool = True
    output_dir: Path = Path("data") / "session_output"
    persist_parquet: bool = True
    benchmark_db_path: Path = Path("data") / "benchmarks" / "accsetups.sqlite"
    benchmark_condition: str = "overall"  # overall | dry | wet
