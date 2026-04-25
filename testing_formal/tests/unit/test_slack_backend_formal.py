"""Unit tests for Slack backend utilities and message mapping."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from src.backend.services.slack_backend import (
    SlackMessage,
    SlackService,
    format_message_time,
    validate_user_token,
)


class TestSlackBackendFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_validate_user_token
    # Purpose: Validate the validate user token scenario.
    # -------------------------
    def test_validate_user_token(self):
        self.assertEqual(validate_user_token(""), (False, "Token is required"))
        self.assertFalse(validate_user_token("xoxb-abc")[0])
        self.assertTrue(validate_user_token("xoxp-1-2-3")[0])

    # -------------------------
    # FUNCTION: test_format_message_time
    # Purpose: Validate the format message time scenario.
    # -------------------------
    def test_format_message_time(self):
        now = datetime.now()
        self.assertIn("ago", format_message_time(now - timedelta(minutes=3)))
        self.assertEqual(format_message_time("bad"), "Unknown")

    # -------------------------
    # FUNCTION: test_slack_message_to_dict
    # Purpose: Validate the slack message to dict scenario.
    # -------------------------
    def test_slack_message_to_dict(self):
        message_data = {
            "user": "U1",
            "text": "Urgent: please check this now",
            "ts": str(datetime.now().timestamp()),
        }
        channel_info = {"id": "C1", "is_im": False, "is_channel": True, "name": "general"}
        user_cache = {"U1": {"name": "alice", "real_name": "Alice A", "email": "alice@example.com"}}

        msg = SlackMessage(message_data, channel_info, user_cache)
        payload = msg.to_dict()

        self.assertEqual(payload["source"], "slack")
        self.assertEqual(payload["sender"], "Alice A")
        self.assertEqual(payload["priority"], "urgent")
        self.assertTrue(payload["subject"].startswith("#"))

    # -------------------------
    # FUNCTION: test_service_disconnect_resets_state
    # Purpose: Validate the service disconnect resets state scenario.
    # -------------------------
    def test_service_disconnect_resets_state(self):
        svc = SlackService()
        svc.is_connected = True
        svc.client = object()
        svc.users_cache["x"] = {"id": "x"}
        svc.processed_messages.add("1")

        svc.disconnect()

        self.assertFalse(svc.is_connected)
        self.assertIsNone(svc.client)
        self.assertEqual(svc.users_cache, {})
        self.assertEqual(svc.processed_messages, set())

    # -------------------------
    # FUNCTION: test_sync_all_messages_not_connected
    # Purpose: Validate the sync all messages not connected scenario.
    # -------------------------
    def test_sync_all_messages_not_connected(self):
        svc = SlackService()
        self.assertEqual(svc.sync_all_messages(limit=10), [])


if __name__ == "__main__":
    unittest.main()
