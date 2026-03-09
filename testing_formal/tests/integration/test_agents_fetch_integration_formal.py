"""Integration-style tests for GmailAgent/SlackAgent fetch flows with mocked backends."""

from __future__ import annotations

import types
import unittest
from datetime import datetime

from src.backend.agents.gmail_agent import GmailAgent
from src.backend.agents.slack_agent import SlackAgent
from src.backend.models.agent_models import AgentRequest, Intent
from src.backend.models.event_models import CalendarItemType, EventCandidate


class _FakeGmailBackend:
    is_connected = True

    def fetch_messages(self, max_results=25, query="in:inbox"):
        return [
            {
                "id": "g1",
                "source": "gmail",
                "subject": "Meeting tomorrow",
                "full_content": "Meeting tomorrow at 7pm",
                "sender": "Alice",
            }
        ]


class _FakeSlackBackend:
    def sync_all_messages(self, limit=200):
        return [
            {
                "id": "s1",
                "source": "slack",
                "subject": "Reminder",
                "full_content": "Please send report",
                "content_preview": "Please send report",
            }
        ]


class _FakeEventExtractor:
    async def extract_from_message(self, _msg):
        return [
            EventCandidate(
                item_type=CalendarItemType.EVENT,
                title="Meeting",
                start_dt=datetime(2026, 3, 5, 19, 0),
                end_dt=datetime(2026, 3, 5, 20, 0),
                all_day=False,
                timezone="UTC",
                source="gmail",
                source_id="x",
                confidence=0.9,
            )
        ]


class TestAgentsFetchIntegrationFormal(unittest.IsolatedAsyncioTestCase):
    async def test_gmail_agent_handle_fetch_with_ai(self):
        agent = GmailAgent.__new__(GmailAgent)
        agent.name = "gmail_agent"
        agent.backend = _FakeGmailBackend()
        agent.event_extractor = _FakeEventExtractor()

        async def _priority(_msg):
            return "Medium"

        async def _tasks(_msg):
            return ["Simple Reply Required"]

        agent._analyze_priority = types.MethodType(lambda self, msg: _priority(msg), agent)
        agent._extract_tasks = types.MethodType(lambda self, msg: _tasks(msg), agent)

        req = AgentRequest(intent=Intent.FETCH_MESSAGES, parameters={"add_ai_analysis": True})
        out = await GmailAgent._handle_fetch(agent, req)

        self.assertTrue(out.success)
        self.assertEqual(out.data["count"], 1)
        msg = out.data["messages"][0]
        self.assertEqual(msg["priority"], "Medium")
        self.assertEqual(msg["ai_events_count"], 1)

    async def test_slack_agent_handle_fetch_with_ai(self):
        agent = SlackAgent.__new__(SlackAgent)
        agent.name = "slack_agent"
        agent.backend = _FakeSlackBackend()
        agent.event_extractor = _FakeEventExtractor()

        async def _priority(_msg):
            return "Low"

        async def _tone(_msg):
            return "neutral"

        agent._analyze_priority = types.MethodType(lambda self, msg: _priority(msg), agent)
        agent._analyze_tone = types.MethodType(lambda self, msg: _tone(msg), agent)
        agent._classify_task = types.MethodType(lambda self, msg: ["Informational"], agent)

        req = AgentRequest(intent=Intent.FETCH_MESSAGES, parameters={"add_ai_analysis": True})
        out = await SlackAgent._handle_fetch(agent, req)

        self.assertTrue(out.success)
        self.assertEqual(out.data["count"], 1)
        msg = out.data["messages"][0]
        self.assertEqual(msg["priority"], "Low")
        self.assertEqual(msg["ai_events_count"], 1)


if __name__ == "__main__":
    unittest.main()
