# -------------------------
# AUTOMATION SETTINGS SERVICE
# -------------------------
"""
Service for loading and persisting automation settings.
"""

# -------------------------
# IMPORTS
# -------------------------
import json
import os
from typing import Optional

from src.backend.models.automation_models import AutomationSettings


class AutomationSettingsService:
    """
    Persistence wrapper for automation settings.

    This service isolates file I/O from policy logic so the rest of the
    automation pipeline can work against typed models only.
    """

    def __init__(self, settings_path: Optional[str] = None):
        # Allow custom paths for tests; use the shared data path by default.
        if settings_path:
            self.settings_path = settings_path
        else:
            self.settings_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "data", "automation_settings.json"
            )

    def load_settings(self) -> AutomationSettings:
        """
        Load settings from disk.

        Returns default settings when the file is missing or cannot be parsed.
        """
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                return AutomationSettings(**raw)
        except Exception as e:
            print(f"Could not load automation settings: {e}")

        return AutomationSettings()

    def save_settings(self, settings: AutomationSettings) -> bool:
        """Persist settings to disk and return whether the write succeeded."""
        try:
            # Ensure the data directory exists before writing the JSON file.
            os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings.model_dump(), f, indent=2)
            return True
        except Exception as e:
            print(f"Could not save automation settings: {e}")
            return False
