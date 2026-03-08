"""
Data models for automation policy and settings.
"""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class AutomationAction(str, Enum):
    """High-level action selected by automation policy."""

    DRAFT_ONLY = "draft_only"
    PLAIN_REPLY = "plain_reply"
    AUTO_REPLY = "auto_reply"
    IGNORE = "ignore"


class AutomationSettings(BaseModel):
    """User-configurable automation settings."""

    dnd_enabled: bool = False
    auto_reply_enabled: bool = False
    auto_reply_allowlist: List[str] = Field(default_factory=list)
    file_access_paths: List[str] = Field(default_factory=list)
    max_auto_attachments: int = Field(default=3, ge=0, le=10)
    require_user_confirm_plain_reply: bool = True


class PolicyDecision(BaseModel):
    """Decision output from the policy engine."""

    action: AutomationAction
    reason: str
    sender_identity: str = ""
    sender_allowed: bool = False
