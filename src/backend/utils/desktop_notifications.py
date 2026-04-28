"""Desktop notification helpers with a macOS-safe implementation."""

from __future__ import annotations

import shutil
import subprocess
import sys


def notify_desktop(title: str, message: str, timeout: int = 6) -> bool:
    """Send a desktop notification when the current platform supports it."""
    if sys.platform == "darwin":
        if _notify_macos(title, message):
            return True
        return _notify_with_plyer(title, message, timeout)

    return _notify_with_plyer(title, message, timeout)


def _notify_macos(title: str, message: str) -> bool:
    """Use macOS Notification Center through AppleScript."""
    if not shutil.which("osascript"):
        return False

    script = (
        f'display notification "{_applescript_text(message)}" '
        f'with title "{_applescript_text(title)}"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _notify_with_plyer(title: str, message: str, timeout: int) -> bool:
    """Fallback notification path for platforms where plyer works."""
    try:
        from plyer import notification

        notification.notify(title=title, message=message, timeout=timeout)
        return True
    except Exception:
        return False


def _applescript_text(value: str) -> str:
    """Escape text for an AppleScript double-quoted string."""
    text = str(value or "").replace("\\", "\\\\").replace('"', '\\"')
    return " ".join(text.splitlines())
