# -------------------------
# TONE MODELS
# -------------------------
"""
Data models for tone adjustment and recommendation system.
Uses a clean 2-tone model: Formal and Informal.
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
# Canonical 2-tone vocabulary used across backend and frontend.
# -------------------------
class ToneType(str, Enum):
    """Available tone types for message adjustment"""
    FORMAL = "formal"
    INFORMAL = "informal"


# -------------------------
# TONE RECOMMENDATION
# Model returned by recommendation logic (deterministic + LLM fallback).
# -------------------------
class ToneRecommendation(BaseModel):
    """AI-generated tone recommendation"""
    recommended_tone: ToneType
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0 to 1.0")
    reasoning: str = Field(default="", description="Explanation for the recommendation")
    tone_signal_score: float = Field(default=0.0, ge=-1.0, le=1.0, description="Tone signal score -1.0 to 1.0")
    urgency_level: str = Field(default="medium", description="Message urgency: low, medium, high, critical")
    detected_tone_signal: Optional[str] = Field(default=None, description="Detected tone signal")
    detected_tone: Optional[ToneType] = Field(default=None, description="Detected tone from analysis")
    fallback_used: bool = Field(default=False, description="Whether LLM fallback was used")
    context_factors: Dict[str, Any] = Field(default_factory=dict, description="Factors influencing recommendation")


# -------------------------
# TONE PROFILE
# Persistent user preference model used for adaptive tone behavior.
# -------------------------
class ToneProfile(BaseModel):
    """User's tone preferences and learning patterns"""
    default_tone: ToneType = ToneType.FORMAL
    sender_preferences: Dict[str, ToneType] = Field(default_factory=dict, description="Custom tones per sender")
    domain_preferences: Dict[str, ToneType] = Field(default_factory=dict, description="Custom tones per email domain")
    auto_tone_enabled: bool = True
    manual_override_history: List[Dict[str, Any]] = Field(default_factory=list, description="Learning from user choices")
    tone_effectiveness_scores: Dict[str, float] = Field(default_factory=dict, description="User feedback on tone quality")


# -------------------------
# TONE ANALYSIS
# Full analysis snapshot attached to message/reply workflows.
# -------------------------
class ToneAnalysis(BaseModel):
    """Complete tone analysis for a message"""
    message_id: str
    urgency_level: str = Field(default="medium", description="Message urgency: low, medium, high, critical")
    sender_type: str = Field(default="unknown", description="Sender classification: internal, external, unknown")
    message_type: str = Field(default="info", description="Message category: inquiry, complaint, request, info, etc.")
    recommended_tone: Optional[ToneRecommendation] = None
    user_selected_tone: Optional[ToneType] = None
    analysis_timestamp: datetime = Field(default_factory=datetime.now)


# -------------------------
# TONE ADJUSTMENT REQUEST
# Input contract for "rewrite this text in target tone" operations.
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
# Output contract after a tone rewrite attempt.
# -------------------------
class ToneAdjustmentResponse(BaseModel):
    """Response from tone adjustment"""
    adjusted_text: str
    original_tone: Optional[ToneType] = None
    applied_tone: ToneType
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    changes_made: List[str] = Field(default_factory=list, description="What was changed")
    processing_time_ms: int = Field(default=0, description="Time taken to process in milliseconds")
    success: bool = True
    reasoning: str = ""


# -------------------------
# EXTENDED AGENT MODELS
# Tone-aware wrappers that mirror core agent contracts while carrying
# extra analysis/rewrite fields for tone-enabled workflows.
# -------------------------
class ToneAwareAgentRequest(BaseModel):
    """Extension of AgentRequest with tone support"""
    intent: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[Dict[str, Any]] = None

    # Tone-specific fields
    target_tone: Optional[ToneType] = None
    auto_tone_recommendation: bool = True
    tone_preferences: Optional[ToneProfile] = None


class ToneAwareAgentResponse(BaseModel):
    """Extension of AgentResponse with tone information"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    agent_name: str

    # Tone-specific fields
    tone_analysis: Optional[ToneAnalysis] = None
    applied_tone: Optional[ToneType] = None
    tone_adjustments: List[str] = Field(default_factory=list)


# -------------------------
# UTILITY FUNCTIONS
# Small helpers for UI labels/descriptions so presentation code can
# remain decoupled from enum internals.
# -------------------------

# -------------------------
# GET TONE DISPLAY NAME
# Converts ToneType enum into user-facing short labels.
# -------------------------
def get_tone_display_name(tone: ToneType) -> str:
    """Get display name for tone"""
    display_names = {
        ToneType.FORMAL: "Formal",
        ToneType.INFORMAL: "Informal",
    }
    return display_names.get(tone, str(tone).title())


# -------------------------
# GET TONE DESCRIPTION
# Returns longer explanatory text for tooltips/help text.
# -------------------------
def get_tone_description(tone: ToneType) -> str:
    """Get description for tone"""
    descriptions = {
        ToneType.FORMAL: "Formal and respectful with proper titles",
        ToneType.INFORMAL: "Casual and conversational communication",
    }
    return descriptions.get(tone, "Communication tone")
