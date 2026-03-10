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
        "to-do", "task", "action item", "deliver", "follow up"
    }

    RELATIVE_DAY_WORDS = {
        "today", "tomorrow", "tonight", "this evening", "this afternoon",
        "this morning", "next week", "next month"
    }

    TIME_PATTERN = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE)
    COMBINED_DAY_TIME_PATTERN = re.compile(
        r"\b("
        r"today|tomorrow|tonight|this evening|this afternoon|this morning|"
        r"next\s+[a-z]+|(?:on\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r")\s*(?:at)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        re.IGNORECASE,
    )

    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self, ai_service: Optional[OllamaService] = None,
                 enable_llm_fallback: bool = True,
                 timezone: Optional[str] = None,
                 confidence_threshold: float = 0.85):
        self.ai_service = ai_service
        self.enable_llm_fallback = enable_llm_fallback
        self.confidence_threshold = confidence_threshold

        tz = normalize_timezone(timezone or get_local_timezone_name())
        self.settings = ExtractionSettings(timezone=tz)

    # -------------------------
    # EXTRACT FROM MESSAGE
    # Handles extract functionality for from message.
    # -------------------------
    async def extract_from_message(self, message: Dict[str, Any]) -> List[EventCandidate]:
        """Extract event/task candidates from a message dictionary."""
        subject = message.get("subject", "")
        content = message.get("full_content") or message.get("content") or ""
        source = message.get("source", "gmail")
        source_id = message.get("id", "")

        text = self._normalize_text(subject, content)
        if not text:
            return []

        reference_dt = message.get("datetime")
        if isinstance(reference_dt, str):
            reference_dt = dateparser.parse(reference_dt)
        if reference_dt is not None and reference_dt.tzinfo is None:
            reference_dt = reference_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)

        # Quick keyword check to avoid heavy processing
        if not self._contains_relevant_keywords(text):
            return []

        candidates = self._deterministic_extract(
            text=text,
            subject=subject,
            source=source,
            source_id=source_id,
            reference_dt=reference_dt
        )
        if candidates:
            return candidates

        if self.enable_llm_fallback and self.ai_service:
            llm_candidates = await self._llm_extract(text, subject, source, source_id)
            return llm_candidates

        return []

    # -------------------------
    # NORMALIZE TEXT
    # Handles normalize functionality for text.
    # -------------------------
    def _normalize_text(self, subject: str, content: str) -> str:
        combined = f"{subject}\n{content}".strip()
        return combined[: self.settings.max_text_len]

    # -------------------------
    # CONTAINS RELEVANT KEYWORDS
    # Handles contains functionality for relevant keywords.
    # -------------------------
    def _contains_relevant_keywords(self, text: str) -> bool:
        lower = text.lower()
        for kw in self.EVENT_KEYWORDS.union(self.TASK_KEYWORDS):
            if kw in lower:
                return True
        for kw in self.RELATIVE_DAY_WORDS:
            if kw in lower:
                return True
        # Also look for date-like patterns
        if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", lower):
            return True
        if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", lower):
            return True
        if self.TIME_PATTERN.search(lower) and any(day in lower for day in ("today", "tomorrow", "next", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")):
            return True
        return False

    # -------------------------
    # DETERMINISTIC EXTRACT
    # Handles deterministic functionality for extract.
    # -------------------------
    def _deterministic_extract(self, text: str, subject: str,
                               source: str, source_id: str,
                               reference_dt: Optional[datetime] = None) -> List[EventCandidate]:
        settings = {
            "RETURN_AS_TIMEZONE_AWARE": True,
            "PREFER_DATES_FROM": "future" if self.settings.prefer_future else "current_period",
            "TIMEZONE": normalize_timezone(self.settings.timezone),
            "TO_TIMEZONE": normalize_timezone(self.settings.timezone),
        }
        if reference_dt:
            settings["RELATIVE_BASE"] = reference_dt

        combined_matches = list(self._extract_combined_day_time(text, settings))
        matches = list(combined_matches)
        search_results = search_dates(text, settings=settings, languages=["en"]) or []
        matches.extend(search_results)
        if not matches:
            return []

        candidates: List[EventCandidate] = []
        used_keys = set()
        now_ref = reference_dt or datetime.now()

        for match_text, dt in matches:
            if not isinstance(dt, datetime):
                continue

            # Heuristic: ignore dates too far in the past
            now_dt = now_ref
            if dt.tzinfo and now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=dt.tzinfo)
            if dt < now_dt - timedelta(days=2):
                continue

            has_time = bool(self.TIME_PATTERN.search(match_text.lower()))
            if combined_matches and re.fullmatch(r"\s*\d{1,2}(:\d{2})?\s*(am|pm)\s*", match_text.lower()):
                # Skip bare-time matches when an explicit day+time phrase already exists.
                continue
            is_birthday = "birthday" in text.lower()
            is_task = self._is_task_context(text, match_text)
            is_event_context = self._is_event_context(text, match_text, subject)
            if is_event_context:
                is_task = False

            title = self._derive_title(subject, match_text, text, is_task)
            key = f"{title.lower()}|{dt.isoformat()}"
            if key in used_keys:
                continue
            used_keys.add(key)

            all_day = is_birthday or not has_time
            end_dt = self._default_end(dt, all_day)

            confidence = self._score_confidence(match_text, text, has_time, is_task=is_task)
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

        return self._dedupe_candidates(candidates)

    # -------------------------
    # SCORE CONFIDENCE
    # Handles score functionality for confidence.
    # -------------------------
    def _score_confidence(self, match_text: str, full_text: str, has_time: bool, is_task: bool = False) -> float:
        score = 0.5
        lower = full_text.lower()
        m_lower = match_text.lower()

        # Absolute dates boost confidence
        if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", match_text):
            score += 0.2
        if re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b", m_lower):
            score += 0.2
        if any(word in m_lower for word in self.RELATIVE_DAY_WORDS):
            score += 0.1

        if has_time:
            score += 0.15

        if any(kw in lower for kw in self.EVENT_KEYWORDS):
            score += 0.1
        if is_task:
            score -= 0.05

        return max(0.1, min(0.95, score))

    # -------------------------
    # DERIVE TITLE
    # Handles derive functionality for title.
    # -------------------------
    def _derive_title(self, subject: str, match_text: str, full_text: str, is_task: bool) -> str:
        if subject:
            base = subject.strip()
        else:
            # First sentence fallback
            base = full_text.split(".", 1)[0].strip()
            if not base:
                base = match_text.strip()

        if is_task and not base.lower().startswith("to-do"):
            return f"To-do: {base}"
        return base

    # -------------------------
    # DEFAULT END
    # Handles default functionality for end.
    # -------------------------
    def _default_end(self, start: datetime, all_day: bool) -> datetime:
        if all_day:
            return start + timedelta(days=1)
        return start + timedelta(hours=1)

    # -------------------------
    # EXTRACT LOCATION
    # Handles extract functionality for location.
    # -------------------------
    def _extract_location(self, text: str) -> Optional[str]:
        # Simple heuristic: look for "at <location>" or "in <location>"
        match = re.search(r"\b(?:at|in)\s+([A-Za-z0-9\s\-_,]{3,50})", text)
        if match:
            return match.group(1).strip()
        return None

    # -------------------------
    # IS TASK CONTEXT
    # Evaluates whether task context.
    # -------------------------
    def _is_task_context(self, text: str, match_text: str = "") -> bool:
        lower = text.lower()
        if match_text:
            idx = lower.find(match_text.lower())
            if idx >= 0:
                start = max(0, idx - 80)
                end = min(len(lower), idx + len(match_text) + 80)
                lower = lower[start:end]
        return any(kw in lower for kw in self.TASK_KEYWORDS)

    # -------------------------
    # IS EVENT CONTEXT
    # Evaluates whether event context.
    # -------------------------
    def _is_event_context(self, text: str, match_text: str, subject: str) -> bool:
        combined = f"{subject}\n{text}".lower()
        if any(kw in combined for kw in self.EVENT_KEYWORDS):
            return True
        if match_text and "meeting" in match_text.lower():
            return True
        return False

    # -------------------------
    # BUILD DESCRIPTION
    # Handles build functionality for description.
    # -------------------------
    def _build_description(self, subject: str, text: str) -> str:
        snippet = text.strip().replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet)
        if len(snippet) > 300:
            snippet = snippet[:300] + "..."
        if subject:
            return f"Subject: {subject}\n\nMessage snippet:\n{snippet}"
        return f"Message snippet:\n{snippet}"

    # -------------------------
    # EXTRACT COMBINED DAY TIME
    # Handles extract functionality for combined day time.
    # -------------------------
    def _extract_combined_day_time(self, text: str, settings: Dict[str, Any]) -> List[Tuple[str, datetime]]:
        """Extract phrases like 'tomorrow at 7pm' to avoid date/time split matches."""
        results: List[Tuple[str, datetime]] = []
        for match in self.COMBINED_DAY_TIME_PATTERN.finditer(text):
            phrase = match.group(0).strip()
            dt = dateparser.parse(phrase, settings=settings)
            if isinstance(dt, datetime):
                results.append((phrase, dt))
        return results

    # -------------------------
    # DEDUPE CANDIDATES
    # Handles dedupe functionality for candidates.
    # -------------------------
    def _dedupe_candidates(self, candidates: List[EventCandidate]) -> List[EventCandidate]:
        if not candidates:
            return []

        grouped: Dict[Tuple[str, str], EventCandidate] = {}
        for cand in candidates:
            day_key = cand.start_dt.date().isoformat()
            key = (cand.title.lower(), day_key)

            existing = grouped.get(key)
            if existing is None:
                grouped[key] = cand
                continue

            # Prefer timed entries over all-day entries for the same title/day.
            if existing.all_day and not cand.all_day:
                grouped[key] = cand
                continue
            if (not existing.all_day) and cand.all_day:
                continue

            # Otherwise keep higher confidence candidate.
            if cand.confidence > existing.confidence:
                grouped[key] = cand

        deduped = list(grouped.values())
        deduped.sort(key=lambda x: x.start_dt)

        final: List[EventCandidate] = []
        for cand in deduped:
            match_idx = None
            for idx, existing in enumerate(final):
                same_title = existing.title.lower() == cand.title.lower()
                close_time = abs(existing.start_dt - cand.start_dt) <= timedelta(hours=26)
                if same_title and close_time:
                    match_idx = idx
                    break

            if match_idx is None:
                final.append(cand)
                continue

            existing = final[match_idx]
            replace = False
            if cand.confidence > existing.confidence:
                replace = True
            elif cand.confidence == existing.confidence and cand.start_dt < existing.start_dt:
                replace = True
            elif existing.all_day and not cand.all_day:
                replace = True

            if replace:
                final[match_idx] = cand

        final.sort(key=lambda x: x.start_dt)
        return final

    # -------------------------
    # LLM EXTRACT
    # Handles llm functionality for extract.
    # -------------------------
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
