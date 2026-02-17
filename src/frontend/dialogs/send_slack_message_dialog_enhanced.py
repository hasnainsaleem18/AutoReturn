# -------------------------
# ENHANCED SLACK MESSAGE DIALOG
# -------------------------
"""
Enhanced Slack message dialog with tone adjustment functionality.
Extends existing dialog without modifying original code.
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
from typing import Optional, Dict, Any

# Third-party imports
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QMessageBox
)
from PySide6.QtCore import Qt, Signal

# Local imports
from src.frontend.dialogs.send_slack_message_dialog import SendSlackMessageDialog
from src.frontend.ui.tone_compose_enhancer import enhance_slack_message_dialog
from src.backend.models.tone_models import ToneType


# -------------------------
# ENHANCED SLACK MESSAGE DIALOG CLASS
# -------------------------
class SendSlackMessageDialogEnhanced(SendSlackMessageDialog):
    """Enhanced Slack message dialog with tone adjustment functionality."""
    
    # Signal for tone changes
    tone_changed = Signal(ToneType)
    
    def __init__(self, recipient_info: Dict[str, Any], tone_manager, parent=None):
        """Initialize enhanced Slack message dialog.
        
        Args:
            recipient_info: Recipient information for context
            tone_manager: Tone manager instance
            parent: Parent widget (optional)
        """
        # Initialize parent dialog with original parameters
        user_id = recipient_info.get('id', '')
        user_name = recipient_info.get('name', recipient_info.get('real_name', 'Unknown'))
        
        # Call parent constructor - this will need to match the original constructor
        super().__init__(user_id=user_id, parent=parent)
        
        # Store enhanced properties
        self.recipient_info = recipient_info
        self.tone_manager = tone_manager
        self.tone_enhancer = None
        self.current_tone = None
        
        # Enhance the dialog after UI is built
        self._enhance_with_tone_functionality()
    
    def _enhance_with_tone_functionality(self):
        """Add tone functionality to existing dialog"""
        try:
            # Create message context for tone analysis
            message_context = {
                'id': self.recipient_info.get('id', ''),
                'sender': self.recipient_info.get('name', ''),
                'subject': 'Direct Message',
                'content': '',
                'priority': 'normal',
                'source': 'slack'
            }
            
            # Add tone controls using enhancer
            self.tone_enhancer = enhance_slack_message_dialog(self, self.tone_manager)
            
            # Connect signals
            if self.tone_enhancer:
                self.tone_enhancer.draft_updated.connect(self._on_tone_adjusted_draft)
                self.tone_enhancer.tone_selector.tone_changed.connect(self._on_tone_changed)
            
        except Exception as e:
            print(f"Error enhancing Slack dialog with tone: {e}")
            # Continue without tone functionality if enhancement fails
            QMessageBox.warning(
                self, 
                "Tone Feature Unavailable",
                "Tone adjustment could not be enabled. Standard messaging will be used."
            )
    
    def _on_tone_changed(self, tone: ToneType):
        """Handle tone selection change"""
        self.current_tone = tone
        self.tone_changed.emit(tone)
        
        # Update message with new tone
        if self.tone_enhancer:
            current_message = self.message_text.toPlainText()
            if current_message:
                self.tone_enhancer.set_original_draft(current_message)
    
    def _on_tone_adjusted_draft(self, adjusted_text: str):
        """Handle tone-adjusted message from enhancer"""
        if adjusted_text and adjusted_text != self.message_text.toPlainText():
            # Preserve cursor position if possible
            cursor = self.message_text.textCursor()
            position = cursor.position()
            
            # Update text
            self.message_text.setPlainText(adjusted_text)
            
            # Try to restore cursor position
            try:
                cursor.setPosition(min(position, len(adjusted_text)))
                self.message_text.setTextCursor(cursor)
            except:
                pass  # Cursor restoration is optional
    
    def get_message_with_tone(self) -> Dict[str, Any]:
        """Get message data including tone information"""
        return {
            'text': self.get_message_text(),
            'tone': self.current_tone,
            'recipient': self.recipient_info,
            'user_id': self.recipient_info.get('id', ''),
            'original_message': self.recipient_info
        }
    
    def get_current_tone(self) -> Optional[ToneType]:
        """Get currently selected tone"""
        return self.current_tone
    
    def set_tone(self, tone: ToneType):
        """Manually set tone"""
        if self.tone_enhancer and self.tone_enhancer.tone_selector:
            self.tone_enhancer.tone_selector.set_tone(tone)
    
    def enable_auto_tone(self, enabled: bool):
        """Enable/disable auto-tone recommendations"""
        if self.tone_enhancer and self.tone_enhancer.tone_selector:
            self.tone_enhancer.tone_selector.set_auto_mode(enabled)


# -------------------------
# FACTORY FUNCTION
# -------------------------
def create_enhanced_slack_message_dialog(recipient_info: Dict[str, Any], 
                                     tone_manager, 
                                     parent=None) -> SendSlackMessageDialogEnhanced:
    """Factory function to create enhanced Slack message dialog.
    
    Args:
        recipient_info: Recipient information
        tone_manager: Tone manager instance
        parent: Parent widget (optional)
    
    Returns:
        Enhanced Slack message dialog with tone functionality
    """
    return SendSlackMessageDialogEnhanced(recipient_info, tone_manager, parent)


# -------------------------
# USAGE EXAMPLE
# -------------------------
"""
Example usage in main application:

# Instead of:
# dialog = SendSlackMessageDialog(user_id, user_name)

# Use:
# dialog = create_enhanced_slack_message_dialog(
#     recipient_info=user_info,
#     tone_manager=orchestrator.get_tone_manager(),
#     parent=self
# )

# Connect to tone changes if needed
# dialog.tone_changed.connect(lambda tone: print(f"Tone changed to: {tone}"))

# Get enhanced message data
# if dialog.exec() == QDialog.Accepted:
#     message_data = dialog.get_message_with_tone()
#     print(f"Message: {message_data['text']}")
#     print(f"Tone: {message_data['tone']}")
"""
