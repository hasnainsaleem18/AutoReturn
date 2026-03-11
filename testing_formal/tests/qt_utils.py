"""Qt test helpers for desktop UI modules."""

from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication


# Ensure Qt can initialize in headless CI/dev shells.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# -------------------------
# FUNCTION: get_qapp
# Purpose: Execute get qapp logic for this module.
# -------------------------
def get_qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
