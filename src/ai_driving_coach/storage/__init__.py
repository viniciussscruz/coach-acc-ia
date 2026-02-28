"""Data persistence adapters."""

from ai_driving_coach.storage.persistence import SessionPersistence
from ai_driving_coach.storage.tick_recorder import TickRecorder

__all__ = ["SessionPersistence", "TickRecorder"]
