"""Unit tests for lightweight utility methods in AutoReturnApp."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.backend.models.agent_models import AgentResponse, Intent
from src.frontend.ui.autoreturn_app import AutoReturnApp
from src.backend.models.automation_models import VoiceSettings
from src.backend.services.voice_service import VoiceCommand
from src.backend.services.voice_intent_service import VoiceIntent


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
        self.app_obj._current_page_messages = []
        self.app_obj.active_workers = []
        self.app_obj.AUTO_SYNC_GMAIL_FETCH_LIMIT = 10
        self.app_obj.STARTUP_SLACK_INITIAL_FETCH_LIMIT = 200


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

    # -------------------------
    # FUNCTION: test_execute_ui_voice_action_search_updates_field
    # Purpose: Validate the voice search action scenario.
    # -------------------------
    def test_execute_ui_voice_action_search_updates_field(self):
        self.app_obj.search_field = MagicMock()
        cmd = VoiceCommand(
            action_type="ui_action",
            action="search",
            parameters={"query": "invoice"},
            raw_text="search for invoice",
        )

        AutoReturnApp._execute_ui_voice_action(self.app_obj, cmd)
        self.app_obj.search_field.setText.assert_called_once_with("invoice")

    # -------------------------
    # FUNCTION: test_execute_ui_voice_action_reply_uses_first_visible_sender_match
    # Purpose: Validate sender-matched voice reply scenario.
    # -------------------------
    def test_execute_ui_voice_action_reply_uses_first_visible_sender_match(self):
        self.app_obj._current_page_messages = [
            {"sender": "John Doe", "email": "john@example.com"},
            {"sender": "Jane Doe", "email": "jane@example.com"},
        ]
        self.app_obj.show_send_message_dialog = MagicMock()
        self.app_obj.show_status_message = MagicMock()

        cmd = VoiceCommand(
            action_type="ui_action",
            action="reply_to_sender",
            parameters={"sender_name": "John"},
            raw_text="reply to John",
        )

        AutoReturnApp._execute_ui_voice_action(self.app_obj, cmd)
        self.app_obj.show_send_message_dialog.assert_called_once_with(self.app_obj._current_page_messages[0])

    # -------------------------
    # FUNCTION: test_execute_ui_voice_action_invalid_index_shows_status
    # Purpose: Validate invalid message index voice scenario.
    # -------------------------
    def test_execute_ui_voice_action_invalid_index_shows_status(self):
        self.app_obj._current_page_messages = [{"sender": "John Doe", "email": "john@example.com"}]
        self.app_obj.show_full_message_dialog = MagicMock()
        self.app_obj.show_status_message = MagicMock()

        cmd = VoiceCommand(
            action_type="ui_action",
            action="open_message_by_index",
            parameters={"index": 3},
            raw_text="open message 4",
        )

        AutoReturnApp._execute_ui_voice_action(self.app_obj, cmd)
        self.app_obj.show_full_message_dialog.assert_not_called()
        self.app_obj.show_status_message.assert_called_once()

    # -------------------------
    # FUNCTION: test_voice_direct_send_allows_explicit_text
    # Purpose: Validate direct voice sending only needs setting, action, and text.
    # -------------------------
    def test_voice_direct_send_allows_explicit_text(self):
        self.app_obj.voice_settings = VoiceSettings(send_without_review=True)
        intent = VoiceIntent(
            action="reply_to_sender",
            message="here is update",
        )

        result = AutoReturnApp._can_send_voice_without_review(self.app_obj, intent, "here is update")

        self.assertTrue(result)

    # -------------------------
    # FUNCTION: test_voice_direct_send_blocks_empty_text
    # Purpose: Validate direct voice sending does not send empty replies.
    # -------------------------
    def test_voice_direct_send_blocks_empty_text(self):
        self.app_obj.voice_settings = VoiceSettings(send_without_review=True)
        intent = VoiceIntent(
            action="reply_to_sender",
            message="",
        )

        result = AutoReturnApp._can_send_voice_without_review(self.app_obj, intent, "")

        self.assertFalse(result)

    # -------------------------
    # FUNCTION: test_gmail_voice_contact_lookup_from_loaded_messages
    # Purpose: Validate Gmail contact lookup can resolve loaded sender contacts.
    # -------------------------
    def test_gmail_voice_contact_lookup_from_loaded_messages(self):
        self.app_obj.messages = [
            {"source": "gmail", "sender": "Hasnain Saleem", "email": "hasnain@example.com", "subject": "Update"},
            {"source": "slack", "sender": "Hasnain", "email": "@hasnain"},
        ]

        contact = AutoReturnApp._find_gmail_contact_for_voice_recipient(self.app_obj, "hasnain")

        self.assertEqual(contact["email"], "hasnain@example.com")

    # -------------------------
    # FUNCTION: test_gmail_voice_contact_lookup_accepts_email_address
    # Purpose: Validate direct email addresses work without loaded contacts.
    # -------------------------
    def test_gmail_voice_contact_lookup_accepts_email_address(self):
        self.app_obj.messages = []

        contact = AutoReturnApp._find_gmail_contact_for_voice_recipient(self.app_obj, "person@example.com")

        self.assertEqual(contact["email"], "person@example.com")

    # -------------------------
    # FUNCTION: test_voice_button_click_starts_button_capture
    # Purpose: Validate Mic button activation path.
    # -------------------------
    def test_voice_button_click_starts_button_capture(self):
        self.app_obj.voice_settings = VoiceSettings()
        self.app_obj.voice_service = MagicMock()
        self.app_obj.voice_service.is_available.return_value = True
        self.app_obj.voice_service.is_recording.return_value = False
        self.app_obj.voice_service.start_button_capture.return_value = True
        self.app_obj.show_status_message = MagicMock()

        AutoReturnApp._on_voice_button_clicked(self.app_obj)
        self.app_obj.voice_service.start_button_capture.assert_called_once()

    # -------------------------
    # FUNCTION: test_auto_sync_gmail_uses_lightweight_limit
    # Purpose: Validate faster periodic Gmail sync parameters.
    # -------------------------
    def test_auto_sync_gmail_uses_lightweight_limit(self):
        self.app_obj.gmail_service = MagicMock()
        self.app_obj.gmail_service.is_connected = True
        self.app_obj.handle_gmail_sync = MagicMock()

        AutoReturnApp.auto_sync_gmail(self.app_obj)
        self.app_obj.handle_gmail_sync.assert_called_once_with(
            quiet=True,
            max_results=self.app_obj.AUTO_SYNC_GMAIL_FETCH_LIMIT,
            add_ai_analysis=True,
        )

    # -------------------------
    # FUNCTION: test_handle_gmail_sync_passes_requested_fetch_limit
    # Purpose: Validate Gmail sync request construction.
    # -------------------------
    def test_handle_gmail_sync_passes_requested_fetch_limit(self):
        self.app_obj.gmail_service = MagicMock()
        self.app_obj.gmail_service.is_connected = True
        self.app_obj._is_syncing_gmail = False
        self.app_obj.messages = [
            {
                "id": "g1",
                "source": "gmail",
                "priority": "Low",
                "ai_priority_score": "Low",
                "ai_tasks": ["Informational"],
                "ai_events": [],
                "ai_events_count": 0,
            }
        ]
        self.app_obj.orchestrator = MagicMock()
        self.app_obj.orchestrator.route_request.return_value = object()
        self.app_obj.active_workers = []
        self.app_obj.show_status_message = MagicMock()
        self.app_obj._cleanup_worker = MagicMock()

        created_requests = []

        class _FakeWorker:
            def __init__(self, coro):
                self.coro = coro
                self.result_ready = MagicMock()
                self.error_occurred = MagicMock()
                self.finished = MagicMock()

            def start(self):
                return None

        def _fake_request(intent, parameters):
            created_requests.append((intent, parameters))
            return MagicMock(intent=intent, parameters=parameters)

        import src.frontend.ui.autoreturn_app as app_module

        original_request = app_module.AgentRequest
        original_worker = app_module.AgentWorker
        try:
            app_module.AgentRequest = _fake_request
            app_module.AgentWorker = _FakeWorker
            AutoReturnApp.handle_gmail_sync(self.app_obj, quiet=True, max_results=7, add_ai_analysis=False)
        finally:
            app_module.AgentRequest = original_request
            app_module.AgentWorker = original_worker

        self.assertEqual(created_requests[0][0], Intent.FETCH_MESSAGES)
        self.assertEqual(created_requests[0][1]["max_results"], 7)
        self.assertFalse(created_requests[0][1]["add_ai_analysis"])
        self.assertIn("g1", created_requests[0][1]["analysis_cache"])

    # -------------------------
    # FUNCTION: test_show_settings_routes_logout_signal_to_main_window
    # Purpose: Validate Settings logout requests are wired back to the app.
    # -------------------------
    def test_show_settings_routes_logout_signal_to_main_window(self):
        class _Signal:
            def __init__(self):
                self.callback = None

            def connect(self, callback):
                self.callback = callback

            def emit(self):
                if self.callback:
                    self.callback()

        class _FakeSettingsDialog:
            def __init__(self, *_args, **_kwargs):
                self.connect_slack_callback = None
                self.upload_gmail_json_callback = None
                self.connect_gmail_callback = None
                self.sync_gmail_callback = None
                self.get_gmail_status_callback = None
                self.profile_updated = _Signal()
                self.logout_requested = _Signal()
                self.automation_settings_updated = _Signal()

            def refresh_gmail_status(self):
                return None

            def exec(self):
                self.logout_requested.emit()
                return 1

        self.app_obj.user_data = {"email": "user@example.com"}
        self.app_obj.gmail_service = MagicMock()
        self.app_obj.gmail_service.get_status_snapshot.return_value = {}
        self.app_obj.orchestrator = MagicMock()
        self.app_obj.connect_slack = MagicMock()
        self.app_obj.upload_gmail_credentials = MagicMock()
        self.app_obj.authorize_gmail = MagicMock()
        self.app_obj.handle_gmail_sync = MagicMock()
        self.app_obj.on_profile_updated = MagicMock()
        self.app_obj.on_automation_settings_updated = MagicMock()
        self.app_obj.handle_logout_requested = MagicMock()
        self.app_obj.update_status_bar = MagicMock()

        with patch("src.frontend.ui.autoreturn_app.SettingsDialog", _FakeSettingsDialog), \
                patch(
                    "src.frontend.ui.autoreturn_app.QTimer.singleShot",
                    side_effect=lambda _ms, callback: callback(),
                ):
            AutoReturnApp.show_settings(self.app_obj)

        self.app_obj.handle_logout_requested.assert_called_once()

    # -------------------------
    # FUNCTION: test_initial_slack_sync_complete_forwards_messages
    # Purpose: Validate background Slack startup sync completion path.
    # -------------------------
    def test_initial_slack_sync_complete_forwards_messages(self):
        self.app_obj.on_slack_new_messages = MagicMock()
        self.app_obj.on_agent_error = MagicMock()
        response = AgentResponse(success=True, data={"messages": [{"id": "1", "source": "slack"}]}, agent_name="slack")

        AutoReturnApp._on_initial_slack_sync_complete(self.app_obj, response)
        self.app_obj.on_slack_new_messages.assert_called_once_with([{"id": "1", "source": "slack"}])

    # -------------------------
    # FUNCTION: test_slack_duplicate_does_not_recalculate_priority
    # Purpose: Validate duplicate Slack messages reuse existing analysis.
    # -------------------------
    def test_slack_duplicate_does_not_recalculate_priority(self):
        self.app_obj.messages = [
            {
                "id": "s1",
                "source": "slack",
                "priority": "Low",
                "ai_priority_score": "Low",
                "ai_tasks": ["Informational"],
                "ai_events": [],
                "ai_events_count": 0,
            }
        ]
        self.app_obj.notifications = []
        self.app_obj._schedule_table_refresh = MagicMock()

        slack_agent = MagicMock()
        slack_agent.priority_engine.calculate_priority = MagicMock(return_value="High")
        self.app_obj.orchestrator = MagicMock()
        self.app_obj.orchestrator.agents = {"slack": slack_agent}

        AutoReturnApp.on_slack_new_messages(
            self.app_obj,
            [{"id": "s1", "source": "slack", "priority": "normal", "full_content": "urgent"}],
        )

        slack_agent.priority_engine.calculate_priority.assert_not_called()
        self.assertEqual(len(self.app_obj.messages), 1)


if __name__ == "__main__":
    unittest.main()
