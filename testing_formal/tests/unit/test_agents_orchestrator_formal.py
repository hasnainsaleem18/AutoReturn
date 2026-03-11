"""Unit tests for agent helpers and orchestrator routing logic."""

from __future__ import annotations

import unittest

from src.backend.agents.base_agent import BaseAgent
from src.backend.agents.gmail_agent import GmailAgent
from src.backend.agents.slack_agent import SlackAgent
from src.backend.core.orchestrator import IntentClassification, Orchestrator
from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent


class _DummyAgent(BaseAgent):
    # -------------------------
    # FUNCTION: process_request
    # Purpose: Execute process request logic for this module.
    # -------------------------
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        return self.success_response(data={"intent": request.intent.value})


class TestBaseAgentFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_success_and_error_responses
    # Purpose: Validate the success and error responses scenario.
    # -------------------------
    def test_success_and_error_responses(self):
        agent = _DummyAgent("dummy")
        ok = agent.success_response({"x": 1})
        err = agent.error_response("boom")
        self.assertTrue(ok.success)
        self.assertEqual(ok.agent_name, "dummy")
        self.assertFalse(err.success)


class TestSlackAgentHelpersFormal(unittest.IsolatedAsyncioTestCase):
    # -------------------------
    # FUNCTION: test_classify_task_variants
    # Purpose: Validate the classify task variants scenario.
    # -------------------------
    async def test_classify_task_variants(self):
        agent = SlackAgent.__new__(SlackAgent)

        self.assertEqual(
            agent._classify_task({"full_content": "Please send the report pdf"}),
            ["File Attachment Required"],
        )
        self.assertEqual(
            agent._classify_task({"full_content": "Can you please confirm by today?"}),
            ["Simple Reply Required"],
        )

    # -------------------------
    # FUNCTION: test_analyze_tone_with_tone_engine
    # Purpose: Validate the analyze tone with tone engine scenario.
    # -------------------------
    async def test_analyze_tone_with_tone_engine(self):
        agent = SlackAgent.__new__(SlackAgent)

        class _Tone:
            # -------------------------
            # FUNCTION: analyze_incoming_tone
            # Purpose: Execute analyze incoming tone logic for this module.
            # -------------------------
            def analyze_incoming_tone(self, _text):
                return {"tone_signal": "formal_leaning"}

        agent.tone_engine = _Tone()
        tone = await agent._analyze_tone({"full_content": "Dear team"})
        self.assertEqual(tone, "formal_leaning")


class TestGmailAgentHelpersFormal(unittest.IsolatedAsyncioTestCase):
    # -------------------------
    # FUNCTION: test_extract_tasks_variants
    # Purpose: Validate the extract tasks variants scenario.
    # -------------------------
    async def test_extract_tasks_variants(self):
        agent = GmailAgent.__new__(GmailAgent)

        file_task = await agent._extract_tasks({"full_content": "Please send me your resume pdf"})
        draft_task = await agent._extract_tasks({"full_content": "Please provide a detailed response"})
        auto_task = await agent._extract_tasks({"full_content": "This is to confirm your request has been received"})

        self.assertEqual(file_task, ["File Attachment Required"])
        self.assertEqual(draft_task, ["Draft Generation"])
        self.assertEqual(auto_task, ["Auto Reply"])


class TestOrchestratorRoutingFormal(unittest.IsolatedAsyncioTestCase):
    # -------------------------
    # FUNCTION: test_classify_intent_heuristics
    # Purpose: Validate the classify intent heuristics scenario.
    # -------------------------
    async def test_classify_intent_heuristics(self):
        orch = Orchestrator.__new__(Orchestrator)

        result = await orch._classify_intent("sync gmail messages", {})
        self.assertEqual(result.target_agent, "gmail")
        self.assertEqual(result.action, "fetch")

        result2 = await orch._classify_intent("summarize all", {})
        self.assertEqual(result2.target_agent, "both")
        self.assertEqual(result2.action, "summarize")

    # -------------------------
    # FUNCTION: test_process_user_command_combines_both
    # Purpose: Validate the process user command combines both scenario.
    # -------------------------
    async def test_process_user_command_combines_both(self):
        orch = Orchestrator.__new__(Orchestrator)

        # -------------------------
        # FUNCTION: _classify
        # Purpose: Execute  classify logic for this module.
        # -------------------------
        async def _classify(_command, _context):
            return IntentClassification(target_agent="both", action="fetch", confidence=0.9, parameters={})

        # -------------------------
        # FUNCTION: _execute
        # Purpose: Execute  execute logic for this module.
        # -------------------------
        async def _execute(agent_name, _intent):
            return AgentResponse(success=True, data={"messages": [{"id": agent_name}]}, agent_name=agent_name)

        orch._classify_intent = _classify
        orch._execute_on_agent = _execute

        out = await orch.process_user_command("get all")
        self.assertTrue(out.success)
        self.assertEqual(out.data["count"], 2)


if __name__ == "__main__":
    unittest.main()
