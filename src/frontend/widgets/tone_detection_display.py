# -------------------------
# TONE DETECTION DISPLAY WIDGET
# -------------------------
"""
Widget for displaying incoming tone detection results with visual indicators.
"""

# -------------------------
# IMPORTS
# -------------------------
from typing import Dict, Any
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

from src.backend.models.tone_models import ToneType, get_tone_display_name


# -------------------------
# TONE DETECTION DISPLAY CLASS
# -------------------------
class ToneDetectionDisplay(QWidget):
    """Display incoming message detected tone and confidence."""

    # -------------------------
    # INIT
    # Stores initial message context and builds compact tone display UI.
    # -------------------------
    def __init__(self, message_data=None, parent=None):
        super().__init__(parent)
        self.message_data = message_data or {}
        self.tone_data = None

        self.setup_ui()
        self.update_display()

    # -------------------------
    # SETUP UI
    # Creates labels/badges for detected tone and confidence visibility.
    # -------------------------
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.detected_label = QLabel("Incoming Detected Tone:")
        self.detected_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.detected_label)

        self.detected_badge = QLabel("Formal")
        layout.addWidget(self.detected_badge)

        self.confidence_label = QLabel("")
        layout.addWidget(self.confidence_label)

        layout.addStretch()
        self._apply_theme_styles()

    # -------------------------
    # UPDATE DISPLAY
    # Reads tone payload from message data and refreshes badge/confidence.
    # Hides widget when no tone data is available.
    # -------------------------
    def update_display(self):
        if not self.message_data:
            self.hide()
            return

        self.tone_data = self.message_data.get('tone_detection')
        if not self.tone_data:
            self.hide()
            return

        confidence = self.tone_data.get('confidence', 0.0)
        detected_tone = self.tone_data.get('detected_tone', ToneType.FORMAL.value)

        self.update_detected_badge(detected_tone)
        self.update_confidence_label(confidence)
        self.show()

    # -------------------------
    # UPDATE DETECTED BADGE
    # Formats detected tone into a colored pill-style badge.
    # -------------------------
    def update_detected_badge(self, detected_tone: str):
        tone_colors = {
            ToneType.FORMAL.value: '#1e3a8a',
            ToneType.INFORMAL.value: '#0f766e',
        }
        label = get_tone_display_name(ToneType(detected_tone)) if detected_tone in {t.value for t in ToneType} else "Formal"
        color = tone_colors.get(detected_tone, '#546e7a')
        self.detected_badge.setText(label)
        self.detected_badge.setStyleSheet(
            f"padding: 2px 8px; border-radius: 12px; background-color: {color}; color: white; font-weight: 600;"
        )

    # -------------------------
    # UPDATE CONFIDENCE LABEL
    # Shows confidence text only when score is available.
    # -------------------------
    def update_confidence_label(self, confidence: float):
        if confidence > 0:
            self.confidence_label.setText(f"Confidence: {confidence:.1f}")
            self.confidence_label.show()
        else:
            self.confidence_label.hide()

    # -------------------------
    # SET MESSAGE DATA
    # Replaces source message context and refreshes full display.
    # -------------------------
    def set_message_data(self, message_data: dict):
        self.message_data = message_data
        self.update_display()

    # -------------------------
    # SET TONE DATA
    # Directly injects tone payload and updates UI immediately.
    # -------------------------
    def set_tone_data(self, tone_data: Dict[str, Any]):
        self.tone_data = tone_data
        if tone_data:
            confidence = tone_data.get('confidence', 0.0)
            detected_tone = tone_data.get('detected_tone', ToneType.FORMAL.value)
            self.update_detected_badge(detected_tone)
            self.update_confidence_label(confidence)
            self.show()
        else:
            self.hide()

    # -------------------------
    # CLEAR DISPLAY
    # Resets tone payload and hides widget.
    # -------------------------
    def clear(self):
        self.tone_data = None
        self.hide()

    # -------------------------
    # APPLY THEME STYLES
    # Applies compact neutral style for consistency with app theme.
    # -------------------------
    def _apply_theme_styles(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #9ca3af;
                border-radius: 4px;
                color: #1f2937;
            }
            QLabel {
                color: #1f2937;
            }
        """)


# -------------------------
# COMPACT DISPLAY FACTORY
# Returns a low-height tone display variant for dense layouts.
# -------------------------
def create_tone_detection_display_compact(message_data=None, parent=None) -> ToneDetectionDisplay:
    display = ToneDetectionDisplay(message_data, parent)
    display.setMaximumHeight(30)
    return display


# -------------------------
# DETAILED DISPLAY FACTORY
# Returns a taller tone display variant for expanded views.
# -------------------------
def create_tone_detection_display_detailed(message_data=None, parent=None) -> ToneDetectionDisplay:
    display = ToneDetectionDisplay(message_data, parent)
    display.setMinimumHeight(40)
    return display
