"""
Service for loading and saving automation settings.
"""

import json
import os
from typing import Optional

from src.backend.models.automation_models import AutomationSettings


class AutomationSettingsService:
    """Persistent storage wrapper for automation settings."""

    def __init__(self, settings_path: Optional[str] = None):
        if settings_path:
            self.settings_path = settings_path
        else:
            self.settings_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "data", "automation_settings.json"
            )

    def load_settings(self) -> AutomationSettings:
        """Load settings from disk; fallback to defaults if missing/invalid."""
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                return AutomationSettings(**raw)
        except Exception as e:
            print(f"Could not load automation settings: {e}")

        return AutomationSettings()

    def save_settings(self, settings: AutomationSettings) -> bool:
        """Persist settings to disk."""
        try:
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings.model_dump(), f, indent=2)
            return True
        except Exception as e:
            print(f"Could not save automation settings: {e}")
            return False
