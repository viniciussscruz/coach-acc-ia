from __future__ import annotations

import sqlite3
import unicodedata
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Sequence

from ai_driving_coach.benchmarks.models import BenchmarkEntry, BenchmarkReference

_TRACK_ALIASES = {
    "spa": "spa-franchorchamps",
    "spa francorchamps": "spa-franchorchamps",
    "spa-francorchamps": "spa-franchorchamps",
    "nurburgring 24h": "nordschleife",
    "nurburgring endurance": "nordschleife",
    "zolder": "zolder",
    "barcelona": "barcelona",
    "silverstone": "silverstone",
    "bathurst": "bathurst",
    "mount panorama": "bathurst",
    "brands hatch": "brands-hatch",
    "donington": "donington",
    "hungaroring": "hungaroring",
    "imola": "imola",
    "kyalami": "kyalami",
    "laguna seca": "laguna-seca",
    "misano": "misano",
    "monza": "monza",
    "nurburgring": "nurburgring",
    "oulton park": "oulton-park",
    "paul ricard": "paul-ricard",
    "red bull ring": "red-bull-ring",
    "snetterton": "snetterton",
    "suzuka": "suzuka",
    "valencia": "valencia",
    "watkins glen": "watkins-glen",
    "cota": "cota",
}

_CAR_ALIASES = {
    "bmw m4 gt3": "bmw-m4-gt3-1",
    "bmw_m4_gt3": "bmw-m4-gt3-1",
    "ferrari 296 gt3": "ferrari-296-gt3-1",
    "ferrari_296_gt3": "ferrari-296-gt3-1",
    "lamborghini huracan evo2 gt3": "lamborghini-huracan-evo2-gt3",
    "lamborghini_huracan_evo2_gt3": "lamborghini-huracan-evo2-gt3",
    "mclaren 720s evo gt3": "mclaren-720s-evo-gt3",
    "mclaren_720s_evo_gt3": "mclaren-720s-evo-gt3",
    "mercedes amg gt3 evo": "mercedes-amg-evo-gt3",
    "mercedes_amg_gt3_evo": "mercedes-amg-evo-gt3",
    "audi r8 lms evo ii gt3": "audi-r8-lms-evo-ii-gt3",
    "audi_r8_lms_evo_ii_gt3": "audi-r8-lms-evo-ii-gt3",
    "porsche 992 gt3 r": "porsche-992-gt3-r",
    "porsche_992_gt3_r": "porsche-992-gt3-r",
}


