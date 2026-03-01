# -------------------------
# EVENT/TASK EXTRACTOR
# -------------------------
"""
Extract calendar events/tasks from message content with hybrid deterministic + LLM fallback.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import dateparser
from dateparser.search import search_dates

from src.backend.models.event_models import CalendarItemType, EventCandidate
from src.backend.utils.timezone_utils import get_local_timezone_name, normalize_timezone
from src.backend.services.ai_service import OllamaService


@dataclass
class ExtractionSettings:
    timezone: str
    prefer_future: bool = True
    max_text_len: int = 3000


class EventExtractor:
    """Hybrid extractor for event/task candidates from message data."""

    EVENT_KEYWORDS = {
        "meeting", "interview", "call", "appointment", "demo", "presentation",
        "webinar", "workshop", "conference", "standup", "sync", "catch up",
        "review", "check-in", "kickoff", "birthday"
    }

    TASK_KEYWORDS = {
        "deadline", "due", "submit", "complete", "finish", "todo",
        "task", "action item", "please", "need to"
    }

    TIME_PATTERN = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE)

    def __init__(self, ai_service: Optional[OllamaService] = None,
                 enable_llm_fallback: bool = True,
                 timezone: Optional[str] = None,
                 confidence_threshold: float = 0.85):
        self.ai_service = ai_service
        self.enable_llm_fallback = enable_llm_fallback
        self.confidence_threshold = confidence_threshold

        tz = normalize_timezone(timezone or get_local_timezone_name())
        self.settings = ExtractionSettings(timezone=tz)

    async def extract_from_message(self, message: Dict[str, Any]) -> List[EventCandidate]:
        """Extract event/task candidates from a message dictionary."""
        subject = message.get("subject", "")
        content = message.get("full_content") or message.get("content") or ""
        source = message.get("source", "gmail")
        source_id = message.get("id", "")

        text = self._normalize_text(subject, content)
        if not text:
            return []

        # Quick keyword check to avoid heavy processing
        if not self._contains_relevant_keywords(text):
            return []

        candidates = self._deterministic_extract(text, subject, source, source_id)
        if candidates:
            return candidates

        if self.enable_llm_fallback and self.ai_service:
            llm_candidates = await self._llm_extract(text, subject, source, source_id)
            return llm_candidates

        return []

    def _normalize_text(self, subject: str, content: str) -> str:
        combined = f"{subject}\n{content}".strip()
        return combined[: self.settings.max_text_len]

    def _contains_relevant_keywords(self, text: str) -> bool:
        lower = text.lower()
        for kw in self.EVENT_KEYWORDS.union(self.TASK_KEYWORDS):
            if kw in lower:
                return True
        # Also look for date-like patterns
        if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", lower):
            return True
        if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", lower):
            return True
        return False

    def _deterministic_extract(self, text: str, subject: str,
                               source: str, source_id: str) -> List[EventCandidate]:
        settings = {
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future" if self.settings.prefer_future else "current_period",
            "TIMEZONE": normalize_timezone(self.settings.timezone),
            "TO_TIMEZONE": normalize_timezone(self.settings.timezone),
        }

        matches = search_dates(text, settings=settings) or []
        if not matches:
            return []

        candidates: List[EventCandidate] = []
        used_keys = set()

        for match_text, dt in matches:
            if not isinstance(dt, datetime):
                continue

            # Heuristic: ignore dates too far in the past
            if dt < datetime.now(tz=dt.tzinfo) - timedelta(days=2):
                continue

            has_time = bool(self.TIME_PATTERN.search(match_text))
            is_birthday = "birthday" in text.lower()
            is_task = self._is_task_context(text)

            title = self._derive_title(subject, match_text, text, is_task)
            key = f"{title}|{dt.isoformat()}"
            if key in used_keys:
                continue
            used_keys.add(key)

            all_day = is_birthday or not has_time
            end_dt = self._default_end(dt, all_day)

            confidence = self._score_confidence(match_text, text, has_time)
            item_type = CalendarItemType.TASK if is_task and not is_birthday else CalendarItemType.EVENT

            candidates.append(EventCandidate(
                item_type=item_type,
                title=title,
                start_dt=dt,
                end_dt=end_dt,
                all_day=all_day,
                timezone=normalize_timezone(self.settings.timezone),
                location=self._extract_location(text),
                attendees=[],
                source=source,
                source_id=source_id,
                confidence=confidence,
                description=self._build_description(subject, text),
                recurrence=None,
            ))

        return candidates

    def _score_confidence(self, match_text: str, full_text: str, has_time: bool) -> float:
        score = 0.5
        lower = full_text.lower()

        # Absolute dates boost confidence
        if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", match_text):
            score += 0.2
        if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", match_text.lower()):
            score += 0.2

        if has_time:
            score += 0.15

        if any(kw in lower for kw in self.EVENT_KEYWORDS):
            score += 0.1

        return max(0.1, min(0.95, score))

    def _derive_title(self, subject: str, match_text: str, full_text: str, is_task: bool) -> str:
        if subject:
            base = subject.strip()
        else:
            # First sentence fallback
            base = full_text.split(".", 1)[0].strip()
            if not base:
                base = match_text.strip()

        if is_task and not base.lower().startswith("task"):
            return f"Task: {base}"
        return base

    def _default_end(self, start: datetime, all_day: bool) -> datetime:
        if all_day:
            return start + timedelta(days=1)
        return start + timedelta(hours=1)

    def _extract_location(self, text: str) -> Optional[str]:
        # Simple heuristic: look for "at <location>" or "in <location>"
        match = re.search(r"\b(?:at|in)\s+([A-Za-z0-9\s\-_,]{3,50})", text)
        if match:
            return match.group(1).strip()
        return None

    def _is_task_context(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in self.TASK_KEYWORDS)

    def _build_description(self, subject: str, text: str) -> str:
        snippet = text.strip().replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet)
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        return f"Subject: {subject}\n\n{snippet}" if subject else snippet

    async def _llm_extract(self, text: str, subject: str,
                           source: str, source_id: str) -> List[EventCandidate]:
        prompt = f"""
        Extract events and tasks from the message. Return STRICT JSON only.

        Schema:
        {{
          "items": [
            {{
              "item_type": "event"|"task",
              "title": "...",
              "start_dt": "YYYY-MM-DDTHH:MM:SS±HH:MM",
              "end_dt": "YYYY-MM-DDTHH:MM:SS±HH:MM"|null,
              "all_day": true|false,
              "timezone": "{self.settings.timezone}",
              "location": "..."|null,
              "confidence": 0.0-1.0,
              "description": "...",
              "recurrence": null
            }}
          ]
        }}

        Message subject: {subject}
        Message body: {text[:1500]}
        """

        try:
            response = await self.ai_service.generate_summary_async(prompt)
            data = json.loads(response)
            items = data.get("items", [])
            results: List[EventCandidate] = []
            for item in items:
                try:
                    results.append(EventCandidate(
                        item_type=CalendarItemType(item.get("item_type", "event")),
                        title=item.get("title", "Untitled"),
                        start_dt=dateparser.parse(item.get("start_dt")),
                        end_dt=dateparser.parse(item.get("end_dt")) if item.get("end_dt") else None,
                        all_day=bool(item.get("all_day", False)),
                        timezone=item.get("timezone", self.settings.timezone),
                        location=item.get("location"),
                        attendees=[],
                        source=source,
                        source_id=source_id,
                        confidence=float(item.get("confidence", 0.5)),
                        description=item.get("description"),
                        recurrence=item.get("recurrence"),
                    ))
                except Exception:
                    continue
            return results
        except Exception:
            return []
