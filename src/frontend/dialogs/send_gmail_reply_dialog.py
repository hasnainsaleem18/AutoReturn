# -------------------------
# GMAIL REPLY DIALOG
# -------------------------
"""
Dialog for composing and sending email replies via Gmail.

This module provides a user interface for composing and sending email replies
with support for recipient, subject, and message body editing.
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
from typing import Optional

# Third-party imports
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

# Local imports for tone features
from src.frontend.widgets.tone_selector import ToneSelector
from src.frontend.widgets.tone_detection_display import ToneDetectionDisplay


# -------------------------
# GMAIL REPLY DIALOG CLASS
# -------------------------
class SendGmailReplyDialog(QDialog):
    """Dialog for composing and sending email replies via Gmail."""
    
    def __init__(self, to_email: str, subject: str, parent=None, orchestrator=None, original_message=None):
        super().__init__(parent)

        self.to_email = to_email
        self.subject = subject or "(No Subject)"
        self.orchestrator = orchestrator
        self.original_message = original_message or {}
        self.selected_tone = None
        self.tone_selector = None
        self.attachments = []

        self.setWindowTitle("Reply via Gmail")
        self.setMinimumSize(620, 500)

        self._apply_theme_styles()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Reply to Email")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #003135;")

        to_label = QLabel("To:")
        to_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #024950;")
        to_value = QLabel(self.to_email or "(unknown)")
        to_value.setStyleSheet("font-size: 13px; color: #003135;")

        subject_label = QLabel("Subject:")
        subject_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #024950;")
        subject_value = QLabel(f"Re: {self.subject}")
        subject_value.setStyleSheet("font-size: 13px; color: #003135;")
        subject_value.setWordWrap(True)

        # Add tone display and selector if orchestrator available
        self.tone_detection_display = None
        if self.orchestrator and self.original_message:
            info_label = QLabel("Analyze incoming message mood, then select tone for your reply:")
            info_label.setStyleSheet("font-size: 12px; color: #024950; margin-bottom: 8px;")
            layout.addWidget(info_label)

            # Tone detection display badge for incoming message
            self.tone_detection_display = ToneDetectionDisplay(self.original_message)

            # Tone selector for outgoing message
            self.tone_selector = ToneSelector(self.orchestrator, self.original_message)
            self.tone_selector.tone_changed.connect(self._on_tone_changed)

        # Perform tone analysis
        if self.tone_detection_display:
            self._perform_tone_detection()

        body_label = QLabel("Message:")
        body_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #024950;")

        self.message_text = QTextEdit()
        self.message_text.setPlaceholderText("Type your reply here...")
        self.message_text.setStyleSheet("""
            QTextEdit {
                padding: 12px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 2px solid #0FA4AF;
            }
        """)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        send_btn = QPushButton("Send Reply")
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #0FA4AF;
                color: white;
                border: none;
                padding: 10px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #024950; }
            QPushButton:disabled { background-color: #AFDDE5; color: #666; }
        """)
        send_btn.clicked.connect(self._handle_send)
        self.send_btn = send_btn

        attach_btn = QPushButton("📎 Attach")
        attach_btn.setCursor(Qt.PointingHandCursor)
        attach_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 16px;
                border: 2px solid #AFDDE5;
                background-color: white;
                border-radius: 8px;
                font-size: 13px;
                color: #024950;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #AFDDE5; }
        """)
        attach_btn.clicked.connect(self._select_attachments)

        self.attachments_label = QLabel("No attachments")
        self.attachments_label.setStyleSheet("font-size: 12px; color: #024950;")

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 10px 24px;
                border: 2px solid #AFDDE5;
                background-color: white;
                border-radius: 8px;
                font-size: 14px;
                color: #024950;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #AFDDE5; }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(send_btn)
        btn_layout.addWidget(attach_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()

        # Assemble layout
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(to_label)
        layout.addWidget(to_value)
        layout.addSpacing(4)
        layout.addWidget(subject_label)
        layout.addWidget(subject_value)

        if self.tone_detection_display:
            layout.addSpacing(8)
            layout.addWidget(self.tone_detection_display)

        if self.tone_selector:
            layout.addSpacing(8)
            layout.addWidget(self.tone_selector)

        layout.addSpacing(8)
        layout.addWidget(body_label)
        layout.addWidget(self.message_text, 1)
        layout.addWidget(self.attachments_label)
        layout.addLayout(btn_layout)

        self.message_text.textChanged.connect(self._update_send_button_state)
        self._update_send_button_state()

    def _update_send_button_state(self) -> None:
        text = self.message_text.toPlainText().strip()
        has_attachments = bool(self.attachments)
        self.send_btn.setEnabled(len(text) > 0 or has_attachments)

    def _handle_send(self) -> None:
        if self.get_message_text() or self.attachments:
            self.accept()

    def _select_attachments(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Attachments")
        if files:
            self.attachments.extend(files)
            names = [f.split("/")[-1] for f in self.attachments]
            self.attachments_label.setText("Attachments: " + ", ".join(names))
            self.attachments_label.setStyleSheet("font-size: 12px; color: #024950;")
            self._update_send_button_state()

    def get_message_text(self) -> str:
        return self.message_text.toPlainText().strip()

    def set_message_text(self, text: str) -> None:
        self.message_text.setPlainText(text or "")
        self._update_send_button_state()

    def get_selected_tone(self):
        return self.selected_tone if self.tone_selector else None

    def get_attachments(self):
        return list(self.attachments)

    def set_attachments(self, files: list):
        """Preload attachments in the dialog (used by automation draft flow)."""
        normalized = []
        for file_path in files or []:
            if file_path and file_path not in normalized:
                normalized.append(file_path)
        self.attachments = normalized
        if self.attachments:
            names = [f.split("/")[-1] for f in self.attachments]
            self.attachments_label.setText("Attachments: " + ", ".join(names))
            self.attachments_label.setStyleSheet(
                """
                font-size: 12px;
                color: #0B5E36;
                font-weight: 700;
                background-color: #E8F7EF;
                border: 1px solid #77C39D;
                border-radius: 6px;
                padding: 4px 8px;
                """
            )
        else:
            self.attachments_label.setText("No attachments")
            self.attachments_label.setStyleSheet("font-size: 12px; color: #024950;")
        self._update_send_button_state()

    # -------------------------
    # TONE METHODS
    # -------------------------
    def _perform_tone_detection(self):
        """Perform tone analysis on the original message using tone_engine."""
        if not self.orchestrator or not self.original_message:
            return
        try:
            content = self.original_message.get('full_content', '') or self.original_message.get('content', '') or self.original_message.get('preview', '')
            if content:
                # Use orchestrator tone engine for incoming message tone detection.
                tone_engine = getattr(self.orchestrator, 'tone_engine', None) or getattr(self.orchestrator, 'tone_manager', None)
                if tone_engine:
                    tone_result = tone_engine.analyze_incoming_tone(content)
                    self.original_message['tone_detection'] = tone_result
                    if self.tone_detection_display:
                        self.tone_detection_display.set_tone_data(tone_result)
        except Exception as e:
            print(f"Tone analysis error: {e}")

    def _on_tone_changed(self, tone):
        self.selected_tone = tone
        if self.orchestrator and self.original_message:
            try:
                tone_engine = getattr(self.orchestrator, 'tone_engine', None) or getattr(self.orchestrator, 'tone_manager', None)
                if tone_engine:
                    tone_engine.update_user_preferences(tone, self.original_message)
                    print(f"Learned tone preference: {tone.value}")
            except Exception as e:
                print(f"Error learning tone preference: {e}")

    def _apply_theme_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #1f2937; background-color: transparent; }
            QTextEdit { background-color: #ffffff; color: #1f2937; }
            QComboBox { background-color: #ffffff; color: #1f2937; }
            QFrame { background-color: #ffffff; }
        """)
