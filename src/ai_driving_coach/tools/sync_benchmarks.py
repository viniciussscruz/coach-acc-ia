from __future__ import annotations

import argparse
from pathlib import Path

from ai_driving_coach.benchmarks.accsetups_scraper import ACCSetupsScraper
from ai_driving_coach.benchmarks.repository import BenchmarkRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sincroniza benchmark de voltas do accsetups.com para SQLite local."
    )
    parser.add_argument(
        "--db",
        default="data/benchmarks/accsetups.sqlite",
        help="Caminho do banco SQLite de benchmark.",
    )
    parser.add_argument(
        "--max-tracks",
        type=int,
        default=0,
        help="Limite de pistas para teste rapido (0 = todas).",
    )
    parser.add_argument(
        "--delay-s",
        type=float,
        default=0.15,
        help="Atraso entre requests para evitar sobrecarga no site.",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=25.0,
        help="Timeout por request em segundos.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db)

    scraper = ACCSetupsScraper(delay_s=args.delay_s, timeout_s=args.timeout_s)
    print(f"[BENCH] iniciando scrape max_tracks={args.max_tracks} delay_s={args.delay_s:.2f}")
    entries = scraper.scrape(max_tracks=args.max_tracks)
    print(f"[BENCH] registros coletados: {len(entries)}")

    repo = BenchmarkRepository(db_path)
    upserted = repo.upsert_entries(entries)
    total = repo.count_entries()
    print(
        f"[BENCH] upsert={upserted} total={total} "
        f"tracks={len(repo.list_tracks())} cars={len(repo.list_cars())} db={db_path}"
    )


if __name__ == "__main__":
    main()

