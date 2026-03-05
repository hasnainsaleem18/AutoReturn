# -------------------------
# EVENT/TASK MODELS
# -------------------------
"""
Structured models for extracted calendar events and tasks.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CalendarItemType(str, Enum):
    EVENT = "event"
    TASK = "task"


class EventCandidate(BaseModel):
    """Candidate calendar item extracted from a message."""

    item_type: CalendarItemType = CalendarItemType.EVENT
    title: str
    start_dt: datetime
    end_dt: Optional[datetime] = None
    all_day: bool = False
    timezone: str
    location: Optional[str] = None
    attendees: List[str] = Field(default_factory=list)
    source: str
    source_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    description: Optional[str] = None
    recurrence: Optional[str] = None

    def ensure_end(self) -> "EventCandidate":
        """Ensure end_dt is set with a sensible default."""
        if self.end_dt:
            return self

        if self.all_day:
            # All-day events use end date as next day
            self.end_dt = self.start_dt + timedelta(days=1)
        else:
            # Default duration: 60 minutes
            self.end_dt = self.start_dt + timedelta(hours=1)

        return self
