"""Benchmark ingestion and lookup for lap-time references."""

from ai_driving_coach.benchmarks.models import BenchmarkEntry, BenchmarkReference
from ai_driving_coach.benchmarks.repository import BenchmarkRepository

__all__ = ["BenchmarkEntry", "BenchmarkReference", "BenchmarkRepository"]
