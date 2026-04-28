"""Unit tests for desktop notification platform helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from src.backend.utils import desktop_notifications
from src.frontend.ui.autoreturn_app import AutoReturnApp


class TestDesktopNotificationsFormal(unittest.TestCase):
    # -------------------------
    # FUNCTION: test_macos_notification_uses_osascript
    # Purpose: Validate macOS avoids plyer when osascript is available.
    # -------------------------
    def test_macos_notification_uses_osascript(self):
        with patch.object(desktop_notifications.sys, "platform", "darwin"), \
                patch.object(desktop_notifications.shutil, "which", return_value="/usr/bin/osascript"), \
                patch.object(desktop_notifications.subprocess, "run") as run_mock, \
                patch.object(desktop_notifications, "_notify_with_plyer") as plyer_mock:
            ok = desktop_notifications.notify_desktop(
                "AutoReturn",
                'New "quoted"\nmessage',
                timeout=6,
            )

        self.assertTrue(ok)
        run_mock.assert_called_once()
        plyer_mock.assert_not_called()
        script = run_mock.call_args.args[0][2]
        self.assertIn("display notification", script)
        self.assertIn('\\"quoted\\" message', script)

    # -------------------------
    # FUNCTION: test_macos_notification_falls_back_when_osascript_missing
    # Purpose: Validate macOS fallback behavior remains quiet.
    # -------------------------
    def test_macos_notification_falls_back_when_osascript_missing(self):
        with patch.object(desktop_notifications.sys, "platform", "darwin"), \
                patch.object(desktop_notifications.shutil, "which", return_value=None), \
                patch.object(desktop_notifications, "_notify_with_plyer", return_value=False) as plyer_mock:
            ok = desktop_notifications.notify_desktop("Title", "Message", timeout=6)

        self.assertFalse(ok)
        plyer_mock.assert_called_once_with("Title", "Message", 6)

    # -------------------------
    # FUNCTION: test_app_notification_wrapper_suppresses_helper_failure
    # Purpose: Validate UI notification calls do not surface backend errors.
    # -------------------------
    def test_app_notification_wrapper_suppresses_helper_failure(self):
        app_obj = AutoReturnApp.__new__(AutoReturnApp)
        app_obj._get_automation_status_snapshot = lambda: (False, {})

        with patch("src.frontend.ui.autoreturn_app.notify_desktop", return_value=False) as notify_mock:
            AutoReturnApp._notify_desktop(app_obj, "Title", "Message")

        notify_mock.assert_called_once_with("Title", "Message", timeout=6)


if __name__ == "__main__":
    unittest.main()
