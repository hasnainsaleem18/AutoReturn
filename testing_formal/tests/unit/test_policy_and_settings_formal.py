"""Unit tests for policy evaluation and settings persistence."""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from src.backend.core.automation_coordinator import AutomationCoordinator
from src.backend.core.reply_policy_engine import ReplyPolicyEngine
from src.backend.models.automation_models import AutomationAction, AutomationSettings
from src.backend.services.automation_settings_service import AutomationSettingsService


class TestReplyPolicyEngineFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: setUp
    # Purpose: Execute setUp logic for this module.
    # -------------------------
    def setUp(self):
        self.engine = ReplyPolicyEngine()

    # -------------------------
    # FUNCTION: test_dnd_auto_reply_allowlisted
    # Purpose: Validate the dnd auto reply allowlisted scenario.
    # -------------------------
    def test_dnd_auto_reply_allowlisted(self):
        settings = AutomationSettings(
            dnd_enabled=True,
            auto_reply_enabled=True,
            auto_reply_allowlist=["boss@example.com"],
        )
        msg = {"source": "gmail", "email": "boss@example.com"}
        decision = self.engine.evaluate(msg, settings)
        self.assertEqual(decision.action, AutomationAction.AUTO_REPLY)
        self.assertTrue(decision.sender_allowed)

    # -------------------------
    # FUNCTION: test_dnd_draft_only_when_not_allowlisted
    # Purpose: Validate the dnd draft only when not allowlisted scenario.
    # -------------------------
    def test_dnd_draft_only_when_not_allowlisted(self):
        settings = AutomationSettings(dnd_enabled=True, auto_reply_enabled=True, auto_reply_allowlist=[])
        msg = {"source": "gmail", "email": "other@example.com"}
        decision = self.engine.evaluate(msg, settings)
        self.assertEqual(decision.action, AutomationAction.DRAFT_ONLY)

    # -------------------------
    # FUNCTION: test_plain_reply_when_dnd_off
    # Purpose: Validate the plain reply when dnd off scenario.
    # -------------------------
    def test_plain_reply_when_dnd_off(self):
        settings = AutomationSettings(dnd_enabled=False)
        msg = {"source": "slack", "user_id": "U123"}
        decision = self.engine.evaluate(msg, settings)
        self.assertEqual(decision.action, AutomationAction.PLAIN_REPLY)

    # -------------------------
    # FUNCTION: test_sender_identity_fallbacks
    # Purpose: Validate the sender identity fallbacks scenario.
    # -------------------------
    def test_sender_identity_fallbacks(self):
        self.assertEqual(
            self.engine._extract_sender_identity({"source": "slack", "user_id": "U1"}),
            "U1",
        )
        self.assertEqual(
            self.engine._extract_sender_identity({"source": "slack", "email": "a@b.com"}),
            "a@b.com",
        )
        self.assertEqual(
            self.engine._extract_sender_identity({"sender": "Alice"}),
            "alice",
        )


class TestAutomationSettingsServiceFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_save_and_load_settings
    # Purpose: Validate the save and load settings scenario.
    # -------------------------
    def test_save_and_load_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            svc = AutomationSettingsService(settings_path=path)

            settings = AutomationSettings(dnd_enabled=True, auto_reply_allowlist=["boss@example.com"])
            ok = svc.save_settings(settings)
            self.assertTrue(ok)

            loaded = svc.load_settings()
            self.assertTrue(loaded.dnd_enabled)
            self.assertEqual(loaded.auto_reply_allowlist, ["boss@example.com"])

    # -------------------------
    # FUNCTION: test_load_invalid_file_falls_back
    # Purpose: Validate the load invalid file falls back scenario.
    # -------------------------
    def test_load_invalid_file_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{bad-json")

            svc = AutomationSettingsService(settings_path=path)
            loaded = svc.load_settings()
            self.assertIsInstance(loaded, AutomationSettings)
            self.assertFalse(loaded.dnd_enabled)


class _InMemorySettingsService:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, settings):
        self._settings = settings
        self.saved = None

    # -------------------------
    # FUNCTION: load_settings
    # Purpose: Execute load settings logic for this module.
    # -------------------------
    def load_settings(self):
        return self._settings

    # -------------------------
    # FUNCTION: save_settings
    # Purpose: Execute save settings logic for this module.
    # -------------------------
    def save_settings(self, settings):
        self.saved = settings
        self._settings = settings
        return True


class TestAutomationCoordinatorFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_coordinator_evaluate_and_update
    # Purpose: Validate the coordinator evaluate and update scenario.
    # -------------------------
    def test_coordinator_evaluate_and_update(self):
        settings = AutomationSettings(dnd_enabled=False)
        svc = _InMemorySettingsService(settings)
        coordinator = AutomationCoordinator(settings_service=svc, policy_engine=ReplyPolicyEngine())

        decision = coordinator.evaluate_message({"source": "gmail", "email": "x@y.com"})
        self.assertEqual(decision.action, AutomationAction.PLAIN_REPLY)

        updated = AutomationSettings(dnd_enabled=True)
        self.assertTrue(coordinator.update_settings(updated))
        self.assertTrue(svc.saved.dnd_enabled)


if __name__ == "__main__":
    unittest.main()
