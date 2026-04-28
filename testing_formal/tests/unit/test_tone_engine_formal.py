"""Unit tests for ToneEngine orchestration without loading heavyweight spaCy models."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.backend.models.tone_models import ToneType


class _FakeAIService:
    # -------------------------
    # FUNCTION: generate_text_async
    # Purpose: Execute generate text async logic for this module.
    # -------------------------
    async def generate_text_async(self, prompt: str, temperature: float = 0.55, max_tokens: int = 280):
        return "AI generated draft"

    # -------------------------
    # FUNCTION: generate_summary_async
    # Purpose: Execute generate summary async logic for this module.
    # -------------------------
    async def generate_summary_async(self, prompt: str, sender: str = "", subject: str = ""):
        return "Rewritten reply"


class _FakeDetector:
    # -------------------------
    # FUNCTION: analyze_message
    # Purpose: Execute analyze message logic for this module.
    # -------------------------
    def analyze_message(self, text: str):
        from src.backend.core.tone_engine import ToneDetectionResult

        signal = "informal_leaning" if "hey" in text.lower() else "formal_leaning"
        tone = ToneType.INFORMAL if signal == "informal_leaning" else ToneType.FORMAL
        return ToneDetectionResult(
            detected_tone=tone,
            tone_signal=signal,
            confidence_score=0.82,
            tone_signal_score=0.45,
            tone_scores={ToneType.FORMAL: 0.4, ToneType.INFORMAL: 0.7},
        )


class _LowConfidenceDetector:
    # -------------------------
    # FUNCTION: analyze_message
    # Purpose: Execute analyze message logic for this module.
    # -------------------------
    def analyze_message(self, _text: str):
        from src.backend.core.tone_engine import ToneDetectionResult

        return ToneDetectionResult(
            detected_tone=ToneType.FORMAL,
            tone_signal="neutral",
            confidence_score=0.2,
            tone_signal_score=0.0,
            tone_scores={ToneType.FORMAL: 0.1, ToneType.INFORMAL: 0.1},
        )


class TestToneEngineFormal(unittest.IsolatedAsyncioTestCase):
    @patch("src.backend.core.tone_engine.ToneDetector", return_value=_FakeDetector())
    # -------------------------
    # FUNCTION: test_analyze_and_recommend_flow
    # Purpose: Validate the analyze and recommend flow scenario.
    # -------------------------
    async def test_analyze_and_recommend_flow(self, _mock_detector):
        from src.backend.core.tone_engine import ToneEngine

        engine = ToneEngine(ai_service=_FakeAIService())

        incoming = engine.analyze_incoming_tone("Dear team, please review")
        self.assertEqual(incoming["detected_tone"], ToneType.FORMAL.value)

        rec = await engine.analyze_message_context({"id": "m1", "full_content": "Dear team", "source": "gmail"})
        self.assertIsNotNone(rec)
        self.assertEqual(rec.recommended_tone, ToneType.FORMAL)

        # cache hit path
        rec2 = await engine.analyze_message_context({"id": "m1", "full_content": "Dear team", "source": "gmail"})
        self.assertEqual(rec2.recommended_tone, ToneType.FORMAL)

    @patch("src.backend.core.tone_engine.ToneDetector", return_value=_LowConfidenceDetector())
    # -------------------------
    # FUNCTION: test_effective_tone_manual_and_default_paths
    # Purpose: Validate the effective tone manual and default paths scenario.
    # -------------------------
    async def test_effective_tone_manual_and_default_paths(self, _mock_detector):
        from src.backend.core.tone_engine import ToneEngine

        engine = ToneEngine(ai_service=_FakeAIService())
        with patch.object(engine, "_save_user_profile", return_value=None):
            tone = await engine.get_effective_tone({"full_content": "hello", "source": "slack"}, manual_tone=ToneType.INFORMAL)
            self.assertEqual(tone, ToneType.INFORMAL)

            engine.set_default_tone(ToneType.FORMAL)
            self.assertEqual(engine.user_profile.default_tone, ToneType.FORMAL)

            stats = engine.get_tone_statistics()
            self.assertIn("default_tone", stats)

    @patch("src.backend.core.tone_engine.ToneDetector", return_value=_FakeDetector())
    # -------------------------
    # FUNCTION: test_process_outgoing_and_fallback_draft
    # Purpose: Validate the process outgoing and fallback draft scenario.
    # -------------------------
    async def test_process_outgoing_and_fallback_draft(self, _mock_detector):
        from src.backend.core.tone_engine import ToneEngine

        engine = ToneEngine(ai_service=_FakeAIService())

        out = await engine.process_outgoing_message(
            original_message={"full_content": "meeting update", "source": "gmail", "sender": "A", "subject": "S"},
            draft_text="",
            manual_tone=ToneType.FORMAL,
        )
        self.assertIn("adjusted_draft", out)
        self.assertEqual(out["final_tone"], ToneType.FORMAL)

        fb = engine._build_specific_fallback_draft("Alice", "Schedule", "please attach file", ToneType.INFORMAL)
        self.assertIn("Alice", fb)
        self.assertIn("Thanks", fb)

    @patch("src.backend.core.tone_engine.ToneDetector", return_value=_FakeDetector())
    # -------------------------
    # FUNCTION: test_update_user_preferences
    # Purpose: Validate the update user preferences scenario.
    # -------------------------
    async def test_update_user_preferences(self, _mock_detector):
        from src.backend.core.tone_engine import ToneEngine

        engine = ToneEngine(ai_service=_FakeAIService())
        with patch.object(engine, "_save_user_profile", return_value=None):
            engine.update_user_preferences(
                ToneType.FORMAL,
                {
                    "sender": "boss@example.com",
                    "subject": "Update",
                    "priority": "high",
                    "source": "gmail",
                },
            )
        self.assertIn("boss@example.com", engine.user_profile.sender_preferences)


if __name__ == "__main__":
    unittest.main()
