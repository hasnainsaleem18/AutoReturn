# -------------------------
# TONE MANAGER
# -------------------------
"""
Central tone management system that integrates with existing orchestrator.
Extends functionality without modifying existing components.
"""

# -------------------------
# IMPORTS
# -------------------------
import asyncio
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime

from src.backend.models.tone_models import (
    ToneType, ToneProfile, ToneAnalysis, ToneRecommendation,
    ToneAdjustmentRequest, ToneAdjustmentResponse
)
from src.backend.services.tone_service import ToneService
from src.backend.services.ai_service import OllamaService


# -------------------------
# TONE MANAGER CLASS
# -------------------------
class ToneManager:
    """Central tone management system that works with existing architecture"""
    
    def __init__(self, ai_service: OllamaService):
        self.ai_service = ai_service
        self.tone_service = ToneService(ai_service)
        self.user_profile = self._load_user_profile()
        self.tone_cache = {}  # Cache for tone recommendations
        
        print(f"🎨 Tone Manager initialized with default tone: {self.user_profile.default_tone}")
    
    def _load_user_profile(self) -> ToneProfile:
        """Load user tone profile from configuration"""
        try:
            # Try to load from existing config
            config_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config', 'tone_profile.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                    return ToneProfile(**data)
        except Exception as e:
            print(f"Could not load tone profile: {e}")
        
        # Return default profile
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
    
    async def analyze_message_context(self, message_data: Dict[str, Any]) -> ToneAnalysis:
        """Analyze message to recommend appropriate tone"""
        
        message_id = message_data.get('id', 'unknown')
        
        # Check cache first
        if message_id in self.tone_cache:
            cached_analysis = self.tone_cache[message_id]
            # Use cached result if less than 5 minutes old
            if (datetime.now() - cached_analysis.get('timestamp', datetime.now())).seconds < 300:
                return cached_analysis['analysis']
        
        # Extract context without modifying original message
        sender = message_data.get('sender', '')
        content = message_data.get('full_content', '')
        subject = message_data.get('subject', '')
        priority = message_data.get('priority', 'normal')
        source = message_data.get('source', 'unknown')
        
        # Get AI recommendation
        recommendation = await self.tone_service.recommend_tone(
            message_data=message_data,
            user_preferences=self.user_profile
        )
        
        # Create analysis
        analysis = ToneAnalysis(
            message_id=message_id,
            sentiment_score=await self._analyze_sentiment(content),
            urgency_level=self._classify_urgency(priority, content),
            sender_type=self._classify_sender(sender, source),
            message_type=self._classify_message_type(content, subject),
            recommended_tone=recommendation
        )
        
        # Cache the result
        self.tone_cache[message_id] = {
            'analysis': analysis,
            'timestamp': datetime.now()
        }
        
        return analysis
    
    async def get_effective_tone(self, message_data: Dict[str, Any], 
                                manual_tone: Optional[ToneType] = None) -> ToneType:
        """Get the effective tone (manual override or auto-recommended)"""
        
        if manual_tone:
            # User manually selected tone - learn from this
            self._learn_from_manual_selection(manual_tone, message_data)
            return manual_tone
        
        if self.user_profile.auto_tone_enabled:
            # Use AI recommendation
            try:
                analysis = await self.analyze_message_context(message_data)
                if analysis.recommended_tone.confidence > 0.6:
                    return analysis.recommended_tone.recommended_tone
            except Exception as e:
                print(f"Error in tone recommendation: {e}")
        
        # Use user's default tone
        return self.user_profile.default_tone
    
    async def adjust_message_tone(self, original_text: str, target_tone: ToneType,
                                message_context: Dict[str, Any] = None) -> ToneAdjustmentResponse:
        """Adjust message tone using AI service"""
        
        return await self.tone_service.adjust_tone(
            original_text=original_text,
            target_tone=target_tone,
            message_context=message_context or {}
        )
    
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
    
    async def _analyze_sentiment(self, content: str) -> float:
        """Simple sentiment analysis (can be enhanced with AI)"""
        if not content:
            return 0.0
        
        # Positive words
        positive_words = ['good', 'great', 'excellent', 'thanks', 'appreciate', 'wonderful', 'fantastic', 'love', 'happy']
        # Negative words
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'angry', 'frustrated', 'disappointed', 'problem', 'issue']
        
        content_lower = content.lower()
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count == 0 and negative_count == 0:
            return 0.0
        
        # Simple sentiment calculation
        total_words = len(content.split())
        if total_words == 0:
            return 0.0
        
        sentiment = (positive_count - negative_count) / total_words
        return max(-1.0, min(1.0, sentiment))
    
    def _classify_urgency(self, priority: str, content: str) -> str:
        """Classify message urgency"""
        content_lower = content.lower()
        
        # Urgent keywords
        urgent_keywords = ['urgent', 'asap', 'immediately', 'emergency', 'critical', 'deadline', 'important']
        
        if any(keyword in content_lower for keyword in urgent_keywords):
            return 'critical'
        
        # Priority-based classification
        priority_mapping = {
            'urgent': 'high',
            'high': 'high',
            'normal': 'medium',
            'low': 'low'
        }
        
        return priority_mapping.get(priority, 'medium')
    
    def _classify_sender(self, sender: str, source: str) -> str:
        """Classify sender type (internal vs external)"""
        if not sender:
            return 'unknown'
        
        # Check for internal indicators
        if source == 'slack':
            return 'internal'  # Slack is typically internal
        
        # Email domain analysis
        domain = self._extract_domain(sender)
        internal_domains = ['company.com', 'localhost', 'internal']  # Can be configured
        
        if any(internal in domain for internal in internal_domains):
            return 'internal'
        
        return 'external'
    
    def _classify_message_type(self, content: str, subject: str) -> str:
        """Classify message type"""
        text = (content + ' ' + subject).lower()
        
        # Complaint indicators
        complaint_words = ['complaint', 'issue', 'problem', 'wrong', 'error', 'broken', 'not working']
        if any(word in text for word in complaint_words):
            return 'complaint'
        
        # Request indicators
        request_words = ['request', 'please', 'need', 'want', 'could you', 'would you', 'help']
        if any(word in text for word in request_words):
            return 'request'
        
        # Question indicators
        question_words = ['?', 'how', 'what', 'when', 'where', 'why', 'which', 'who']
        if any(word in text for word in question_words):
            return 'inquiry'
        
        # Information indicators
        info_words = ['info', 'information', 'update', 'fyi', 'announcement', 'notice']
        if any(word in text for word in info_words):
            return 'information'
        
        return 'general'
    
    def _extract_domain(self, sender: str) -> str:
        """Extract domain from email address"""
        if '@' in sender:
            return sender.split('@')[-1].lower()
        return 'unknown'
    
    def _learn_from_manual_selection(self, selected_tone: ToneType, message_context: Dict[str, Any]):
        """Learn from user's manual tone selections"""
        # Update effectiveness scores
        current_score = self.user_profile.tone_effectiveness_scores.get(selected_tone, 0.5)
        self.user_profile.tone_effectiveness_scores[selected_tone] = min(1.0, current_score + 0.1)
    
    def _get_most_used_tones(self) -> Dict[str, int]:
        """Get most used tones from history"""
        tone_counts = {}
        for override in self.user_profile.manual_override_history:
            tone = override.get('selected_tone', 'unknown')
            tone_counts[tone] = tone_counts.get(tone, 0) + 1
        
        # Return top 5 most used tones
        sorted_tones = sorted(tone_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_tones[:5])
