"""
Coordinator for automation settings + policy decisioning.
"""

from src.backend.core.reply_policy_engine import ReplyPolicyEngine
from src.backend.models.automation_models import AutomationSettings, PolicyDecision
from src.backend.services.automation_settings_service import AutomationSettingsService


class AutomationCoordinator:
    """Thin coordination layer around settings persistence and policy evaluation."""

    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(
        self,
        settings_service: AutomationSettingsService,
        policy_engine: ReplyPolicyEngine,
    ):
        self.settings_service = settings_service
        self.policy_engine = policy_engine

    # -------------------------
    # GET SETTINGS
    # Retrieves settings.
    # -------------------------
    def get_settings(self) -> AutomationSettings:
        return self.settings_service.load_settings()

    # -------------------------
    # UPDATE SETTINGS
    # Refreshes or updates settings.
    # -------------------------
    def update_settings(self, settings: AutomationSettings) -> bool:
        return self.settings_service.save_settings(settings)

    # -------------------------
    # EVALUATE MESSAGE
    # Handles evaluate functionality for message.
    # -------------------------
    def evaluate_message(self, message: dict) -> PolicyDecision:
        settings = self.get_settings()
        return self.policy_engine.evaluate(message=message, settings=settings)
