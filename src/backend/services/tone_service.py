# -------------------------
# TONE SERVICE (AI INTEGRATION)
# -------------------------
"""
AI service for tone adjustment and recommendation.

Implements hybrid approach combining deterministic tone detection
with LLM fallback for better reliability.
"""

# -------------------------
# IMPORTS
# -------------------------
import time
from typing import Dict, Any, Optional

from src.backend.models.tone_models import (
    ToneType, ToneRecommendation, ToneProfile,
    ToneAdjustmentResponse
)
from src.backend.services.ai_service import OllamaService


# -------------------------
# TONE SERVICE CLASS
# -------------------------
class ToneService:
    """AI service for tone-related operations with deterministic + LLM fallback."""

    # -------------------------
    # INIT
    # Stores AI service + optional deterministic tone detector.
    # The detector is preferred first; AI fallback is used when confidence is low.
    # -------------------------
    def __init__(self, ai_service: OllamaService, tone_detector=None):
        self.ai_service = ai_service
        self.tone_detector = tone_detector

    # -------------------------
    # RECOMMEND TONE
    # Main recommendation flow:
    # 1) Run deterministic tone detector.
    # 2) If confidence is strong, return detector-backed recommendation.
    # 3) If confidence is weak, trigger LLM fallback for final recommendation.
    # -------------------------
    async def recommend_tone(
        self,
        message_data: Dict[str, Any],
        user_preferences: Optional[ToneProfile] = None
    ) -> ToneRecommendation:
        """Recommend reply tone for an incoming message."""
        content = message_data.get('full_content', '') or message_data.get('content', '')
        if not content:
            return ToneRecommendation(
                recommended_tone=ToneType.FORMAL,
                confidence=0.5,
                reasoning="No content available for tone detection"
            )

        try:
            if not self.tone_detector:
                return ToneRecommendation(
                    recommended_tone=ToneType.FORMAL,
                    confidence=0.5,
                    reasoning="Tone detector unavailable, using formal default"
                )

            tone_result = self.tone_detector.analyze_message(content)
            tone_signal = tone_result.tone_signal
            confidence = tone_result.confidence_score
            detected_tone = tone_result.detected_tone

            recommended_tone = self._map_tone_signal_to_tone(
                tone_signal, confidence, message_data, user_preferences
            )

            if confidence >= 0.6:
                return ToneRecommendation(
                    recommended_tone=recommended_tone,
                    confidence=confidence,
                    reasoning=f"Tone detection signal: {tone_signal} (confidence: {confidence:.2f})",
                    tone_signal_score=max(-1.0, min(1.0, tone_result.tone_signal_score)),
                    urgency_level="medium",
                    detected_tone_signal=tone_signal,
                    detected_tone=detected_tone,
                )

            return await self._llm_fallback_tone_recommendation(
                content, tone_result, message_data, user_preferences
            )

        except Exception as e:
            print(f"Error in tone recommendation: {e}")
            return ToneRecommendation(
                recommended_tone=ToneType.FORMAL,
                confidence=0.5,
                reasoning="Error in tone detection, using default",
                tone_signal_score=0.0,
                urgency_level="medium",
                detected_tone_signal="neutral",
                detected_tone=ToneType.FORMAL,
                fallback_used=False,
            )

    # -------------------------
    # MAP TONE SIGNAL TO FINAL TONE
    # Applies lightweight policy rules (urgency/source/style indicators)
    # to convert detector signal into the final recommended tone.
    # -------------------------
    def _map_tone_signal_to_tone(
        self,
        tone_signal: str,
        confidence: float,
        message_data: Dict[str, Any],
        user_preferences: Optional[ToneProfile] = None
    ) -> ToneType:
        """Map detector output to final reply tone."""
        source = message_data.get('source', '')
        content = message_data.get('content', '') or message_data.get('full_content', '')

        urgency_keywords = ['urgent', 'asap', 'immediately', 'emergency', 'critical']
        is_urgent = any(keyword in content.lower() for keyword in urgency_keywords)

        formal_indicators = ['dear', 'sincerely', 'regards', 'formal', 'official', 'business']
        is_formal = any(keyword in content.lower() for keyword in formal_indicators)

        casual_indicators = ['hey', 'hi', 'thanks', 'cool', 'awesome', 'lol', 'btw']
        is_casual = any(keyword in content.lower() for keyword in casual_indicators)

        if is_urgent:
            return ToneType.FORMAL
        if is_formal or source == 'gmail':
            return ToneType.FORMAL
        if is_casual or source == 'slack':
            return ToneType.INFORMAL

        return ToneType.FORMAL if tone_signal == 'formal_leaning' else ToneType.INFORMAL

    # -------------------------
    # LLM FALLBACK RECOMMENDATION
    # Invoked only when deterministic confidence is below threshold.
    # Uses AI prompt-based reasoning, then normalizes output to ToneType.
    # -------------------------
    async def _llm_fallback_tone_recommendation(
        self,
        content: str,
        tone_result: Any,
        message_data: Dict[str, Any],
        user_preferences: Optional[ToneProfile] = None
    ) -> ToneRecommendation:
        """Fallback to LLM when deterministic confidence is low."""
        try:
            tone_signal = tone_result.tone_signal
            confidence = tone_result.confidence_score

            prompt = f"""
            Analyze this message and recommend the most appropriate tone for a reply.

            Message: {content[:500]}...

            Deterministic tone detection signal:
            - Signal: {tone_signal}
            - Confidence: {confidence:.2f} (low, so this is fallback)

            Available tones: FORMAL, INFORMAL
            Source: {message_data.get('source', 'unknown')}

            Respond with:
            Recommended tone: [TONE_NAME]
            Confidence: [0.0-1.0]
            Reasoning: [brief explanation]
            """

            response = await self.ai_service.generate_summary_async(prompt)

            recommended_tone = ToneType.FORMAL
            llm_confidence = 0.5
            reasoning = f"LLM fallback (deterministic confidence: {confidence:.2f})"

            response_upper = response.upper()
            for tone in ToneType:
                if tone.value.upper() in response_upper:
                    recommended_tone = tone
                    break

            return ToneRecommendation(
                recommended_tone=recommended_tone,
                confidence=llm_confidence,
                reasoning=reasoning,
                tone_signal_score=max(-1.0, min(1.0, tone_result.tone_signal_score)),
                urgency_level="medium",
                detected_tone_signal=tone_signal,
                detected_tone=tone_result.detected_tone,
                fallback_used=True
            )

        except Exception as e:
            print(f"Error in LLM fallback: {e}")
            return ToneRecommendation(
                recommended_tone=ToneType.FORMAL,
                confidence=tone_result.confidence_score,
                reasoning="LLM fallback failed, using deterministic result",
                tone_signal_score=max(-1.0, min(1.0, tone_result.tone_signal_score)),
                urgency_level="medium",
                detected_tone_signal=tone_result.tone_signal,
                detected_tone=tone_result.detected_tone
            )

    # -------------------------
    # ADJUST TONE
    # Rewrites outgoing text into target tone using AI while preserving intent.
    # Returns structured result with timing, success flag, and reasoning.
    # -------------------------
    async def adjust_tone(
        self,
        original_text: str,
        target_tone: ToneType,
        message_context: Dict[str, Any] = None
    ) -> ToneAdjustmentResponse:
        """Adjust text to match target tone using LLM."""
        start_time = time.time()
        try:
            tone_instructions = {
                ToneType.FORMAL: "Rewrite this message in a formal, professional tone with proper titles and complete sentences.",
                ToneType.INFORMAL: "Rewrite this message in an informal, conversational tone."
            }

            instruction = tone_instructions.get(target_tone, "Rewrite this message in a formal tone.")

            prompt = f"""
            {instruction}

            Original message: {original_text}

            Requirements:
            - Maintain the original meaning and intent
            - Use {target_tone.value} tone throughout
            - Keep it natural and appropriate
            - Don't add information that wasn't in the original

            Rewritten message:
            """

            adjusted_text = await self.ai_service.generate_summary_async(prompt)
            adjusted_text = adjusted_text.strip()
            if adjusted_text.startswith('"') and adjusted_text.endswith('"'):
                adjusted_text = adjusted_text[1:-1]

            processing_ms = int((time.time() - start_time) * 1000)
            return ToneAdjustmentResponse(
                adjusted_text=adjusted_text,
                original_tone=None,
                applied_tone=target_tone,
                confidence=0.8,
                changes_made=["tone_rewrite"],
                processing_time_ms=processing_ms,
                success=True,
                reasoning=f"Successfully adjusted to {target_tone.value} tone"
            )

        except Exception as e:
            print(f"Error in tone adjustment: {e}")
            processing_ms = int((time.time() - start_time) * 1000)
            return ToneAdjustmentResponse(
                adjusted_text=original_text,
                original_tone=None,
                applied_tone=target_tone,
                confidence=0.0,
                changes_made=[],
                processing_time_ms=processing_ms,
                success=False,
                reasoning=f"Error in tone adjustment: {str(e)}"
            )
