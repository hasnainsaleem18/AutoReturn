# -------------------------
# TONE MODELS
# -------------------------
"""
Data models for tone adjustment and recommendation system.
Integrates with existing agent models without modification.
"""

# -------------------------
# IMPORTS
# -------------------------
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


# -------------------------
# TONE ENUMS
# -------------------------
class ToneType(str, Enum):
    """Available tone types for message adjustment"""
    FORMAL = "formal"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    FRIENDLY = "friendly"
    ASSERTIVE = "assertive"
    PERSUASIVE = "persuasive"
    APOLOGETIC = "apologetic"
    EMPATHETIC = "empathetic"
    DIPLOMATIC = "diplomatic"
    CONCISE = "concise"
    HUMOROUS = "humorous"
    APPRECIATIVE = "appreciative"
    URGENT = "urgent"


# -------------------------
# TONE RECOMMENDATION
# -------------------------
class ToneRecommendation(BaseModel):
    """AI-generated tone recommendation"""
    recommended_tone: ToneType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    reasoning: str = Field(description="Explanation for the recommendation")
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="Sentiment analysis -1.0 to 1.0")
    urgency_level: str = Field(description="Message urgency: low, medium, high, critical")
    detected_sentiment: Optional[str] = Field(description="Detected sentiment polarity")
    detected_tone: Optional[ToneType] = Field(description="Detected tone from analysis")
    fallback_used: bool = Field(default=False, description="Whether LLM fallback was used")
    context_factors: Dict[str, Any] = Field(default_factory=dict, description="Factors influencing recommendation")


# -------------------------
# TONE PROFILE
# -------------------------
class ToneProfile(BaseModel):
    """User's tone preferences and learning patterns"""
    default_tone: ToneType = ToneType.PROFESSIONAL
    sender_preferences: Dict[str, ToneType] = Field(default_factory=dict, description="Custom tones per sender")
    domain_preferences: Dict[str, ToneType] = Field(default_factory=dict, description="Custom tones per email domain")
    auto_tone_enabled: bool = True
    manual_override_history: List[Dict[str, Any]] = Field(default_factory=list, description="Learning from user choices")
    tone_effectiveness_scores: Dict[ToneType, float] = Field(default_factory=dict, description="User feedback on tone quality")


# -------------------------
# TONE ANALYSIS
# -------------------------
class ToneAnalysis(BaseModel):
    """Complete tone analysis for a message"""
    message_id: str
    sentiment_score: float = Field(ge=-1.0, le=1.0, description="Sentiment analysis -1.0 to 1.0")
    urgency_level: str = Field(description="Message urgency: low, medium, high, critical")
    sender_type: str = Field(description="Sender classification: internal, external, unknown")
    message_type: str = Field(description="Message category: inquiry, complaint, request, info, etc.")
    recommended_tone: ToneRecommendation
    user_selected_tone: Optional[ToneType] = None
    analysis_timestamp: datetime = Field(default_factory=datetime.now)


# -------------------------
# TONE ADJUSTMENT REQUEST
# -------------------------
class ToneAdjustmentRequest(BaseModel):
    """Request for tone adjustment"""
    original_text: str
    target_tone: ToneType
    message_context: Dict[str, Any] = Field(default_factory=dict)
    preserve_intent: bool = True
    user_preferences: Optional[ToneProfile] = None


# -------------------------
# TONE ADJUSTMENT RESPONSE
# -------------------------
class ToneAdjustmentResponse(BaseModel):
    """Response from tone adjustment"""
    adjusted_text: str
    original_tone: Optional[ToneType] = None
    applied_tone: ToneType
    confidence: float = Field(ge=0.0, le=1.0)
    changes_made: List[str] = Field(default_factory=list, description="What was changed")
    processing_time_ms: int = Field(description="Time taken to process in milliseconds")


# -------------------------
# EXTENDED AGENT MODELS
# -------------------------
# Extend existing agent models to support tone without modifying them
class ToneAwareAgentRequest(BaseModel):
    """Extension of AgentRequest with tone support"""
    # Original fields
    intent: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None
    
    # NEW: Tone-specific fields
    target_tone: Optional[ToneType] = None
    auto_tone_recommendation: bool = True
    tone_preferences: Optional[ToneProfile] = None


class ToneAwareAgentResponse(BaseModel):
    """Extension of AgentResponse with tone information"""
    # Original fields
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    agent_name: str
    
    # NEW: Tone-specific fields
    tone_analysis: Optional[ToneAnalysis] = None
    applied_tone: Optional[ToneType] = None
    tone_adjustments: List[str] = Field(default_factory=list)


# -------------------------
# UTILITY FUNCTIONS
# -------------------------

def get_tone_display_name(tone: ToneType) -> str:
    """Get display name for tone"""
    display_names = {
        ToneType.FORMAL: "Formal",
        ToneType.PROFESSIONAL: "Professional",
        ToneType.CASUAL: "Casual",
        ToneType.FRIENDLY: "Friendly",
        ToneType.ASSERTIVE: "Assertive",
        ToneType.PERSUASIVE: "Persuasive",
        ToneType.APOLOGETIC: "Apologetic",
        ToneType.EMPATHETIC: "Empathetic",
        ToneType.DIPLOMATIC: "Diplomatic",
        ToneType.CONCISE: "Concise",
        ToneType.HUMOROUS: "Humorous",
        ToneType.APPRECIATIVE: "Appreciative",
        ToneType.URGENT: "Urgent"
    }
    return display_names.get(tone, tone.value.title())


def get_tone_description(tone: ToneType) -> str:
    """Get description for tone"""
    descriptions = {
        ToneType.FORMAL: "Formal and respectful with proper titles",
        ToneType.PROFESSIONAL: "Business-appropriate and balanced",
        ToneType.CASUAL: "Relaxed and conversational",
        ToneType.FRIENDLY: "Warm and approachable",
        ToneType.ASSERTIVE: "Confident and direct",
        ToneType.PERSUASIVE: "Convincing and influential",
        ToneType.APOLOGETIC: "Sincere and apologetic",
        ToneType.EMPATHETIC: "Understanding and compassionate",
        ToneType.DIPLOMATIC: "Tactful and careful",
        ToneType.CONCISE: "Brief and to-the-point",
        ToneType.HUMOROUS: "Light-hearted and amusing",
        ToneType.APPRECIATIVE: "Grateful and thankful",
        ToneType.URGENT: "Time-sensitive and action-oriented"
    }
    return descriptions.get(tone, "Professional communication tone")
