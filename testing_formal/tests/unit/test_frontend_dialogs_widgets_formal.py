"""Unit tests for frontend dialogs/widgets without live backend side effects."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from src.frontend.dialogs.auth_dialog import AuthDialog
from src.frontend.dialogs.event_review_dialog import EventReviewDialog
from src.frontend.dialogs.notification_dialog import NotificationDialog
from src.frontend.dialogs.plain_reply_review_dialog import PlainReplyReviewDialog
from src.frontend.dialogs.send_gmail_reply_dialog import SendGmailReplyDialog
from src.frontend.dialogs.send_slack_message_dialog import SendSlackMessageDialog
from src.frontend.ui.styles import get_stylesheet
from src.frontend.widgets.tone_detection_display import ToneDetectionDisplay
from src.frontend.widgets.tone_selector import ToneSelector

from testing_formal.tests.qt_utils import get_qapp


class _FakeOrchestrator:
    class _ToneEngine:
        # -------------------------
        # FUNCTION: analyze_incoming_tone
        # Purpose: Execute analyze incoming tone logic for this module.
        # -------------------------
        def analyze_incoming_tone(self, _text):
            return {"detected_tone": "formal", "confidence": 0.8, "tone_signal": "formal_leaning"}

        # -------------------------
        # FUNCTION: update_user_preferences
        # Purpose: Execute update user preferences logic for this module.
        # -------------------------
        def update_user_preferences(self, *_args, **_kwargs):
            return None

    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self):
        self.tone_engine = self._ToneEngine()


class _FakeCalendarService:
    # -------------------------
    # FUNCTION: connect
    # Purpose: Execute connect logic for this module.
    # -------------------------
    def connect(self, allow_flow=True):
        return True, "ok"

    # -------------------------
    # FUNCTION: find_conflicts
    # Purpose: Execute find conflicts logic for this module.
    # -------------------------
    def find_conflicts(self, ev):
        return []

    # -------------------------
    # FUNCTION: create_events
    # Purpose: Execute create events logic for this module.
    # -------------------------
    def create_events(self, events):
        return len(events), []

    # -------------------------
    # FUNCTION: export_ics
    # Purpose: Execute export ics logic for this module.
    # -------------------------
    def export_ics(self, events, output_dir):
        return os.path.join(output_dir, "dummy.ics"), len(events)


class TestFrontendDialogsWidgetsFormal(unittest.TestCase):
    @classmethod
    # -------------------------
    # FUNCTION: setUpClass
    # Purpose: Execute setUpClass logic for this module.
    # -------------------------
    def setUpClass(cls):
        cls.app = get_qapp()

    # -------------------------
    # FUNCTION: test_auth_dialog_email_validation
    # Purpose: Validate the auth dialog email validation scenario.
    # -------------------------
    def test_auth_dialog_email_validation(self):
        dialog = AuthDialog()
        self.assertTrue(dialog._is_valid_email("a@b.com"))
        self.assertFalse(dialog._is_valid_email("invalid"))

    # -------------------------
    # FUNCTION: test_auth_dialog_google_secret_validation
    # Purpose: Validate the auth dialog google secret validation scenario.
    # -------------------------
    def test_auth_dialog_google_secret_validation(self):
        dialog = AuthDialog()
        with tempfile.TemporaryDirectory() as tmp:
            valid = os.path.join(tmp, "valid.json")
            invalid = os.path.join(tmp, "invalid.json")

            with open(valid, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "installed": {
                            "client_id": "id",
                            "client_secret": "secret",
                            "redirect_uris": ["http://localhost"],
                        }
                    },
                    f,
                )
            with open(invalid, "w", encoding="utf-8") as f:
                json.dump({"foo": "bar"}, f)

            self.assertTrue(dialog._is_valid_google_client_secret(valid))
            self.assertFalse(dialog._is_valid_google_client_secret(invalid))

    # -------------------------
    # FUNCTION: test_notification_dialog_mark_read_and_clear
    # Purpose: Validate the notification dialog mark read and clear scenario.
    # -------------------------
    def test_notification_dialog_mark_read_and_clear(self):
        notifs = [{"message": "A", "time": "1", "read": False}]
        dialog = NotificationDialog(notifications=notifs)

        with patch("src.frontend.dialogs.notification_dialog.QMessageBox.information"):
            dialog.mark_all_read()
        self.assertTrue(all(n["read"] for n in notifs))

        with patch("src.frontend.dialogs.notification_dialog.QMessageBox.question", return_value=16384), \
             patch("src.frontend.dialogs.notification_dialog.QMessageBox.information"):
            dialog.clear_all()
        self.assertEqual(len(notifs), 0)

    # -------------------------
    # FUNCTION: test_send_gmail_dialog_button_state
    # Purpose: Validate the send gmail dialog button state scenario.
    # -------------------------
    def test_send_gmail_dialog_button_state(self):
        dialog = SendGmailReplyDialog("a@b.com", "Subject")
        self.assertFalse(dialog.send_btn.isEnabled())
        dialog.set_message_text("Hello")
        self.assertTrue(dialog.send_btn.isEnabled())

    # -------------------------
    # FUNCTION: test_send_slack_dialog_button_state
    # Purpose: Validate the send slack dialog button state scenario.
    # -------------------------
    def test_send_slack_dialog_button_state(self):
        users = [{"id": "U1", "name": "alice", "real_name": "Alice"}]
        dialog = SendSlackMessageDialog(users=users, orchestrator=None)
        self.assertFalse(dialog.send_btn.isEnabled())
        dialog.message_text.setPlainText("Hi")
        dialog._update_send_button_state()
        self.assertTrue(dialog.send_btn.isEnabled())

    # -------------------------
    # FUNCTION: test_plain_reply_review_dialog_decisions
    # Purpose: Validate the plain reply review dialog decisions scenario.
    # -------------------------
    def test_plain_reply_review_dialog_decisions(self):
        dialog = PlainReplyReviewDialog(
            source="gmail",
            recipient="a@b.com",
            subject="S",
            message_text="Body",
            attachments=[],
        )
        dialog._on_send()
        self.assertEqual(dialog.decision, "send")

    # -------------------------
    # FUNCTION: test_event_review_selected_events
    # Purpose: Validate the event review selected events scenario.
    # -------------------------
    def test_event_review_selected_events(self):
        events = [
            {
                "item_type": "event",
                "title": "Meeting",
                "start_dt": datetime(2026, 3, 5, 10, 0),
                "end_dt": datetime(2026, 3, 5, 11, 0),
                "all_day": False,
                "timezone": "UTC",
                "source": "gmail",
                "source_id": "m1",
                "confidence": 0.9,
            }
        ]
        dialog = EventReviewDialog(
            events=events,
            calendar_service=_FakeCalendarService(),
            auto_add_high_confidence=False,
            ics_output_dir=tempfile.gettempdir(),
        )
        selected = dialog._selected_events()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].title, "Meeting")

    # -------------------------
    # FUNCTION: test_stylesheet_contains_expected_tokens
    # Purpose: Validate the stylesheet contains expected tokens scenario.
    # -------------------------
    def test_stylesheet_contains_expected_tokens(self):
        css = get_stylesheet()
        self.assertIn("QMainWindow", css)
        self.assertIn("#messageTable", css)

    # -------------------------
    # FUNCTION: test_tone_detection_display_visibility
    # Purpose: Validate the tone detection display visibility scenario.
    # -------------------------
    def test_tone_detection_display_visibility(self):
        widget = ToneDetectionDisplay({"tone_detection": {"detected_tone": "formal", "confidence": 0.7}})
        self.assertTrue(widget.isVisible())
        widget.clear()
        self.assertFalse(widget.isVisible())

    # -------------------------
    # FUNCTION: test_tone_selector_auto_suggest
    # Purpose: Validate the tone selector auto suggest scenario.
    # -------------------------
    def test_tone_selector_auto_suggest(self):
        orchestrator = _FakeOrchestrator()
        selector = ToneSelector(orchestrator=orchestrator, message_data={"full_content": "Dear team"})
        selector.perform_auto_suggest()
        self.assertIn("Confidence", selector.confidence_label.text())


if __name__ == "__main__":
    unittest.main()
