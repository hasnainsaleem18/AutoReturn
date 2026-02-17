# -------------------------
# TONE SELECTOR WIDGET
# -------------------------
"""
Tone selection widget that can be added to any existing dialog.
Provides manual tone selection and AI recommendations.
"""

# -------------------------
# IMPORTS
# -------------------------
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QLabel, 
    QPushButton, QFrame, QToolTip
)
from PySide6.QtCore import Signal, Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QPainter, QPen
from typing import Optional

from src.backend.models.tone_models import ToneType, ToneRecommendation


# -------------------------
# TONE SELECTOR CLASS
# -------------------------
class ToneSelector(QWidget):
    """Widget for tone selection with AI recommendations"""
    
    # Signals
    tone_changed = Signal(ToneType)
    auto_tone_toggled = Signal(bool)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_recommendation = None
        self.setup_ui()
        self.setup_animations()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)
        
        # Header section
        header_layout = QHBoxLayout()
        
        # Title label
        self.title_label = QLabel("Message Tone:")
        self.title_label.setFont(QFont("Arial", 10, QFont.Bold))
        header_layout.addWidget(self.title_label)
        
        # Auto-tone toggle
        self.auto_button = QPushButton("🤖 Auto")
        self.auto_button.setCheckable(True)
        self.auto_button.setChecked(True)
        self.auto_button.setToolTip("Enable AI tone recommendations")
        self.auto_button.clicked.connect(self._on_auto_tone_toggled)
        header_layout.addWidget(self.auto_button)
        
        header_layout.addStretch()
        main_layout.addLayout(header_layout)
        
        # Tone selection row
        tone_layout = QHBoxLayout()
        
        # Tone dropdown
        self.tone_combo = QComboBox()
        self.tone_combo.setMinimumWidth(150)
        self._populate_tone_combo()
        self.tone_combo.currentTextChanged.connect(self._on_tone_changed)
        tone_layout.addWidget(self.tone_combo)
        
        # Confidence indicator
        self.confidence_label = QLabel("")
        self.confidence_label.setFont(QFont("Arial", 8))
        self.confidence_label.setStyleSheet("color: #666; padding: 2px;")
        tone_layout.addWidget(self.confidence_label)
        
        tone_layout.addStretch()
        main_layout.addLayout(tone_layout)
        
        # Reasoning section (initially hidden)
        self.reasoning_frame = QFrame()
        self.reasoning_frame.setFrameStyle(QFrame.Box)
        self.reasoning_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background-color: #f9f9f9;
                margin: 2px;
            }
        """)
        
        reasoning_layout = QVBoxLayout(self.reasoning_frame)
        
        self.reasoning_label = QLabel("")
        self.reasoning_label.setWordWrap(True)
        self.reasoning_label.setFont(QFont("Arial", 8))
        reasoning_layout.addWidget(self.reasoning_label)
        
        self.reasoning_frame.hide()
        main_layout.addWidget(self.reasoning_frame)
        
        # Set initial state
        self._update_auto_mode()
    
    def _populate_tone_combo(self):
        """Populate tone combo box with all available tones"""
        # Add tones with display names
        tone_display_names = {
            ToneType.FORMAL: "Formal",
            ToneType.PROFESSIONAL: "Professional",
            ToneType.CASUAL: "Casual",
            ToneType.FRIENDLY: "Friendly",
            ToneType.ASSERTIVE: "Assertive",
            ToneType.PERSUASIVE: "Persuasive",
            ToneType.APOLOGETIC: "Apologetic",
            ToneType.EMPATHETIC: "Empathetic",
            ToneType.DIPLOMATIC: "Diplomatic",
            ToneType.CONCISE: "Concise",
            ToneType.HUMOROUS: "Humorous",
            ToneType.APPRECIATIVE: "Appreciative",
            ToneType.URGENT: "Urgent"
        }
        
        for tone in ToneType:
            display_name = tone_display_names.get(tone, tone.value.title())
            self.tone_combo.addItem(display_name, tone)
    
    def setup_animations(self):
        """Setup animations for smooth transitions"""
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(300)
        self.fade_animation.setEasingCurve(QEasingCurve.InOutQuad)
    
    def _on_tone_changed(self):
        """Handle tone selection change"""
        tone = self.tone_combo.currentData()
        if tone:
            self.tone_changed.emit(tone)
            self._update_confidence_display()
    
    def _on_auto_tone_toggled(self):
        """Handle auto-tone toggle"""
        is_auto = self.auto_button.isChecked()
        self.auto_tone_toggled.emit(is_auto)
        self._update_auto_mode()
    
    def _update_auto_mode(self):
        """Update UI based on auto mode"""
        is_auto = self.auto_button.isChecked()
        
        if is_auto:
            self.auto_button.setText("🤖 Auto")
            self.auto_button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
            """)
            self.tone_combo.setEnabled(False)
        else:
            self.auto_button.setText("Manual")
            self.auto_button.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    color: #333;
                    border: 1px solid #ccc;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
            """)
            self.tone_combo.setEnabled(True)
    
    def _update_confidence_display(self):
        """Update confidence indicator"""
        if self.current_recommendation:
            confidence = self.current_recommendation.confidence
            self.confidence_label.setText(f"Confidence: {confidence:.0%}")
            
            # Color code confidence
            if confidence >= 0.8:
                color = "#4CAF50"  # Green
            elif confidence >= 0.6:
                color = "#FF9800"  # Orange
            else:
                color = "#F44336"  # Red
            
            self.confidence_label.setStyleSheet(f"color: {color}; padding: 2px;")
        else:
            self.confidence_label.setText("")
    
    def set_recommended_tone(self, recommendation: ToneRecommendation):
        """Set AI-recommended tone with confidence"""
        self.current_recommendation = recommendation
        
        # Update combo box selection
        index = self.tone_combo.findData(recommendation.recommended_tone)
        if index >= 0:
            self.tone_combo.setCurrentIndex(index)
        
        # Update confidence display
        self._update_confidence_display()
        
        # Show reasoning
        if recommendation.reasoning:
            self.reasoning_label.setText(f"🤖 AI Recommendation: {recommendation.reasoning}")
            self.reasoning_frame.show()
        else:
            self.reasoning_frame.hide()
    
    def get_selected_tone(self) -> Optional[ToneType]:
        """Get currently selected tone"""
        return self.tone_combo.currentData()
    
    def set_tone(self, tone: ToneType):
        """Manually set tone"""
        index = self.tone_combo.findData(tone)
        if index >= 0:
            self.tone_combo.setCurrentIndex(index)
    
    def set_auto_mode(self, enabled: bool):
        """Enable/disable auto mode"""
        self.auto_button.setChecked(enabled)
        self._update_auto_mode()
    
    def is_auto_mode(self) -> bool:
        """Check if auto mode is enabled"""
        return self.auto_button.isChecked()
    
    def clear_recommendation(self):
        """Clear current recommendation"""
        self.current_recommendation = None
        self.reasoning_frame.hide()
        self.confidence_label.setText("")
    
    def set_loading(self, loading: bool):
        """Show loading state"""
        if loading:
            self.tone_combo.setEnabled(False)
            self.confidence_label.setText("🔄 Analyzing...")
            self.confidence_label.setStyleSheet("color: #666; padding: 2px;")
        else:
            self.tone_combo.setEnabled(not self.auto_button.isChecked())
            self._update_confidence_display()
