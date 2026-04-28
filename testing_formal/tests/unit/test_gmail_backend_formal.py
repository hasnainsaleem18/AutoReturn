"""Unit tests for Gmail backend local parsing and data mapping logic."""

from __future__ import annotations

import os
import tempfile
import unittest

from src.backend.services.gmail_backend import GmailIntegrationService


class TestGmailBackendFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.svc = GmailIntegrationService(data_dir=self.tmp.name)

    # -------------------------
    # FUNCTION: test_configure_client_secret
    # Purpose: Validate the configure client secret scenario.
    # -------------------------
    def test_configure_client_secret(self):
        source = os.path.join(self.tmp.name, "source.json")
        with open(source, "w", encoding="utf-8") as f:
            f.write("{}")

        out = self.svc.configure_client_secret(source)
        self.assertTrue(os.path.exists(out))
        self.assertTrue(self.svc.has_client_secret())

    # -------------------------
    # FUNCTION: test_get_status_snapshot
    # Purpose: Validate the get status snapshot scenario.
    # -------------------------
    def test_get_status_snapshot(self):
        status = self.svc.get_status_snapshot()
        self.assertIn("has_client_secret", status)
        self.assertIn("is_connected", status)

    # -------------------------
    # FUNCTION: test_clean_display_text
    # Purpose: Validate the clean display text scenario.
    # -------------------------
    def test_clean_display_text(self):
        text = "Hello   [image:abc]   world\n\n"
        self.assertEqual(self.svc._clean_display_text(text), "Hello world")

    # -------------------------
    # FUNCTION: test_parse_sender
    # Purpose: Validate the parse sender scenario.
    # -------------------------
    def test_parse_sender(self):
        name, email = self.svc._parse_sender("Alice <alice@example.com>")
        self.assertEqual(name, "Alice")
        self.assertEqual(email, "alice@example.com")

    # -------------------------
    # FUNCTION: test_to_inbox_message_mapping
    # Purpose: Validate the to inbox message mapping scenario.
    # -------------------------
    def test_to_inbox_message_mapping(self):
        raw = {
            "id": "m1",
            "threadId": "t1",
            "from": "Alice <alice@example.com>",
            "subject": "Important update",
            "snippet": "Please check ASAP",
            "body": "Please check ASAP",
            "internalDate": "1760000000000",
            "labelIds": ["INBOX", "UNREAD"],
        }

        msg = self.svc._to_inbox_message(raw)
        self.assertEqual(msg["source"], "gmail")
        self.assertEqual(msg["sender"], "Alice")
        self.assertEqual(msg["email"], "alice@example.com")
        self.assertEqual(msg["thread_id"], "t1")
        self.assertFalse(msg["read"])

    # -------------------------
    # FUNCTION: test_detect_priority
    # Purpose: Validate the detect priority scenario.
    # -------------------------
    def test_detect_priority(self):
        urgent = self.svc._detect_priority({"subject": "Urgent action", "snippet": "immediately"})
        high = self.svc._detect_priority({"subject": "Important notice", "snippet": "priority"})
        low = self.svc._detect_priority({"subject": "hello", "snippet": "normal"})
        self.assertEqual(urgent, "urgent")
        self.assertEqual(high, "high")
        self.assertEqual(low, "normal")


if __name__ == "__main__":
    unittest.main()
