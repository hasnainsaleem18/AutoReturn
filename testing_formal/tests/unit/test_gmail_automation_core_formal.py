"""Unit tests for AutoReturn_Gmail_Automation core utilities and wrappers."""

from __future__ import annotations

import base64
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.backend.core.AutoReturn_Gmail_Automation import (
    GmailService,
    MessageParser,
    OAuthManager,
)


class _FakeExec:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, data):
        self._data = data

    # -------------------------
    # FUNCTION: execute
    # Purpose: Execute execute logic for this module.
    # -------------------------
    def execute(self, **_kwargs):
        return self._data


class _FakeMessages:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, message_payload):
        self._message_payload = message_payload

    # -------------------------
    # FUNCTION: list
    # Purpose: Execute list logic for this module.
    # -------------------------
    def list(self, **_kwargs):
        return _FakeExec({"messages": [{"id": "m1"}]})

    # -------------------------
    # FUNCTION: get
    # Purpose: Execute get logic for this module.
    # -------------------------
    def get(self, **_kwargs):
        return _FakeExec(self._message_payload)

    # -------------------------
    # FUNCTION: send
    # Purpose: Execute send logic for this module.
    # -------------------------
    def send(self, **_kwargs):
        return _FakeExec({"id": "sent_1"})

    # -------------------------
    # FUNCTION: modify
    # Purpose: Execute modify logic for this module.
    # -------------------------
    def modify(self, **_kwargs):
        return _FakeExec({})

    # -------------------------
    # FUNCTION: delete
    # Purpose: Execute delete logic for this module.
    # -------------------------
    def delete(self, **_kwargs):
        return _FakeExec({})


class _FakeDrafts:
    # -------------------------
    # FUNCTION: create
    # Purpose: Execute create logic for this module.
    # -------------------------
    def create(self, **_kwargs):
        return _FakeExec({"id": "d1"})

    # -------------------------
    # FUNCTION: list
    # Purpose: Execute list logic for this module.
    # -------------------------
    def list(self, **_kwargs):
        return _FakeExec({"drafts": []})

    # -------------------------
    # FUNCTION: get
    # Purpose: Execute get logic for this module.
    # -------------------------
    def get(self, **_kwargs):
        return _FakeExec({"message": {"payload": {"headers": []}}})

    # -------------------------
    # FUNCTION: send
    # Purpose: Execute send logic for this module.
    # -------------------------
    def send(self, **_kwargs):
        return _FakeExec({"id": "sent_d1"})


class _FakeUsers:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, payload):
        self._payload = payload

    # -------------------------
    # FUNCTION: messages
    # Purpose: Execute messages logic for this module.
    # -------------------------
    def messages(self):
        return _FakeMessages(self._payload)

    # -------------------------
    # FUNCTION: drafts
    # Purpose: Execute drafts logic for this module.
    # -------------------------
    def drafts(self):
        return _FakeDrafts()


class _FakeService:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, payload):
        self._payload = payload

    # -------------------------
    # FUNCTION: users
    # Purpose: Execute users logic for this module.
    # -------------------------
    def users(self):
        return _FakeUsers(self._payload)


class TestGmailAutomationCoreFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_message_parser_extract_header
    # Purpose: Validate the message parser extract header scenario.
    # -------------------------
    def test_message_parser_extract_header(self):
        headers = [{"name": "From", "value": "Alice <alice@example.com>"}]
        self.assertEqual(MessageParser.extract_header(headers, "from"), "Alice <alice@example.com>")

    # -------------------------
    # FUNCTION: test_message_parser_decode_message
    # Purpose: Validate the message parser decode message scenario.
    # -------------------------
    def test_message_parser_decode_message(self):
        raw = base64.urlsafe_b64encode(b"Hello world").decode()
        payload = {"body": {"data": raw}}
        text = MessageParser.decode_message(payload)
        self.assertIn("Hello", text)

    # -------------------------
    # FUNCTION: test_oauth_manager_non_interactive_failure
    # Purpose: Validate the oauth manager non interactive failure scenario.
    # -------------------------
    def test_oauth_manager_non_interactive_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            oauth = OAuthManager(
                client_secret_path=os.path.join(tmp, "missing_client_secret.json"),
                token_path=os.path.join(tmp, "missing_token.json"),
            )
            self.assertFalse(oauth.load_or_generate_token(allow_flow=False))

    # -------------------------
    # FUNCTION: test_oauth_manager_load_existing_token
    # Purpose: Validate the oauth manager load existing token scenario.
    # -------------------------
    def test_oauth_manager_load_existing_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_path = os.path.join(tmp, "token.json")
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump({"access_token": "x"}, f)

            fake_creds = MagicMock()
            fake_creds.scopes = ["https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/calendar"]

            with patch("src.backend.core.AutoReturn_Gmail_Automation.Credentials.from_authorized_user_info", return_value=fake_creds):
                oauth = OAuthManager(token_path=token_path, scopes=["https://www.googleapis.com/auth/gmail.readonly"])
                self.assertTrue(oauth.load_or_generate_token(allow_flow=False))

    # -------------------------
    # FUNCTION: test_gmail_service_read_and_list
    # Purpose: Validate the gmail service read and list scenario.
    # -------------------------
    def test_gmail_service_read_and_list(self):
        body_raw = base64.urlsafe_b64encode(b"Body text").decode()
        payload = {
            "threadId": "t1",
            "internalDate": "1760000000000",
            "labelIds": ["INBOX"],
            "historyId": "h1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Alice <alice@example.com>"},
                    {"name": "Subject", "value": "Test"},
                ],
                "body": {"data": body_raw},
            },
        }

        with patch("src.backend.core.AutoReturn_Gmail_Automation.build", return_value=_FakeService(payload)):
            svc = GmailService(creds=object())
            self.assertEqual(svc.list_messages(), [{"id": "m1"}])

            msg = svc.read_message("m1")
            self.assertEqual(msg["subject"], "Test")
            self.assertIn("Body", msg["body"])

    # -------------------------
    # FUNCTION: test_gmail_service_attachment_detection_and_mime
    # Purpose: Validate the gmail service attachment detection and mime scenario.
    # -------------------------
    def test_gmail_service_attachment_detection_and_mime(self):
        with patch("src.backend.core.AutoReturn_Gmail_Automation.build", return_value=_FakeService({"payload": {}})):
            svc = GmailService(creds=object())
            self.assertTrue(svc._has_attachments({"filename": "x.pdf"}))
            self.assertFalse(svc._has_attachments({"parts": []}))

            with tempfile.TemporaryDirectory() as tmp:
                file_path = os.path.join(tmp, "file.txt")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("abc")
                raw = svc._build_mime_message("a@b.com", "Sub", "Body", [file_path])
                self.assertIsInstance(raw, str)
                self.assertGreater(len(raw), 0)


if __name__ == "__main__":
    unittest.main()
