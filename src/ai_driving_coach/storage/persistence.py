from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List

import pyarrow as pa
import pyarrow.parquet as pq

from ai_driving_coach.features.models import CornerFeature


class SessionPersistence:
    """CSV and Parquet persistence for extracted features."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_lap_features_csv(self, lap_number: int, features: Iterable[CornerFeature]) -> Path:
        rows = [feature.to_dict() for feature in features]
        file_path = self.output_dir / f"lap_{lap_number:03d}_features.csv"
        if not rows:
            file_path.write_text("", encoding="utf-8")
            return file_path

        with file_path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return file_path

    def save_lap_features_parquet(self, lap_number: int, features: List[CornerFeature]) -> Path:
        rows = [feature.to_dict() for feature in features]
        file_path = self.output_dir / f"lap_{lap_number:03d}_features.parquet"
        table = pa.Table.from_pylist(rows) if rows else pa.Table.from_pylist([{"lap_number": lap_number}]).slice(0, 0)
        pq.write_table(table, file_path)
        return file_path

