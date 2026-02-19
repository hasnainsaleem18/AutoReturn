# -------------------------
# TONE SERVICE (AI INTEGRATION)
# -------------------------
"""
AI service for tone adjustment and recommendation.

Implements hybrid approach combining deterministic sentiment analysis
with LLM fallback for optimal performance and reliability.

Priority System:
1. Deterministic Analysis: Feature-engineered sentiment analyzer runs first
2. Confidence Threshold: LLM fallback only when confidence < 0.6
3. Context Awareness: Different tone mappings for Gmail vs Slack
4. Graceful Fallback: LLM used only when deterministic analysis is uncertain
"""

# -------------------------
# IMPORTS
# -------------------------
import asyncio
from typing import Dict, Any, Optional

from src.backend.models.tone_models import (
    ToneType, ToneRecommendation, ToneProfile,
    ToneAdjustmentRequest, ToneAdjustmentResponse
)
from src.backend.services.ai_service import OllamaService
from src.backend.core.sentiment_analyzer import SentimentAnalyzer, SentimentAnalysisResult


# -------------------------
# TONE SERVICE CLASS
# -------------------------
class ToneService:
    """
    AI service for tone-related operations with hybrid deterministic/LLM approach.
    
    Provides intelligent tone recommendations by combining:
    - Deterministic sentiment analysis for primary processing
    - LLM fallback for cases with low confidence
    - Context-aware tone mapping for different communication platforms
    - Robust error handling and graceful degradation
    """
    
    def __init__(self, ai_service: OllamaService):
        self.ai_service = ai_service
        self.sentiment_analyzer = SentimentAnalyzer()
    
    async def recommend_tone(self, message_data: Dict[str, Any], 
                          user_preferences: Optional[ToneProfile] = None) -> ToneRecommendation:
        """
        Recommend tone using hybrid deterministic/LLM approach.
        
        Priority:
        1. Deterministic sentiment analysis (our algorithm)
        2. Fallback to LLM only when confidence is low (< 0.6)
        
        Returns:
            ToneRecommendation with confidence scoring and reasoning
        """
        
        content = message_data.get('full_content', '') or message_data.get('content', '')
        if not content:
            return ToneRecommendation(
                recommended_tone=ToneType.PROFESSIONAL,
                confidence=0.5,
                reasoning="No content available for analysis"
            )
        
        try:
            # STEP 1: Use deterministic sentiment analysis first
            sentiment_result = self.sentiment_analyzer.analyze_message(content)
            
            # Get sentiment polarity and confidence from result object
            sentiment = sentiment_result.sentiment_polarity
            confidence = sentiment_result.confidence_score
            
            # Get detected tone if available
            detected_tone = sentiment_result.detected_tone
            
            # STEP 2: Map sentiment to appropriate tone based on context
            recommended_tone = self._map_sentiment_to_tone(
                sentiment, confidence, message_data, user_preferences
            )
            
            # STEP 3: If confidence is high, use deterministic result
            if confidence >= 0.6:
                return ToneRecommendation(
                    recommended_tone=recommended_tone,
                    confidence=confidence,
                    reasoning=f"Deterministic sentiment analysis: {sentiment} (confidence: {confidence:.2f})",
                    sentiment_score=max(-1.0, min(1.0, sentiment_result.normalized_sentiment_score)),
                    urgency_level="medium",  # Could be derived from urgency_words in features
                    detected_sentiment=sentiment,
                    detected_tone=detected_tone
                )
            
            # STEP 4: Fallback to LLM only when confidence is low
            print(f"⚠️  Low confidence ({confidence:.2f}) in deterministic analysis, falling back to LLM")
            return await self._llm_fallback_tone_recommendation(
                content, sentiment_result, message_data, user_preferences
            )
            
        except Exception as e:
            print(f"Error in tone recommendation: {e}")
            return ToneRecommendation(
                recommended_tone=ToneType.PROFESSIONAL,
                confidence=0.5,
                reasoning="Error in analysis, using default",
                sentiment_score=0.0,
                urgency_level="medium",
                detected_sentiment="neutral",
                detected_tone=ToneType.PROFESSIONAL,
                fallback_used=False
            )
    
    def _map_sentiment_to_tone(self, sentiment: str, confidence: float, 
                              message_data: Dict[str, Any], 
                              user_preferences: Optional[ToneProfile] = None) -> ToneType:
        """Map sentiment analysis result to appropriate tone"""
        
        # Get message context
        sender = message_data.get('sender', '').lower()
        subject = message_data.get('subject', '').lower()
        source = message_data.get('source', '')
        content = message_data.get('content', '')
        
        # Check for urgency indicators
        urgency_keywords = ['urgent', 'asap', 'immediately', 'emergency', 'critical']
        is_urgent = any(keyword in content.lower() for keyword in urgency_keywords)
        
        # Check for formal context
        formal_indicators = ['dear', 'sincerely', 'regards', 'formal', 'official', 'business']
        is_formal = any(keyword in content.lower() for keyword in formal_indicators)
        
        # Check for casual context
        casual_indicators = ['hey', 'hi', 'thanks', 'cool', 'awesome', 'lol', 'btw']
        is_casual = any(keyword in content.lower() for keyword in casual_indicators)
        
        # Priority-based tone mapping
        if is_urgent:
            return ToneType.URGENT
        elif is_formal or source == 'gmail':
            if sentiment == 'negative':
                return ToneType.DIPLOMATIC
            elif sentiment == 'positive':
                return ToneType.PROFESSIONAL
            else:
                return ToneType.PROFESSIONAL
        elif is_casual or source == 'slack':
            if sentiment == 'negative':
                return ToneType.EMPATHETIC
            elif sentiment == 'positive':
                return ToneType.FRIENDLY
            else:
                return ToneType.CASUAL
        else:
            # Default based on sentiment
            if sentiment == 'negative':
                return ToneType.EMPATHETIC
            elif sentiment == 'positive':
                return ToneType.FRIENDLY
            else:
                return ToneType.PROFESSIONAL
    
    async def _llm_fallback_tone_recommendation(self, content: str, 
                                              sentiment_result: SentimentAnalysisResult,
                                              message_data: Dict[str, Any],
                                              user_preferences: Optional[ToneProfile] = None) -> ToneRecommendation:
        """Fallback to LLM when deterministic confidence is low"""
        
        try:
            # Include deterministic analysis as context for LLM
            sentiment = sentiment_result.sentiment_polarity
            confidence = sentiment_result.confidence_score
            
            prompt = f"""
            Analyze this message and recommend the most appropriate tone for a reply.
            
            Message: {content[:500]}...
            
            Our deterministic analysis detected:
            - Sentiment: {sentiment}
            - Confidence: {confidence:.2f} (low, hence this LLM fallback)
            
            Available tones: FORMAL, PROFESSIONAL, CASUAL, FRIENDLY, ASSERTIVE, PERSUASIVE, 
            APOLOGETIC, EMPATHETIC, DIPLOMATIC, CONCISE, HUMOROUS, APPRECIATIVE, URGENT
            
            Consider:
            - Sender relationship (formal vs casual)
            - Message content and intent
            - Urgency and importance
            - Emotional tone
            - Source: {message_data.get('source', 'unknown')}
            
            Respond with:
            Recommended tone: [TONE_NAME]
            Confidence: [0.0-1.0]
            Reasoning: [brief explanation]
            """
            
            response = await self.ai_service.generate_summary_async(prompt)
            
            # Parse response (simplified)
            recommended_tone = ToneType.PROFESSIONAL
            llm_confidence = 0.5
            reasoning = f"LLM fallback (deterministic confidence: {confidence:.2f})"
            
            # Try to extract tone from response
            response_upper = response.upper()
            for tone in ToneType:
                if tone.value in response_upper:
                    recommended_tone = tone
                    break
            
            return ToneRecommendation(
                recommended_tone=recommended_tone,
                confidence=llm_confidence,
                reasoning=reasoning,
                sentiment_score=max(-1.0, min(1.0, sentiment_result.normalized_sentiment_score)),
                urgency_level="medium",  # Could be derived from urgency_words in feature_vector
                detected_sentiment=sentiment,
                detected_tone=sentiment_result.detected_tone,
                fallback_used=True
            )
            
        except Exception as e:
            print(f"Error in LLM fallback: {e}")
            # Return deterministic result even with low confidence
            return ToneRecommendation(
                recommended_tone=ToneType.PROFESSIONAL,
                confidence=sentiment_result.confidence_score,
                reasoning="LLM fallback failed, using deterministic result",
                sentiment_score=max(-1.0, min(1.0, sentiment_result.normalized_sentiment_score)),
                urgency_level="medium",
                detected_sentiment=sentiment_result.sentiment_polarity,
                detected_tone=sentiment_result.detected_tone
            )
    
    async def adjust_tone(self, original_text: str, target_tone: ToneType,
                        message_context: Dict[str, Any] = None) -> ToneAdjustmentResponse:
        """Adjust text to match target tone using LLM"""
        
        try:
            # Create tone-specific prompt
            tone_instructions = {
                ToneType.FORMAL: "Rewrite this message in a formal, professional tone with proper titles and complete sentences.",
                ToneType.PROFESSIONAL: "Rewrite this message in a professional business tone.",
                ToneType.CASUAL: "Rewrite this message in a casual, conversational tone.",
                ToneType.FRIENDLY: "Rewrite this message in a warm, friendly tone.",
                ToneType.ASSERTIVE: "Rewrite this message in a confident, direct, assertive tone.",
                ToneType.PERSUASIVE: "Rewrite this message to be more convincing and persuasive.",
                ToneType.APOLOGETIC: "Rewrite this message in a sincere, apologetic tone.",
                ToneType.EMPATHETIC: "Rewrite this message in an understanding, empathetic tone.",
                ToneType.DIPLOMATIC: "Rewrite this message in a tactful, diplomatic tone.",
                ToneType.CONCISE: "Rewrite this message to be brief and to-the-point.",
                ToneType.HUMOROUS: "Rewrite this message in a light-hearted, humorous tone.",
                ToneType.APPRECIATIVE: "Rewrite this message in a grateful, appreciative tone.",
                ToneType.URGENT: "Rewrite this message with urgency and action-oriented language."
            }
            
            instruction = tone_instructions.get(target_tone, "Rewrite this message in a professional tone.")
            
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
            
            # Clean up response
            adjusted_text = adjusted_text.strip()
            if adjusted_text.startswith('"') and adjusted_text.endswith('"'):
                adjusted_text = adjusted_text[1:-1]
            
            return ToneAdjustmentResponse(
                original_text=original_text,
                adjusted_text=adjusted_text,
                target_tone=target_tone,
                success=True,
                confidence=0.8,
                reasoning=f"Successfully adjusted to {target_tone.value} tone"
            )
            
        except Exception as e:
            print(f"Error in tone adjustment: {e}")
            return ToneAdjustmentResponse(
                original_text=original_text,
                adjusted_text=original_text,
                target_tone=target_tone,
                success=False,
                confidence=0.0,
                reasoning=f"Error in tone adjustment: {str(e)}"
            )
    
    def analyze_sentiment_simple(self, text: str) -> Dict[str, Any]:
        """Simple sentiment analysis (fallback method)"""
        
        # Simple keyword-based sentiment analysis
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'perfect', 'love', 'thank', 'appreciate']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'angry', 'frustrated', 'disappointed', 'problem', 'issue', 'error']
        
        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        if positive_count > negative_count:
            sentiment = 'positive'
        elif negative_count > positive_count:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        return {
            'sentiment': sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'confidence': abs(positive_count - negative_count) / max(len(words), 1)
        }
