# -------------------------
# AUTOMATION MODELS
# -------------------------
"""
Data models for automation policy and settings.
"""

# -------------------------
# IMPORTS
# -------------------------
from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class AutomationAction(str, Enum):
    """Action selected by the automation policy engine."""

    DRAFT_ONLY = "draft_only"
    PLAIN_REPLY = "plain_reply"
    AUTO_REPLY = "auto_reply"
    IGNORE = "ignore"


class VoiceActivationMode(str, Enum):
    """Voice activation mode for microphone behavior."""

    MANUAL = "manual"
    WAKE_WORD = "wake_word"


class VoiceSettings(BaseModel):
    """Persisted configuration for push-to-talk voice control."""

    enabled: bool = True
    hotkey: str = "ctrl+shift+v"
    activation_mode: VoiceActivationMode = VoiceActivationMode.MANUAL
    language: str = "en"


class AutomationSettings(BaseModel):
    """User-configurable automation settings persisted on disk."""

    dnd_enabled: bool = False
    auto_reply_enabled: bool = False
    auto_reply_allowlist: List[str] = Field(default_factory=list)
    file_access_paths: List[str] = Field(default_factory=list)
    max_auto_attachments: int = Field(default=3, ge=0, le=10)
    require_user_confirm_plain_reply: bool = True
    voice: VoiceSettings = Field(default_factory=VoiceSettings)


class PolicyDecision(BaseModel):
    """Final policy decision returned to the calling workflow."""

    action: AutomationAction
    reason: str
    sender_identity: str = ""
    sender_allowed: bool = False
