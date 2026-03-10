# -------------------------
# SEND SLACK MESSAGE DIALOG
# -------------------------
"""
Dialog for composing and sending Slack direct messages.
Supports tone detection/recommendation and optional file attachments.
"""

# -------------------------
# IMPORTS
# -------------------------
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette

# Local imports for tone features
from src.frontend.widgets.tone_selector import ToneSelector
from src.frontend.widgets.tone_detection_display import ToneDetectionDisplay


# -------------------------
# SEND SLACK MESSAGE DIALOG CLASS
# Compose UI for Slack DM replies with optional tone assistance.
# -------------------------
class SendSlackMessageDialog(QDialog):
    
    # -------------------------
    # INIT
    # Stores user list/context and builds dialog UI with project theme styling.
    # -------------------------
    def __init__(self, users: list, parent=None, orchestrator=None, original_message=None):
        super().__init__(parent)
        
        self.users = users
        self.selected_user = None
        self.orchestrator = orchestrator
        self.original_message = original_message or {}
        self.selected_tone = None
        self.attachments = []
        
        self.setWindowTitle("Send Slack Direct Message")
        self.setMinimumSize(520, 430)

        self._apply_theme_styles()
        self._build_ui()
    
    # -------------------------
    # BUILD UI
    # Creates recipient picker, message editor, tone widgets,
    # attachment controls, and send/cancel actions.
    # -------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel("Send Direct Message")
        title.setStyleSheet("font-size: 18px; font-weight: 600; color: #003135;")
        
        recipient_label = QLabel("To:")
        recipient_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #024950;")
        
        self.user_combo = QComboBox()
        self.user_combo.setStyleSheet("""
            QComboBox {
                padding: 8px 12px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QComboBox:focus { border: 2px solid #0FA4AF; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                border: 1px solid #AFDDE5;
                background-color: white;
                selection-background-color: #AFDDE5;
                padding: 4px;
            }
        """)
        
        sorted_users = sorted(self.users, key=lambda u: u.get('real_name', u.get('name', '')))
        for user in sorted_users:
            real_name = user.get('real_name', user.get('name', 'Unknown'))
            username = user.get('name', '')
            self.user_combo.addItem(f"{real_name} (@{username})", user)
        
        message_label = QLabel("Message:")
        message_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #024950;")
        
        self.message_text = QTextEdit()
        self.message_text.setPlaceholderText("Type your message here...")
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
            QTextEdit:focus { border: 2px solid #0FA4AF; }
        """)
        
        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setStyleSheet("font-size: 11px; color: #666; font-style: italic;")
        self.char_count_label.setAlignment(Qt.AlignRight)
        self.message_text.textChanged.connect(self._update_char_count)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        send_btn = QPushButton("Send Message")
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
        self.attach_btn = attach_btn

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
        layout.addWidget(recipient_label)
        layout.addWidget(self.user_combo)
        layout.addSpacing(4)
        
        # Tone detection display for incoming message
        self.tone_detection_display = None
        if self.orchestrator and self.original_message:
            self.tone_detection_display = ToneDetectionDisplay(self.original_message)
            self._perform_tone_detection()
        
        # Tone selector for outgoing message
        self.tone_selector = None
        if self.orchestrator:
            self.tone_selector = ToneSelector(self.orchestrator, self.original_message)
            self.tone_selector.tone_changed.connect(self._on_tone_changed)
        
        if self.tone_detection_display:
            layout.addSpacing(8)
            layout.addWidget(self.tone_detection_display)

        info_label = QLabel("Analyze message mood, then select tone for your reply:")
        info_label.setStyleSheet("font-size: 12px; color: #024950; margin-bottom: 8px;")
        layout.addWidget(info_label)
        
        if self.tone_selector:
            layout.addSpacing(8)
            layout.addWidget(self.tone_selector)
        
        layout.addSpacing(4)
        layout.addWidget(message_label)
        layout.addWidget(self.message_text, 1)
        layout.addWidget(self.char_count_label)
        layout.addWidget(self.attachments_label)
        layout.addSpacing(8)
        layout.addLayout(btn_layout)
        
        self._update_send_button_state()
    
    # -------------------------
    # UPDATE CHARACTER COUNT
    # Refreshes live message length indicator and send button state.
    # -------------------------
    def _update_char_count(self):
        count = len(self.message_text.toPlainText())
        self.char_count_label.setText(f"{count} characters")
        self._update_send_button_state()
    
    # -------------------------
    # UPDATE SEND BUTTON STATE
    # Enables send if message text exists or at least one attachment is selected.
    # -------------------------
    def _update_send_button_state(self):
        text = self.message_text.toPlainText().strip()
        has_attachments = bool(self.attachments)
        self.send_btn.setEnabled(len(text) > 0 or has_attachments)
    
    # -------------------------
    # HANDLE SEND ACTION
    # Accepts dialog only when content or attachments are present.
    # -------------------------
    def _handle_send(self):
        if self.get_message_text() or self.attachments:
            self.accept()

    # -------------------------
    # SELECT ATTACHMENTS
    # Opens file picker, appends selected files, and updates attachment status UI.
    # -------------------------
    def _select_attachments(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Attachments")
        if files:
            self.attachments.extend(files)
            names = [f.split("/")[-1] for f in self.attachments]
            self.attachments_label.setText("Attachments: " + ", ".join(names))
            self.attachments_label.setStyleSheet("font-size: 12px; color: #024950;")
            self._update_send_button_state()
    
    # -------------------------
    # GET SELECTED USER
    # Returns Slack user object currently selected in recipient combo.
    # -------------------------
    def get_selected_user(self) -> dict:
        return self.user_combo.currentData()
    
    # -------------------------
    # GET MESSAGE TEXT
    # Returns trimmed outgoing message body from editor.
    # -------------------------
    def get_message_text(self) -> str:
        return self.message_text.toPlainText().strip()

    # -------------------------
    # SET MESSAGE TEXT
    # Prefills editor body and refreshes counters/state.
    # -------------------------
    def set_message_text(self, text: str):
        self.message_text.setPlainText(text or "")
        self._update_char_count()

    # -------------------------
    # GET ATTACHMENTS
    # Returns a copy of selected attachment paths.
    # -------------------------
    def get_attachments(self):
        return list(self.attachments)

    # -------------------------
    # SET ATTACHMENTS
    # Preloads and de-duplicates attachment list (used by automation flows).
    # -------------------------
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
    # GET SELECTED TONE
    # Returns manually selected tone (if tone selector is enabled).
    # -------------------------
    def get_selected_tone(self):
        return self.selected_tone if self.tone_selector else None
    
    # -------------------------
    # TONE METHODS
    # -------------------------
    # -------------------------
    # PERFORM TONE DETECTION
    # Runs incoming-message tone analysis and updates tone display widget.
    # -------------------------
    def _perform_tone_detection(self):
        """Perform tone analysis on the original message."""
        if not self.orchestrator or not self.original_message:
            return
        try:
            content = self.original_message.get('full_content', '') or self.original_message.get('content', '') or self.original_message.get('text', '') or self.original_message.get('preview', '')
            if content:
                tone_engine = getattr(self.orchestrator, 'tone_engine', None) or getattr(self.orchestrator, 'tone_manager', None)
                if tone_engine:
                    tone_result = tone_engine.analyze_incoming_tone(content)
                    self.original_message['tone_detection'] = tone_result
                    if self.tone_detection_display:
                        self.tone_detection_display.set_tone_data(tone_result)
        except Exception as e:
            print(f"Tone analysis error: {e}")
    
    # -------------------------
    # HANDLE TONE CHANGE
    # Persists user tone selection back into tone preference learning layer.
    # -------------------------
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

    # -------------------------
    # APPLY THEME STYLES
    # Provides a light consistent baseline palette for dialog controls.
    # -------------------------
    def _apply_theme_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { color: #1f2937; background-color: transparent; }
            QTextEdit { background-color: #ffffff; color: #1f2937; }
            QComboBox { background-color: #ffffff; color: #1f2937; }
        """)
