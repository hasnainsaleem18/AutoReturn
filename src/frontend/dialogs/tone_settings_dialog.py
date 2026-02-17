# -------------------------
# TONE SETTINGS DIALOG
# -------------------------
"""
Dialog for managing tone preferences and settings.
Integrates with existing settings system.
"""

# -------------------------
# IMPORTS
# -------------------------
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QGroupBox, QGridLayout,
    QTextEdit, QTabWidget, QWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.backend.models.tone_models import ToneType, ToneProfile
from src.backend.core.tone_manager import ToneManager


# -------------------------
# TONE SETTINGS DIALOG CLASS
# -------------------------
class ToneSettingsDialog(QDialog):
    """Dialog for managing tone preferences and settings"""
    
    # Signal to notify parent of changes
    settings_changed = Signal()
    
    def __init__(self, tone_manager: ToneManager, parent=None):
        super().__init__(parent)
        self.tone_manager = tone_manager
        self.user_profile = tone_manager.user_profile
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("🎨 Tone Settings")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Tab widget for organized settings
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.create_general_tab()
        self.create_sender_preferences_tab()
        self.create_analytics_tab()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        self.reset_button = QPushButton("Reset to Default")
        self.reset_button.clicked.connect(self.reset_to_default)
        button_layout.addWidget(self.reset_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
    
    def create_general_tab(self):
        """Create general tone settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Default tone group
        default_group = QGroupBox("Default Tone Settings")
        default_layout = QVBoxLayout(default_group)
        
        # Default tone selection
        tone_layout = QHBoxLayout()
        tone_label = QLabel("Default Tone:")
        tone_label.setMinimumWidth(120)
        tone_layout.addWidget(tone_label)
        
        self.default_tone_combo = QComboBox()
        self._populate_tone_combo(self.default_tone_combo)
        tone_layout.addWidget(self.default_tone_combo)
        tone_layout.addStretch()
        
        default_layout.addLayout(tone_layout)
        
        # Auto-tone recommendation
        self.auto_tone_checkbox = QCheckBox("Enable AI Tone Recommendations")
        self.auto_tone_checkbox.setToolTip("Automatically recommend appropriate tones based on message context")
        default_layout.addWidget(self.auto_tone_checkbox)
        
        layout.addWidget(default_group)
        
        # Description
        info_label = QLabel("""
        📝 About Tone Settings:
        
        • Default Tone: Used when no specific tone is selected
        • AI Recommendations: Automatically suggests appropriate tones based on message content, sender, and context
        • Sender Preferences: Override tones for specific senders
        • Analytics: Track tone usage and effectiveness
        
        The system learns from your manual tone selections to improve future recommendations.
        """)
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 10px; background-color: #f9f9f9; border-radius: 4px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "General")
    
    def create_sender_preferences_tab(self):
        """Create sender-specific preferences tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Sender preferences table
        prefs_group = QGroupBox("Sender-Specific Tone Preferences")
        prefs_layout = QVBoxLayout(prefs_group)
        
        # Table for sender preferences
        self.sender_table = QTableWidget()
        self.sender_table.setColumnCount(3)
        self.sender_table.setHorizontalHeaderLabels(["Sender", "Preferred Tone", "Actions"])
        
        # Configure table
        header = self.sender_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        
        self.sender_table.setAlternatingRowColors(True)
        self.sender_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        prefs_layout.addWidget(self.sender_table)
        
        # Add new preference
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("Add Sender Preference:"))
        
        self.new_sender_edit = QTextEdit()
        self.new_sender_edit.setMaximumHeight(60)
        self.new_sender_edit.setPlaceholderText("Enter email address or name...")
        add_layout.addWidget(self.new_sender_edit)
        
        self.new_tone_combo = QComboBox()
        self._populate_tone_combo(self.new_tone_combo)
        add_layout.addWidget(self.new_tone_combo)
        
        self.add_pref_button = QPushButton("Add")
        self.add_pref_button.clicked.connect(self.add_sender_preference)
        add_layout.addWidget(self.add_pref_button)
        
        prefs_layout.addLayout(add_layout)
        layout.addWidget(prefs_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Sender Preferences")
    
    def create_analytics_tab(self):
        """Create analytics and statistics tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Statistics group
        stats_group = QGroupBox("Tone Usage Analytics")
        stats_layout = QGridLayout(stats_group)
        
        # Get statistics
        stats = self.tone_manager.get_tone_statistics()
        
        # Display statistics
        stats_items = [
            ("Default Tone:", stats['default_tone']),
            ("Auto-Tone Enabled:", "Yes" if stats['auto_tone_enabled'] else "No"),
            ("Total Manual Overrides:", str(stats['total_manual_overrides'])),
            ("Sender Preferences:", str(stats['sender_preferences_count'])),
            ("Domain Preferences:", str(stats['domain_preferences_count']))
        ]
        
        for i, (label, value) in enumerate(stats_items):
            row = i // 2
            col = (i % 2) * 2
            
            stats_layout.addWidget(QLabel(f"<b>{label}</b>"), row, col)
            stats_layout.addWidget(QLabel(value), row, col + 1)
        
        layout.addWidget(stats_group)
        
        # Most used tones
        if stats.get('most_used_tones'):
            most_group = QGroupBox("Most Used Tones")
            most_layout = QVBoxLayout(most_group)
            
            for tone, count in stats['most_used_tones'].items():
                tone_label = QLabel(f"{tone.title()}: {count} times")
                tone_label.setStyleSheet("padding: 2px; background-color: #f0f0f0; margin: 1px; border-radius: 2px;")
                most_layout.addWidget(tone_label)
            
            layout.addWidget(most_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Analytics")
    
    def _populate_tone_combo(self, combo_box):
        """Populate combo box with tone options"""
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
            combo_box.addItem(display_name, tone)
    
    def load_current_settings(self):
        """Load current settings into UI"""
        # General settings
        default_index = self.default_tone_combo.findData(self.user_profile.default_tone)
        if default_index >= 0:
            self.default_tone_combo.setCurrentIndex(default_index)
        
        self.auto_tone_checkbox.setChecked(self.user_profile.auto_tone_enabled)
        
        # Sender preferences
        self._load_sender_preferences()
    
    def _load_sender_preferences(self):
        """Load sender preferences into table"""
        self.sender_table.setRowCount(0)
        
        for sender, tone in self.user_profile.sender_preferences.items():
            row = self.sender_table.rowCount()
            self.sender_table.insertRow(row)
            
            # Sender
            self.sender_table.setItem(row, 0, QTableWidgetItem(sender))
            
            # Tone
            tone_index = self.new_tone_combo.findData(tone)
            tone_text = self.new_tone_combo.itemText(tone_index) if tone_index >= 0 else tone.value
            self.sender_table.setItem(row, 1, QTableWidgetItem(tone_text))
            
            # Remove button
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda checked, s=sender: self.remove_sender_preference(s))
            self.sender_table.setCellWidget(row, 2, remove_button)
    
    def add_sender_preference(self):
        """Add new sender preference"""
        sender = self.new_sender_edit.toPlainText().strip()
        tone = self.new_tone_combo.currentData()
        
        if not sender:
            QMessageBox.warning(self, "Warning", "Please enter a sender email or name.")
            return
        
        if sender in self.user_profile.sender_preferences:
            QMessageBox.warning(self, "Warning", f"Preference for '{sender}' already exists.")
            return
        
        # Add preference
        self.user_profile.sender_preferences[sender] = tone
        self._load_sender_preferences()
        
        # Clear inputs
        self.new_sender_edit.clear()
        
        QMessageBox.information(self, "Success", f"Added tone preference for '{sender}'.")
    
    def remove_sender_preference(self, sender: str):
        """Remove sender preference"""
        if sender in self.user_profile.sender_preferences:
            del self.user_profile.sender_preferences[sender]
            self._load_sender_preferences()
            QMessageBox.information(self, "Success", f"Removed preference for '{sender}'.")
    
    def save_settings(self):
        """Save all settings"""
        try:
            # Update user profile
            self.user_profile.default_tone = self.default_tone_combo.currentData()
            self.user_profile.auto_tone_enabled = self.auto_tone_checkbox.isChecked()
            
            # Save through tone manager
            self.tone_manager.user_profile = self.user_profile
            self.tone_manager._save_user_profile()
            
            # Emit signal
            self.settings_changed.emit()
            
            QMessageBox.information(self, "Success", "Tone settings saved successfully!")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {str(e)}")
    
    def reset_to_default(self):
        """Reset all settings to default"""
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Are you sure you want to reset all tone settings to default values?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset to default profile
            self.user_profile = ToneProfile()
            self.tone_manager.user_profile = self.user_profile
            self.tone_manager._save_user_profile()
            
            # Reload UI
            self.load_current_settings()
            
            QMessageBox.information(self, "Success", "Settings reset to default values.")
            self.settings_changed.emit()
