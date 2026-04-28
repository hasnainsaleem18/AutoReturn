#!/usr/bin/env python3
# -------------------------
# TONE SELECTOR TEST
# -------------------------
"""
Test script for Phase 1 tone selector widget implementation.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt

from src.backend.core.orchestrator import Orchestrator
from src.backend.models.tone_models import ToneType
from src.frontend.widgets.tone_selector import ToneSelector
from src.frontend.widgets.tone_detection_display import ToneDetectionDisplay


class TestWindow(QMainWindow):
    """Test window for tone selector widget"""
    
    # -------------------------
    # INIT
    # Initializes orchestrator (if available) and builds test harness UI.
    # -------------------------
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tone Selector Test - Phase 1")
        self.setGeometry(100, 100, 600, 400)
        
        # Initialize orchestrator
        try:
            self.orchestrator = Orchestrator()
            print("Orchestrator initialized successfully")
        except Exception as e:
            print(f"Orchestrator initialization failed: {e}")
            self.orchestrator = None
        
        # Setup UI
        self.setup_ui()
    
    # -------------------------
    # SETUP UI
    # Builds selector/display widgets and test action buttons.
    # -------------------------
    def setup_ui(self):
        """Setup test UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Test message data
        test_message = {
            'id': 'test_123',
            'sender': 'test@example.com',
            'subject': 'Test Message',
            'content': 'This is a test message for tone analysis. Please respond professionally.',
            'full_content': 'This is a test message for tone analysis. Please respond professionally. Thank you for your consideration.',
            'source': 'gmail',
            'priority': 'normal'
        }
        
        # Tone selector
        self.tone_selector = ToneSelector(self.orchestrator, test_message)
        layout.addWidget(self.tone_selector)
        
        # Tone detection display
        self.tone_detection_display = ToneDetectionDisplay(test_message)
        layout.addWidget(self.tone_detection_display)
        
        # Test buttons
        test_button = QPushButton("Test Auto-Suggest")
        test_button.clicked.connect(self.test_auto_suggest)
        layout.addWidget(test_button)
        
        update_button = QPushButton("Update Message Data")
        update_button.clicked.connect(self.update_message_data)
        layout.addWidget(update_button)
        
        # Status label
        self.status_label = QLabel("Ready for testing")
        layout.addWidget(self.status_label)
        
        # Connect signals
        self.tone_selector.tone_changed.connect(self.on_tone_changed)
        
        # Initial tone analysis
        self.perform_tone_detection(test_message)
    
    # -------------------------
    # TEST AUTO-SUGGEST
    # Triggers selector auto-suggest flow and updates status label.
    # -------------------------
    def test_auto_suggest(self):
        """Test auto-suggest functionality"""
        if self.orchestrator:
            self.tone_selector.on_auto_suggest()
            self.status_label.setText("Auto-suggest triggered")
        else:
            self.status_label.setText("No orchestrator available")
    
    # -------------------------
    # UPDATE MESSAGE DATA
    # Swaps test payload to a new scenario and refreshes tone widgets.
    # -------------------------
    def update_message_data(self):
        """Update message data with new content"""
        new_message = {
            'id': 'test_456',
            'sender': 'urgent@example.com',
            'subject': 'URGENT: Action Required',
            'content': 'This is extremely urgent and requires immediate attention!',
            'full_content': 'This is extremely urgent and requires immediate attention! Please respond as soon as possible.',
            'source': 'slack',
            'priority': 'high'
        }
        
        self.tone_selector.set_message_data(new_message)
        self.tone_detection_display.set_message_data(new_message)
        self.perform_tone_detection(new_message)
        self.status_label.setText("Message data updated")
    
    # -------------------------
    # PERFORM TONE DETECTION
    # Runs tone analysis through orchestrator tone engine and updates UI.
    # -------------------------
    def perform_tone_detection(self, message_data):
        """Perform tone analysis on message"""
        if not self.orchestrator:
            return
        
        try:
            content = message_data.get('full_content', '')
            if content:
                tone_result = self.orchestrator.tone_engine.analyze_incoming_tone(content)
                
                # Add tone data to message
                message_data['tone_detection'] = tone_result
                
                # Update displays
                self.tone_detection_display.set_message_data(message_data)
                
                print(f"Tone analysis: {tone_result.get('tone_signal')} ({tone_result.get('confidence'):.2f})")
        except Exception as e:
            print(f"Tone analysis error: {e}")
    
    # -------------------------
    # HANDLE TONE CHANGED SIGNAL
    # Displays currently selected tone in status label.
    # -------------------------
    def on_tone_changed(self, tone):
        """Handle tone change"""
        if isinstance(tone, ToneType):
            self.status_label.setText(f"Tone changed to: {tone.value}")
        else:
            self.status_label.setText(f"Tone changed to: {tone}")


# -------------------------
# MAIN TEST ENTRY
# Launches Qt application and opens interactive tone widget test window.
# -------------------------
def main():
    """Main test function"""
    app = QApplication(sys.argv)
    
    # Create test window
    window = TestWindow()
    window.show()
    
    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
