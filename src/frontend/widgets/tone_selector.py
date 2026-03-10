# -------------------------
# TONE SELECTOR WIDGET
# -------------------------
"""
Reusable tone selector widget for AutoReturn application.

Provides dropdown with 2 tone types (Formal/Informal), auto-suggest functionality, and manual override.
"""

# -------------------------
# IMPORTS
# -------------------------
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QComboBox, QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Signal, Qt, QTimer
from PySide6.QtGui import QPalette

from src.backend.models.tone_models import ToneType, get_tone_display_name


# -------------------------
# TONE SELECTOR CLASS
# -------------------------
class ToneSelector(QWidget):
    """
    Tone selector widget with dropdown and auto-suggest functionality.
    
    Provides user interface for tone selection with:
    - Dropdown menu with 2 tone types
    - Auto-suggest button for AI-powered recommendations
    - Real-time tone change notifications
    - Professional styling with AutoReturn theme colors
    
    Signals:
        tone_changed: Emitted when user selects a different tone
        auto_suggest_requested: Emitted when user requests AI suggestion
    """
    
    # Signals
    tone_changed = Signal(ToneType)
    auto_suggest_requested = Signal()
    
    # -------------------------
    # INIT
    # Stores orchestration context and builds tone selection controls.
    # -------------------------
    def __init__(self, orchestrator, message_data=None, parent=None):
        super().__init__(parent)
        self.orchestrator = orchestrator
        self.message_data = message_data or {}
        self.current_tone = ToneType.FORMAL
        self.auto_suggest_in_progress = False
        
        self.setup_ui()
        self.populate_tones()
        self.connect_signals()
        
    # -------------------------
    # SETUP UI
    # Builds label, tone dropdown, suggest button, and confidence indicator.
    # -------------------------
    def setup_ui(self):
        """Setup the user interface"""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Tone selection widget for outgoing message styling
        self.tone_label = QLabel("Reply Tone:")
        layout.addWidget(self.tone_label)
        
        # Tone dropdown
        self.tone_combo = QComboBox()
        self.tone_combo.setMinimumWidth(150)
        self.tone_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.tone_combo)
        
        # Auto-suggest button
        self.auto_btn = QPushButton("💡 Suggest Tone")
        self.auto_btn.setMinimumWidth(60)
        self.auto_btn.setToolTip("Get AI-powered tone suggestion")
        layout.addWidget(self.auto_btn)
        
        # Confidence label (initially hidden)
        self.confidence_label = QLabel("")
        self.confidence_label.setStyleSheet("font-style: italic;")
        self.confidence_label.setVisible(False)
        layout.addWidget(self.confidence_label)
        
        # Add stretch to push everything to the left
        layout.addStretch()
        
        self._apply_theme_styles()
    
    # -------------------------
    # POPULATE TONES
    # Loads supported ToneType values and sets current default tone.
    # -------------------------
    def populate_tones(self):
        """Populate tone dropdown with all available tones"""
        self.tone_combo.clear()
        
        # Add all supported tone types
        for tone in ToneType:
            display_name = get_tone_display_name(tone)
            self.tone_combo.addItem(display_name, tone)
        
        # Set default selection
        default_tone = ToneType.FORMAL
        if hasattr(self, 'orchestrator') and self.orchestrator:
            default_tone = self.orchestrator.tone_engine.user_profile.default_tone
        self.set_tone(default_tone)
    
    # -------------------------
    # CONNECT SIGNALS
    # Wires dropdown and suggest button interactions to handlers.
    # -------------------------
    def connect_signals(self):
        """Connect widget signals"""
        self.tone_combo.currentIndexChanged.connect(self.on_tone_changed)
        self.auto_btn.clicked.connect(self.on_auto_suggest)
    
    # -------------------------
    # HANDLE TONE CHANGE
    # Updates current selection, emits signal, and records preference learning.
    # -------------------------
    def on_tone_changed(self, index: int):
        """Handle tone selection change"""
        if index >= 0:
            tone_val = self.tone_combo.itemData(index)
            if tone_val:
                try:
                    tone = ToneType(tone_val)
                    if tone != self.current_tone:
                        self.current_tone = tone
                        self.tone_changed.emit(tone)
                except ValueError:
                    pass
                
                # Learn from user selection
                if self.orchestrator and self.message_data:
                    self.orchestrator.tone_engine.update_user_preferences(tone, self.message_data)
    
    # -------------------------
    # HANDLE AUTO-SUGGEST CLICK
    # Starts guarded async suggestion flow and updates button state.
    # -------------------------
    def on_auto_suggest(self):
        """Handle auto-suggest button click"""
        if not self.auto_suggest_in_progress and self.orchestrator and self.message_data:
            self.auto_suggest_in_progress = True
            self.auto_btn.setText("Loading...")
            self.auto_btn.setEnabled(False)
            
            # Start async tone suggestion
            QTimer.singleShot(100, lambda: self.perform_auto_suggest())
    
    # -------------------------
    # PERFORM AUTO-SUGGEST
    # Runs deterministic tone analysis and applies suggestion if confidence is sufficient.
    # -------------------------
    def perform_auto_suggest(self):
        """Perform auto-suggest using orchestrator"""
        try:
            # Get deterministic tone analysis
            content = self.message_data.get('full_content', '') or self.message_data.get('content', '')
            if content:
                tone_result = self.orchestrator.tone_engine.analyze_incoming_tone(content)
                suggested_tone = ToneType(tone_result.get('detected_tone', ToneType.FORMAL.value))
                confidence = tone_result.get('confidence', 0.5)
                
                # Set suggested tone if confident enough
                if confidence > 0.4:
                    self.set_tone(suggested_tone)
                    self.confidence_label.setText(f"Confidence: {confidence:.1f}")
                    self.confidence_label.setVisible(True)
                else:
                    self.confidence_label.setText("Low confidence")
                    self.confidence_label.setVisible(True)
            else:
                self.confidence_label.setText("No content")
                self.confidence_label.setVisible(True)
                
        except Exception as e:
            print(f"Auto-suggest error: {e}")
            self.confidence_label.setText("Error")
            self.confidence_label.setVisible(True)
        
        finally:
            # Reset button state
            self.auto_suggest_in_progress = False
            self.auto_btn.setText("Auto")
            self.auto_btn.setEnabled(True)
    
    # -------------------------
    # SET TONE
    # Programmatically selects a tone in dropdown and syncs internal state.
    # -------------------------
    def set_tone(self, tone: ToneType):
        """Set selected tone"""
        index = self.tone_combo.findData(tone)
        if index >= 0:
            self.tone_combo.setCurrentIndex(index)
            self.current_tone = tone
    
    # -------------------------
    # GET TONE
    # Returns currently selected tone value.
    # -------------------------
    def get_tone(self) -> ToneType:
        """Get current selected tone"""
        return self.current_tone
    
    # -------------------------
    # SET MESSAGE DATA
    # Updates source message context used by auto-suggest pipeline.
    # -------------------------
    def set_message_data(self, message_data: dict):
        """Update message data for auto-suggest"""
        self.message_data = message_data
        # Reset confidence display when message changes
        self.confidence_label.setVisible(False)
    
    # -------------------------
    # RESET WIDGET
    # Restores default tone and clears transient suggest state.
    # -------------------------
    def reset(self):
        """Reset widget to default state"""
        default_tone = ToneType.FORMAL
        if hasattr(self, 'orchestrator') and self.orchestrator:
            default_tone = self.orchestrator.tone_engine.user_profile.default_tone
        self.set_tone(default_tone)
        self.confidence_label.setVisible(False)
        self.auto_suggest_in_progress = False
        self.auto_btn.setText("Auto")
        self.auto_btn.setEnabled(True)

    # -------------------------
    # APPLY THEME STYLES
    # Applies high-contrast neutral control styling for readability.
    # -------------------------
    def _apply_theme_styles(self):
        """Use high-contrast styling with white text surfaces for dark-mode visibility."""
        palette = self.palette()
        button = palette.color(QPalette.Button).name()
        button_text = palette.color(QPalette.ButtonText).name()

        self.setStyleSheet(f"""
            QWidget {{
                background-color: transparent;
            }}
            QLabel {{
                color: #1f2937;
                font-weight: 500;
            }}
            QComboBox {{
                padding: 4px 8px;
                border: 1px solid #9ca3af;
                border-radius: 4px;
                background-color: #ffffff;
                min-height: 20px;
                color: #1f2937;
            }}
            QComboBox QAbstractItemView {{
                background-color: #ffffff;
                color: #1f2937;
                selection-background-color: #dbeafe;
                selection-color: #1f2937;
                border: 1px solid #9ca3af;
            }}
            QPushButton {{
                padding: 4px 8px;
                border: 1px solid #6b7280;
                border-radius: 4px;
                background-color: {button};
                color: {button_text};
                font-weight: 500;
            }}
        """)
