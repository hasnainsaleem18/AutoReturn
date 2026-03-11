"""Unit tests for CalendarService helpers and payload formatting."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone

from src.backend.models.event_models import CalendarItemType, EventCandidate
from src.backend.services.calendar_service import CalendarService


class _FakeEventsAPI:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, items):
        self._items = items

    # -------------------------
    # FUNCTION: list
    # Purpose: Execute list logic for this module.
    # -------------------------
    def list(self, **_kwargs):
        return self

    # -------------------------
    # FUNCTION: execute
    # Purpose: Execute execute logic for this module.
    # -------------------------
    def execute(self):
        return {"items": self._items}


class _FakeService:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, items):
        self._items = items

    # -------------------------
    # FUNCTION: events
    # Purpose: Execute events logic for this module.
    # -------------------------
    def events(self):
        return _FakeEventsAPI(self._items)


class TestCalendarServiceFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = CalendarService(self.tmp.name)

    # -------------------------
    # FUNCTION: _sample_event
    # Purpose: Execute  sample event logic for this module.
    # -------------------------
    def _sample_event(self, **overrides):
        data = {
            "item_type": CalendarItemType.EVENT,
            "title": "Team Meeting",
            "start_dt": datetime(2026, 3, 5, 19, 0),
            "end_dt": datetime(2026, 3, 5, 20, 0),
            "all_day": False,
            "timezone": "PKT",
            "source": "gmail",
            "source_id": "abc123",
            "confidence": 0.92,
            "description": "desc",
        }
        data.update(overrides)
        return EventCandidate(**data)

    # -------------------------
    # FUNCTION: test_ics_escape
    # Purpose: Validate the ics escape scenario.
    # -------------------------
    def test_ics_escape(self):
        text = "A,B;C\\D\nE"
        escaped = self.svc._ics_escape(text)
        self.assertIn("\\,", escaped)
        self.assertIn("\\;", escaped)
        self.assertIn("\\\\", escaped)
        self.assertIn("\\n", escaped)

    # -------------------------
    # FUNCTION: test_event_to_payload_timed
    # Purpose: Validate the event to payload timed scenario.
    # -------------------------
    def test_event_to_payload_timed(self):
        ev = self._sample_event()
        payload = self.svc._event_to_payload(ev)
        self.assertIn("dateTime", payload["start"])
        self.assertEqual(payload["start"]["timeZone"], "Asia/Karachi")
        self.assertEqual(payload["summary"], "Team Meeting")

    # -------------------------
    # FUNCTION: test_event_to_payload_all_day
    # Purpose: Validate the event to payload all day scenario.
    # -------------------------
    def test_event_to_payload_all_day(self):
        ev = self._sample_event(all_day=True, end_dt=datetime(2026, 3, 6, 0, 0))
        payload = self.svc._event_to_payload(ev)
        self.assertEqual(payload["start"], {"date": "2026-03-05"})
        self.assertEqual(payload["end"], {"date": "2026-03-06"})

    # -------------------------
    # FUNCTION: test_export_ics_creates_file
    # Purpose: Validate the export ics creates file scenario.
    # -------------------------
    def test_export_ics_creates_file(self):
        ev = self._sample_event()
        output_path, count = self.svc.export_ics([ev], self.tmp.name)
        self.assertEqual(count, 1)
        self.assertTrue(os.path.exists(output_path))

    # -------------------------
    # FUNCTION: test_parse_google_dt
    # Purpose: Validate the parse google dt scenario.
    # -------------------------
    def test_parse_google_dt(self):
        dt = self.svc._parse_google_dt({"dateTime": "2026-03-05T19:00:00+05:00"}, "Asia/Karachi")
        self.assertIsNotNone(dt)

        all_day = self.svc._parse_google_dt({"date": "2026-03-05"}, "UTC")
        self.assertIsNotNone(all_day)

        none_case = self.svc._parse_google_dt({}, "UTC")
        self.assertIsNone(none_case)

    # -------------------------
    # FUNCTION: test_find_conflicts_detects_overlap
    # Purpose: Validate the find conflicts detects overlap scenario.
    # -------------------------
    def test_find_conflicts_detects_overlap(self):
        ev = self._sample_event(
            start_dt=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 3, 5, 11, 0, tzinfo=timezone.utc),
            timezone="UTC",
        )
        self.svc.is_connected = True
        self.svc.service = _FakeService(
            [
                {
                    "id": "1",
                    "summary": "Busy slot",
                    "status": "confirmed",
                    "start": {"dateTime": "2026-03-05T10:30:00+00:00"},
                    "end": {"dateTime": "2026-03-05T11:30:00+00:00"},
                },
                {
                    "id": "2",
                    "summary": "Cancelled",
                    "status": "cancelled",
                    "start": {"dateTime": "2026-03-05T10:15:00+00:00"},
                    "end": {"dateTime": "2026-03-05T10:45:00+00:00"},
                },
            ]
        )

        conflicts = self.svc.find_conflicts(ev)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["summary"], "Busy slot")


if __name__ == "__main__":
    unittest.main()
