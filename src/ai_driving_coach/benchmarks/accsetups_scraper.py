from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

from ai_driving_coach.benchmarks.models import BenchmarkEntry

BASE_URL = "https://accsetups.com/"

_TIME_RE = re.compile(r"(?P<m>\d{1,2}):(?P<s>\d{2}\.\d{2,3})")


@dataclass(slots=True)
class RawSetupRow:
    track_slug: str
    track_name: str
    car_slug: str
    car_name: str
    car_class: str
    lap_time_s: float
    lap_time_text: str
    has_wet_variant: bool
    source_url: str
    source_setup_id: str | None


class ACCSetupsScraper:
    """Scrapes setup rows and lap times from accsetups.com."""

    def __init__(self, delay_s: float = 0.2, timeout_s: float = 25.0) -> None:
        self.delay_s = max(0.0, delay_s)
        self.timeout_s = timeout_s
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "ai-driving-coach/0.1 (+local benchmark sync)",
                "Accept-Language": "en-US,en;q=0.9",
            }
        )

    def scrape(self, max_tracks: int = 0) -> List[BenchmarkEntry]:
        track_urls = self._discover_track_urls()
        if max_tracks > 0:
            track_urls = sorted(track_urls)[:max_tracks]

        rows: List[RawSetupRow] = []
        for idx, track_url in enumerate(sorted(track_urls), start=1):
            track_rows = self._scrape_track_page(track_url)
            if track_rows:
                rows.extend(track_rows)
            if self.delay_s > 0.0 and idx < len(track_urls):
                time.sleep(self.delay_s)

        return self._build_benchmarks(rows)

    def _discover_track_urls(self) -> Set[str]:
        home = self._get(BASE_URL)
        track_urls = set()
        for link in home.select("a[href*='/games/assetto-corsa-competizione/tracks/']"):
            href = (link.get("href") or "").strip()
            if not href:
                continue
            full = urljoin(BASE_URL, href)
            if "/tracks/base-setup/" in full:
                continue
            track_urls.add(full)
        if track_urls:
            return track_urls

        # Fallback path in case home structure changes.
        car_urls = set()
        for link in home.select("a[href*='/games/assetto-corsa-competizione/cars/']"):
            href = (link.get("href") or "").strip()
            if not href:
                continue
            car_urls.add(urljoin(BASE_URL, href))

        for car_url in sorted(car_urls):
            soup = self._get(car_url)
            for link in soup.select("a[href*='/games/assetto-corsa-competizione/tracks/']"):
                href = (link.get("href") or "").strip()
                if not href:
                    continue
                full = urljoin(BASE_URL, href)
                if "/tracks/base-setup/" in full:
                    continue
                track_urls.add(full)
            if self.delay_s > 0.0:
                time.sleep(self.delay_s)

        return track_urls

    def _scrape_track_page(self, track_url: str) -> List[RawSetupRow]:
        soup = self._get(track_url)
        rows: List[RawSetupRow] = []
        for row in soup.select("div.setup-list__row.setup-list__row--item"):
            parsed = self._parse_row(row=row, source_url=track_url)
            if parsed is not None:
                rows.append(parsed)
        return rows

    def _parse_row(self, row: Tag, source_url: str) -> RawSetupRow | None:
        car_link = row.select_one(".setup-list__car a[href*='/cars/']")
        class_link = row.select_one(".setup-list__car .setup-list__class")
        track_link = row.select_one(".setup-list__track a[href*='/tracks/']")
        time_span = row.select_one(".setup-list__time")
        if car_link is None or class_link is None or track_link is None or time_span is None:
            return None

        car_href = car_link.get("href") or ""
        track_href = track_link.get("href") or ""
        car_slug = self._slug_from_href(car_href, "cars")
        track_slug = self._slug_from_href(track_href, "tracks")
        if not car_slug or not track_slug:
            return None

        time_text = self._extract_time_text(time_span.get_text(" ", strip=True))
        lap_time_s = self._parse_lap_time_seconds(time_text)
        if lap_time_s <= 0.0:
            return None

        return RawSetupRow(
            track_slug=track_slug,
            track_name=track_link.get_text(" ", strip=True),
            car_slug=car_slug,
            car_name=car_link.get_text(" ", strip=True),
            car_class=class_link.get_text(" ", strip=True),
            lap_time_s=lap_time_s,
            lap_time_text=time_text,
            has_wet_variant=row.select_one(".setup-list__variants__wet") is not None,
            source_url=source_url,
            source_setup_id=row.get("data-id"),
        )

    def _build_benchmarks(self, rows: Iterable[RawSetupRow]) -> List[BenchmarkEntry]:
        grouped: dict[tuple[str, str], List[RawSetupRow]] = {}
        for row in rows:
            grouped.setdefault((row.track_slug, row.car_slug), []).append(row)

        benchmarks: List[BenchmarkEntry] = []
        for _, entries in grouped.items():
            entries_sorted = sorted(entries, key=lambda r: r.lap_time_s)
            best_overall = entries_sorted[0]
            benchmarks.append(self._to_entry(best_overall, condition="overall"))

            dry_candidates = [r for r in entries_sorted if not r.has_wet_variant]
            wet_candidates = [r for r in entries_sorted if r.has_wet_variant]
            if dry_candidates:
                benchmarks.append(self._to_entry(dry_candidates[0], condition="dry"))
            else:
                benchmarks.append(self._to_entry(best_overall, condition="dry"))
            if wet_candidates:
                benchmarks.append(self._to_entry(wet_candidates[0], condition="wet"))

        return benchmarks

    def _to_entry(self, row: RawSetupRow, condition: str) -> BenchmarkEntry:
        return BenchmarkEntry(
            track_slug=row.track_slug,
            track_name=row.track_name,
            car_slug=row.car_slug,
            car_name=row.car_name,
            car_class=row.car_class,
            condition=condition,
            lap_time_s=row.lap_time_s,
            lap_time_text=row.lap_time_text,
            source_url=row.source_url,
            source_setup_id=row.source_setup_id,
        )

    def _get(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=self.timeout_s)
        if response.status_code >= 400:
            raise RuntimeError(f"Falha ao carregar pagina: status={response.status_code} url={url}")
        return BeautifulSoup(response.text, "html.parser")

    def _slug_from_href(self, href: str, kind: str) -> str:
        token = f"/{kind}/"
        if token not in href:
            return ""
        return href.split(token, 1)[1].strip("/").split("/", 1)[0]

    def _extract_time_text(self, text: str) -> str:
        match = _TIME_RE.search(text)
        return match.group(0) if match is not None else ""

    def _parse_lap_time_seconds(self, lap_time_text: str) -> float:
        match = _TIME_RE.fullmatch(lap_time_text)
        if match is None:
            return 0.0
        minutes = int(match.group("m"))
        seconds = float(match.group("s"))
        return minutes * 60.0 + seconds
