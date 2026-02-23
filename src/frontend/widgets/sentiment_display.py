# -------------------------
# SENTIMENT DISPLAY WIDGET
# -------------------------
"""
Widget for displaying sentiment analysis results with visual indicators.

Shows incoming message analysis results with:
- Sentiment polarity classification (positive/negative/neutral/mixed)
- Confidence score display (0.0-1.0 range)
- Detected tone from linguistic analysis
- Most used tones from user history
- Professional styling with AutoReturn theme colors
"""

# -------------------------
# IMPORTS
# -------------------------
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QFrame, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QPainter, QColor

from src.backend.models.tone_models import ToneType, get_tone_display_name


# -------------------------
# SENTIMENT DISPLAY CLASS
# -------------------------
class SentimentDisplay(QWidget):
    """
    Widget for displaying sentiment analysis results with visual indicators.
    
    Provides clear visual feedback for incoming message analysis:
    - Sentiment polarity with color-coded badges
    - Confidence scoring with percentage display
    - Detected tone from linguistic analysis
    - Most used tones from user learning
    - Professional styling matching AutoReturn theme
    """
    
    def __init__(self, message_data=None, parent=None):
        super().__init__(parent)
        self.message_data = message_data or {}
        self.sentiment_data = None
        
        self.setup_ui()
        self.update_display()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)
        
        # Sentiment display widget for incoming message analysis
        self.sentiment_label = QLabel("Incoming Message Mood:")
        self.sentiment_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(self.sentiment_label)
        
        # Sentiment badge
        self.sentiment_badge = QLabel("Neutral")
        self.sentiment_badge.setFont(QFont("Arial", 8, QFont.Bold))
        self.sentiment_badge.setStyleSheet("""
            QLabel {
                padding: 2px 8px;
                border-radius: 12px;
                background-color: #6c757d;
                color: white;
            }
        """)
        layout.addWidget(self.sentiment_badge)
        
        # Most used tones label
        self.most_used_label = QLabel("")
        self.most_used_label.setFont(QFont("Arial", 8))
        self.most_used_label.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: #024950;
                margin-top: 8px;
            }}
        """)
        layout.addWidget(self.most_used_label)
        
        # Confidence label
        self.confidence_label = QLabel("")
        self.confidence_label.setFont(QFont("Arial", 8))
        self.confidence_label.setStyleSheet("color: #666;")
        layout.addWidget(self.confidence_label)
        
        # Tone label
        self.tone_label = QLabel("")
        self.tone_label.setFont(QFont("Arial", 8))
        self.tone_label.setStyleSheet("color: #333; font-weight: 500;")
        layout.addWidget(self.tone_label)
        
        # Add stretch
        layout.addStretch()
        
        # Set widget style
        self.setStyleSheet("""
            QWidget {
                background-color: #ffffff;
                border: 1px solid #AFDDE5;
                border-radius: 4px;
            }
        """)
    
    def update_display(self):
        """Update display with current sentiment data"""
        if not self.message_data:
            self.hide()
            return
        
        # Get sentiment data from message
        self.sentiment_data = self.message_data.get('sentiment_analysis')
        
        if not self.sentiment_data:
            self.hide()
            return
        
        # Update sentiment badge
        sentiment = self.sentiment_data.get('sentiment', 'neutral')
        confidence = self.sentiment_data.get('confidence', 0.0)
        detected_tone = self.sentiment_data.get('detected_tone', 'professional')
        
        self.update_sentiment_badge(sentiment)
        self.update_confidence_label(confidence)
        self.update_tone_label(detected_tone)
        
        self.show()
    
    def update_sentiment_badge(self, sentiment: str):
        """Update sentiment badge with appropriate color"""
        # Use app theme colors
        sentiment_colors = {
            'positive': '#0FA4AF',      # App primary color (green-like)
            'negative': '#964734',      # App danger color (red-like)
            'neutral': '#AFDDE5',       # App secondary color (gray-like)
            'mixed': '#fd7e14'         # Orange accent
        }
        
        sentiment_labels = {
            'positive': 'Positive',
            'negative': 'Negative',
            'neutral': 'Neutral',
            'mixed': 'Mixed'
        }
        
        color = sentiment_colors.get(sentiment, '#6c757d')
        label = sentiment_labels.get(sentiment, 'Neutral')
        
        self.sentiment_badge.setText(label)
        self.sentiment_badge.setStyleSheet(f"""
            QLabel {{
                padding: 2px 8px;
                border-radius: 12px;
                background-color: {color};
                color: white;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
    
    def update_confidence_label(self, confidence: float):
        """Update confidence label"""
        if confidence > 0:
            self.confidence_label.setText(f"Confidence: {confidence:.1f}")
            self.confidence_label.show()
        else:
            self.confidence_label.hide()
    
    def update_tone_label(self, detected_tone: str):
        """Update tone label"""
        try:
            tone_enum = ToneType(detected_tone)
            display_name = get_tone_display_name(tone_enum)
            self.tone_label.setText(f"Detected: {display_name}")
            self.tone_label.show()
        except ValueError:
            self.tone_label.hide()
    
    def set_message_data(self, message_data: dict):
        """Update message data and refresh display"""
        self.message_data = message_data
        self.update_display()
    
    def set_sentiment_data(self, sentiment_data: Dict[str, Any]):
        """Set sentiment data directly"""
        self.sentiment_data = sentiment_data
        if sentiment_data:
            sentiment = sentiment_data.get('sentiment', 'neutral')
            confidence = sentiment_data.get('confidence', 0.0)
            detected_tone = sentiment_data.get('detected_tone', 'professional')
            
            self.update_sentiment_badge(sentiment)
            self.update_confidence_label(confidence)
            self.update_tone_label(detected_tone)
            self.show()
        else:
            self.hide()
    
    def clear(self):
        """Clear the display"""
        self.sentiment_data = None
        self.hide()


# -------------------------
# UTILITY FUNCTIONS
# -------------------------

def create_sentiment_display_compact(message_data=None, parent=None) -> SentimentDisplay:
    """Create a compact sentiment display widget"""
    display = SentimentDisplay(message_data, parent)
    display.setMaximumHeight(30)  # Compact height
    return display


def create_sentiment_display_detailed(message_data=None, parent=None) -> SentimentDisplay:
    """Create a detailed sentiment display widget"""
    display = SentimentDisplay(message_data, parent)
    display.setMinimumHeight(40)  # Detailed height
    return display
