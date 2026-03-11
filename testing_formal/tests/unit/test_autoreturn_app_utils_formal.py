"""Unit tests for lightweight utility methods in AutoReturnApp."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.frontend.ui.autoreturn_app import AutoReturnApp


class TestAutoReturnAppUtilsFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.app_obj = AutoReturnApp.__new__(AutoReturnApp)
        self.app_obj.rows_per_page = 15
        self.app_obj.current_page = 1
        self.app_obj.active_filter = "all"
        self.app_obj.search_filters = {}
        self.app_obj.messages = []
        self.app_obj.current_sort_column = None


    # -------------------------
    # FUNCTION: test_message_key_uses_id_when_present
    # Purpose: Validate the message key uses id when present scenario.
    # -------------------------
    def test_message_key_uses_id_when_present(self):
        msg = {"id": "abc123", "source": "gmail"}
        key = AutoReturnApp._message_key(self.app_obj, msg)
        self.assertEqual(key, "abc123")

    # -------------------------
    # FUNCTION: test_message_key_fallback
    # Purpose: Validate the message key fallback scenario.
    # -------------------------
    def test_message_key_fallback(self):
        msg = {
            "source": "gmail",
            "timestamp": 123,
            "sender": "Alice",
            "subject": "S",
            "preview": "hello",
        }
        key = AutoReturnApp._message_key(self.app_obj, msg)
        self.assertIn("gmail", key)

    # -------------------------
    # FUNCTION: test_summary_for_table_prefers_summary
    # Purpose: Validate the summary for table prefers summary scenario.
    # -------------------------
    def test_summary_for_table_prefers_summary(self):
        msg = {"summary": "Short summary", "ai_analysis": "Summary: x\n\nTask:y"}
        out = AutoReturnApp._summary_for_table(self.app_obj, msg)
        self.assertEqual(out, "Short summary")

    # -------------------------
    # FUNCTION: test_summary_for_table_falls_back_to_ai_analysis
    # Purpose: Validate the summary for table falls back to ai analysis scenario.
    # -------------------------
    def test_summary_for_table_falls_back_to_ai_analysis(self):
        msg = {"summary": "", "ai_analysis": "Summary: Something happened\n\nTask: Auto Reply"}
        out = AutoReturnApp._summary_for_table(self.app_obj, msg)
        self.assertEqual(out, "Something happened")

    # -------------------------
    # FUNCTION: test_paginated_messages
    # Purpose: Validate the paginated messages scenario.
    # -------------------------
    def test_paginated_messages(self):
        data = [{"id": str(i)} for i in range(22)]
        page_items, total_pages = AutoReturnApp._get_paginated_messages(self.app_obj, data)
        self.assertEqual(len(page_items), 15)
        self.assertEqual(total_pages, 2)

    # -------------------------
    # FUNCTION: test_parse_search_query
    # Purpose: Validate the parse search query scenario.
    # -------------------------
    def test_parse_search_query(self):
        filters = AutoReturnApp._parse_search_query(self.app_obj, "last week with attachment meeting alice")
        self.assertTrue(filters["require_attachments"])
        self.assertIsNotNone(filters["date_from"])
        self.assertIn("meeting", filters["terms"])

    # -------------------------
    # FUNCTION: test_parse_time_to_minutes
    # Purpose: Validate the parse time to minutes scenario.
    # -------------------------
    def test_parse_time_to_minutes(self):
        self.assertEqual(AutoReturnApp.parse_time_to_minutes(self.app_obj, "2h ago"), 120)
        self.assertEqual(AutoReturnApp.parse_time_to_minutes(self.app_obj, "5m ago"), 5)
        self.assertEqual(AutoReturnApp.parse_time_to_minutes(self.app_obj, "bad"), 999999)

    # -------------------------
    # FUNCTION: test_filter_message_search_and_source
    # Purpose: Validate the filter message search and source scenario.
    # -------------------------
    def test_filter_message_search_and_source(self):
        now = datetime.now()
        self.app_obj.active_filter = "gmail"
        self.app_obj.search_filters = {
            "raw": "meeting",
            "terms": ["meeting"],
            "date_from": now - timedelta(days=2),
            "date_to": None,
            "require_attachments": True,
        }
        msg = {
            "source": "gmail",
            "priority": "Medium",
            "sender": "Alice",
            "email": "alice@example.com",
            "content_preview": "meeting notes",
            "preview": "meeting notes",
            "summary": "meeting scheduled",
            "full_content": "meeting tomorrow",
            "channel_name": "",
            "datetime": now,
            "has_attachments": True,
        }
        self.assertTrue(AutoReturnApp.filter_message(self.app_obj, msg))

        msg["has_attachments"] = False
        self.assertFalse(AutoReturnApp.filter_message(self.app_obj, msg))

    # -------------------------
    # FUNCTION: test_format_schedule_and_sender_stats
    # Purpose: Validate the format schedule and sender stats scenario.
    # -------------------------
    def test_format_schedule_and_sender_stats(self):
        now = datetime.now()
        self.app_obj.messages = [
            {"sender": "Alice", "email": "alice@example.com", "subject": "S1", "time": "1h ago", "timestamp": now.timestamp(), "datetime": now},
            {"sender": "Alice", "email": "alice@example.com", "subject": "S2", "time": "2d ago", "timestamp": (now - timedelta(days=2)).timestamp(), "datetime": now - timedelta(days=2)},
            {"sender": "Bob", "email": "bob@example.com", "subject": "S3", "time": "10d ago", "timestamp": (now - timedelta(days=10)).timestamp(), "datetime": now - timedelta(days=10)},
        ]

        text = AutoReturnApp._format_schedule_items(
            self.app_obj,
            [{"item_type": "event", "title": "Meeting", "start_dt": now, "end_dt": now + timedelta(hours=1), "confidence": 0.9}],
        )
        self.assertIn("Meeting", text)

        recent = AutoReturnApp._build_sender_recent_messages(self.app_obj, {"sender": "Alice", "email": "alice@example.com"})
        self.assertIn("S1", recent)

        stats = AutoReturnApp.compute_sender_stats(self.app_obj, "Alice", "alice@example.com")
        self.assertGreaterEqual(stats["last_week"], 1)

    # -------------------------
    # FUNCTION: test_sort_by_column
    # Purpose: Validate the sort by column scenario.
    # -------------------------
    def test_sort_by_column(self):
        self.app_obj.messages = [
            {"sender": "Charlie", "subject": "b", "summary": "z", "priority": "Low", "timestamp": 2},
            {"sender": "Alice", "subject": "a", "summary": "a", "priority": "High", "timestamp": 1},
        ]
        self.app_obj.sort_order = 0
        self.app_obj.populate_table = MagicMock()

        AutoReturnApp.sort_by_column(self.app_obj, 2)
        self.assertEqual(self.app_obj.messages[0]["sender"], "Alice")
        self.app_obj.populate_table.assert_called()


if __name__ == "__main__":
    unittest.main()
