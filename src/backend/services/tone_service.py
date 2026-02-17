# -------------------------
# TONE SERVICE
# -------------------------
"""
AI-powered tone adjustment and recommendation service.
Works alongside existing AI service without conflicts.
"""

# -------------------------
# IMPORTS
# -------------------------
import asyncio
import time
from typing import Dict, Any, Optional, List
from src.backend.models.tone_models import (
    ToneType, ToneRecommendation, ToneAdjustmentRequest, 
    ToneAdjustmentResponse, ToneProfile, ToneAnalysis
)
from src.backend.services.ai_service import OllamaService


# -------------------------
# TONE SERVICE CLASS
# -------------------------
class ToneService:
    """AI service for tone adjustment and recommendations"""
    
    def __init__(self, ai_service: OllamaService):
        self.ai_service = ai_service
        self.tone_instructions = self._initialize_tone_instructions()
    
    def _initialize_tone_instructions(self) -> Dict[ToneType, str]:
        """Initialize tone-specific instructions"""
        return {
            ToneType.FORMAL: "Make this message formal, professional, and respectful. Use proper grammar, avoid slang, and maintain a business-appropriate tone.",
            ToneType.PROFESSIONAL: "Make this message professional and business-oriented. Use clear, concise language appropriate for workplace communication.",
            ToneType.CASUAL: "Make this message casual and friendly. Use conversational language, appropriate for informal communication.",
            ToneType.FRIENDLY: "Make this message warm and approachable. Use positive language and a friendly, welcoming tone.",
            ToneType.ASSERTIVE: "Make this message confident and direct. State clearly what you want or need, be decisive but not aggressive.",
            ToneType.PERSUASIVE: "Make this message convincing and compelling. Use persuasive language to encourage agreement or action.",
            ToneType.APOLOGETIC: "Make this message sincerely apologetic and empathetic. Acknowledge issues, take responsibility, and offer solutions.",
            ToneType.EMPATHETIC: "Make this message understanding and caring. Show emotional intelligence and acknowledge feelings.",
            ToneType.DIPLOMATIC: "Make this message diplomatic and tactful. Handle sensitive topics carefully, find common ground.",
            ToneType.CONCISE: "Make this message brief and to the point. Remove unnecessary words, focus on essential information.",
            ToneType.HUMOROUS: "Add appropriate humor to this message. Use wit and light-hearted comments where suitable.",
            ToneType.APPRECIATIVE: "Make this message grateful and appreciative. Express thanks and recognition sincerely.",
            ToneType.URGENT: "Make this message convey urgency and importance. Use strong action words and clear deadlines."
        }
    
    async def recommend_tone(self, message_data: Dict[str, Any], 
                           user_preferences: Optional[ToneProfile] = None) -> ToneRecommendation:
        """AI-powered tone recommendation based on message context"""
        
        # Extract context information
        sender = message_data.get('sender', '')
        subject = message_data.get('subject', '')
        content = message_data.get('full_content', '')[:1000]  # Limit for processing
        priority = message_data.get('priority', 'normal')
        source = message_data.get('source', 'unknown')
        
        # Build AI prompt for tone recommendation
        prompt = f"""
        Analyze this message and recommend the most appropriate tone for a reply:

        MESSAGE DETAILS:
        Sender: {sender}
        Subject: {subject}
        Content: {content}
        Priority: {priority}
        Source: {source}

        USER PREFERENCES:
        Default Tone: {user_preferences.default_tone if user_preferences else 'professional'}
        Auto-Tone Enabled: {user_preferences.auto_tone_enabled if user_preferences else True}

        ANALYSIS CRITERIA:
        1. Sender relationship (internal colleague vs external client)
        2. Message sentiment and emotional content
        3. Priority and urgency level
        4. Professional context and domain
        5. Communication best practices

        AVAILABLE TONES:
        - formal: Professional, respectful, business-appropriate
        - professional: Clear, workplace-oriented, standard business
        - casual: Informal, friendly, conversational
        - friendly: Warm, approachable, positive
        - assertive: Confident, direct, decisive
        - persuasive: Convincing, compelling, action-oriented
        - apologetic: Sincere, empathetic, solution-focused
        - empathetic: Understanding, caring, emotionally aware
        - diplomatic: Tactful, sensitive, conflict-resolution
        - concise: Brief, to-the-point, efficient
        - humorous: Light-hearted, witty, appropriate humor
        - appreciative: Grateful, thankful, recognizing
        - urgent: Time-sensitive, action-oriented, important

        RESPONSE FORMAT:
        Recommended Tone: [tone_name]
        Confidence: [0.0-1.0]
        Reasoning: [brief explanation]
        Context Factors: [key factors considered]

        Choose the single best tone for this situation.
        """
        
        try:
            start_time = time.time()
            response = await self.ai_service.generate_summary_async(prompt)
            processing_time = int((time.time() - start_time) * 1000)
            
            # Parse AI response
            recommended_tone = self._parse_tone_from_response(response)
            confidence = self._parse_confidence_from_response(response)
            reasoning = self._parse_reasoning_from_response(response)
            
            return ToneRecommendation(
                recommended_tone=recommended_tone,
                confidence=confidence,
                reasoning=reasoning,
                context_factors={
                    'sender': sender,
                    'priority': priority,
                    'source': source,
                    'processing_time_ms': processing_time
                }
            )
            
        except Exception as e:
            print(f"Error in tone recommendation: {e}")
            # Fallback to professional tone
            return ToneRecommendation(
                recommended_tone=ToneType.PROFESSIONAL,
                confidence=0.5,
                reasoning="Fallback due to processing error",
                context_factors={'error': str(e)}
            )
    
    async def adjust_tone(self, original_text: str, target_tone: ToneType,
                        message_context: Dict[str, Any] = None) -> ToneAdjustmentResponse:
        """Adjust text to match target tone while preserving intent"""
        
        start_time = time.time()
        
        # Get tone-specific instruction
        instruction = self.tone_instructions.get(target_tone, self.tone_instructions[ToneType.PROFESSIONAL])
        
        # Build AI prompt for tone adjustment
        context_info = ""
        if message_context:
            sender = message_context.get('sender', 'Unknown')
            subject = message_context.get('subject', 'No subject')
            context_info = f"\nContext: Replying to {sender} about '{subject}'"
        
        prompt = f"""
        ORIGINAL MESSAGE:
        {original_text}

        TARGET TONE: {target_tone.value.upper()}
        INSTRUCTION: {instruction}{context_info}

        REQUIREMENTS:
        1. Preserve the original meaning and intent completely
        2. Adjust only the tone, style, and emotional expression
        3. Keep the message clear, concise, and appropriate
        4. Ensure the tone is consistent throughout
        5. Maintain all key information and action items

        Adjust the message to match the {target_tone.value} tone exactly.
        Provide only the adjusted message, no explanations.
        """
        
        try:
            adjusted_text = await self.ai_service.generate_summary_async(prompt)
            processing_time = int((time.time() - start_time) * 1000)
            
            # Analyze changes made
            changes = self._analyze_changes(original_text, adjusted_text, target_tone)
            
            return ToneAdjustmentResponse(
                adjusted_text=adjusted_text or original_text,  # Fallback to original
                original_tone=self._detect_original_tone(original_text),
                applied_tone=target_tone,
                confidence=0.8 if adjusted_text else 0.2,
                changes_made=changes,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            print(f"Error in tone adjustment: {e}")
            return ToneAdjustmentResponse(
                adjusted_text=original_text,  # Fallback to original
                original_tone=self._detect_original_tone(original_text),
                applied_tone=target_tone,
                confidence=0.1,
                changes_made=[f"Error: {str(e)}"],
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
    
    def _parse_tone_from_response(self, response: str) -> ToneType:
        """Parse tone from AI response"""
        response_lower = response.lower()
        
        for tone in ToneType:
            if tone.value in response_lower:
                return tone
        
        # Fallback parsing
        if "professional" in response_lower:
            return ToneType.PROFESSIONAL
        elif "formal" in response_lower:
            return ToneType.FORMAL
        elif "casual" in response_lower:
            return ToneType.CASUAL
        
        return ToneType.PROFESSIONAL  # Default fallback
    
    def _parse_confidence_from_response(self, response: str) -> float:
        """Parse confidence score from AI response"""
        import re
        
        # Look for confidence patterns
        confidence_patterns = [
            r'confidence[:\s]*([0-9.]+)',
            r'confidence[:\s]*([0-9.]+)',
            r'([0-9.]+)%',
        ]
        
        for pattern in confidence_patterns:
            match = re.search(pattern, response.lower())
            if match:
                try:
                    value = float(match.group(1))
                    return min(value, 1.0) if value <= 1.0 else value / 100.0
                except:
                    continue
        
        return 0.7  # Default confidence
    
    def _parse_reasoning_from_response(self, response: str) -> str:
        """Parse reasoning from AI response"""
        lines = response.split('\n')
        for line in lines:
            if 'reasoning' in line.lower() or 'because' in line.lower():
                return line.split(':', 1)[-1].strip()
        
        return "AI-based context analysis"
    
    def _detect_original_tone(self, text: str) -> ToneType:
        """Simple heuristic tone detection"""
        text_lower = text.lower()
        
        # Check for formal indicators
        formal_words = ['dear', 'sincerely', 'regards', 'respectfully', 'cordially']
        if any(word in text_lower for word in formal_words):
            return ToneType.FORMAL
        
        # Check for casual indicators
        casual_words = ['hey', 'hi', 'thanks', 'cool', 'awesome', 'lol']
        if any(word in text_lower for word in casual_words):
            return ToneType.CASUAL
        
        # Check for urgent indicators
        urgent_words = ['urgent', 'asap', 'immediately', 'emergency', 'critical']
        if any(word in text_lower for word in urgent_words):
            return ToneType.URGENT
        
        return ToneType.PROFESSIONAL  # Default assumption
    
    def _analyze_changes(self, original: str, adjusted: str, target_tone: ToneType) -> List[str]:
        """Analyze what changes were made during tone adjustment"""
        changes = []
        
        if len(adjusted) != len(original):
            changes.append(f"Length changed from {len(original)} to {len(adjusted)} characters")
        
        # Check for specific tone indicators
        original_lower = original.lower()
        adjusted_lower = adjusted.lower()
        
        if target_tone == ToneType.FORMAL:
            if 'dear' in adjusted_lower and 'dear' not in original_lower:
                changes.append("Added formal greeting")
            if 'sincerely' in adjusted_lower and 'sincerely' not in original_lower:
                changes.append("Added formal closing")
        
        elif target_tone == ToneType.CASUAL:
            if any(word in adjusted_lower for word in ['hey', 'hi']) and not any(word in original_lower for word in ['hey', 'hi']):
                changes.append("Changed to casual greeting")
        
        if not changes:
            changes.append("Tone and style adjusted")
        
        return changes
