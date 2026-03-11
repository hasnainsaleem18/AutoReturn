"""Unit tests for tone recommendation and adjustment service."""

from __future__ import annotations

import unittest

from src.backend.models.tone_models import ToneType
from src.backend.services.tone_service import ToneService


class _DetectorResult:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, tone_signal="formal_leaning", confidence=0.8, detected_tone=ToneType.FORMAL, score=0.2):
        self.tone_signal = tone_signal
        self.confidence_score = confidence
        self.detected_tone = detected_tone
        self.tone_signal_score = score


class _FakeDetector:
    # -------------------------
    # FUNCTION: __init__
    # Purpose: Execute   init   logic for this module.
    # -------------------------
    def __init__(self, result):
        self._result = result

    # -------------------------
    # FUNCTION: analyze_message
    # Purpose: Execute analyze message logic for this module.
    # -------------------------
    def analyze_message(self, _text):
        return self._result


class _FakeAI:
    # -------------------------
    # FUNCTION: generate_summary_async
    # Purpose: Execute generate summary async logic for this module.
    # -------------------------
    async def generate_summary_async(self, prompt: str, sender: str = "", subject: str = ""):
        if "Recommended tone" in prompt:
            return "Recommended tone: INFORMAL\nConfidence: 0.7\nReasoning: casual"
        return "Rewritten content"


class _FailingAI:
    # -------------------------
    # FUNCTION: generate_summary_async
    # Purpose: Execute generate summary async logic for this module.
    # -------------------------
    async def generate_summary_async(self, *_args, **_kwargs):
        raise RuntimeError("llm failed")


class TestToneServiceFormal(unittest.IsolatedAsyncioTestCase):
    # -------------------------
    # FUNCTION: test_recommend_tone_no_content
    # Purpose: Validate the recommend tone no content scenario.
    # -------------------------
    async def test_recommend_tone_no_content(self):
        svc = ToneService(ai_service=_FakeAI(), tone_detector=_FakeDetector(_DetectorResult()))
        rec = await svc.recommend_tone({"full_content": ""})
        self.assertEqual(rec.recommended_tone, ToneType.FORMAL)

    # -------------------------
    # FUNCTION: test_recommend_tone_deterministic_high_confidence
    # Purpose: Validate the recommend tone deterministic high confidence scenario.
    # -------------------------
    async def test_recommend_tone_deterministic_high_confidence(self):
        svc = ToneService(ai_service=_FakeAI(), tone_detector=_FakeDetector(_DetectorResult(confidence=0.9)))
        rec = await svc.recommend_tone({"full_content": "Dear team", "source": "gmail"})
        self.assertEqual(rec.recommended_tone, ToneType.FORMAL)
        self.assertGreaterEqual(rec.confidence, 0.6)

    # -------------------------
    # FUNCTION: test_recommend_tone_llm_fallback
    # Purpose: Validate the recommend tone llm fallback scenario.
    # -------------------------
    async def test_recommend_tone_llm_fallback(self):
        svc = ToneService(ai_service=_FakeAI(), tone_detector=_FakeDetector(_DetectorResult(confidence=0.3)))
        rec = await svc.recommend_tone({"full_content": "hi bro", "source": "slack"})
        self.assertTrue(rec.fallback_used)

    # -------------------------
    # FUNCTION: test_recommend_tone_detector_exception
    # Purpose: Validate the recommend tone detector exception scenario.
    # -------------------------
    async def test_recommend_tone_detector_exception(self):
        class _BadDetector:
            # -------------------------
            # FUNCTION: analyze_message
            # Purpose: Execute analyze message logic for this module.
            # -------------------------
            def analyze_message(self, _text):
                raise RuntimeError("broken")

        svc = ToneService(ai_service=_FakeAI(), tone_detector=_BadDetector())
        rec = await svc.recommend_tone({"full_content": "hello"})
        self.assertEqual(rec.recommended_tone, ToneType.FORMAL)

    # -------------------------
    # FUNCTION: test_adjust_tone_success
    # Purpose: Validate the adjust tone success scenario.
    # -------------------------
    async def test_adjust_tone_success(self):
        svc = ToneService(ai_service=_FakeAI(), tone_detector=_FakeDetector(_DetectorResult()))
        out = await svc.adjust_tone("thanks", ToneType.FORMAL)
        self.assertTrue(out.success)
        self.assertTrue(out.adjusted_text)

    # -------------------------
    # FUNCTION: test_adjust_tone_failure
    # Purpose: Validate the adjust tone failure scenario.
    # -------------------------
    async def test_adjust_tone_failure(self):
        svc = ToneService(ai_service=_FailingAI(), tone_detector=_FakeDetector(_DetectorResult()))
        out = await svc.adjust_tone("thanks", ToneType.INFORMAL)
        self.assertFalse(out.success)
        self.assertEqual(out.adjusted_text, "thanks")


if __name__ == "__main__":
    unittest.main()
