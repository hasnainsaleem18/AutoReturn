# -------------------------
# TONE COMPOSE ENHANCER
# -------------------------
"""
Enhances existing compose dialogs with tone functionality.
Integrates seamlessly without modifying existing code.
"""

# -------------------------
# IMPORTS
# -------------------------
import asyncio
from typing import Dict, Any, Optional
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel
from PySide6.QtCore import QTimer, Signal, QObject

from src.backend.models.tone_models import ToneType, ToneAnalysis
from src.backend.core.tone_manager import ToneManager
from src.frontend.ui.tone_selector import ToneSelector


# -------------------------
# TONE COMPOSE ENHANCER CLASS
# -------------------------
class ToneComposeEnhancer(QObject):
    """Enhances existing compose dialogs with tone functionality"""
    
    # Signals
    draft_updated = Signal(str)  # Emitted when tone-adjusted draft is ready
    
    def __init__(self, compose_dialog, tone_manager: ToneManager):
        super().__init__()
        self.compose_dialog = compose_dialog
        self.tone_manager = tone_manager
        self.tone_selector = None
        self.message_context = {}
        self.original_draft = ""
        self.current_tone = None
        self.analysis_timer = QTimer()
        self.analysis_timer.timeout.connect(self._delayed_tone_analysis)
        self.analysis_timer.setSingleShot(True)
        
        # Track original methods to extend them
        self._setup_compose_enhancement()
    
    def _setup_compose_enhancement(self):
        """Setup tone enhancement without modifying existing dialog"""
        # This will be called when the enhancer is properly integrated
        pass
    
    def add_tone_controls(self, layout: QVBoxLayout, message_context: Dict[str, Any]):
        """Add tone controls to existing compose dialog layout"""
        self.message_context = message_context
        
        # Create tone selector container
        tone_container = QWidget()
        tone_container.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                margin: 2px;
            }
        """)
        
        tone_layout = QVBoxLayout(tone_container)
        tone_layout.setContentsMargins(10, 8, 10, 8)
        
        # Add header
        header_label = QLabel("🎨 Tone Adjustment")
        header_label.setFont(QFont("Arial", 10, QFont.Bold))
        header_label.setStyleSheet("color: #495057; margin-bottom: 4px;")
        tone_layout.addWidget(header_label)
        
        # Add tone selector
        self.tone_selector = ToneSelector()
        self.tone_selector.tone_changed.connect(self._on_tone_changed)
        self.tone_selector.auto_tone_toggled.connect(self._on_auto_tone_toggled)
        tone_layout.addWidget(self.tone_selector)
        
        # Insert into existing layout (before buttons)
        # Find the button layout and insert before it
        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                # Look for button layout or buttons
                if any(hasattr(widget, attr) for attr in ['accept', 'reject', 'buttons']):
                    layout.insertWidget(i, tone_container)
                    break
        else:
            # Fallback: add at the end
            layout.addWidget(tone_container)
        
        # Start tone analysis
        self._start_tone_analysis()
    
    def _start_tone_analysis(self):
        """Start async tone analysis"""
        if self.message_context and self.tone_selector.is_auto_mode():
            self.tone_selector.set_loading(True)
            # Delay analysis to avoid blocking UI
            self.analysis_timer.start(500)
    
    def _delayed_tone_analysis(self):
        """Perform delayed tone analysis"""
        asyncio.create_task(self._analyze_message_tone())
    
    async def _analyze_message_tone(self):
        """Analyze message and recommend tone"""
        try:
            if not self.message_context:
                return
            
            # Get tone analysis
            analysis = await self.tone_manager.analyze_message_context(self.message_context)
            
            # Update UI with recommendation
            if self.tone_selector and analysis.recommended_tone.confidence > 0.5:
                self.tone_selector.set_recommended_tone(analysis.recommended_tone)
            
            self.tone_selector.set_loading(False)
            
        except Exception as e:
            print(f"Error in tone analysis: {e}")
            if self.tone_selector:
                self.tone_selector.set_loading(False)
    
    def _on_tone_changed(self, tone: ToneType):
        """Handle tone selection change"""
        self.current_tone = tone
        
        # Update draft with new tone
        if self.original_draft:
            asyncio.create_task(self._update_draft_with_tone(tone))
        
        # Learn from user selection
        if self.message_context:
            self.tone_manager.update_user_preferences(tone, self.message_context)
    
    def _on_auto_tone_toggled(self, enabled: bool):
        """Handle auto-tone toggle"""
        if enabled:
            self._start_tone_analysis()
        else:
            self.tone_selector.clear_recommendation()
    
    async def _update_draft_with_tone(self, target_tone: ToneType):
        """Update draft text with selected tone"""
        try:
            if not self.original_draft:
                return
            
            # Get tone-adjusted version
            response = await self.tone_manager.adjust_message_tone(
                original_text=self.original_draft,
                target_tone=target_tone,
                message_context=self.message_context
            )
            
            # Emit updated draft
            if response.adjusted_text != self.original_draft:
                self.draft_updated.emit(response.adjusted_text)
            
        except Exception as e:
            print(f"Error updating draft with tone: {e}")
    
    def set_original_draft(self, draft_text: str):
        """Set the original draft text"""
        self.original_draft = draft_text
        
        # If auto-tone is enabled, apply tone adjustment
        if self.tone_selector and self.tone_selector.is_auto_mode():
            asyncio.create_task(self._update_draft_with_tone(self.tone_selector.get_selected_tone()))
    
    def get_current_tone(self) -> Optional[ToneType]:
        """Get currently selected tone"""
        return self.current_tone
    
    def update_message_context(self, message_context: Dict[str, Any]):
        """Update message context and re-analyze"""
        self.message_context = message_context
        if self.tone_selector and self.tone_selector.is_auto_mode():
            self._start_tone_analysis()
    
    def reset(self):
        """Reset the enhancer state"""
        self.original_draft = ""
        self.current_tone = None
        self.message_context = {}
        if self.tone_selector:
            self.tone_selector.clear_recommendation()


# -------------------------
# INTEGRATION HELPER FUNCTIONS
# -------------------------

def enhance_gmail_reply_dialog(reply_dialog, tone_manager: ToneManager):
    """Helper function to enhance Gmail reply dialog with tone functionality"""
    
    # Create enhancer
    enhancer = ToneComposeEnhancer(reply_dialog, tone_manager)
    
    # Get original message context from dialog
    if hasattr(reply_dialog, 'original_message'):
        message_context = {
            'id': reply_dialog.original_message.get('id', ''),
            'sender': reply_dialog.original_message.get('sender', ''),
            'subject': reply_dialog.original_message.get('subject', ''),
            'content': reply_dialog.original_message.get('full_content', ''),
            'priority': reply_dialog.original_message.get('priority', 'normal'),
            'source': 'gmail'
        }
        
        # Add tone controls to existing layout
        if hasattr(reply_dialog, 'main_layout'):
            enhancer.add_tone_controls(reply_dialog.main_layout, message_context)
        
        # Connect to draft generation
        if hasattr(reply_dialog, 'draft_text'):
            # Monitor draft text changes
            reply_dialog.draft_text.textChanged.connect(
                lambda: enhancer.set_original_draft(reply_dialog.draft_text.toPlainText())
            )
            
            # Connect tone updates back to draft
            enhancer.draft_updated.connect(
                lambda text: reply_dialog.draft_text.setPlainText(text)
            )
    
    return enhancer


def enhance_slack_message_dialog(message_dialog, tone_manager: ToneManager):
    """Helper function to enhance Slack message dialog with tone functionality"""
    
    # Create enhancer
    enhancer = ToneComposeEnhancer(message_dialog, tone_manager)
    
    # Get message context from dialog
    if hasattr(message_dialog, 'recipient_info'):
        message_context = {
            'id': message_dialog.recipient_info.get('id', ''),
            'sender': message_dialog.recipient_info.get('name', ''),
            'subject': 'Direct Message',
            'content': '',
            'priority': 'normal',
            'source': 'slack'
        }
        
        # Add tone controls to existing layout
        if hasattr(message_dialog, 'main_layout'):
            enhancer.add_tone_controls(message_dialog.main_layout, message_context)
        
        # Connect to message text
        if hasattr(message_dialog, 'message_text'):
            message_dialog.message_text.textChanged.connect(
                lambda: enhancer.set_original_draft(message_dialog.message_text.toPlainText())
            )
            
            # Connect tone updates back to message
            enhancer.draft_updated.connect(
                lambda text: message_dialog.message_text.setPlainText(text)
            )
    
    return enhancer
