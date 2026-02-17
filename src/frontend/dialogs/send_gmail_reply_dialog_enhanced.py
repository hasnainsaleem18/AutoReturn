# -------------------------
# ENHANCED GMAIL REPLY DIALOG
# -------------------------
"""
Enhanced Gmail reply dialog with tone adjustment functionality.
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
from src.frontend.dialogs.send_gmail_reply_dialog import SendGmailReplyDialog
from src.frontend.ui.tone_compose_enhancer import enhance_gmail_reply_dialog
from src.backend.models.tone_models import ToneType


# -------------------------
# ENHANCED GMAIL REPLY DIALOG CLASS
# -------------------------
class SendGmailReplyDialogEnhanced(SendGmailReplyDialog):
    """Enhanced Gmail reply dialog with tone adjustment functionality."""
    
    # Signal for tone changes
    tone_changed = Signal(ToneType)
    
    def __init__(self, original_message: Dict[str, Any], tone_manager, parent=None):
        """Initialize enhanced Gmail reply dialog.
        
        Args:
            original_message: Original message data for context
            tone_manager: Tone manager instance
            parent: Parent widget (optional)
        """
        # Initialize parent dialog with original parameters
        to_email = original_message.get('sender_email', original_message.get('sender', ''))
        subject = original_message.get('subject', '')
        
        super().__init__(to_email=to_email, subject=subject, parent=parent)
        
        # Store enhanced properties
        self.original_message = original_message
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
                'id': self.original_message.get('id', ''),
                'sender': self.original_message.get('sender', ''),
                'subject': self.original_message.get('subject', ''),
                'content': self.original_message.get('full_content', ''),
                'priority': self.original_message.get('priority', 'normal'),
                'source': 'gmail'
            }
            
            # Add tone controls using enhancer
            self.tone_enhancer = enhance_gmail_reply_dialog(self, self.tone_manager)
            
            # Connect signals
            if self.tone_enhancer:
                self.tone_enhancer.draft_updated.connect(self._on_tone_adjusted_draft)
                self.tone_enhancer.tone_selector.tone_changed.connect(self._on_tone_changed)
            
            # Generate initial draft if AI is available
            self._generate_ai_draft()
            
        except Exception as e:
            print(f"Error enhancing Gmail dialog with tone: {e}")
            # Continue without tone functionality if enhancement fails
            QMessageBox.warning(
                self, 
                "Tone Feature Unavailable",
                "Tone adjustment could not be enabled. Standard reply will be used."
            )
    
    def _generate_ai_draft(self):
        """Generate AI-powered initial draft"""
        try:
            # Use existing draft manager through tone manager
            content = self.original_message.get('full_content', '')
            if content and len(content) > 50:
                # Generate context-aware draft
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    # Simple draft generation
                    draft_prompt = f"""
                    Generate a professional reply to this email:
                    
                    From: {self.original_message.get('sender', 'Unknown')}
                    Subject: {self.original_message.get('subject', 'No Subject')}
                    Content: {content[:500]}...
                    
                    Requirements:
                    - Be professional and courteous
                    - Address the main points
                    - Keep it concise but complete
                    - Include appropriate greeting and closing
                    
                    Reply:
                    """
                    
                    draft = loop.run_until_complete(
                        self.tone_manager.ai_service.generate_summary_async(draft_prompt)
                    )
                    
                    if draft and len(draft.strip()) > 10:
                        self.message_text.setPlainText(draft.strip())
                        
                except Exception as e:
                    print(f"AI draft generation failed: {e}")
                finally:
                    loop.close()
                    
        except Exception as e:
            print(f"Error in AI draft generation: {e}")
    
    def _on_tone_changed(self, tone: ToneType):
        """Handle tone selection change"""
        self.current_tone = tone
        self.tone_changed.emit(tone)
        
        # Update draft with new tone
        if self.tone_enhancer:
            current_draft = self.message_text.toPlainText()
            if current_draft:
                self.tone_enhancer.set_original_draft(current_draft)
    
    def _on_tone_adjusted_draft(self, adjusted_text: str):
        """Handle tone-adjusted draft from enhancer"""
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
            'to_email': self.to_email,
            'subject': f"Re: {self.subject}",
            'original_message': self.original_message
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
def create_enhanced_gmail_reply_dialog(original_message: Dict[str, Any], 
                                   tone_manager, 
                                   parent=None) -> SendGmailReplyDialogEnhanced:
    """Factory function to create enhanced Gmail reply dialog.
    
    Args:
        original_message: Original message data
        tone_manager: Tone manager instance
        parent: Parent widget (optional)
    
    Returns:
        Enhanced Gmail reply dialog with tone functionality
    """
    return SendGmailReplyDialogEnhanced(original_message, tone_manager, parent)


# -------------------------
# USAGE EXAMPLE
# -------------------------
"""
Example usage in main application:

# Instead of:
# dialog = SendGmailReplyDialog(to_email, subject)

# Use:
# dialog = create_enhanced_gmail_reply_dialog(
#     original_message=message_data,
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
