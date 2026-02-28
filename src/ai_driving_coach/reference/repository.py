from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pyarrow.parquet as pq

from ai_driving_coach.features.models import CornerFeature


@dataclass(slots=True)
class ReferenceLap:
    source_path: str
    features: List[CornerFeature]


class ReferenceLapRepository:
    """Loads external corner features as baseline (pro/coach data)."""

    def load_features(self, path: str) -> ReferenceLap:
        file_path = Path(path)
        if not file_path.exists():
            raise RuntimeError(f"Reference file nao encontrado: {file_path}")

        ext = file_path.suffix.lower()
        if ext == ".csv":
            rows = self._read_csv(file_path)
        elif ext in {".parquet", ".pq"}:
            rows = self._read_parquet(file_path)
        else:
            raise RuntimeError("Reference file invalido. Use .csv ou .parquet.")

        features = [self._row_to_feature(row) for row in rows]
        if not features:
            raise RuntimeError("Reference file vazio.")
        return ReferenceLap(source_path=str(file_path), features=features)

    def _read_csv(self, file_path: Path) -> List[dict]:
        with file_path.open("r", newline="", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            return [row for row in reader]

    def _read_parquet(self, file_path: Path) -> List[dict]:
        return pq.read_table(file_path).to_pylist()

    def _row_to_feature(self, row: dict) -> CornerFeature:
        def _f(name: str, default: float = 0.0) -> float:
            value = row.get(name)
            if value in (None, "", "None"):
                return default
            return float(value)

        def _i(name: str, default: int = 0) -> int:
            value = row.get(name)
            if value in (None, "", "None"):
                return default
            return int(value)

        return CornerFeature(
            lap_number=_i("lap_number", 0),
            corner_index=_i("corner_index", 0),
            brake_start_point=_f("brake_start_point"),
            turn_in_point=_f("turn_in_point"),
            apex_point=_f("apex_point"),
            brake_peak=_f("brake_peak"),
            brake_duration=_f("brake_duration"),
            min_speed=_f("min_speed"),
            throttle_on_point=_f("throttle_on_point"),
            exit_stabilization_point=_f("exit_stabilization_point"),
            time_to_full_throttle=_f("time_to_full_throttle"),
            exit_speed=_f("exit_speed"),
            track_name=(row.get("track_name") or None),
            track_length_m=(
                float(row["track_length_m"]) if row.get("track_length_m") not in (None, "", "None") else None
            ),
        )

