"""Unit tests for EventExtractor deterministic behavior."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from src.backend.core.event_extractor import EventExtractor


class TestEventExtractorFormal(unittest.IsolatedAsyncioTestCase):
    # -------------------------
    # FUNCTION: asyncSetUp
    # Purpose: Execute asyncSetUp logic for this module.
    # -------------------------
    async def asyncSetUp(self):
        self.extractor = EventExtractor(
            ai_service=None,
            enable_llm_fallback=False,
            timezone="UTC",
            confidence_threshold=0.85,
        )

    # -------------------------
    # FUNCTION: test_extract_relative_meeting
    # Purpose: Validate the extract relative meeting scenario.
    # -------------------------
    async def test_extract_relative_meeting(self):
        base = datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc)
        message = {
            "id": "evt_001",
            "source": "gmail",
            "subject": "Meeting reminder",
            "full_content": "Hi, we have a meeting tomorrow at 7pm.",
            "datetime": base,
        }

        events = await self.extractor.extract_from_message(message)

        self.assertGreaterEqual(len(events), 1)
        first = events[0]
        self.assertEqual(first.item_type.value, "event")
        self.assertFalse(first.all_day)
        self.assertEqual(first.start_dt.date(), (base + timedelta(days=1)).date())

    # -------------------------
    # FUNCTION: test_extract_birthday_as_all_day
    # Purpose: Validate the extract birthday as all day scenario.
    # -------------------------
    async def test_extract_birthday_as_all_day(self):
        message = {
            "id": "evt_002",
            "source": "gmail",
            "subject": "Birthday reminder",
            "full_content": "Sara's birthday is on May 12.",
        }

        events = await self.extractor.extract_from_message(message)

        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(any(e.all_day for e in events))

    # -------------------------
    # FUNCTION: test_ignore_irrelevant_text
    # Purpose: Validate the ignore irrelevant text scenario.
    # -------------------------
    async def test_ignore_irrelevant_text(self):
        message = {
            "id": "evt_003",
            "source": "slack",
            "subject": "Status",
            "full_content": "Thanks for the update. Looks good to me.",
        }

        events = await self.extractor.extract_from_message(message)
        self.assertEqual(events, [])

    # -------------------------
    # FUNCTION: test_detect_task_context
    # Purpose: Validate the detect task context scenario.
    # -------------------------
    async def test_detect_task_context(self):
        message = {
            "id": "evt_004",
            "source": "gmail",
            "subject": "Submission deadline",
            "full_content": "Please submit the final report tomorrow at 5pm before the deadline.",
            "datetime": datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc),
        }

        events = await self.extractor.extract_from_message(message)

        self.assertGreaterEqual(len(events), 1)
        self.assertTrue(any(e.item_type.value == "task" for e in events))


if __name__ == "__main__":
    unittest.main()
