"""Unit tests for Orchestrator initialization with patched dependencies."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.backend.models.agent_models import AgentResponse


class _FakeAgent:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service
        self.tone_engine = None

    def set_tone_engine(self, tone_engine):
        self.tone_engine = tone_engine

    async def process_request(self, request):
        return AgentResponse(success=True, data={"messages": []}, agent_name="fake")


class _FakeDraftManager:
    def __init__(self, ai_service, tone_engine=None):
        self.ai_service = ai_service
        self.tone_engine = tone_engine


class _FakeToneEngine:
    def __init__(self, ai_service=None):
        self.ai_service = ai_service


class _FakeSettingsService:
    pass


class _FakePolicyEngine:
    pass


class _FakeCoordinator:
    def __init__(self, settings_service=None, policy_engine=None):
        self.settings_service = settings_service
        self.policy_engine = policy_engine


class TestOrchestratorInitFormal(unittest.TestCase):
    @patch("src.backend.core.orchestrator.GmailAgent", _FakeAgent)
    @patch("src.backend.core.orchestrator.SlackAgent", _FakeAgent)
    @patch("src.backend.core.orchestrator.DraftManager", _FakeDraftManager)
    @patch("src.backend.core.orchestrator.ToneEngine", _FakeToneEngine)
    @patch("src.backend.core.orchestrator.AutomationSettingsService", _FakeSettingsService)
    @patch("src.backend.core.orchestrator.ReplyPolicyEngine", _FakePolicyEngine)
    @patch("src.backend.core.orchestrator.AutomationCoordinator", _FakeCoordinator)
    def test_init_and_agent_binding(self):
        from src.backend.core.orchestrator import Orchestrator

        orch = Orchestrator(ollama_model="unit-model")

        self.assertIn("gmail", orch.agents)
        self.assertIn("slack", orch.agents)
        self.assertIsNotNone(orch.tone_engine)
        self.assertIsNone(orch.pydantic_agent)


if __name__ == "__main__":
    unittest.main()
