"""Unit tests for settings dialog basics and main entry flow."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from src.frontend.dialogs.settings_dialog import SettingsDialog, ToggleSwitch
from testing_formal.tests.qt_utils import get_qapp


class TestSettingsDialogFormal(unittest.TestCase):
    @classmethod
    # -------------------------
    # FUNCTION: setUpClass
    # Purpose: Execute setUpClass logic for this module.
    # -------------------------
    def setUpClass(cls):
        cls.app = get_qapp()

    # -------------------------
    # FUNCTION: test_toggle_switch_size_hint
    # Purpose: Validate the toggle switch size hint scenario.
    # -------------------------
    def test_toggle_switch_size_hint(self):
        t = ToggleSwitch()
        size = t.sizeHint()
        self.assertEqual(size.width(), 52)
        self.assertEqual(size.height(), 28)

    # -------------------------
    # FUNCTION: test_settings_dialog_initializes_user_defaults
    # Purpose: Validate the settings dialog initializes user defaults scenario.
    # -------------------------
    def test_settings_dialog_initializes_user_defaults(self):
        dialog = SettingsDialog(user_data={"email": "x@y.com"})
        self.assertEqual(dialog.user_data.get("email"), "x@y.com")
        self.assertIn("name", dialog.user_data)


class TestMainEntrypointFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_main_exits_when_auth_cancelled
    # Purpose: Validate the main exits when auth cancelled scenario.
    # -------------------------
    def test_main_exits_when_auth_cancelled(self):
        import main as app_main

        fake_qapp = MagicMock()
        fake_qapp.exec.return_value = 0

        fake_auth_instance = MagicMock()
        fake_auth_instance.exec.return_value = 0  # rejected
        fake_auth_instance.authenticated.connect = MagicMock()

        with patch.object(app_main, "QApplication", return_value=fake_qapp), \
             patch.object(app_main, "AuthDialog", return_value=fake_auth_instance), \
             self.assertRaises(SystemExit) as cm:
            app_main.main()

        self.assertEqual(cm.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
