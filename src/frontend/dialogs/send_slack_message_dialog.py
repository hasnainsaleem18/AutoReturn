from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt


class SendSlackMessageDialog(QDialog):
    
    def __init__(self, users: list, parent=None):
        super().__init__(parent)
        
        self.users = users
        self.selected_user = None
        
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