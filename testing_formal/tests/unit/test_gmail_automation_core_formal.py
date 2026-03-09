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
    def __init__(self, data):
        self._data = data

    def execute(self, **_kwargs):
        return self._data


class _FakeMessages:
    def __init__(self, message_payload):
        self._message_payload = message_payload

    def list(self, **_kwargs):
        return _FakeExec({"messages": [{"id": "m1"}]})

    def get(self, **_kwargs):
        return _FakeExec(self._message_payload)

    def send(self, **_kwargs):
        return _FakeExec({"id": "sent_1"})

    def modify(self, **_kwargs):
        return _FakeExec({})

    def delete(self, **_kwargs):
        return _FakeExec({})


class _FakeDrafts:
    def create(self, **_kwargs):
        return _FakeExec({"id": "d1"})

    def list(self, **_kwargs):
        return _FakeExec({"drafts": []})

    def get(self, **_kwargs):
        return _FakeExec({"message": {"payload": {"headers": []}}})

    def send(self, **_kwargs):
        return _FakeExec({"id": "sent_d1"})


class _FakeUsers:
    def __init__(self, payload):
        self._payload = payload

    def messages(self):
        return _FakeMessages(self._payload)

    def drafts(self):
        return _FakeDrafts()


class _FakeService:
    def __init__(self, payload):
        self._payload = payload

    def users(self):
        return _FakeUsers(self._payload)


class TestGmailAutomationCoreFormal(unittest.TestCase):
    def test_message_parser_extract_header(self):
        headers = [{"name": "From", "value": "Alice <alice@example.com>"}]
        self.assertEqual(MessageParser.extract_header(headers, "from"), "Alice <alice@example.com>")

    def test_message_parser_decode_message(self):
        raw = base64.urlsafe_b64encode(b"Hello world").decode()
        payload = {"body": {"data": raw}}
        text = MessageParser.decode_message(payload)
        self.assertIn("Hello", text)

    def test_oauth_manager_non_interactive_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            oauth = OAuthManager(
                client_secret_path=os.path.join(tmp, "missing_client_secret.json"),
                token_path=os.path.join(tmp, "missing_token.json"),
            )
            self.assertFalse(oauth.load_or_generate_token(allow_flow=False))

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
