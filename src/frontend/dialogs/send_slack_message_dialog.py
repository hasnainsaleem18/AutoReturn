from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt

# Local imports for tone features
from src.frontend.widgets.tone_selector import ToneSelector
from src.frontend.widgets.sentiment_display import SentimentDisplay
from src.backend.core.tone_manager import ToneManager


class SendSlackMessageDialog(QDialog):
    
    def __init__(self, users: list, parent=None, orchestrator=None, original_message=None):
        super().__init__(parent)
        
        self.users = users
        self.selected_user = None
        self.orchestrator = orchestrator
        self.original_message = original_message or {}
        self.selected_tone = None
        
        self.setWindowTitle("Send Slack Direct Message")
        self.setMinimumSize(500, 400)
        
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Send Direct Message")
        title.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #003135;"
        )
        
        # Recipient selector
        recipient_label = QLabel("To:")
        recipient_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #024950;"
        )
        
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
            QComboBox:focus {
                border: 2px solid #0FA4AF;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #AFDDE5;
                background-color: white;
                selection-background-color: #AFDDE5;
                padding: 4px;
            }
        """)
        
        # Populate users (sorted by real name)
        sorted_users = sorted(self.users, key=lambda u: u.get('real_name', u.get('name', '')))
        
        for user in sorted_users:
            real_name = user.get('real_name', user.get('name', 'Unknown'))
            username = user.get('name', '')
            display_name = f"{real_name} (@{username})"
            
            self.user_combo.addItem(display_name, user)
        
        # Message text area
        message_label = QLabel("Message:")
        message_label.setStyleSheet(
            "font-size: 13px; font-weight: 500; color: #024950;"
        )
        
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
            QTextEdit:focus {
                border: 2px solid #0FA4AF;
            }
        """)
        
        # Character count (optional)
        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setStyleSheet(
            "font-size: 11px; color: #666; font-style: italic;"
        )
        self.char_count_label.setAlignment(Qt.AlignRight)
        self.message_text.textChanged.connect(self._update_char_count)
        
        # Buttons
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
        
        # Add to layout
        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(recipient_label)
        layout.addWidget(self.user_combo)
        layout.addSpacing(4)
        
        # NEW: Add sentiment display for original message
        self.sentiment_display = None
        if self.orchestrator and self.original_message:
            self.sentiment_display = SentimentDisplay(self.original_message)
            # Perform sentiment analysis
            self._perform_sentiment_analysis()
        
        # NEW: Add tone selector
        self.tone_selector = None
        if self.orchestrator:
            self.tone_selector = ToneSelector(self.orchestrator, self.original_message)
            self.tone_selector.tone_changed.connect(self._on_tone_changed)
        
        # Add sentiment display if available
        if self.sentiment_display:
            layout.addSpacing(8)
            layout.addWidget(self.sentiment_display)
        
        # Add helpful explanation
        info_label = QLabel("📊 Analyze message mood, then select tone for your reply:")
        info_label.setStyleSheet("font-size: 12px; color: #024950; margin-bottom: 8px;")
        layout.addWidget(info_label)
        
        # Add tone selector if available
        if self.tone_selector:
            layout.addSpacing(8)
            layout.addWidget(self.tone_selector)
        
        layout.addSpacing(4)
        layout.addWidget(message_label)
        layout.addWidget(self.message_text, 1)
        layout.addWidget(self.char_count_label)
        layout.addSpacing(8)
        layout.addLayout(btn_layout)
        
        # Initial state
        self._update_send_button_state()
    
    def _update_char_count(self):
        text = self.message_text.toPlainText()
        count = len(text)
        self.char_count_label.setText(f"{count} characters")
        self._update_send_button_state()
    
    def _update_send_button_state(self):
        text = self.message_text.toPlainText().strip()
        self.send_btn.setEnabled(len(text) > 0)
    
    def _handle_send(self):
        message = self.get_message_text()
        if message:
            self.accept()
    
    def get_selected_user(self) -> dict:
        return self.user_combo.currentData()
    
    def get_message_text(self) -> str:
        return self.message_text.toPlainText().strip()
    
    def get_selected_tone(self):
        """Get the selected tone for the message.
        
        Returns:
            ToneType or None: The selected tone
        """
        return self.selected_tone if self.tone_selector else None
    
    # -------------------------
    # TONE AND SENTIMENT METHODS
    # -------------------------
    def _perform_sentiment_analysis(self):
        """Perform sentiment analysis on the original message"""
        if not self.orchestrator or not self.original_message:
            return
        
        try:
            content = self.original_message.get('full_content', '') or self.original_message.get('content', '')
            if content:
                # Use ToneManager directly instead of orchestrator
                from src.backend.services.ai_service import OllamaService
                from src.backend.core.tone_manager import ToneManager
                
                ai_service = OllamaService()
                tone_manager = ToneManager(ai_service)
                sentiment_result = tone_manager.analyze_message_sentiment(content)
                
                # Add sentiment data to message
                self.original_message['sentiment_analysis'] = sentiment_result
                
                # Update sentiment display
                if self.sentiment_display:
                    self.sentiment_display.set_sentiment_data(sentiment_result)
                
        except Exception as e:
            print(f"Sentiment analysis error: {e}")
    
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
                selected_user = self.get_selected_user()
                message_context = {
                    'sender': selected_user.get('name', 'Unknown') if selected_user else 'Unknown',
                    'subject': 'Slack Direct Message',
                    'source': 'slack',
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