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

    # -------------------------
    # FUNCTION: fetch_messages
    # Purpose: Execute fetch messages logic for this module.
    # -------------------------
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
    # -------------------------
    # FUNCTION: sync_all_messages
    # Purpose: Execute sync all messages logic for this module.
    # -------------------------
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
    # -------------------------
    # FUNCTION: extract_from_message
    # Purpose: Execute extract from message logic for this module.
    # -------------------------
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
    # -------------------------
    # FUNCTION: test_gmail_agent_handle_fetch_with_ai
    # Purpose: Validate the gmail agent handle fetch with ai scenario.
    # -------------------------
    async def test_gmail_agent_handle_fetch_with_ai(self):
        agent = GmailAgent.__new__(GmailAgent)
        agent.name = "gmail_agent"
        agent.backend = _FakeGmailBackend()
        agent.event_extractor = _FakeEventExtractor()

        # -------------------------
        # FUNCTION: _priority
        # Purpose: Execute  priority logic for this module.
        # -------------------------
        async def _priority(_msg):
            return "Medium"

        # -------------------------
        # FUNCTION: _tasks
        # Purpose: Execute  tasks logic for this module.
        # -------------------------
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

    # -------------------------
    # FUNCTION: test_gmail_agent_reuses_cached_analysis
    # Purpose: Validate repeat Gmail syncs do not recompute existing analysis.
    # -------------------------
    async def test_gmail_agent_reuses_cached_analysis(self):
        agent = GmailAgent.__new__(GmailAgent)
        agent.name = "gmail_agent"
        agent.backend = _FakeGmailBackend()

        calls = {"priority": 0, "tasks": 0, "events": 0}

        async def _priority(_msg):
            calls["priority"] += 1
            return "Medium"

        async def _tasks(_msg):
            calls["tasks"] += 1
            return ["Simple Reply Required"]

        class _CountingEventExtractor:
            async def extract_from_message(self, _msg):
                calls["events"] += 1
                return []

        agent.event_extractor = _CountingEventExtractor()
        agent._analyze_priority = types.MethodType(lambda self, msg: _priority(msg), agent)
        agent._extract_tasks = types.MethodType(lambda self, msg: _tasks(msg), agent)

        req = AgentRequest(
            intent=Intent.FETCH_MESSAGES,
            parameters={
                "add_ai_analysis": True,
                "analysis_cache": {
                    "g1": {
                        "priority": "High",
                        "ai_priority_score": "High",
                        "ai_tasks": ["Informational"],
                        "ai_events": [],
                        "ai_events_count": 0,
                    }
                },
            },
        )
        out = await GmailAgent._handle_fetch(agent, req)

        self.assertTrue(out.success)
        self.assertEqual(calls, {"priority": 0, "tasks": 0, "events": 0})
        msg = out.data["messages"][0]
        self.assertEqual(msg["priority"], "High")
        self.assertEqual(msg["ai_tasks"], ["Informational"])
        self.assertEqual(msg["ai_events"], [])

    # -------------------------
    # FUNCTION: test_slack_agent_handle_fetch_with_ai
    # Purpose: Validate the slack agent handle fetch with ai scenario.
    # -------------------------
    async def test_slack_agent_handle_fetch_with_ai(self):
        agent = SlackAgent.__new__(SlackAgent)
        agent.name = "slack_agent"
        agent.backend = _FakeSlackBackend()
        agent.event_extractor = _FakeEventExtractor()

        # -------------------------
        # FUNCTION: _priority
        # Purpose: Execute  priority logic for this module.
        # -------------------------
        async def _priority(_msg):
            return "Low"

        # -------------------------
        # FUNCTION: _tone
        # Purpose: Execute  tone logic for this module.
        # -------------------------
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

    # -------------------------
    # FUNCTION: test_slack_agent_reuses_cached_analysis
    # Purpose: Validate repeat Slack syncs do not recompute existing analysis.
    # -------------------------
    async def test_slack_agent_reuses_cached_analysis(self):
        agent = SlackAgent.__new__(SlackAgent)
        agent.name = "slack_agent"
        agent.backend = _FakeSlackBackend()

        calls = {"priority": 0, "tone": 0, "tasks": 0, "events": 0}

        async def _priority(_msg):
            calls["priority"] += 1
            return "Low"

        async def _tone(_msg):
            calls["tone"] += 1
            return "neutral"

        def _tasks(_msg):
            calls["tasks"] += 1
            return ["Informational"]

        class _CountingEventExtractor:
            async def extract_from_message(self, _msg):
                calls["events"] += 1
                return []

        agent.event_extractor = _CountingEventExtractor()
        agent._analyze_priority = types.MethodType(lambda self, msg: _priority(msg), agent)
        agent._analyze_tone = types.MethodType(lambda self, msg: _tone(msg), agent)
        agent._classify_task = types.MethodType(lambda self, msg: _tasks(msg), agent)

        req = AgentRequest(
            intent=Intent.FETCH_MESSAGES,
            parameters={
                "add_ai_analysis": True,
                "analysis_cache": {
                    "s1": {
                        "priority": "Medium",
                        "ai_priority_score": "Medium",
                        "ai_tone_signal": "formal_leaning",
                        "ai_tasks": ["Simple Reply Required"],
                        "ai_events": [],
                        "ai_events_count": 0,
                    }
                },
            },
        )
        out = await SlackAgent._handle_fetch(agent, req)

        self.assertTrue(out.success)
        self.assertEqual(calls, {"priority": 0, "tone": 0, "tasks": 0, "events": 0})
        msg = out.data["messages"][0]
        self.assertEqual(msg["priority"], "Medium")
        self.assertEqual(msg["ai_tone_signal"], "formal_leaning")
        self.assertEqual(msg["ai_tasks"], ["Simple Reply Required"])
        self.assertEqual(msg["ai_events"], [])


if __name__ == "__main__":
    unittest.main()