class BenchmarkRepository:
    """Persists and resolves benchmark lap times from external sources."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_entries (
                    track_slug TEXT NOT NULL,
                    track_name TEXT NOT NULL,
                    car_slug TEXT NOT NULL,
                    car_name TEXT NOT NULL,
                    car_class TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    lap_time_s REAL NOT NULL,
                    lap_time_text TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_setup_id TEXT,
                    updated_at_utc TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                    PRIMARY KEY (track_slug, car_slug, condition)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_benchmark_track_cond
                ON benchmark_entries (track_slug, condition, lap_time_s)
                """
            )

    def upsert_entries(self, entries: Iterable[BenchmarkEntry]) -> int:
        upserted = 0
        with self._connect() as conn:
            for entry in entries:
                conn.execute(
                    """
                    INSERT INTO benchmark_entries (
                        track_slug, track_name, car_slug, car_name, car_class,
                        condition, lap_time_s, lap_time_text, source_url, source_setup_id
                    ) VALUES (
                        :track_slug, :track_name, :car_slug, :car_name, :car_class,
                        :condition, :lap_time_s, :lap_time_text, :source_url, :source_setup_id
                    )
                    ON CONFLICT(track_slug, car_slug, condition) DO UPDATE SET
                        track_name = excluded.track_name,
                        car_name = excluded.car_name,
                        car_class = excluded.car_class,
                        source_url = excluded.source_url,
                        source_setup_id = excluded.source_setup_id,
                        updated_at_utc = (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                        lap_time_s = CASE
                            WHEN excluded.lap_time_s < benchmark_entries.lap_time_s THEN excluded.lap_time_s
                            ELSE benchmark_entries.lap_time_s
                        END,
                        lap_time_text = CASE
                            WHEN excluded.lap_time_s < benchmark_entries.lap_time_s THEN excluded.lap_time_text
                            ELSE benchmark_entries.lap_time_text
                        END
                    """,
                    asdict(entry),
                )
                upserted += 1
            conn.commit()
        return upserted

    def count_entries(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM benchmark_entries").fetchone()
            return int(row["n"]) if row is not None else 0

    def list_tracks(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT track_slug FROM benchmark_entries ORDER BY track_slug").fetchall()
            return [str(row["track_slug"]) for row in rows]

    def list_cars(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT car_slug FROM benchmark_entries ORDER BY car_slug").fetchall()
            return [str(row["car_slug"]) for row in rows]

    def find_reference(
        self,
        track_name: str | None,
        car_name: str | None,
        condition: str = "overall",
    ) -> BenchmarkReference | None:
        track_slug = self._resolve_track_slug(track_name)
        if not track_slug:
            return None
        car_slug = self._resolve_car_slug(car_name)
        requested_condition = (condition or "overall").strip().lower()

        with self._connect() as conn:
            if car_slug:
                row = self._find_by_track_and_car(conn, track_slug, car_slug, requested_condition)
                if row is not None:
                    return self._row_to_reference(row, scope="same_car", requested_condition=requested_condition)

            row = self._find_by_track_best(conn, track_slug, requested_condition)
            if row is None:
                return None
            return self._row_to_reference(row, scope="track_overall", requested_condition=requested_condition)

    def _find_by_track_and_car(
        self,
        conn: sqlite3.Connection,
        track_slug: str,
        car_slug: str,
        condition: str,
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT *
            FROM benchmark_entries
            WHERE track_slug = ? AND car_slug = ? AND condition = ?
            LIMIT 1
            """,
            (track_slug, car_slug, condition),
        ).fetchone()
        if row is not None or condition == "overall":
            return row
        return conn.execute(
            """
            SELECT *
            FROM benchmark_entries
            WHERE track_slug = ? AND car_slug = ? AND condition = 'overall'
            LIMIT 1
            """,
            (track_slug, car_slug),
        ).fetchone()

    def _find_by_track_best(
        self,
        conn: sqlite3.Connection,
        track_slug: str,
        condition: str,
    ) -> sqlite3.Row | None:
        row = conn.execute(
            """
            SELECT *
            FROM benchmark_entries
            WHERE track_slug = ? AND condition = ?
            ORDER BY lap_time_s ASC
            LIMIT 1
            """,
            (track_slug, condition),
        ).fetchone()
        if row is not None or condition == "overall":
            return row
        return conn.execute(
            """
            SELECT *
            FROM benchmark_entries
            WHERE track_slug = ? AND condition = 'overall'
            ORDER BY lap_time_s ASC
            LIMIT 1
            """,
            (track_slug,),
        ).fetchone()

    def _resolve_track_slug(self, track_name: str | None) -> str | None:
        if not track_name:
            return None
        normalized = _normalize(track_name)
        if normalized in _TRACK_ALIASES:
            return _TRACK_ALIASES[normalized]
        candidates = self.list_tracks()
        return _best_slug_match(normalized, candidates)

    def _resolve_car_slug(self, car_name: str | None) -> str | None:
        if not car_name:
            return None
        normalized = _normalize(car_name)
        if normalized in _CAR_ALIASES:
            return _CAR_ALIASES[normalized]
        candidates = self.list_cars()
        return _best_slug_match(normalized, candidates)

    def _row_to_reference(self, row: sqlite3.Row, scope: str, requested_condition: str) -> BenchmarkReference:
        return BenchmarkReference(
            track_slug=str(row["track_slug"]),
            track_name=str(row["track_name"]),
            car_slug=str(row["car_slug"]),
            car_name=str(row["car_name"]),
            car_class=str(row["car_class"]),
            condition=str(row["condition"]),
            lap_time_s=float(row["lap_time_s"]),
            lap_time_text=str(row["lap_time_text"]),
            source_url=str(row["source_url"]),
            source_setup_id=row["source_setup_id"],
            scope=scope,
            requested_condition=requested_condition,
        )


def _normalize(value: str) -> str:
    clean = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    tokens = [token for token in _split_tokens(clean) if token]
    return " ".join(tokens)


def _split_tokens(value: str) -> list[str]:
    token = []
    result: list[str] = []
    for char in value.lower():
        if char.isalnum():
            token.append(char)
        else:
            if token:
                result.append("".join(token))
                token = []
    if token:
        result.append("".join(token))
    return result


def _best_slug_match(query: str, candidates: Sequence[str]) -> str | None:
    if not query:
        return None
    query_tokens = set(_split_tokens(query))
    if not query_tokens:
        return None

    best_slug: str | None = None
    best_score = 0.0
    for slug in candidates:
        candidate_tokens = set(_split_tokens(slug))
        if not candidate_tokens:
            continue
        overlap = len(query_tokens & candidate_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(query_tokens), len(candidate_tokens))
        if score > best_score:
            best_score = score
            best_slug = slug

    if best_score < 0.35:
        return None
    return best_slug
