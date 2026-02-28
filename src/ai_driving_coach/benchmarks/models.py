from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class BenchmarkEntry:
    track_slug: str
    track_name: str
    car_slug: str
    car_name: str
    car_class: str
    condition: str  # overall | dry | wet
    lap_time_s: float
    lap_time_text: str
    source_url: str
    source_setup_id: Optional[str] = None


@dataclass(slots=True)
class BenchmarkReference:
    track_slug: str
    track_name: str
    car_slug: str
    car_name: str
    car_class: str
    condition: str
    lap_time_s: float
    lap_time_text: str
    source_url: str
    source_setup_id: Optional[str]
    scope: str  # same_car | track_overall
    requested_condition: str
