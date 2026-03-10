"""
Rule-based policy engine for deciding Draft/Plain Reply/Auto Reply flows.
"""

from src.backend.models.automation_models import (
    AutomationAction,
    AutomationSettings,
    PolicyDecision,
)


class ReplyPolicyEngine:
    """Applies automation settings to a message and returns a policy decision."""

    # -------------------------
    # EVALUATE
    # Handles evaluate functionality for the operation.
    # -------------------------
    def evaluate(self, message: dict, settings: AutomationSettings) -> PolicyDecision:
        sender_identity = self._extract_sender_identity(message)
        sender_allowed = self._is_sender_allowed(sender_identity, settings)

        if settings.dnd_enabled:
            if settings.auto_reply_enabled and sender_allowed:
                return PolicyDecision(
                    action=AutomationAction.AUTO_REPLY,
                    reason="DND is enabled, auto-reply is enabled, and sender is allowlisted.",
                    sender_identity=sender_identity,
                    sender_allowed=True,
                )

            return PolicyDecision(
                action=AutomationAction.DRAFT_ONLY,
                reason="DND is enabled; creating a draft instead of sending.",
                sender_identity=sender_identity,
                sender_allowed=sender_allowed,
            )

        return PolicyDecision(
            action=AutomationAction.PLAIN_REPLY,
            reason="DND is disabled; route to plain reply with user confirmation.",
            sender_identity=sender_identity,
            sender_allowed=sender_allowed,
        )

    # -------------------------
    # EXTRACT SENDER IDENTITY
    # Handles extract functionality for sender identity.
    # -------------------------
    def _extract_sender_identity(self, message: dict) -> str:
        source = str(message.get("source", "")).lower()

        if source == "gmail":
            return str(message.get("email", "")).strip().lower()

        if source == "slack":
            sender_id = str(message.get("user_id", "")).strip()
            if sender_id:
                return sender_id
            sender_email = str(message.get("email", "")).strip().lower()
            if sender_email:
                return sender_email
            return str(message.get("sender", "")).strip().lower()

        sender_email = str(message.get("email", "")).strip().lower()
        if sender_email:
            return sender_email
        return str(message.get("sender", "")).strip().lower()

    # -------------------------
    # IS SENDER ALLOWED
    # Evaluates whether sender allowed.
    # -------------------------
    def _is_sender_allowed(self, sender_identity: str, settings: AutomationSettings) -> bool:
        if not sender_identity:
            return False

        allow = {item.strip().lower() for item in settings.auto_reply_allowlist if item and item.strip()}
        return sender_identity.lower() in allow
