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
    QPushButton, QTextEdit
)
from PySide6.QtCore import Qt


# -------------------------
# GMAIL REPLY DIALOG CLASS
# -------------------------
class SendGmailReplyDialog(QDialog):
    """Dialog for composing and sending email replies via Gmail.
    
    This dialog provides a user interface for composing email replies with
    pre-filled recipient and subject fields, along with a rich text editor
    for the message body.
    """
    
    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self, to_email: str, subject: str, parent=None):
        """Initialize the Gmail reply dialog.
        
        Args:
            to_email: Email address of the recipient
            subject: Original email subject (will be prefixed with 'Re: ')
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        self.to_email = to_email
        self.subject = subject or "(No Subject)"

        self.setWindowTitle("Reply via Gmail")
        self.setMinimumSize(600, 450)

        self._build_ui()

    # -------------------------
    # UI CREATION
    # -------------------------
    def _build_ui(self) -> None:
        """Build and configure the user interface components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Reply to Email")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #003135;"
        )

        to_label = QLabel("To:")
        to_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #024950;"
        )
        to_value = QLabel(self.to_email or "(unknown)")
        to_value.setStyleSheet(
            "font-size: 13px; color: #003135;"
        )

        subject_label = QLabel("Subject:")
        subject_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #024950;"
        )
        subject_value = QLabel(f"Re: {self.subject}")
        subject_value.setStyleSheet(
            "font-size: 13px; color: #003135;"
        )
        subject_value.setWordWrap(True)

        body_label = QLabel("Message:")
        body_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #024950;"
        )

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
            QPushButton:hover {
                background-color: #024950;
            }
            QPushButton:disabled {
                background-color: #AFDDE5;
                color: #666;
            }
        """)
        send_btn.clicked.connect(self._handle_send)
        self.send_btn = send_btn

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
            QPushButton:hover {
                background-color: #AFDDE5;
            }
        """)
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(send_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()

        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(to_label)
        layout.addWidget(to_value)
        layout.addSpacing(4)
        layout.addWidget(subject_label)
        layout.addWidget(subject_value)
        layout.addSpacing(8)
        layout.addWidget(body_label)
        layout.addWidget(self.message_text, 1)
        layout.addLayout(btn_layout)

        self.message_text.textChanged.connect(self._update_send_button_state)
        self._update_send_button_state()

    # -------------------------
    # UI UPDATES
    # -------------------------
    def _update_send_button_state(self) -> None:
        """Update the send button state based on message content.
        
        Enables the send button only when there is text in the message body.
        """
        text = self.message_text.toPlainText().strip()
        self.send_btn.setEnabled(len(text) > 0)

    # -------------------------
    # EVENT HANDLERS
    # -------------------------
    def _handle_send(self) -> None:
        """Handle send button click event.
        
        Validates the message and closes the dialog with accept status
        if the message is not empty.
        """
        if self.get_message_text():
            self.accept()

    # -------------------------
    # PUBLIC METHODS
    # -------------------------
    def get_message_text(self) -> str:
        """Get the composed message text.
        
        Returns:
            str: The trimmed message text
        """
        return self.message_text.toPlainText().strip()
