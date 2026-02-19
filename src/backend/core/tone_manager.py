# -------------------------
# TONE MANAGER (MINIMAL ARCHITECTURE)
# -------------------------
"""
Minimal Tone Manager that integrates deterministic Sentiment Analysis 
with Tone Preference using existing orchestrator patterns.
Follows existing project architecture.
"""

# -------------------------
# IMPORTS
# -------------------------
import asyncio
import json
import os
from typing import Dict, Any, Optional
from datetime import datetime

from src.backend.models.tone_models import (
    ToneType, ToneProfile, ToneRecommendation,
    ToneAdjustmentRequest, ToneAdjustmentResponse
)
from src.backend.services.tone_service import ToneService
from src.backend.services.ai_service import OllamaService
from src.backend.core.sentiment_analyzer import SentimentAnalyzer, SentimentAnalysisResult


# -------------------------
# TONE MANAGER CLASS
# -------------------------
class ToneManager:
    """Minimal tone management following existing architecture patterns"""
    
    def __init__(self, ai_service: OllamaService):
        self.ai_service = ai_service
        self.tone_service = ToneService(ai_service)
        
        # NEW: Deterministic Sentiment Analyzer (no LLM dependency)
        self.sentiment_analyzer = SentimentAnalyzer()
        
        self.user_profile = self._load_user_profile()
        self.tone_cache = {}  # Cache for tone recommendations
        
        print(f"🎨 Tone Manager initialized with deterministic sentiment analysis")
        print(f"   Default tone: {self.user_profile.default_tone}")
    
    def _load_user_profile(self) -> ToneProfile:
        """Load user tone profile from configuration"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'tone_profile.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    return ToneProfile(**data)
        except Exception as e:
            print(f"Could not load tone profile: {e}")
        
        return ToneProfile()
    
    def _save_user_profile(self):
        """Save user tone profile to configuration"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'tone_profile.json')
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                json.dump(self.user_profile.dict(), f, indent=2, default=str)
        except Exception as e:
            print(f"Could not save tone profile: {e}")
    
    def analyze_message_sentiment(self, message_text: str) -> Dict[str, Any]:
        """
        Deterministic sentiment analysis (no LLM calls)
        Uses feature-engineered pipeline for reliable analysis.
        """
        try:
            # Use deterministic sentiment analyzer
            result = self.sentiment_analyzer.analyze_message(message_text)
            
            return {
                'sentiment': result.sentiment_polarity,
                'detected_tone': result.detected_tone.value,
                'confidence': result.confidence_score,
                'feature_vector': result.normalized_sentiment_score,
                'tone_scores': {tone.value: score for tone, score in result.tone_scores.items()}
            }
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
            return {'sentiment': 'neutral', 'detected_tone': 'professional', 'confidence': 0.5}
    
    async def analyze_message_context(self, message_data: Dict[str, Any]) -> Optional[ToneRecommendation]:
        """Analyze message to recommend appropriate tone using deterministic analysis"""
        
        message_id = message_data.get('id', 'unknown')
        
        # Check cache first
        if message_id in self.tone_cache:
            cached_analysis = self.tone_cache[message_id]
            if (datetime.now() - cached_analysis.get('timestamp', datetime.now())).seconds < 300:
                return cached_analysis['recommendation']
        
        # Use deterministic sentiment analysis (not LLM)
        content = message_data.get('full_content', '') or message_data.get('content', '')
        if not content:
            return None
        
        # Perform deterministic analysis
        analysis_result = self.sentiment_analyzer.analyze_message(content)
        
        # Create recommendation based on deterministic analysis
        recommendation = ToneRecommendation(
            recommended_tone=analysis_result.detected_tone,
            confidence=analysis_result.confidence_score,
            reasoning=f"Detected {analysis_result.sentiment_polarity} sentiment with {analysis_result.detected_tone.value} tone (confidence: {analysis_result.confidence_score:.2f})",
            sentiment_score=0.0,  # Can be calculated from feature_vector if needed
            urgency_level="medium"  # Can be enhanced later
        )
        
        # Cache the result
        self.tone_cache[message_id] = {
            'recommendation': recommendation,
            'timestamp': datetime.now()
        }
        
        return recommendation
    
    async def get_effective_tone(self, message_data: Dict[str, Any], 
                                manual_tone: Optional[ToneType] = None) -> ToneType:
        """Get effective tone using deterministic analysis and orchestration logic"""
        
        if manual_tone:
            # User manually selected tone - learn from this
            self._learn_from_manual_selection(manual_tone, message_data)
            return manual_tone
        
        if self.user_profile.auto_tone_enabled:
            try:
                # Use deterministic sentiment analysis for recommendation
                content = message_data.get('full_content', '') or message_data.get('content', '')
                if content:
                    analysis_result = self.sentiment_analyzer.analyze_message(content)
                    
                    # Apply orchestration logic based on deterministic analysis
                    suggested_tone = self._orchestrate_tone_decision(
                        analysis_result, message_data
                    )
                    
                    if analysis_result.confidence_score > 0.4:
                        return suggested_tone
                        
            except Exception as e:
                print(f"Error in deterministic tone orchestration: {e}")
        
        # Use user's default tone
        return self.user_profile.default_tone
    
    def _orchestrate_tone_decision(self, analysis_result: SentimentAnalysisResult, 
                                 message_data: Dict[str, Any]) -> ToneType:
        """
        NEW: Tone orchestration logic using deterministic analysis output
        Implements decision logic without LLM dependency for suggestions.
        """
        sentiment = analysis_result.sentiment_polarity
        detected_tone = analysis_result.detected_tone
        confidence = analysis_result.confidence_score
        
        # Priority-based override (hook for future algorithm)
        priority = message_data.get('priority', 'normal').lower()
        if priority in ['urgent', 'high']:
            return ToneType.ASSERTIVE if confidence > 0.5 else ToneType.URGENT
        
        # Sentiment-based orchestration
        if sentiment == 'negative':
            # Negative sentiment: suggest diplomatic or empathetic tones
            if detected_tone in [ToneType.FORMAL, ToneType.PROFESSIONAL]:
                return ToneType.DIPLOMATIC
            else:
                return ToneType.EMPATHETIC
        
        # Source-based adjustment
        source = message_data.get('source', '').lower()
        if source == 'slack':
            # Slack typically more casual
            if detected_tone in [ToneType.FORMAL, ToneType.PROFESSIONAL]:
                return ToneType.FRIENDLY
        elif source == 'gmail':
            # Gmail typically more formal
            if detected_tone in [ToneType.CASUAL, ToneType.FRIENDLY]:
                return ToneType.PROFESSIONAL
        
        # Return detected tone if confident enough
        if confidence > 0.6:
            return detected_tone
        
        # Default fallback
        return ToneType.PROFESSIONAL
    
    async def adjust_message_tone(self, original_text: str, target_tone: ToneType,
                                message_context: Dict[str, Any] = None) -> ToneAdjustmentResponse:
        """Adjust message tone using existing AI service (LLM only for stylistic rewriting)"""
        
        return await self.tone_service.adjust_tone(
            original_text=original_text,
            target_tone=target_tone,
            message_context=message_context or {}
        )
    
    async def process_outgoing_message(self, original_message: Dict[str, Any],
                                   draft_text: str = "",
                                   manual_tone: Optional[ToneType] = None) -> Dict[str, Any]:
        """Process outgoing message with tone adjustment using existing draft generation"""
        
        try:
            # Get effective tone using deterministic analysis
            effective_tone = await self.get_effective_tone(original_message, manual_tone)
            
            # Adjust or generate draft
            if draft_text and draft_text.strip():
                # Adjust existing draft using LLM (only for stylistic rewriting)
                response = await self.adjust_message_tone(draft_text, effective_tone, original_message)
                adjusted_draft = response.adjusted_text
            else:
                # Generate new draft using existing AI service with tone instruction
                adjusted_draft = await self._generate_draft_with_tone(original_message, effective_tone)
            
            # Get deterministic analysis for reasoning
            content = original_message.get('full_content', '') or original_message.get('content', '')
            if content:
                analysis_result = self.sentiment_analyzer.analyze_message(content)
                recommendation = ToneRecommendation(
                    recommended_tone=analysis_result.detected_tone,
                    confidence=analysis_result.confidence_score,
                    reasoning=f"Based on deterministic analysis: {analysis_result.sentiment_polarity} sentiment detected"
                )
            else:
                recommendation = None
            
            return {
                'adjusted_draft': adjusted_draft,
                'final_tone': effective_tone,
                'recommended_tone': recommendation.recommended_tone if recommendation else effective_tone,
                'confidence': recommendation.confidence if recommendation else 0.5,
                'reasoning': recommendation.reasoning if recommendation else "Using default tone",
                'sentiment_analysis': {
                    'sentiment': analysis_result.sentiment_polarity,
                    'detected_tone': analysis_result.detected_tone.value,
                    'confidence': analysis_result.confidence_score,
                    'feature_vector': analysis_result.normalized_sentiment_score
                } if content else None
            }
            
        except Exception as e:
            print(f"Error in tone processing: {e}")
            return {
                'adjusted_draft': draft_text,
                'final_tone': manual_tone or self.user_profile.default_tone,
                'recommended_tone': self.user_profile.default_tone,
                'confidence': 0.0,
                'reasoning': 'Error in tone processing',
                'sentiment_analysis': None
            }
    
    async def _generate_draft_with_tone(self, original_message: Dict[str, Any], target_tone: ToneType) -> str:
        """Generate draft with tone using existing AI service (LLM only for generation)"""
        
        try:
            # Use existing AI service with tone-specific prompt
            sender = original_message.get('sender', 'Unknown')
            subject = original_message.get('subject', 'No subject')
            content = original_message.get('full_content', '')[:300]  # Limit content
            
            tone_instructions = {
                ToneType.FORMAL: "Generate a formal response with proper titles and complete sentences.",
                ToneType.PROFESSIONAL: "Generate a professional business response.",
                ToneType.CASUAL: "Generate a casual, conversational response.",
                ToneType.FRIENDLY: "Generate a warm, friendly response.",
                ToneType.ASSERTIVE: "Generate a confident, direct response.",
                ToneType.PERSUASIVE: "Generate a convincing, persuasive response.",
                ToneType.APOLOGETIC: "Generate a sincere, apologetic response.",
                ToneType.EMPATHETIC: "Generate an understanding, empathetic response.",
                ToneType.DIPLOMATIC: "Generate a tactful, diplomatic response.",
                ToneType.CONCISE: "Generate a brief, to-the-point response.",
                ToneType.HUMOROUS: "Generate a light-hearted, humorous response.",
                ToneType.APPRECIATIVE: "Generate a grateful, appreciative response.",
                ToneType.URGENT: "Generate an urgent, action-oriented response."
            }
            
            instruction = tone_instructions.get(target_tone, "Generate a professional response.")
            
            prompt = f"""
            {instruction}
            
            Original message details:
            From: {sender}
            Subject: {subject}
            Content: {content}...
            
            Requirements:
            - Address sender appropriately
            - Respond to main points
            - Use {target_tone.value} tone throughout
            - Include appropriate greeting and closing
            
            Response:
            """
            
            draft = await self.ai_service.generate_summary_async(prompt)
            return draft.strip() if draft else "Thank you for your message."
            
        except Exception as e:
            print(f"Error in draft generation: {e}")
            return "Thank you for your message."
    
    def update_user_preferences(self, tone_selection: ToneType, 
                                message_context: Dict[str, Any]):
        """Learn from user's manual tone selections"""
        
        sender = message_context.get('sender', '')
        domain = self._extract_domain(sender)
        
        # Update sender preferences
        if sender:
            self.user_profile.sender_preferences[sender] = tone_selection
        
        # Update domain preferences
        if domain:
            self.user_profile.domain_preferences[domain] = tone_selection
        
        # Record override for learning
        self.user_profile.manual_override_history.append({
            'timestamp': datetime.now().isoformat(),
            'selected_tone': tone_selection.value,
            'message_context': {
                'sender': sender,
                'subject': message_context.get('subject', ''),
                'priority': message_context.get('priority', ''),
                'source': message_context.get('source', '')
            }
        })
        
        # Limit history size
        if len(self.user_profile.manual_override_history) > 1000:
            self.user_profile.manual_override_history = self.user_profile.manual_override_history[-500:]
        
        # Save preferences
        self._save_user_profile()
    
    def set_default_tone(self, tone: ToneType):
        """Set user's default tone"""
        self.user_profile.default_tone = tone
        self._save_user_profile()
        print(f"🎨 Default tone updated to: {tone.value}")
    
    def set_auto_tone_enabled(self, enabled: bool):
        """Enable/disable auto-tone recommendations"""
        self.user_profile.auto_tone_enabled = enabled
        self._save_user_profile()
        print(f"🎨 Auto-tone {'enabled' if enabled else 'disabled'}")
    
    def get_sender_preferences(self, sender: str) -> Optional[ToneType]:
        """Get preferred tone for a specific sender"""
        return self.user_profile.sender_preferences.get(sender)
    
    def get_tone_statistics(self) -> Dict[str, Any]:
        """Get tone usage statistics"""
        stats = {
            'default_tone': self.user_profile.default_tone.value,
            'auto_tone_enabled': self.user_profile.auto_tone_enabled,
            'total_manual_overrides': len(self.user_profile.manual_override_history),
            'sender_preferences_count': len(self.user_profile.sender_preferences),
            'domain_preferences_count': len(self.user_profile.domain_preferences),
            'most_used_tones': self._get_most_used_tones()
        }
        return stats
    
    # -------------------------
    # PRIVATE HELPER METHODS
    # -------------------------
    
    def _learn_from_manual_selection(self, selected_tone: ToneType, message_context: Dict[str, Any]):
        """Learn from user's manual tone selections"""
        # Update effectiveness scores
        current_score = self.user_profile.tone_effectiveness_scores.get(selected_tone, 0.5)
        self.user_profile.tone_effectiveness_scores[selected_tone] = min(1.0, current_score + 0.1)
    
    def _extract_domain(self, sender: str) -> str:
        """Extract domain from email address"""
        if '@' in sender:
            return sender.split('@')[1].lower()
        return 'unknown'
    
    def _get_most_used_tones(self) -> Dict[str, int]:
        """Get most used tones from history"""
        tone_counts = {}
        for override in self.user_profile.manual_override_history:
            tone = override.get('selected_tone', 'unknown')
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
        
        # Return top 5 most used tones
        sorted_tones = sorted(tone_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_tones[:5])
