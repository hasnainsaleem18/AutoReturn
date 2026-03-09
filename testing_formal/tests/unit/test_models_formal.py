"""Unit tests for model definitions and small helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent
from src.backend.models.automation_models import AutomationAction, AutomationSettings, PolicyDecision
from src.backend.models.event_models import CalendarItemType, EventCandidate
from src.backend.models.tone_models import ToneType, get_tone_description, get_tone_display_name


class TestModelsFormal(unittest.TestCase):
    def test_automation_settings_defaults(self):
        settings = AutomationSettings()
        self.assertFalse(settings.dnd_enabled)
        self.assertEqual(settings.max_auto_attachments, 3)
        self.assertTrue(settings.require_user_confirm_plain_reply)

    def test_automation_settings_bounds(self):
        with self.assertRaises(ValidationError):
            AutomationSettings(max_auto_attachments=99)

    def test_policy_decision_model(self):
        decision = PolicyDecision(
            action=AutomationAction.AUTO_REPLY,
            reason="allowlisted",
            sender_identity="x@example.com",
            sender_allowed=True,
        )
        self.assertEqual(decision.action, AutomationAction.AUTO_REPLY)
        self.assertTrue(decision.sender_allowed)

    def test_event_candidate_ensure_end_timed(self):
        start = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        event = EventCandidate(
            item_type=CalendarItemType.EVENT,
            title="Meeting",
            start_dt=start,
            timezone="UTC",
            source="gmail",
            source_id="m1",
            confidence=0.9,
        )
        event.ensure_end()
        self.assertEqual((event.end_dt - event.start_dt).seconds, 3600)

    def test_event_candidate_ensure_end_all_day(self):
        start = datetime(2026, 5, 10, 0, 0, tzinfo=timezone.utc)
        event = EventCandidate(
            item_type=CalendarItemType.EVENT,
            title="Birthday",
            start_dt=start,
            all_day=True,
            timezone="UTC",
            source="gmail",
            source_id="m2",
            confidence=0.8,
        )
        event.ensure_end()
        self.assertEqual((event.end_dt - event.start_dt).days, 1)

    def test_tone_display_helpers(self):
        self.assertEqual(get_tone_display_name(ToneType.FORMAL), "Formal")
        self.assertIn("Formal", get_tone_description(ToneType.FORMAL))

    def test_agent_models(self):
        req = AgentRequest(intent=Intent.FETCH_MESSAGES, parameters={"x": 1})
        resp = AgentResponse(success=True, data={"ok": True}, agent_name="agent")
        self.assertEqual(req.intent, Intent.FETCH_MESSAGES)
        self.assertTrue(resp.success)


if __name__ == "__main__":
    unittest.main()
