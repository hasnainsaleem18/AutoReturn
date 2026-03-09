"""Unit tests for DraftManager generation and fallback behaviors."""

from __future__ import annotations

import unittest

from src.backend.core.draft_manager import DraftManager
from src.backend.models.tone_models import ToneType


class _FakeAIService:
    async def generate_text_async(self, prompt: str, temperature: float = 0.55, max_tokens: int = 260):
        return "Generated draft body"


class _FailingAIService:
    async def generate_text_async(self, *_args, **_kwargs):
        raise RuntimeError("llm failed")


class _FakeToneEngine:
    async def process_outgoing_message(self, original_message, draft_text, manual_tone=None):
        return {
            "adjusted_draft": "Tone-adjusted draft",
            "final_tone": manual_tone or ToneType.FORMAL,
            "recommended_tone": ToneType.FORMAL,
            "confidence": 0.8,
            "reasoning": "ok",
            "tone_detection": {"confidence": 0.7},
        }


class _FailingToneEngine:
    async def process_outgoing_message(self, *args, **kwargs):
        raise RuntimeError("tone error")


class TestDraftManagerFormal(unittest.IsolatedAsyncioTestCase):
    async def test_generate_basic_draft(self):
        mgr = DraftManager(ai_service=_FakeAIService())
        draft = await mgr.generate_draft("Please respond")
        self.assertIn("Generated", draft)

    async def test_generate_tone_aware_draft(self):
        mgr = DraftManager(ai_service=_FakeAIService(), tone_engine=_FakeToneEngine())
        draft = await mgr.generate_draft("Please respond", tone=ToneType.FORMAL)
        self.assertEqual(draft, "Tone-adjusted draft")

    async def test_tone_aware_fallback_to_basic(self):
        mgr = DraftManager(ai_service=_FakeAIService(), tone_engine=_FailingToneEngine())
        draft = await mgr.generate_draft("Please respond", tone=ToneType.INFORMAL)
        self.assertEqual(draft, "Generated draft body")

    async def test_generate_conflict_reply_fallback(self):
        mgr = DraftManager(ai_service=_FailingAIService())
        reply = await mgr.generate_conflict_reply(
            message_data={"sender": "Alice"},
            conflicting_event_title="Existing meeting",
            conflicting_start="2026-03-10 10:00",
            conflicting_end="2026-03-10 11:00",
        )
        self.assertIn("alternative time", reply.lower())

    async def test_process_reply_draft_without_tone_engine(self):
        mgr = DraftManager(ai_service=_FakeAIService())
        result = await mgr.process_reply_draft(original_message={"x": 1}, user_draft="")
        self.assertIn("draft", result)
        self.assertEqual(result["tone"], ToneType.FORMAL)

    async def test_process_reply_draft_with_tone_engine(self):
        mgr = DraftManager(ai_service=_FakeAIService(), tone_engine=_FakeToneEngine())
        result = await mgr.process_reply_draft(
            original_message={"x": 1},
            user_draft="Hi",
            manual_tone=ToneType.INFORMAL,
        )
        self.assertEqual(result["draft"], "Tone-adjusted draft")
        self.assertEqual(result["tone"], ToneType.INFORMAL)


if __name__ == "__main__":
    unittest.main()
