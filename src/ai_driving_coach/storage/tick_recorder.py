from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional

import pyarrow as pa
import pyarrow.parquet as pq

from ai_driving_coach.models.telemetry import TelemetryTick


class TickRecorder:
    """Stores raw telemetry ticks by lap for replay and offline analysis."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._ticks_by_lap: Dict[int, List[TelemetryTick]] = {}

    def record(self, tick: TelemetryTick) -> None:
        self._ticks_by_lap.setdefault(tick.lap_count, []).append(tick)

    def flush_lap(self, lap_number: int, persist_parquet: bool = True) -> tuple[Optional[Path], Optional[Path]]:
        ticks = self._ticks_by_lap.pop(lap_number, [])
        if not ticks:
            return None, None

        rows = [asdict(tick) for tick in ticks]
        csv_path = self.output_dir / f"lap_{lap_number:03d}_ticks.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        parquet_path: Optional[Path] = None
        if persist_parquet:
            parquet_path = self.output_dir / f"lap_{lap_number:03d}_ticks.parquet"
            pq.write_table(pa.Table.from_pylist(rows), parquet_path)

        return csv_path, parquet_path

    def flush_all(self, persist_parquet: bool = True) -> List[tuple[int, Optional[Path], Optional[Path]]]:
        flushed: List[tuple[int, Optional[Path], Optional[Path]]] = []
        for lap_number in sorted(list(self._ticks_by_lap.keys())):
            csv_path, parquet_path = self.flush_lap(lap_number, persist_parquet=persist_parquet)
            flushed.append((lap_number, csv_path, parquet_path))
        return flushed
