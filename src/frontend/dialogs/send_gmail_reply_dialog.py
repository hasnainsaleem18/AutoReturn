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

# Local imports for tone features
from src.frontend.widgets.tone_selector import ToneSelector
from src.frontend.widgets.tone_detection_display import ToneDetectionDisplay


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
    def __init__(self, to_email: str, subject: str, parent=None, orchestrator=None, original_message=None):
        """Initialize the Gmail reply dialog.
        
        Args:
            to_email: Email address of the recipient
            subject: Original email subject (will be prefixed with 'Re: ')
            parent: Parent widget (optional)
            orchestrator: Orchestrator instance for tone features (optional)
            original_message: Original message data for sentiment analysis (optional)
        """
        super().__init__(parent)

        self.to_email = to_email
        self.subject = subject or "(No Subject)"
        self.orchestrator = orchestrator
        self.original_message = original_message or {}
        self.selected_tone = None
        self.attachments = []

        self.setWindowTitle("Reply via Gmail")
        self.setMinimumSize(620, 500)

        # Force white background - dialog inherits dark theme from main window otherwise
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel {
                color: #003135;
                background-color: transparent;
            }
            QTextEdit {
                background-color: #ffffff;
                color: #003135;
            }
            QFrame {
                background-color: #ffffff;
            }
        """)

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

        # NEW: Add tone display for incoming message
        self.tone_display = None
        if self.orchestrator and self.original_message:
            # Add tone selector and tone display
            info_label = QLabel("📊 Analyze incoming message mood, then select tone for your reply:")
            info_label.setStyleSheet("font-size: 12px; color: #024950; margin-bottom: 8px;")
            layout.addWidget(info_label)
            
            # Tone detection display for incoming message
            self.tone_display = ToneDetectionDisplay(self.original_message)
            layout.addWidget(self.tone_display)
            
            # Tone selector for outgoing message
            self.tone_selector = ToneSelector(self.orchestrator, self.original_message)
            self.tone_selector.tone_changed.connect(self._on_tone_changed)
            layout.addWidget(self.tone_selector)
        
        # Perform tone detection
        if self.tone_display:
            self._perform_tone_detection()

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

        attach_btn = QPushButton("📎 Attach")
        attach_btn.setCursor(Qt.PointingHandCursor)
        attach_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 2px solid #AFDDE5;
                background-color: white;
                border-radius: 8px;
                font-size: 13px;
                color: #024950;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #AFDDE5;
            }
        """)
        attach_btn.clicked.connect(self._select_attachments)
        self.attach_btn = attach_btn

        self.attachments_label = QLabel("No attachments")
        self.attachments_label.setStyleSheet("font-size: 12px; color: #024950;")

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
        btn_layout.addWidget(attach_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()

        # Add widgets to layout
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(to_label)
        layout.addWidget(to_value)
        layout.addSpacing(4)
        layout.addWidget(subject_label)
        layout.addWidget(subject_value)
        
        # NEW: Add tone display if available
        if self.tone_display:
            layout.addSpacing(8)
            layout.addWidget(self.tone_display)
        
        # NEW: Add tone selector if available
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

    # -------------------------
    # UI UPDATES
    # -------------------------
    def _update_send_button_state(self) -> None:
        """Update the send button state based on message content.
        
        Enables the send button only when there is text in the message body.
        """
        text = self.message_text.toPlainText().strip()
        has_attachments = bool(self.attachments)
        self.send_btn.setEnabled(len(text) > 0 or has_attachments)

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
    
    def get_selected_tone(self):
        """Get the selected tone for the message.
        
        Returns:
            ToneType or None: The selected tone
        """
        return self.selected_tone if self.tone_selector else None

    def get_attachments(self):
        """Return list of attachment file paths."""
        return list(self.attachments)

    def set_attachments(self, files):
        self.attachments = list(files or [])
        self._refresh_attachment_label()

    # -------------------------
    # ATTACHMENT HANDLERS
    # -------------------------
    def _select_attachments(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Attachment(s)",
            "",
            "All Files (*.*)"
        )
        if files:
            self.attachments.extend([f for f in files if f not in self.attachments])
            self._refresh_attachment_label()

    def _refresh_attachment_label(self):
        if not self.attachments:
            self.attachments_label.setText("No attachments")
            self._update_send_button_state()
            return
        names = [f.split("/")[-1] for f in self.attachments]
        self.attachments_label.setText("Attachments: " + ", ".join(names))
        self._update_send_button_state()
    
    # -------------------------
    # TONE AND SENTIMENT METHODS
    # -------------------------
    def _perform_tone_detection(self) -> None:
        """Analyze incoming message tone using ToneManager."""
        if not self.orchestrator or not self.original_message or not self.tone_display:
            return
            
        try:
            content = self.original_message.get('full_content', '') or self.original_message.get('preview', '')
            if content:
                # Use tone_manager to get detection result
                result = self.orchestrator.tone_manager.analyze_incoming_tone(content)
                self.tone_display.set_tone_data(result.get('tone_detection', {}))
        except Exception as e:
            print(f"Tone detection error in dialog: {e}")
    
    def _on_tone_changed(self, tone):
        """Handle tone selection change"""
        self.selected_tone = tone
        
        # Learn from user's manual tone selection
        if self.orchestrator and self.original_message:
            try:
                self.orchestrator.tone_manager.update_user_preferences(tone, self.original_message)
                print(f"� Learned tone preference: {tone.value} for message")
            except Exception as e:
                print(f"Error learning tone preference: {e}")
        
        # Optionally adjust message text based on tone
        if self.orchestrator and self.message_text.toPlainText().strip():
            self._adjust_message_tone(tone)
    
    def _adjust_message_tone(self, tone):
        """Adjust message text based on selected tone"""
        if not self.orchestrator:
            return
        
        try:
            import asyncio
            
            current_text = self.message_text.toPlainText()
            if current_text.strip():
                # Create message context for tone adjustment
                message_context = {
                    'sender': self.to_email,
                    'subject': f"Re: {self.subject}",
                    'source': 'gmail',
                    'original_message': self.original_message
                }
                
                # Perform tone adjustment asynchronously
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                result = loop.run_until_complete(
                    self.orchestrator.tone_manager.adjust_message_tone(
                        current_text, tone, message_context
                    )
                )
                
                if result.success and result.adjusted_text != current_text:
                    # Store cursor position
                    cursor = self.message_text.textCursor()
                    position = cursor.position()
                    
                    # Update text
                    self.message_text.setPlainText(result.adjusted_text)
                    
                    # Restore cursor position (within bounds)
                    cursor.setPosition(min(position, len(result.adjusted_text)))
                    self.message_text.setTextCursor(cursor)
                
                loop.close()
                
        except Exception as e:
            print(f"Tone adjustment error: {e}")
