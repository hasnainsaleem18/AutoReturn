# -------------------------
# SETTINGS DIALOG
# -------------------------
"""
Settings dialog for configuring application preferences, integrations,
and user profile settings.
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
import os
import json

# Third-party imports
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QTabWidget, QScrollArea, QTimeEdit, QLineEdit, QCheckBox,
    QMessageBox, QFileDialog, QTextEdit
)
from PySide6.QtCore import Qt, QTime, Signal, QSize
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush

# Local application imports
from src.frontend.ui.styles import get_stylesheet

# Local imports for tone features
from src.backend.models.tone_models import ToneType, get_tone_display_name
from src.backend.models.automation_models import AutomationSettings

# -------------------------
# STYLE CONSTANTS
# -------------------------
# -------------------------
# STYLE CONSTANTS CLASS
# -------------------------
class StyleConstants:
    """Shared visual tokens used across settings-related dialogs."""
    # Colors
    COLOR_PRIMARY = "#0FA4AF"
    COLOR_DARK_PRIMARY = "#024950"
    COLOR_DARKEST = "#003135"
    COLOR_LIGHT = "#AFDDE5"
    COLOR_LIGHTEST = "#D4F4F7"
    COLOR_DANGER = "#964734"
    COLOR_WHITE = "#FFFFFF"
    COLOR_GRAY_LIGHT = "#F5F5F5"
    COLOR_GRAY_MEDIUM = "#666666"
    
    # Spacing
    SPACING_SMALL = 6
    SPACING_MEDIUM = 12
    SPACING_LARGE = 20
    SPACING_XLARGE = 32
    
    # Sizes
    FONT_SIZE_SMALL = 12
    FONT_SIZE_MEDIUM = 13
    FONT_SIZE_LARGE = 14
    FONT_SIZE_XLARGE = 15
    FONT_SIZE_HEADER = 18
    FONT_SIZE_TITLE = 20
    FONT_SIZE_HERO = 24
    FONT_SIZE_DISPLAY = 28
    
    # Border Radius
    RADIUS_SMALL = 6
    RADIUS_MEDIUM = 8
    RADIUS_LARGE = 12
    RADIUS_XLARGE = 16
    
    # Padding
    PADDING_SMALL = 8
    PADDING_MEDIUM = 10
    PADDING_LARGE = 12


# -------------------------
# UI CONSTANTS
# -------------------------
# -------------------------
# UI CONSTANTS CLASS
# -------------------------
class UIConstants:
    """Layout and sizing constants for settings dialog sections."""
    DIALOG_MIN_WIDTH = 900
    DIALOG_MIN_HEIGHT = 700
    HEADER_HEIGHT = 80
    CLOSE_BUTTON_SIZE = 32
    
    # Tab identifiers
    TAB_PROFILE = 0
    TAB_QUIET_HOURS = 1
    TAB_PRIORITY_RULES = 2
    TAB_INTEGRATIONS = 3


class ToggleSwitch(QCheckBox):
    """Compact cross-platform switch-style toggle."""

    # -------------------------
    # INIT
    # Configures fixed-size switch behavior and keyboard focus support.
    # -------------------------
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(52, 28)
        self.setText("")
        self.setTristate(False)
        self.setFocusPolicy(Qt.StrongFocus)

    # -------------------------
    # SIZE HINT
    # Provides stable control dimensions for layouts.
    # -------------------------
    def sizeHint(self):
        return QSize(52, 28)

    # -------------------------
    # MOUSE RELEASE HANDLER
    # Toggles switch on left click when pointer is inside control bounds.
    # -------------------------
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self.toggle()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -------------------------
    # KEY PRESS HANDLER
    # Supports keyboard toggling via Space/Enter for accessibility.
    # -------------------------
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

    # -------------------------
    # PAINT EVENT
    # Draws custom track + knob using theme-aware colors.
    # -------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2

        on_color = QColor(StyleConstants.COLOR_PRIMARY)
        is_dark = self.palette().window().color().lightness() < 128
        off_color = QColor("#4B5563") if is_dark else QColor("#AFDDE5")
        border_color = self.palette().dark().color()

        track_color = on_color if self.isChecked() else off_color
        painter.setPen(QPen(border_color, 1))
        painter.setBrush(QBrush(track_color))
        painter.drawRoundedRect(rect, radius, radius)

        knob_d = rect.height() - 6
        knob_y = rect.top() + 3
        knob_x = rect.right() - knob_d - 3 if self.isChecked() else rect.left() + 3
        knob_rect = rect.adjusted(0, 0, 0, 0)
        knob_rect.setX(knob_x)
        knob_rect.setY(knob_y)
        knob_rect.setWidth(knob_d)
        knob_rect.setHeight(knob_d)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(self.palette().base().color()))
        painter.drawEllipse(knob_rect)

# -------------------------
# SETTINGS DIALOG CLASS
# -------------------------
class SettingsDialog(QDialog):
    # Signals for communication with parent
    profile_updated = Signal(dict)
    logout_requested = Signal()
    
    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self, user_data=None, parent=None, gmail_status=None, orchestrator=None):
        super().__init__(parent)
        
        # Initialize user data with defaults if not provided
        self.user_data = self._initialize_user_data(user_data)
        self.gmail_status = gmail_status or {}
        self.gmail_status_labels = {}
        self.upload_gmail_json_callback = None
        self.connect_gmail_callback = None
        self.sync_gmail_callback = None
        self.get_gmail_status_callback = None
        
        # Orchestrator reference used by tone and automation settings tabs.
        self.orchestrator = orchestrator
        self.automation_settings = self._load_automation_settings()
        
        # -------------------------
        # DIALOG SETUP
        # -------------------------
        self._setup_dialog()
        
        # -------------------------
        # UI CONSTRUCTION
        # -------------------------
        self._build_ui()

    # -------------------------
    # ASSET HANDLING
    # -------------------------
    def _get_asset_path(self, file_name: str) -> str:
        """Get the full path to an asset file in the frontend/assets directory.
        
        Args:
            file_name (str): Name of the asset file
            
        Returns:
            str: Full path to the asset file or empty string if not found
        """
        base_dir = os.path.dirname(os.path.dirname(__file__))  # Go up one level to frontend directory
        path = os.path.join(base_dir, "assets", file_name)
        return path if os.path.exists(path) else ""

    # -------------------------
    # GMAIL STATUS HANDLING
    # -------------------------
    def refresh_gmail_status(self):
        """Update the Gmail connection status display with current status."""
        status = self.gmail_status
        if self.get_gmail_status_callback:
            try:
                status = self.get_gmail_status_callback() or {}
            except Exception:
                status = self.gmail_status
        self.gmail_status = status or {}
        labels = self.gmail_status_labels
        if not labels:
            return
        has_secret = self.gmail_status.get('has_client_secret', False)
        has_token = self.gmail_status.get('has_token', False)
        is_connected = self.gmail_status.get('is_connected', False)
        file_name = self.gmail_status.get('client_secret_name') or 'Not uploaded'
        labels.get('credentials').setText("Credentials: " + (file_name if has_secret else "Not uploaded"))
        labels.get('token').setText("Token: " + ("Available" if has_token else "Missing"))
        labels.get('connection').setText("Connection: " + ("Connected" if is_connected else "Offline"))

    # -------------------------
    # GMAIL CREDENTIALS HANDLING
    # -------------------------
    def handle_gmail_upload_json(self):
        """Handle the Gmail JSON credentials file upload."""
        if not self.upload_gmail_json_callback:
            QMessageBox.information(self, "Coming Soon", "Gmail upload handler is not wired yet.")
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select client_secret.json",
            "",
            "JSON Files (*.json)"
        )
        if not file_path:
            return
        success, message = self.upload_gmail_json_callback(file_path)
        if success:
            QMessageBox.information(self, "Gmail Credentials", message)
            self.refresh_gmail_status()
        else:
            QMessageBox.warning(self, "Gmail Credentials", message)

    # -------------------------
    # GMAIL AUTHENTICATION
    # -------------------------
    def handle_gmail_authorize(self):
        """Initiate Gmail OAuth authorization flow."""
        if not self.connect_gmail_callback:
            QMessageBox.information(self, "Coming Soon", "Gmail authorization handler is not wired yet.")
            return
        success, message = self.connect_gmail_callback()
        if success:
            QMessageBox.information(self, "Gmail Authorization", message)
            self.refresh_gmail_status()
        else:
            QMessageBox.warning(self, "Gmail Authorization", message)

    # -------------------------
    # GMAIL SYNCHRONIZATION
    # -------------------------
    def handle_gmail_sync(self):
        """Manually trigger Gmail sync."""
        if not self.sync_gmail_callback:
            QMessageBox.information(self, "Coming Soon", "Gmail sync handler is not wired yet.")
            return
        success, message = self.sync_gmail_callback()
        if success:
            QMessageBox.information(self, "Gmail Sync", message)
        else:
            QMessageBox.warning(self, "Gmail Sync", message)
    
    # -------------------------
    # USER DATA MANAGEMENT
    # -------------------------
    def _initialize_user_data(self, user_data):
        """Initialize user data with default values if not provided.
        
        Args:
            user_data (dict): User data to initialize
            
        Returns:
            dict: Initialized user data with defaults
        """
        default_data = {
            'name': 'User',
            'email': 'user@example.com',
            'auth_method': 'email',
            'connected_accounts': {
                'gmail': False,
                'slack': False
            }
        }
        
        if user_data:
            default_data.update(user_data)
        
        return default_data

    def _load_automation_settings(self) -> AutomationSettings:
        """Load automation settings from orchestrator coordinator when available."""
        try:
            if self.orchestrator and hasattr(self.orchestrator, "get_automation_coordinator"):
                coordinator = self.orchestrator.get_automation_coordinator()
                if coordinator:
                    return coordinator.get_settings()
        except Exception as e:
            print(f"Could not load automation settings: {e}")
        return AutomationSettings()
    
    # -------------------------
    # DIALOG SETUP
    # -------------------------
    def _setup_dialog(self):
        """Configure basic dialog properties and appearance."""
        self.setWindowTitle("Settings")
        self.setMinimumSize(
            UIConstants.DIALOG_MIN_WIDTH,
            UIConstants.DIALOG_MIN_HEIGHT
        )
    
    # -------------------------
    # UI CONSTRUCTION
    # -------------------------
    def _build_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Add components
        layout.addWidget(self._create_header())
        layout.addWidget(self._create_tab_widget())
    
    # -------------------------
    # HEADER CREATION
    # -------------------------
    def _create_header(self):
        """Create the header section with title and close button."""
        header = QWidget()
        header.setStyleSheet(f"""
            QWidget {{
                background: #024950;
                border-bottom: 2px solid #0FA4AF;
            }}
        """)
        header.setFixedHeight(UIConstants.HEADER_HEIGHT)
        
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(
            StyleConstants.SPACING_XLARGE, 0,
            StyleConstants.SPACING_XLARGE, 0
        )
        
        # Title
        title = QLabel("Settings")
        title.setObjectName("logo")

        # Close button
        close_btn = QPushButton("✕")
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: none;
                border: none;
                font-size: {StyleConstants.FONT_SIZE_HERO}px;
                color: {StyleConstants.COLOR_LIGHT};
            }}
            QPushButton:hover {{
                color: {StyleConstants.COLOR_WHITE};
            }}
        """)
        close_btn.clicked.connect(self.reject)
        close_btn.setFixedSize(
            UIConstants.CLOSE_BUTTON_SIZE,
            UIConstants.CLOSE_BUTTON_SIZE
        )
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        
        return header
    
    # -------------------------
    # TAB WIDGET CREATION
    # -------------------------
    def _create_tab_widget(self):
        """Create and configure the tab widget for different settings sections."""
        tabs = QTabWidget()
        tabs.setStyleSheet(self._get_tab_stylesheet())
        
        # Add tabs in order
        tabs.addTab(self._create_profile_tab(), "Profile")
        tabs.addTab(self._create_priority_rules_tab(), "Priority Rules")
        tabs.addTab(self._create_integrations_tab(), "Integrations")
        
        # Tone and automation tabs are available when orchestrator is provided.
        if self.orchestrator:
            tabs.addTab(self._create_tone_settings_tab(), "Tone Settings")
            tabs.addTab(self._create_automation_settings_tab(), "Automation")

        return tabs
    
    # -------------------------
    # STYLESHEET GENERATION
    # -------------------------
    def _get_tab_stylesheet(self):
        """Generate CSS styles for the tab widget."""
        return f"""
            QTabWidget::pane {{
                border: none;
                background: {StyleConstants.COLOR_WHITE};
            }}
            QTabBar {{
                background: #024950;
            }}
            QTabBar::tab {{
                padding: {StyleConstants.PADDING_LARGE}px {StyleConstants.FONT_SIZE_HERO}px;
                background: {StyleConstants.COLOR_DARK_PRIMARY};
                border: none;
                color: {StyleConstants.COLOR_LIGHT};
                font-size: {StyleConstants.FONT_SIZE_LARGE}px;
                font-weight: 500;
                min-width: 120px;
            }}
            QTabBar::tab:hover {{
                background-color: {StyleConstants.COLOR_DARKEST};
                color: {StyleConstants.COLOR_WHITE};
            }}
            QTabBar::tab:selected {{
                background-color: {StyleConstants.COLOR_WHITE};
                color: {StyleConstants.COLOR_PRIMARY};
                font-weight: 600;
                border-bottom: 3px solid {StyleConstants.COLOR_PRIMARY};
            }}
        """
    
    # -------------------------
    # PROFILE TAB CREATION
    # -------------------------
    def _create_profile_tab(self):
        """Create the Profile tab content."""
        scroll = self._create_scroll_area()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE
        )
        layout.setSpacing(StyleConstants.SPACING_XLARGE)
        
        # Profile Information Section
        layout.addWidget(self._create_section_header("Profile Information"))
        layout.addWidget(self._create_profile_info_section())
        layout.addWidget(
            self._create_primary_button("Edit Profile", self.edit_profile),
            alignment=Qt.AlignLeft
        )
        
        # Separator
        layout.addSpacing(StyleConstants.SPACING_LARGE)
        layout.addWidget(self._create_separator())
        layout.addSpacing(StyleConstants.PADDING_MEDIUM)
        
        # Account Actions Section
        layout.addWidget(self._create_section_header("Account Actions"))
        layout.addWidget(
            self._create_danger_button("Logout", self.handle_logout),
            alignment=Qt.AlignLeft
        )
        
        layout.addStretch()
        scroll.setWidget(content)
        return scroll
    
    # -------------------------
    # PROFILE INFO SECTION
    # -------------------------
    def _create_profile_info_section(self):
        """Create the user profile information section."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(StyleConstants.SPACING_LARGE)
        
        # Add profile fields
        profile_fields = [
            ("Full Name", self.user_data.get('name', 'User')),
            ("Email Address", self.user_data.get('email', 'user@example.com')),
            ("Authentication Method", self._get_auth_method_display())
        ]
        
        for label_text, value_text in profile_fields:
            layout.addWidget(self._create_info_field(label_text, value_text))
        
        return container
    
    # -------------------------
    # AUTHENTICATION HELPERS
    # -------------------------
    def _get_auth_method_display(self):
        """Get display text for the authentication method."""
        auth_method = self.user_data.get('auth_method', 'email')
        return "Email/Password" if auth_method == 'email' else "Google OAuth"
    
    # -------------------------
    # PRIORITY RULES TAB
    # -------------------------
    def _create_priority_rules_tab(self):
        """Create the Priority Rules tab content."""
        scroll = self._create_scroll_area()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE
        )
        layout.setSpacing(StyleConstants.SPACING_LARGE)
        
        # Section header
        layout.addWidget(self._create_section_header("Priority Rules"))
        
        # Description
        description = self._create_description(
            "Define your priority senders. Format: sender@email.com = score (0-10)\n"
            "Example: boss@company.com = 10"
        )
        layout.addWidget(description)
        
        # Text Edit for Sender Priorities
        self.priority_text_edit = QTextEdit()
        self.priority_text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {StyleConstants.COLOR_WHITE};
                color: {StyleConstants.COLOR_DARKEST};
                border: 1px solid {StyleConstants.COLOR_LIGHT};
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                padding: {StyleConstants.PADDING_SMALL}px;
                font-family: monospace;
            }}
        """)
        self.priority_text_edit.setMinimumHeight(250)
        
        self._load_priority_data()
        layout.addWidget(self.priority_text_edit)
        
        # Save Button
        save_btn = QPushButton("Save Priority Rules")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {StyleConstants.COLOR_PRIMARY};
                color: white;
                border: none;
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                padding: {StyleConstants.PADDING_MEDIUM}px 0;
                font-weight: bold;
                font-size: {StyleConstants.FONT_SIZE_MEDIUM}px;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_DARK_PRIMARY};
            }}
        """)
        save_btn.clicked.connect(self._save_priority_rules)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        scroll.setWidget(content)
        return scroll
    
    def _load_priority_data(self):
        dataset_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'priority_dataset.json')
        try:
            with open(dataset_path, 'r') as f:
                self.priority_data = json.load(f)
            
            senders = self.priority_data.get("sender_scores", {}).get("user_priority_list", {})
            text_lines = []
            for sender, score in senders.items():
                if not sender.startswith("_"):
                    text_lines.append(f"{sender} = {score}")
            
            self.priority_text_edit.setPlainText("\\n".join(text_lines))
        except Exception as e:
            self.priority_text_edit.setPlainText(f"Error loading data: {e}")
            self.priority_data = {}

    def _save_priority_rules(self):
        try:
            lines = self.priority_text_edit.toPlainText().split('\\n')
            new_rules = {}
            for line in lines:
                if '=' in line:
                    parts = line.split('=')
                    sender = parts[0].strip()
                    try:
                        score = float(parts[1].strip())
                        new_rules[sender] = score
                    except ValueError:
                        continue
            
            # Update the JSON structure
            if "sender_scores" not in self.priority_data:
                self.priority_data["sender_scores"] = {}
            if "user_priority_list" not in self.priority_data["sender_scores"]:
                self.priority_data["sender_scores"]["user_priority_list"] = {}
                
            self.priority_data["sender_scores"]["user_priority_list"] = new_rules
            
            dataset_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), 'data', 'priority_dataset.json')
            with open(dataset_path, 'w') as f:
                json.dump(self.priority_data, f, indent=4)
                
            QMessageBox.information(self, "Success", "Priority rules saved successfully!")
            
            # Update running agents
            parent = self.parent()
            if hasattr(parent, 'orchestrator'):
                for name in ['gmail', 'slack']:
                    agent = parent.orchestrator.get_agent(name)
                    if agent and hasattr(agent, 'priority_engine'):
                        agent.priority_engine.set_user_priority_list(new_rules)
                        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save rules: {e}")
    
    # -------------------------
    # INTEGRATIONS TAB
    # -------------------------
    def _create_integrations_tab(self):
        """Create the Integrations tab content."""
        scroll = self._create_scroll_area()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE,
            StyleConstants.SPACING_XLARGE
        )
        layout.setSpacing(StyleConstants.FONT_SIZE_HERO)
        
        # Header
        layout.addWidget(self._create_section_header("Connected Apps & Integrations"))
        
        # Description
        description = self._create_description(
            "Connect your Gmail and Slack accounts to unify your communications."
        )
        layout.addWidget(description)
        layout.addSpacing(StyleConstants.SPACING_MEDIUM)
        
        # Integration cards
        layout.addWidget(self._create_gmail_integration_card())
        layout.addSpacing(StyleConstants.PADDING_SMALL)
        layout.addWidget(self._create_slack_integration_card())
        
        layout.addStretch()
        scroll.setWidget(content)
        return scroll
    
    # -------------------------
    # GMAIL INTEGRATION CARD
    # -------------------------
    def _create_gmail_integration_card(self):
        """Create the Gmail integration settings card."""
        card = self._create_integration_card_base()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.SPACING_LARGE,
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.SPACING_LARGE
        )
        card_layout.setSpacing(StyleConstants.RADIUS_XLARGE)
        
        # Header
        card_layout.addWidget(self._create_integration_header(
            icon_path=self._get_asset_path("Gmail_Logo_32px.png"),
            title="Gmail",
            subtitle="Connect your Gmail account to read and send emails",
            is_connected=self.user_data.get('connected_accounts', {}).get('gmail', False)
        ))
        
        # Setup section
        card_layout.addWidget(self._create_subsection_header("Setup Instructions"))
        setup_desc = self._create_description(
            "1. Upload the Google OAuth JSON you downloaded.\n"
            "2. Run the authorization flow (browser will open for login).\n"
            "3. Once token.json is generated, sync your Gmail inbox."
        )
        card_layout.addWidget(setup_desc)

        # Status summary
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(6)
        status_layout.addWidget(self._create_subsection_header("Status"))
        status_items = {
            'credentials': QLabel("Credentials: Not uploaded"),
            'token': QLabel("Token: Missing"),
            'connection': QLabel("Connection: Offline")
        }
        for label in status_items.values():
            label.setStyleSheet(
                f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; "
                f"color: {StyleConstants.COLOR_DARKEST};"
            )
            status_layout.addWidget(label)
        self.gmail_status_labels = status_items
        card_layout.addWidget(status_container)

        # Guide button
        card_layout.addWidget(
            self._create_guide_button(
                "How to Get Credentials",
                self.show_gmail_setup_guide
            )
        )

        # Action buttons
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(StyleConstants.SPACING_SMALL)
        upload_btn = self._create_primary_button("Upload client_secret.json", self.handle_gmail_upload_json)
        authorize_btn = self._create_primary_button("Run Gmail Authorization", self.handle_gmail_authorize)
        actions_layout.addWidget(upload_btn)
        actions_layout.addWidget(authorize_btn)
        card_layout.addLayout(actions_layout)
        
        return card
    
    # -------------------------
    # SLACK INTEGRATION CARD
    # -------------------------
    def _create_slack_integration_card(self):
        """Create the Slack integration settings card."""
        card = self._create_integration_card_base()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.SPACING_LARGE,
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.SPACING_LARGE
        )
        card_layout.setSpacing(StyleConstants.RADIUS_XLARGE)
        
        # Header
        card_layout.addWidget(self._create_integration_header(
            icon_path=self._get_asset_path("icons8-slack-new-48.png"),
            title="Slack",
            subtitle="Connect your Slack workspace to send and receive messages as you",
            is_connected=self.user_data.get('connected_accounts', {}).get('slack', False)
        ))
        
        # Setup section
        card_layout.addWidget(self._create_subsection_header("Setup Instructions"))
        
        # Simplified description
        desc_text = (
            "You'll need a <b>User OAuth Token</b> that allows your app to "
            "send/receive messages including DMs. This token starts with <b>xoxp-</b>"
        )
        desc = QLabel(desc_text)
        desc.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY}; "
            f"line-height: 1.5; "
            f"margin-bottom: {StyleConstants.PADDING_SMALL}px;"
        )
        desc.setWordWrap(True)
        card_layout.addWidget(desc)
        
        # Single token input
        token_input = self._create_credential_input(
            "User OAuth Token",
            "xoxp-1234567890-123456789012-abcdefABCDEF123456",
            is_password=True
        )
        
        card_layout.addWidget(token_input)
        
        # Guide button
        card_layout.addWidget(
            self._create_guide_button(
                "How to Get Your Slack User OAuth Token",
                self.show_slack_setup_guide
            )
        )
        
        # Action buttons
        card_layout.addLayout(self._create_integration_buttons(
            "Connect Slack",
            lambda: self.handle_slack_connect(
                token_input.findChild(QLineEdit)
            ),
            self.test_slack_connection
        ))
        
        return card
    
    # -------------------------
    # SCROLL AREA CREATION
    # -------------------------
    def _create_scroll_area(self):
        """Create a scroll area with proper styling."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            f"background-color: {StyleConstants.COLOR_WHITE}; border: none;"
        )
        return scroll
    
    # -------------------------
    # UI COMPONENT CREATION
    # -------------------------
    def _create_section_header(self, text):
        """Create a styled section header.
        
        Args:
            text (str): Text to display in the header
            
        Returns:
            QLabel: Configured header label
        """
        header = QLabel(text)
        header.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_HEADER}px; "
            f"font-weight: 600; "
            f"color: {StyleConstants.COLOR_DARKEST};"
        )
        return header
    
    def _create_subsection_header(self, text):
        """Create a styled subsection header.
        
        Args:
            text (str): Text to display in the subsection header
            
        Returns:
            QLabel: Configured subsection header label
        """
        header = QLabel(text)
        header.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_LARGE}px; "
            f"font-weight: 600; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY}; "
            f"margin-top: {StyleConstants.PADDING_SMALL}px;"
        )
        return header
    
    def _create_description(self, text):
        """Create a description label with the specified text.
        
        Args:
            text (str): Description text to display
            
        Returns:
            QLabel: Configured description label
        """
        desc = QLabel(text)
        desc.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_LARGE}px; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY}; "
            f"line-height: 1.5;"
        )
        desc.setWordWrap(True)
        return desc
    
    def _create_separator(self):
        """Create a horizontal line separator.
        
        Returns:
            QFrame: Configured separator line
        """
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(
            f"background-color: {StyleConstants.COLOR_LIGHT};"
        )
        return separator
    
    def _create_info_field(self, label_text, value_text):
        """Create a labeled information field.
        
        Args:
            label_text (str): Label text
            value_text (str): Value text to display
            
        Returns:
            QWidget: Widget containing the label and value
        """
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(StyleConstants.SPACING_SMALL)
        
        # Label
        label = QLabel(label_text)
        label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; "
            f"font-weight: 500; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY};"
        )
        
        # Value
        value = QLabel(value_text)
        value.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_XLARGE}px; "
            f"color: {StyleConstants.COLOR_DARKEST}; "
            f"padding: 2px 0;"
        )
        
        layout.addWidget(label)
        layout.addWidget(value)
        
        return field
    
    # -------------------------
    # BUTTON CREATION
    # -------------------------
    def _create_primary_button(self, text, callback):
        """Create a primary action button.
        
        Args:
            text (str): Button text
            callback (callable): Function to call when clicked
            
        Returns:
            QPushButton: Configured primary button
        """
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {StyleConstants.COLOR_PRIMARY};
                color: {StyleConstants.COLOR_WHITE};
                border: none;
                padding: {StyleConstants.PADDING_MEDIUM}px {StyleConstants.FONT_SIZE_HERO}px;
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                font-size: {StyleConstants.FONT_SIZE_LARGE}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_DARK_PRIMARY};
            }}
        """)
        button.clicked.connect(callback)
        return button
    
    
    def _create_danger_button(self, text, callback):
        """Create a danger/destructive action button.
        
        Args:
            text (str): Button text
            callback (callable): Function to call when clicked
            
        Returns:
            QPushButton: Configured danger button
        """
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {StyleConstants.COLOR_WHITE};
                color: {StyleConstants.COLOR_DANGER};
                border: 2px solid {StyleConstants.COLOR_DANGER};
                padding: {StyleConstants.PADDING_MEDIUM}px {StyleConstants.FONT_SIZE_HERO}px;
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                font-size: {StyleConstants.FONT_SIZE_LARGE}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_DANGER};
                color: {StyleConstants.COLOR_WHITE};
            }}
        """)
        button.clicked.connect(callback)
        return button
    
    def _create_guide_button(self, text, callback):
        """Create a guide/help button.
        
        Args:
            text (str): Button text
            callback (callable): Function to call when clicked
            
        Returns:
            QPushButton: Configured guide button
        """
        button = QPushButton(text)
        button.setCursor(Qt.PointingHandCursor)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {StyleConstants.COLOR_GRAY_LIGHT};
                color: {StyleConstants.COLOR_DARK_PRIMARY};
                border: none;
                padding: {StyleConstants.SPACING_SMALL}px {StyleConstants.SPACING_MEDIUM}px;
                border-radius: {StyleConstants.RADIUS_SMALL}px;
                font-size: {StyleConstants.FONT_SIZE_SMALL}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_LIGHT};
            }}
        """)
        button.clicked.connect(callback)
        return button
    
    # -------------------------
    # CARD CREATION
    # -------------------------
    def _create_coming_soon_card(self, message):
        """Create a placeholder card for upcoming features.
        
        Args:
            message (str): Message to display in the card
            
        Returns:
            QWidget: Configured card widget
        """
        card = QWidget()
        card.setObjectName("comingCard")
        card.setStyleSheet(f"""
            QWidget#comingCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {StyleConstants.COLOR_LIGHT}, 
                    stop:1 {StyleConstants.COLOR_LIGHTEST});
                border: 2px solid {StyleConstants.COLOR_DARK_PRIMARY};
                border-radius: {StyleConstants.RADIUS_XLARGE}px;
            }}

            QWidget#comingCard QLabel {{
                background: transparent;
            }}
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 60, 40, 60)
        card_layout.setAlignment(Qt.AlignCenter)
        
        # Icon
        icon = QLabel("🚧")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("font-size: 64px;")
        
        # Title
        title = QLabel("Coming Soon")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: {StyleConstants.FONT_SIZE_DISPLAY}px;
            font-weight: 700;
            color: {StyleConstants.COLOR_DARK_PRIMARY};
        """)
        
        # Description
        desc = QLabel(message)
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet(f"""
            font-size: {StyleConstants.FONT_SIZE_LARGE}px;
            color: {StyleConstants.COLOR_DARK_PRIMARY};
            margin-top: {StyleConstants.PADDING_SMALL}px;
        """)
        
        card_layout.addWidget(icon)
        card_layout.addWidget(title)
        card_layout.addWidget(desc)
        
        return card
    
    # -------------------------
    # INTEGRATION CARD COMPONENTS
    # -------------------------
    def _create_integration_card_base(self):
        """Create the base widget for integration cards.
        
        Returns:
            tuple: (base_widget, layout) for the card
        """
        card = QWidget()
        card.setObjectName("integrationCard")
        card.setStyleSheet(f"""
            QWidget#integrationCard {{
                background: {StyleConstants.COLOR_WHITE};
                border: 1px solid {StyleConstants.COLOR_LIGHT};
                border-radius: {StyleConstants.RADIUS_XLARGE}px;
            }}
        """)
        return card
    
    def _create_integration_header(self, icon_path, title, subtitle, is_connected):
        """Create the header section for integration cards.
        
        Args:
            icon_path (str): Path to the integration icon
            title (str): Integration title
            subtitle (str): Integration subtitle/status
            is_connected (bool): Whether the integration is connected
            
        Returns:
            QWidget: Configured header widget
        """
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Icon container
        icon_label = QLabel()
        icon_label.setFixedSize(56, 56)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {StyleConstants.COLOR_LIGHTEST};
                border-radius: {StyleConstants.RADIUS_LARGE}px;
            }}
        """)
        if icon_path:
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                icon_label.setPixmap(
                    pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
        
        # Title and subtitle
        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_HEADER}px; "
            f"font-weight: 600; "
            f"color: {StyleConstants.COLOR_DARKEST};"
        )
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY};"
        )
        subtitle_label.setWordWrap(True)
        
        text_layout.addWidget(title_label)
        text_layout.addWidget(subtitle_label)
        
        # Status badge
        status_text = "✓ Connected" if is_connected else "Not Connected"
        status_bg = StyleConstants.COLOR_LIGHT if is_connected else StyleConstants.COLOR_GRAY_LIGHT
        status_color = StyleConstants.COLOR_DARK_PRIMARY if is_connected else StyleConstants.COLOR_GRAY_MEDIUM
        
        status_badge = QLabel(status_text)
        status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {status_bg};
                color: {status_color};
                padding: 4px {StyleConstants.SPACING_MEDIUM}px;
                border-radius: {StyleConstants.RADIUS_LARGE}px;
                font-size: {StyleConstants.FONT_SIZE_SMALL}px;
                font-weight: 600;
            }}
        """)
        status_badge.setFixedHeight(24)
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(text_widget, 1)
        header_layout.addWidget(status_badge)
        
        return header
    
    # -------------------------
    # CREDENTIAL INPUTS
    # -------------------------
    def _create_credential_input(self, label_text, placeholder, is_password=False):
        """Create a labeled input field for credentials.
        
        Args:
            label_text (str): Label for the input field
            placeholder (str): Placeholder text
            is_password (bool): Whether to mask the input
            
        Returns:
            tuple: (label, input_field) widgets
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(StyleConstants.SPACING_SMALL)
        
        # Label
        label = QLabel(label_text)
        label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_SMALL}px; "
            f"font-weight: 500; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY};"
        )
        
        # Input field
        input_field = QLineEdit()
        input_field.setPlaceholderText(placeholder)
        if is_password:
            input_field.setEchoMode(QLineEdit.Password)
        
        input_field.setStyleSheet(f"""
            QLineEdit {{
                padding: {StyleConstants.PADDING_SMALL}px {StyleConstants.SPACING_MEDIUM}px;
                border: 1px solid {StyleConstants.COLOR_LIGHT};
                border-radius: {StyleConstants.RADIUS_SMALL}px;
                font-size: {StyleConstants.FONT_SIZE_MEDIUM}px;
                background-color: {StyleConstants.COLOR_WHITE};
                color: {StyleConstants.COLOR_DARKEST};
            }}
            QLineEdit:focus {{
                border: 2px solid {StyleConstants.COLOR_PRIMARY};
            }}
        """)
        
        layout.addWidget(label)
        layout.addWidget(input_field)
        
        return widget
    
    # -------------------------
    # INTEGRATION BUTTONS
    # -------------------------
    def _create_integration_buttons(self, connect_text, connect_callback, test_callback):
        """Create action buttons for integration cards.
        
        Args:
            connect_text (str): Text for the connect/disconnect button
            connect_callback (callable): Function to call when connect button is clicked
            test_callback (callable): Function to call when test button is clicked
            
        Returns:
            QWidget: Widget containing the action buttons
        """
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(StyleConstants.SPACING_MEDIUM)
        
        # Connect button
        connect_btn = self._create_primary_button(connect_text, connect_callback)
        
        btn_layout.addWidget(connect_btn)
        btn_layout.addStretch()
        
        return btn_layout
    
    # -------------------------
    # PROFILE ACTIONS
    # -------------------------
    def edit_profile(self):
        """Open the edit profile dialog."""
        dialog = EditProfileDialog(self.user_data, self)
        
        if dialog.exec() == QDialog.Accepted:
            updated_data = dialog.get_updated_data()
            self.user_data.update(updated_data)
            self.profile_updated.emit(self.user_data)
            
            QMessageBox.information(
                self,
                "Profile Updated",
                "Your profile has been updated successfully!"
            )
            self.close()
    
    # -------------------------
    # AUTHENTICATION ACTIONS
    # -------------------------
    def handle_logout(self):
        """Handle logout button click."""
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to logout?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.logout_requested.emit()
            self.accept()
    
    # -------------------------
    # SETUP GUIDES
    # -------------------------
    def show_gmail_setup_guide(self):
        """Display the Gmail API setup guide."""
        """Display Gmail API setup guide"""
        guide_text = """
<b>How to Get Gmail API Credentials</b>

<b>1. Create a Google Cloud Project:</b>
   • Go to: https://console.cloud.google.com/
   • Create a new project or select existing one

<b>2. Enable Gmail API:</b>
   • Navigate to "APIs & Services" → "Library"
   • Search for "Gmail API" and enable it

<b>3. Create OAuth 2.0 Credentials:</b>
   • Go to "APIs & Services" → "Credentials"
   • Click "Create Credentials" → "OAuth client ID"
   • Application type: "Desktop app"
   • Name it "WorkEase"

<b>4. Configure OAuth Consent Screen:</b>
   • Add scopes: gmail.readonly, gmail.modify, gmail.send
   • Add test users (your email)

<b>5. Download Credentials:</b>
   • Download the JSON file
   • Copy Client ID and Client Secret
   • Paste them in the fields above

<b>Note:</b> Keep your credentials secure and never share them!
        """
        
        self._show_info_dialog("Gmail API Setup Guide", guide_text)
    
    def show_slack_setup_guide(self):
        """Display the Slack setup guide."""
        """Display Slack User OAuth Token setup guide"""
        guide_text = """
<b>How to Get Your Slack User OAuth Token</b>

This token will let your desktop app send and receive messages as you, including direct messages.

<b>Step 1: Open Slack App Management</b>
   1. Go to: <a href="https://api.slack.com/apps">https://api.slack.com/apps</a>
   2. Click <b>Create New App</b> → <b>From scratch</b>
   3. Give your app a name, e.g., <b>MyUnifiedApp</b>, and choose your Slack workspace
   4. Click <b>Create App</b>

<b>Step 2: Add OAuth Scopes</b>
   1. In your app page, go to <b>OAuth & Permissions</b> on the left menu
   2. Scroll down to <b>User Token Scopes</b>
   3. Add the following scopes exactly:
      • <b>chat:write</b> → to send messages
      • <b>im:write</b> → to open DM channels
      • <b>im:history</b> → to read your direct messages
      • <b>users:read</b> → to get user info (IDs, names)
      • <b>channels:read</b> → to read public channels (optional)
      • <b>groups:read</b> → to read private channels (optional)
      • <b>mpim:read</b> → to read multi-person DMs

   <i>Tip: For just sending/receiving DMs, the first 4 scopes are enough.</i>

<b>Step 3: Install App to Workspace</b>
   1. Scroll up to <b>OAuth Tokens for Your Workspace</b>
   2. Click <b>Install to Workspace</b>
   3. Slack will ask for permissions — click <b>Allow</b>
   4. After installation, you'll see <b>User OAuth Token</b> (xoxp-…)
   
   Example: <code>xoxp-1234567890-123456789012-abcdefABCDEF123456</code>

<b>Step 4: Copy and Paste Token</b>
   Copy the User OAuth Token and paste it in the field above.

<b>Important:</b> Keep your token secure and never share it publicly!
        """
        
        self._show_info_dialog("Slack User OAuth Token Setup", guide_text)
    
    # -------------------------
    # CONNECTION HANDLERS
    # -------------------------
    def handle_gmail_connect(self, client_id_input, client_secret_input):
        """Handle Gmail connect button click.
        
        Args:
            client_id_input: Input field for client ID
            client_secret_input: Input field for client secret
        """
        client_id = client_id_input.text().strip()
        client_secret = client_secret_input.text().strip()
        
        if not client_id or not client_secret:
            QMessageBox.warning(
                self,
                "Missing Credentials",
                "Please enter both Client ID and Client Secret."
            )
            return
        
        # Current behavior shows the Gmail OAuth flow guidance steps.
        QMessageBox.information(
            self,
            "Gmail Connection",
            "Gmail OAuth flow will be implemented here.\n\n"
            "The app will:\n"
            "1. Open browser for Google authentication\n"
            "2. Get authorization\n"
            "3. Store access tokens securely\n"
            "4. Start syncing emails"
        )
    
    def handle_slack_connect(self, token_input):
        """Handle Slack connect button click.
        
        Args:
            token_input: Input field for Slack token
        """
        user_token = token_input.text().strip()
        
        if not user_token:
            QMessageBox.warning(
                self,
                "Missing Token",
                "Please enter your Slack User OAuth Token."
            )
            return
        
        # Validate token format
        if not user_token.startswith('xoxp-'):
            QMessageBox.warning(
                self,
                "Invalid Token",
                "User OAuth Token should start with 'xoxp-'\n\n"
                "Please check your token and try again."
            )
            return
        
        # Call parent's connect_slack method if available
        if hasattr(self, 'connect_slack_callback') and self.connect_slack_callback:
            success = self.connect_slack_callback(user_token)
            if success:
                QMessageBox.information(
                    self,
                    "Connected",
                    "Successfully connected to Slack!\n\n"
                    "Real-time message monitoring has started.\n"
                    "You can now send and receive DMs."
                )
                self.accept()  # Close settings dialog
            else:
                QMessageBox.warning(
                    self,
                    "Connection Failed",
                    "Could not connect to Slack.\n\n"
                    "Please check:\n"
                    "• Token is valid and not expired\n"
                    "• Token has required scopes\n"
                    "• Internet connection is active"
                )
        elif hasattr(self.parent(), 'connect_slack'):
            # Fallback: try parent's connect_slack method
            success = self.parent().connect_slack(user_token)
            if success:
                QMessageBox.information(
                    self,
                    "Connected",
                    "Successfully connected to Slack!\n\n"
                    "Real-time message monitoring has started."
                )
                self.accept()
        else:
            # No connection method available - show info
            QMessageBox.information(
                self,
                "Slack Connection",
                "Slack connection handler not yet implemented.\n\n"
                "Token format is valid. Connection feature coming soon!"
            )
    
    # -------------------------
    # CONNECTION TESTING
    # -------------------------
    def test_gmail_connection(self):
        """Test the Gmail API connection."""
        # Displays connection test expectations until a live API probe is wired.
        QMessageBox.information(
            self,
            "Test Gmail Connection",
            "This will test your Gmail API connection.\n\n"
            "It will verify:\n"
            "✓ API credentials are valid\n"
            "✓ Required scopes are granted\n"
            "✓ Can fetch emails\n"
            "✓ Can send emails"
        )
    
    def test_slack_connection(self):
        """Test the Slack API connection."""
        # Displays connection test expectations until a live API probe is wired.
        QMessageBox.information(
            self,
            "Test Slack Connection",
            "This will test your Slack API connection.\n\n"
            "It will verify:\n"
            "✓ Bot token is valid\n"
            "✓ App is installed in workspace\n"
            "✓ Required scopes are granted\n"
            "✓ Can read messages\n"
            "✓ Can send messages"
        )
    
    # -------------------------
    # DIALOG HELPERS
    # -------------------------
    def _show_info_dialog(self, title, text):
        """Show an information dialog with the given title and text.
        
        Args:
            title (str): Dialog title
            text (str): Dialog message text
        """
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setTextFormat(Qt.RichText)
        msg.setText(text)
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    # -------------------------
    # TONE SETTINGS TAB
    # -------------------------
    # -------------------------
    # TONE UI METRICS
    # Centralized spacing and control dimensions for tone settings widgets.
    # -------------------------
    def _tone_ui_metrics(self):
        return {"margin": StyleConstants.SPACING_XLARGE, "spacing": StyleConstants.SPACING_LARGE, "control_h": 34}

    # -------------------------
    # TONE UI TOKENS
    # Shared colors and visual tokens for tone settings cards/inputs.
    # -------------------------
    def _tone_ui_tokens(self):
        return {
            "text": StyleConstants.COLOR_DARKEST,
            "muted_text": StyleConstants.COLOR_DARK_PRIMARY,
            "card_bg": StyleConstants.COLOR_WHITE,
            "border": StyleConstants.COLOR_LIGHT,
            "input_bg": StyleConstants.COLOR_WHITE,
            "input_text": StyleConstants.COLOR_DARKEST,
            "input_focus": StyleConstants.COLOR_PRIMARY,
            "accent": StyleConstants.COLOR_DARK_PRIMARY,
        }

    # -------------------------
    # TONE SECTION FRAME FACTORY
    # Creates a consistent framed card for tone-related subsections.
    # -------------------------
    def _tone_section_frame(self):
        from PySide6.QtWidgets import QFrame
        tokens = self._tone_ui_tokens()
        section = QFrame()
        section.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {tokens['border']};
                border-radius: {StyleConstants.RADIUS_XLARGE}px;
                background-color: {tokens['card_bg']};
            }}
            QLabel {{
                border: none;
                background: transparent;
                color: {tokens['text']};
            }}
        """)
        return section

    # -------------------------
    # CREATE TONE SETTINGS TAB
    # Assembles default tone, auto-tone, stats, and learning controls.
    # -------------------------
    def _create_tone_settings_tab(self):
        scroll = self._create_scroll_area()
        tab = QWidget()
        metrics = self._tone_ui_metrics()
        tokens = self._tone_ui_tokens()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(metrics["margin"], metrics["margin"], metrics["margin"], metrics["margin"])
        layout.setSpacing(metrics["spacing"])

        layout.addWidget(self._create_section_header("Tone Settings"))
        layout.addWidget(self._create_description("Configure your default tone preferences and auto-suggestion settings."))

        layout.addWidget(self._create_default_tone_section())
        layout.addWidget(self._create_auto_tone_section())
        layout.addWidget(self._create_tone_statistics_section())
        layout.addWidget(self._create_learning_section())
        layout.addStretch()
        scroll.setWidget(tab)
        return scroll

    # -------------------------
    # CREATE DEFAULT TONE SECTION
    # Builds controls for selecting the profile's default outgoing tone.
    # -------------------------
    def _create_default_tone_section(self):
        from PySide6.QtWidgets import QComboBox
        section = self._tone_section_frame()
        tokens = self._tone_ui_tokens()
        metrics = self._tone_ui_metrics()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        layout.setSpacing(StyleConstants.SPACING_SMALL)

        layout.addWidget(self._create_subsection_header("Default Tone"))

        if self.orchestrator:
            current_default = self.orchestrator.tone_engine.user_profile.default_tone
            self.current_default_tone_lbl = QLabel(f"Current default: {get_tone_display_name(current_default)}")
            self.current_default_tone_lbl.setStyleSheet(f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; color: {tokens['muted_text']}; border: none;")
            layout.addWidget(self.current_default_tone_lbl)

            self.default_tone_combo = QComboBox()
            self.default_tone_combo.setMinimumHeight(metrics["control_h"])
            self.default_tone_combo.setMaximumWidth(280)
            for tone in ToneType:
                self.default_tone_combo.addItem(get_tone_display_name(tone), tone)
            idx = self.default_tone_combo.findData(current_default)
            if idx >= 0:
                self.default_tone_combo.setCurrentIndex(idx)
            self.default_tone_combo.currentIndexChanged.connect(self._on_default_tone_combo_changed)
            self.default_tone_combo.setStyleSheet(f"""
                QComboBox {{
                    border: 1px solid {tokens['border']};
                    border-radius: {StyleConstants.RADIUS_SMALL}px;
                    padding: {StyleConstants.PADDING_SMALL}px {StyleConstants.SPACING_MEDIUM}px;
                    background-color: {tokens['input_bg']};
                    color: {tokens['input_text']};
                    min-width: 180px;
                }}
                QComboBox QAbstractItemView {{
                    background-color: {tokens['input_bg']};
                    color: {tokens['input_text']};
                    border: 1px solid {tokens['border']};
                    selection-background-color: {StyleConstants.COLOR_LIGHT};
                }}
                QComboBox:focus {{
                    border: 2px solid {tokens['input_focus']};
                }}
            """)
            layout.addWidget(self.default_tone_combo, 0, Qt.AlignLeft)
        return section

    # -------------------------
    # CREATE AUTO-TONE SECTION
    # Builds toggle UI for enabling/disabling auto tone suggestions.
    # -------------------------
    def _create_auto_tone_section(self):
        section = self._tone_section_frame()
        tokens = self._tone_ui_tokens()
        metrics = self._tone_ui_metrics()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        layout.setSpacing(StyleConstants.SPACING_SMALL)

        layout.addWidget(self._create_subsection_header("Auto-Tone Suggestions"))

        layout.addWidget(self._create_description("Enable AI-powered tone suggestions based on message content and context."))

        if self.orchestrator:
            auto_enabled = self.orchestrator.tone_engine.user_profile.auto_tone_enabled
            self.auto_tone_status = QLabel(f"Status: {'Enabled' if auto_enabled else 'Disabled'}")
            self.auto_tone_status.setStyleSheet(f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; color: {tokens['accent'] if auto_enabled else tokens['muted_text']}; border: none;")
            layout.addWidget(self.auto_tone_status)

            self.auto_tone_toggle_btn = self._create_primary_button(
                f"{'Disable' if auto_enabled else 'Enable'} Auto-Tone",
                self._toggle_auto_tone
            )
            self.auto_tone_toggle_btn.setMinimumHeight(metrics["control_h"])
            self.auto_tone_toggle_btn.setMaximumWidth(280)
            layout.addWidget(self.auto_tone_toggle_btn, 0, Qt.AlignLeft)
        return section

    # -------------------------
    # CREATE TONE STATISTICS SECTION
    # Displays tone usage/profile statistics from tone engine.
    # -------------------------
    def _create_tone_statistics_section(self):
        section = self._tone_section_frame()
        tokens = self._tone_ui_tokens()
        metrics = self._tone_ui_metrics()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        layout.setSpacing(StyleConstants.SPACING_SMALL)

        layout.addWidget(self._create_subsection_header("Usage Statistics"))

        if self.orchestrator:
            self.tone_stats_label = QLabel()
            self.tone_stats_label.setTextFormat(Qt.RichText)
            self.tone_stats_label.setStyleSheet(f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; color: {tokens['muted_text']}; border: none;")
            layout.addWidget(self.tone_stats_label)
            self._update_tone_statistics()
        return section

    # -------------------------
    # UPDATE TONE STATISTICS
    # Refreshes statistics label from current tone engine state.
    # -------------------------
    def _update_tone_statistics(self):
        if not hasattr(self, "tone_stats_label") or not self.orchestrator:
            return
        stats = self.orchestrator.tone_engine.get_tone_statistics()
        stats_text = (
            f"<b>Default Tone:</b> {stats.get('default_tone', 'N/A')}<br>"
            f"<b>Auto-Tone:</b> {'Enabled' if stats.get('auto_tone_enabled') else 'Disabled'}<br>"
            f"<b>Manual Overrides:</b> {stats.get('total_manual_overrides', 0)}<br>"
            f"<b>Sender Preferences:</b> {stats.get('sender_preferences_count', 0)}<br>"
            f"<b>Domain Preferences:</b> {stats.get('domain_preferences_count', 0)}"
        )
        self.tone_stats_label.setText(stats_text)

    # -------------------------
    # CREATE LEARNING SECTION
    # Provides reset controls for learned tone preferences/history.
    # -------------------------
    def _create_learning_section(self):
        section = self._tone_section_frame()
        tokens = self._tone_ui_tokens()
        metrics = self._tone_ui_metrics()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        layout.setSpacing(StyleConstants.SPACING_SMALL)

        layout.addWidget(self._create_subsection_header("Learning & Reset"))

        layout.addWidget(self._create_description("The system learns from manual tone selections to improve suggestions."))

        reset_btn = self._create_danger_button("Reset Learning Data", self._reset_learning_data)
        reset_btn.setMinimumHeight(metrics["control_h"])
        reset_btn.setMaximumWidth(280)
        layout.addWidget(reset_btn, 0, Qt.AlignLeft)
        return section

    # -------------------------
    # DEFAULT TONE COMBO CHANGED
    # Converts combo selection to ToneType and applies update.
    # -------------------------
    def _on_default_tone_combo_changed(self, index):
        if not hasattr(self, "default_tone_combo"):
            return
        tone_val = self.default_tone_combo.itemData(index)
        try:
            tone = ToneType(tone_val)
            self._on_default_tone_changed(tone)
        except ValueError:
            pass

    # -------------------------
    # APPLY DEFAULT TONE CHANGE
    # Persists new default tone and updates dependent UI/state.
    # -------------------------
    def _on_default_tone_changed(self, tone):
        if self.orchestrator:
            self.orchestrator.tone_engine.set_default_tone(tone)
            if hasattr(self, "current_default_tone_lbl"):
                self.current_default_tone_lbl.setText(f"Current default: {get_tone_display_name(tone)}")
            self._update_tone_statistics()
            QMessageBox.information(self, "Default Tone Updated", f"Default tone changed to {get_tone_display_name(tone)}")

    # -------------------------
    # TOGGLE AUTO-TONE
    # Flips auto-tone state and refreshes labels/statistics.
    # -------------------------
    def _toggle_auto_tone(self):
        if self.orchestrator:
            tokens = self._tone_ui_tokens()
            current_state = self.orchestrator.tone_engine.user_profile.auto_tone_enabled
            new_state = not current_state
            self.orchestrator.tone_engine.set_auto_tone_enabled(new_state)
            self.auto_tone_status.setText(f"Status: {'Enabled' if new_state else 'Disabled'}")
            self.auto_tone_status.setStyleSheet(f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; color: {tokens['accent'] if new_state else tokens['muted_text']}; border: none;")
            if hasattr(self, "auto_tone_toggle_btn"):
                self.auto_tone_toggle_btn.setText(f"{'Disable' if new_state else 'Enable'} Auto-Tone")
            self._update_tone_statistics()
            QMessageBox.information(self, "Auto-Tone Updated", f"Auto-tone suggestions {'enabled' if new_state else 'disabled'}")

    # -------------------------
    # RESET LEARNING DATA
    # Clears learned tone history/preferences after confirmation.
    # -------------------------
    def _reset_learning_data(self):
        reply = QMessageBox.question(
            self,
            "Reset Learning Data",
            "Are you sure you want to reset all learning data? This will clear:\n"
            "• Manual override history\n"
            "• Sender preferences\n"
            "• Domain preferences\n"
            "• Tone effectiveness scores",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes and self.orchestrator:
            self.orchestrator.tone_engine.user_profile.manual_override_history = []
            self.orchestrator.tone_engine.user_profile.sender_preferences = {}
            self.orchestrator.tone_engine.user_profile.domain_preferences = {}
            self.orchestrator.tone_engine.user_profile.tone_effectiveness_scores = {tone: 0.5 for tone in ToneType}
            self.orchestrator.tone_engine._save_user_profile()
            QMessageBox.information(self, "Learning Data Reset", "All learning data has been successfully reset.")

    # -------------------------
    # AUTOMATION SETTINGS TAB
    # -------------------------
    # -------------------------
    # AUTOMATION UI TOKENS
    # Palette-aware color map used by automation tab controls.
    # -------------------------
    def _automation_ui_tokens(self):
        palette = self.palette()
        window = palette.window().color().name()
        base = palette.base().color().name()
        text = palette.text().color().name()
        button = palette.button().color().name()
        highlight = palette.highlight().color().name()
        return {
            "window": window,
            "base": base,
            "text": text,
            "button": button,
            "highlight": highlight,
            "border": StyleConstants.COLOR_LIGHT,
            "muted": StyleConstants.COLOR_DARK_PRIMARY,
        }

    def _append_unique_lines(self, editor: QTextEdit, values: list[str]):
        existing = {line.strip() for line in editor.toPlainText().splitlines() if line.strip()}
        for value in values:
            v = (value or "").strip()
            if v:
                existing.add(v)
        editor.setPlainText("\n".join(sorted(existing)))

    def _pick_allowlist_entries(self):
        text, ok = QFileDialog.getOpenFileName(
            self,
            "Pick one sample file to extract path root (optional)",
            "",
            "All Files (*.*)",
        )
        if ok and text:
            self._append_unique_lines(self.auto_reply_allowlist_text, [])

    def _pick_access_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Allowed Folder")
        if folder:
            self._append_unique_lines(self.file_access_paths_text, [folder])

    def _pick_access_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Allowed Files")
        if files:
            self._append_unique_lines(self.file_access_paths_text, files)

    def _create_automation_toggle_row(self, label_text: str, checked: bool, tokens: dict):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(StyleConstants.SPACING_MEDIUM)

        label = QLabel(label_text)
        label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; color: {tokens['text']}; border: none;"
        )
        label.setWordWrap(True)

        toggle = ToggleSwitch()
        toggle.setChecked(checked)

        row_layout.addWidget(label, 1)
        row_layout.addWidget(toggle, 0, Qt.AlignRight | Qt.AlignVCenter)
        return row, toggle

    def _create_automation_settings_tab(self):
        scroll = self._create_scroll_area()
        tab = QWidget()
        tokens = self._tone_ui_tokens()
        metrics = self._tone_ui_metrics()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(metrics["margin"], metrics["margin"], metrics["margin"], metrics["margin"])
        layout.setSpacing(metrics["spacing"])

        layout.addWidget(self._create_section_header("Automation Settings"))
        layout.addWidget(
            self._create_description(
                "Configure DND, auto-reply policy, sender allowlist, and file/folder access paths."
            )
        )

        input_style = f"""
            QTextEdit, QLineEdit {{
                border: 1px solid {tokens['border']};
                border-radius: {StyleConstants.RADIUS_SMALL}px;
                padding: {StyleConstants.PADDING_SMALL}px;
                background-color: {tokens['input_bg']};
                color: {tokens['input_text']};
            }}
            QTextEdit:focus, QLineEdit:focus {{
                border: 2px solid {tokens['input_focus']};
            }}
            QCheckBox {{
                color: {tokens['text']};
                spacing: 8px;
                border: none;
            }}
        """

        policy_section = self._tone_section_frame()
        policy_layout = QVBoxLayout(policy_section)
        policy_layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        policy_layout.setSpacing(StyleConstants.SPACING_SMALL)
        policy_layout.addWidget(self._create_subsection_header("Policy Controls"))
        policy_layout.addWidget(self._create_description("Core decision switches for DND, auto-reply, and manual confirmation."))

        dnd_row, self.dnd_enabled_checkbox = self._create_automation_toggle_row(
            "Enable DND (Do Not Disturb)",
            self.automation_settings.dnd_enabled,
            tokens,
        )
        policy_layout.addWidget(dnd_row)

        auto_row, self.auto_reply_enabled_checkbox = self._create_automation_toggle_row(
            "Enable Auto Reply (used only when DND is ON)",
            self.automation_settings.auto_reply_enabled,
            tokens,
        )
        policy_layout.addWidget(auto_row)

        def _on_dnd_toggled(checked):
            self.auto_reply_enabled_checkbox.setEnabled(checked)
            if not checked:
                self.auto_reply_enabled_checkbox.setChecked(False)

        self.dnd_enabled_checkbox.toggled.connect(_on_dnd_toggled)
        _on_dnd_toggled(self.dnd_enabled_checkbox.isChecked())


        confirm_row, self.require_user_confirm_plain_reply_checkbox = self._create_automation_toggle_row(
            "Require user confirmation for Plain Reply",
            self.automation_settings.require_user_confirm_plain_reply,
            tokens,
        )
        policy_layout.addWidget(confirm_row)
        layout.addWidget(policy_section)

        allowlist_section = self._tone_section_frame()
        allowlist_layout = QVBoxLayout(allowlist_section)
        allowlist_layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        allowlist_layout.setSpacing(StyleConstants.SPACING_SMALL)
        allowlist_layout.addWidget(self._create_subsection_header("Auto-Reply Allowlist"))
        allowlist_layout.addWidget(self._create_description("One sender identity per line (e.g., email or Slack user ID)."))
        self.auto_reply_allowlist_text = QTextEdit()
        self.auto_reply_allowlist_text.setPlaceholderText("sender@example.com\nU01234567")
        self.auto_reply_allowlist_text.setPlainText("\n".join(self.automation_settings.auto_reply_allowlist))
        self.auto_reply_allowlist_text.setMinimumHeight(110)
        self.auto_reply_allowlist_text.setStyleSheet(input_style)
        allowlist_layout.addWidget(self.auto_reply_allowlist_text)
        layout.addWidget(allowlist_section)

        access_section = self._tone_section_frame()
        access_layout = QVBoxLayout(access_section)
        access_layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        access_layout.setSpacing(StyleConstants.SPACING_SMALL)
        access_layout.addWidget(self._create_subsection_header("File & Folder Access"))
        access_layout.addWidget(self._create_description("Paths used for attachment lookup. Add folders/files below."))
        self.file_access_paths_text = QTextEdit()
        self.file_access_paths_text.setPlaceholderText("/home/user/Documents\n/home/user/Desktop/file.pdf")
        self.file_access_paths_text.setPlainText("\n".join(self.automation_settings.file_access_paths))
        self.file_access_paths_text.setMinimumHeight(130)
        self.file_access_paths_text.setStyleSheet(input_style)
        access_layout.addWidget(self.file_access_paths_text)

        picker_row = QHBoxLayout()
        add_folder_btn = self._create_primary_button("Add Folder", self._pick_access_folder)
        add_file_btn = self._create_primary_button("Add Files", self._pick_access_files)
        add_folder_btn.setMinimumHeight(metrics["control_h"])
        add_file_btn.setMinimumHeight(metrics["control_h"])
        picker_row.addWidget(add_folder_btn)
        picker_row.addWidget(add_file_btn)
        picker_row.addStretch()
        access_layout.addLayout(picker_row)

        max_label = QLabel("Max auto attachments (0-10)")
        max_label.setStyleSheet(f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; color: {tokens['muted_text']}; border: none;")
        access_layout.addWidget(max_label)
        self.max_auto_attachments_input = QLineEdit(str(self.automation_settings.max_auto_attachments))
        self.max_auto_attachments_input.setPlaceholderText("Max auto attachments (0-10)")
        self.max_auto_attachments_input.setMaximumWidth(220)
        self.max_auto_attachments_input.setStyleSheet(input_style)
        access_layout.addWidget(self.max_auto_attachments_input, 0, Qt.AlignLeft)
        layout.addWidget(access_section)

        actions_section = self._tone_section_frame()
        actions_layout = QVBoxLayout(actions_section)
        actions_layout.setContentsMargins(metrics["spacing"], metrics["spacing"], metrics["spacing"], metrics["spacing"])
        actions_layout.setSpacing(StyleConstants.SPACING_SMALL)
        actions_layout.addWidget(self._create_subsection_header("Save Changes"))
        actions_layout.addWidget(self._create_description("Apply and persist automation settings."))
        save_btn = self._create_primary_button("Save Automation Settings", self._save_automation_settings)
        save_btn.setMinimumHeight(metrics["control_h"])
        save_btn.setMaximumWidth(280)
        actions_layout.addWidget(save_btn, alignment=Qt.AlignLeft)
        layout.addWidget(actions_section)

        layout.addStretch()
        scroll.setWidget(tab)
        return scroll

    def _save_automation_settings(self):
        try:
            allowlist = [
                line.strip()
                for line in self.auto_reply_allowlist_text.toPlainText().splitlines()
                if line.strip()
            ]
            file_access_paths = [
                line.strip()
                for line in self.file_access_paths_text.toPlainText().splitlines()
                if line.strip()
            ]

            max_auto_attachments = int((self.max_auto_attachments_input.text() or "3").strip())
            if max_auto_attachments < 0 or max_auto_attachments > 10:
                raise ValueError("Max auto attachments must be between 0 and 10.")

            updated = AutomationSettings(
                dnd_enabled=self.dnd_enabled_checkbox.isChecked(),
                auto_reply_enabled=self.auto_reply_enabled_checkbox.isChecked(),
                auto_reply_allowlist=allowlist,
                file_access_paths=file_access_paths,
                max_auto_attachments=max_auto_attachments,
                require_user_confirm_plain_reply=self.require_user_confirm_plain_reply_checkbox.isChecked(),
            )

            if not self.orchestrator or not hasattr(self.orchestrator, "get_automation_coordinator"):
                QMessageBox.warning(self, "Automation Settings", "Automation coordinator is not available.")
                return

            coordinator = self.orchestrator.get_automation_coordinator()
            ok = coordinator.update_settings(updated)
            if not ok:
                QMessageBox.warning(self, "Automation Settings", "Failed to save automation settings.")
                return

            self.automation_settings = updated
            QMessageBox.information(self, "Automation Settings", "Automation settings updated successfully.")
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
        except Exception as e:
            QMessageBox.warning(self, "Automation Settings", f"Could not save settings: {e}")


# -------------------------
# EDIT PROFILE DIALOG CLASS
# -------------------------
class EditProfileDialog(QDialog):
    
    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self, user_data, parent=None):
        super().__init__(parent)
        
        self.user_data = user_data.copy()
        
        # -------------------------
        # DIALOG SETUP
        # -------------------------
        self._setup_dialog()
        
        # -------------------------
        # UI CONSTRUCTION
        # -------------------------
        self._build_ui()
    
    # -------------------------
    # SETUP DIALOG
    # Configures base title and minimum dimensions.
    # -------------------------
    def _setup_dialog(self):
        """Configure dialog properties"""
        self.setWindowTitle("Edit Profile")
        self.setMinimumSize(450, 350)
    
    # -------------------------
    # BUILD UI
    # Assembles profile fields, optional password section,
    # and action buttons for save/cancel.
    # -------------------------
    def _build_ui(self):
        """Build the dialog UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.FONT_SIZE_HERO,
            StyleConstants.FONT_SIZE_HERO
        )
        layout.setSpacing(StyleConstants.RADIUS_XLARGE)
        
        # Header
        header = QLabel("Edit Your Profile")
        header.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_TITLE}px; "
            f"font-weight: 600; "
            f"color: {StyleConstants.COLOR_DARKEST};"
        )
        
        layout.addWidget(header)
        layout.addSpacing(StyleConstants.PADDING_SMALL)
        
        # Name input
        layout.addWidget(self._create_name_field())
        
        # Email display (read-only)
        layout.addWidget(self._create_email_display())
        
        # Password section (if applicable)
        if self.user_data.get('auth_method') == 'email':
            layout.addWidget(self._create_password_section())
        
        layout.addStretch()
        
        # Action buttons
        layout.addLayout(self._create_action_buttons())
    
    # -------------------------
    # FORM FIELD CREATION
    # -------------------------
    def _create_name_field(self):
        """Create the name input field."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(StyleConstants.SPACING_SMALL)
        
        label = QLabel("Full Name")
        label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; "
            f"font-weight: 500; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY};"
        )
        
        self.name_input = QLineEdit()
        self.name_input.setText(self.user_data.get('name', ''))
        self.name_input.setPlaceholderText("Enter your full name")
        self.name_input.setStyleSheet(f"""
            QLineEdit {{
                padding: {StyleConstants.PADDING_MEDIUM}px {StyleConstants.FONT_SIZE_LARGE}px;
                border: 2px solid {StyleConstants.COLOR_LIGHT};
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                font-size: {StyleConstants.FONT_SIZE_LARGE}px;
                background-color: {StyleConstants.COLOR_WHITE};
                color: {StyleConstants.COLOR_DARKEST};
            }}
            QLineEdit:focus {{
                border: 2px solid {StyleConstants.COLOR_PRIMARY};
            }}
        """)
        
        layout.addWidget(label)
        layout.addWidget(self.name_input)
        
        return widget
    
    # -------------------------
    # CREATE EMAIL DISPLAY
    # Shows current email as read-only account identity field.
    # -------------------------
    def _create_email_display(self):
        """Create the email display field."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(StyleConstants.SPACING_SMALL)
        
        label = QLabel("Email Address")
        label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_MEDIUM}px; "
            f"font-weight: 500; "
            f"color: {StyleConstants.COLOR_DARK_PRIMARY};"
        )
        
        email_display = QLabel(self.user_data.get('email', ''))
        email_display.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_LARGE}px; "
            f"color: {StyleConstants.COLOR_GRAY_MEDIUM}; "
            f"padding: 2px 0;"
        )
        
        note = QLabel("Email cannot be changed")
        note.setStyleSheet(
            f"font-size: 11px; "
            f"color: {StyleConstants.COLOR_GRAY_MEDIUM}; "
            f"font-style: italic;"
        )
        
        layout.addWidget(label)
        layout.addWidget(email_display)
        layout.addWidget(note)
        
        return widget
    
    # -------------------------
    # CREATE PASSWORD SECTION
    # Provides password-management CTA for email-auth accounts.
    # -------------------------
    def _create_password_section(self):
        """Create the password change section."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(StyleConstants.PADDING_SMALL)

        section_label = QLabel("Password Management")
        section_label.setStyleSheet(
            f"font-size: {StyleConstants.FONT_SIZE_LARGE}px; "
            f"font-weight: 600; "
            f"color: {StyleConstants.COLOR_DARKEST};"
        )
        
        change_btn = QPushButton("Change Password")
        change_btn.setCursor(Qt.PointingHandCursor)
        change_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {StyleConstants.COLOR_WHITE};
                color: {StyleConstants.COLOR_DARK_PRIMARY};
                border: 2px solid {StyleConstants.COLOR_PRIMARY};
                padding: {StyleConstants.PADDING_SMALL}px {StyleConstants.RADIUS_XLARGE}px;
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                font-size: {StyleConstants.FONT_SIZE_MEDIUM}px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_LIGHT};
            }}
        """)
        change_btn.clicked.connect(self._handle_password_change)
        
        layout.addWidget(section_label)
        layout.addWidget(change_btn)
        
        return widget
    
    # -------------------------
    # BUTTON CREATION
    # -------------------------
    def _create_action_buttons(self):
        """Create the dialog action buttons."""
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(StyleConstants.SPACING_MEDIUM)
        
        # Save button
        save_btn = QPushButton("Save Changes")
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {StyleConstants.COLOR_PRIMARY};
                color: {StyleConstants.COLOR_WHITE};
                border: none;
                padding: {StyleConstants.SPACING_MEDIUM}px {StyleConstants.FONT_SIZE_HERO}px;
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                font-size: {StyleConstants.FONT_SIZE_LARGE}px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_DARK_PRIMARY};
            }}
        """)
        save_btn.clicked.connect(self._save_changes)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                padding: {StyleConstants.SPACING_MEDIUM}px {StyleConstants.FONT_SIZE_HERO}px;
                border: 2px solid {StyleConstants.COLOR_LIGHT};
                background-color: {StyleConstants.COLOR_WHITE};
                border-radius: {StyleConstants.RADIUS_MEDIUM}px;
                font-size: {StyleConstants.FONT_SIZE_LARGE}px;
                color: {StyleConstants.COLOR_DARK_PRIMARY};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {StyleConstants.COLOR_LIGHT};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        
        return btn_layout
    
    # -------------------------
    # PROFILE ACTIONS
    # -------------------------
    def _save_changes(self):
        """Validate and save profile changes"""
        new_name = self.name_input.text().strip()
        
        if not new_name:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Name cannot be empty."
            )
            return
        
        self.user_data['name'] = new_name
        self.accept()
    
    def _handle_password_change(self):
        """Handle password change request"""
        QMessageBox.information(
            self,
            "Change Password",
            "Password change functionality will be implemented here.\n\n"
            "This would typically involve:\n"
            "1. Verify current password\n"
            "2. Enter new password\n"
            "3. Confirm new password\n"
            "4. Update in backend"
        )
    
    # -------------------------
    # DATA RETRIEVAL
    # -------------------------
    def get_updated_data(self):
        """Get the updated user data.
        
        Returns:
            dict: Updated user data
        """
        return self.user_data
