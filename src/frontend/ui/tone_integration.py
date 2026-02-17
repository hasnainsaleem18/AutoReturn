# -------------------------
# TONE INTEGRATION
# -------------------------
"""
Integration layer for adding tone functionality to main application.
Provides seamless integration without modifying existing UI code.
"""

# -------------------------
# IMPORTS
# -------------------------
from typing import Dict, Any, Optional
from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QFont

from src.backend.models.tone_models import ToneType, ToneProfile
from src.backend.core.tone_manager import ToneManager
from src.frontend.ui.tone_selector import ToneSelector
from src.frontend.dialogs.tone_settings_dialog import ToneSettingsDialog


# -------------------------
# TONE INTEGRATION CLASS
# -------------------------
class ToneIntegration:
    """Integration layer for tone functionality in main application"""
    
    # Signals
    tone_settings_requested = Signal()
    
    def __init__(self, main_app, tone_manager: ToneManager):
        super().__init__()
        self.main_app = main_app
        self.tone_manager = tone_manager
        self.tone_selector = None
        self.settings_dialog = None
        
        # Integration state
        self.is_integration_active = False
        
        print("🎨 Tone Integration initialized")
    
    def integrate_into_main_ui(self, main_layout: QVBoxLayout):
        """Integrate tone controls into main application UI"""
        try:
            if self.is_integration_active:
                return
            
            # Create tone control panel
            tone_panel = self._create_tone_control_panel()
            
            # Insert into main layout (after toolbar, before table)
            # Find the right place to insert
            for i in range(main_layout.count()):
                item = main_layout.itemAt(i)
                if item and item.widget():
                    widget = item.widget()
                    # Look for the main table or similar component
                    if hasattr(widget, 'setRowCount') or 'table' in str(type(widget)).lower():
                        main_layout.insertWidget(i, tone_panel)
                        break
            
            # If no table found, add at the beginning
            if not any(hasattr(main_layout.itemAt(i).widget(), 'setRowCount') 
                   for i in range(main_layout.count()) if main_layout.itemAt(i)):
                main_layout.insertWidget(0, tone_panel)
            
            self.is_integration_active = True
            print("✅ Tone controls integrated into main UI")
            
        except Exception as e:
            print(f"❌ Failed to integrate tone controls: {e}")
    
    def _create_tone_control_panel(self) -> QWidget:
        """Create the main tone control panel"""
        panel = QWidget()
        panel.setMaximumHeight(80)
        panel.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 6px;
                margin: 4px;
            }
        """)
        
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(12, 8, 12, 8)
        
        # Title
        title_label = QLabel("🎨 Quick Tone")
        title_label.setFont(QFont("Arial", 10, QFont.Bold))
        title_label.setStyleSheet("color: #495057; margin-right: 12px;")
        layout.addWidget(title_label)
        
        # Tone selector
        self.tone_selector = ToneSelector()
        self.tone_selector.tone_changed.connect(self._on_global_tone_changed)
        layout.addWidget(self.tone_selector)
        
        # Settings button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setMaximumWidth(80)
        settings_btn.clicked.connect(self._show_tone_settings)
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        layout.addWidget(settings_btn)
        
        layout.addStretch()
        
        return panel
    
    def _on_global_tone_changed(self, tone: ToneType):
        """Handle global tone change"""
        print(f"🎨 Global tone changed to: {tone.value}")
        
        # Update tone manager default
        self.tone_manager.set_default_tone(tone)
        
        # Notify main app if it has tone change handler
        if hasattr(self.main_app, 'on_global_tone_changed'):
            self.main_app.on_global_tone_changed(tone)
    
    def _show_tone_settings(self):
        """Show tone settings dialog"""
        if not self.settings_dialog:
            self.settings_dialog = ToneSettingsDialog(self.tone_manager, self.main_app)
            self.settings_dialog.settings_changed.connect(self._on_tone_settings_changed)
        
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()
    
    def _on_tone_settings_changed(self):
        """Handle tone settings changes"""
        print("🎨 Tone settings updated")
        
        # Refresh tone selector
        if self.tone_selector:
            self.tone_selector.clear_recommendation()
        
        # Notify main app
        if hasattr(self.main_app, 'on_tone_settings_changed'):
            self.main_app.on_tone_settings_changed()
    
    def enhance_reply_dialogs(self):
        """Enhance existing reply dialogs with tone functionality"""
        try:
            # This method can be called to enhance any existing reply dialogs
            # The actual enhancement will be done when dialogs are created
            
            # Hook into dialog creation if possible
            if hasattr(self.main_app, 'create_gmail_reply_dialog'):
                original_method = self.main_app.create_gmail_reply_dialog
                
                def enhanced_create_gmail_reply(message_data):
                    # Create enhanced dialog
                    from src.frontend.dialogs.send_gmail_reply_dialog_enhanced import create_enhanced_gmail_reply_dialog
                    return create_enhanced_gmail_reply_dialog(
                        message_data, 
                        self.tone_manager, 
                        self.main_app
                    )
                
                # Replace method with enhanced version
                self.main_app.create_gmail_reply_dialog = enhanced_create_gmail_reply_dialog
                print("✅ Gmail reply dialog enhanced with tone functionality")
            
            if hasattr(self.main_app, 'create_slack_message_dialog'):
                original_method = self.main_app.create_slack_message_dialog
                
                def enhanced_create_slack_message(recipient_info):
                    # Create enhanced dialog
                    from src.frontend.dialogs.send_slack_message_dialog_enhanced import create_enhanced_slack_message_dialog
                    return create_enhanced_slack_message_dialog(
                        recipient_info, 
                        self.tone_manager, 
                        self.main_app
                    )
                
                # Replace method with enhanced version
                self.main_app.create_slack_message_dialog = enhanced_create_slack_message_dialog
                print("✅ Slack message dialog enhanced with tone functionality")
                
        except Exception as e:
            print(f"❌ Failed to enhance reply dialogs: {e}")
    
    def get_current_tone(self) -> Optional[ToneType]:
        """Get currently selected global tone"""
        if self.tone_selector:
            return self.tone_selector.get_selected_tone()
        return self.tone_manager.user_profile.default_tone
    
    def set_global_tone(self, tone: ToneType):
        """Set global tone"""
        if self.tone_selector:
            self.tone_selector.set_tone(tone)
    
    def enable_auto_tone(self, enabled: bool):
        """Enable/disable auto-tone globally"""
        if self.tone_selector:
            self.tone_selector.set_auto_mode(enabled)
        self.tone_manager.set_auto_tone_enabled(enabled)
    
    def get_tone_statistics(self) -> Dict[str, Any]:
        """Get tone usage statistics"""
        return self.tone_manager.get_tone_statistics()
    
    def cleanup(self):
        """Clean up resources"""
        if self.settings_dialog:
            self.settings_dialog.close()
            self.settings_dialog = None


# -------------------------
# INTEGRATION HELPER FUNCTIONS
# -------------------------

def integrate_tone_system(main_app, orchestrator) -> ToneIntegration:
    """Helper function to integrate tone system into main application.
    
    Args:
        main_app: Main application instance
        orchestrator: Orchestrator instance with tone manager
    
    Returns:
        ToneIntegration instance for further customization
    """
    # Get tone manager from orchestrator
    tone_manager = orchestrator.get_tone_manager()
    
    # Create integration
    integration = ToneIntegration(main_app, tone_manager)
    
    # Integrate into main UI if layout is available
    if hasattr(main_app, 'central_widget') or hasattr(main_app, 'main_layout'):
        main_layout = getattr(main_app, 'main_layout', None) or getattr(main_app, 'central_widget', None)
        if main_layout and hasattr(main_layout, 'addLayout') or hasattr(main_layout, 'layout'):
            integration.integrate_into_main_ui(main_layout)
    
    # Enhance reply dialogs
    integration.enhance_reply_dialogs()
    
    return integration


# -------------------------
# USAGE INSTRUCTIONS
# -------------------------
"""
To integrate tone system into main application:

1. In main application initialization, after creating orchestrator:

```python
# After creating orchestrator
self.orchestrator = Orchestrator()

# Integrate tone system
from src.frontend.ui.tone_integration import integrate_tone_system
self.tone_integration = integrate_tone_system(self, self.orchestrator)

# Optionally connect to tone events
self.tone_integration.tone_settings_requested.connect(self.show_tone_settings)
```

2. The integration will:
   - Add tone control panel to main UI
   - Enhance existing reply dialogs
   - Provide tone settings management
   - Maintain all existing functionality

3. No existing code is modified - only enhanced through extension
"""
