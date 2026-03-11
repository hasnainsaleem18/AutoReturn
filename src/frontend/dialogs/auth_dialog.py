# -------------------------
# AUTHENTICATION DIALOG
# -------------------------
"""
Authentication dialog for user login and signup.

This module provides a user interface for authentication, including
login, signup, and password reset functionality.
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
import json
import os
import shutil
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from typing import Optional, Tuple

# Third-party imports
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QLineEdit, QWidget, QStackedWidget, QCheckBox,
    QMessageBox, QScrollArea, QInputDialog, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont


# -------------------------
# AUTH DIALOG CLASS
# -------------------------
class AuthDialog(QDialog):
    """Dialog for user authentication including login and signup.
    
    This dialog provides a tabbed interface for user authentication,
    supporting email/password login, social login, and new user registration.
    """
    
    # -------------------------
    # SIGNALS
    # -------------------------
    authenticated = Signal(dict)  # Emits user data on successful auth
    
    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self, parent=None):
        """Initialize the authentication dialog.
        
        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.setWindowTitle("AutoReturn - Welcome")
        self.setFixedSize(520, 720)
        self.setModal(True)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with gradient
        header = QWidget()
        header.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #024950, stop:1 #003135);
            }
        """)
        header.setFixedHeight(90)
        header_layout = QVBoxLayout(header)
        header_layout.setAlignment(Qt.AlignCenter)
        header_layout.setSpacing(4)
        
        # Logo/Title
        logo = QLabel("AutoReturn")
        logo.setStyleSheet("""
            font-size: 28px;
            font-weight: 700;
            color: #AFDDE5;
        """)
        logo.setAlignment(Qt.AlignCenter)
        
        tagline = QLabel("Unified Communication Management")
        tagline.setStyleSheet("""
            font-size: 13px;
            color: #AFDDE5;
        """)
        tagline.setAlignment(Qt.AlignCenter)
        
        header_layout.addWidget(logo)
        header_layout.addWidget(tagline)
        
        # Stacked widget for login/signup pages
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet("background-color: white;")
        
        # Create pages
        self.login_page = self.create_login_page()
        self.signup_page = self.create_signup_page()
        
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.signup_page)
        
        layout.addWidget(header)
        layout.addWidget(self.stacked_widget)

    # -------------------------
    # UI CREATION - LOGIN PAGE
    # -------------------------
    def create_login_page(self) -> QScrollArea:
        """Create the login page UI components.
        
        Returns:
            QScrollArea: Scrollable widget containing the login form
        """
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #AFDDE5;
            }
            QScrollBar::handle:vertical {
                background: #0FA4AF;
                border-radius: 4px;
            }
        """)
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 25, 40, 25)
        layout.setSpacing(12)
        
        # Welcome text
        welcome = QLabel("Welcome Back!")
        welcome.setStyleSheet("""
            font-size: 22px;
            font-weight: 600;
            color: #003135;
        """)
        welcome.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Sign in to continue to AutoReturn")
        subtitle.setStyleSheet("""
            font-size: 13px;
            color: #024950;
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(welcome)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        
        # Email input
        email_label = QLabel("Email Address")
        email_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #003135;
        """)
        
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("your.email@example.com")
        self.login_email.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QLineEdit:focus {
                border: 2px solid #0FA4AF;
            }
            QLineEdit:hover {
                border: 2px solid #0FA4AF;
            }
        """)
        
        layout.addWidget(email_label)
        layout.addWidget(self.login_email)
        layout.addSpacing(4)
        
        # Password input
        password_label = QLabel("Password")
        password_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #003135;
        """)
        
        self.login_password = QLineEdit()
        self.login_password.setPlaceholderText("Enter your password")
        self.login_password.setEchoMode(QLineEdit.Password)
        self.login_password.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QLineEdit:focus {
                border: 2px solid #0FA4AF;
            }
            QLineEdit:hover {
                border: 2px solid #0FA4AF;
            }
        """)
        
        layout.addWidget(password_label)
        layout.addWidget(self.login_password)
        layout.addSpacing(8)
        
        # Remember me & Forgot password
        options_widget = QWidget()
        options_layout = QHBoxLayout(options_widget)
        options_layout.setContentsMargins(0, 0, 0, 0)
        
        remember_me = QCheckBox("Remember me")
        remember_me.setStyleSheet("""
            QCheckBox {
                font-size: 12px;
                color: #024950;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #AFDDE5;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #0FA4AF;
                border-color: #0FA4AF;
            }
        """)
        
        forgot_password = QPushButton("Forgot Password?")
        forgot_password.setFlat(True)
        forgot_password.setCursor(Qt.PointingHandCursor)
        forgot_password.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #0FA4AF;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                color: #024950;
                text-decoration: underline;
            }
        """)
        forgot_password.clicked.connect(self.show_forgot_password)
        
        options_layout.addWidget(remember_me)
        options_layout.addStretch()
        options_layout.addWidget(forgot_password)
        
        layout.addWidget(options_widget)
        layout.addSpacing(8)
        
        # Login button
        login_btn = QPushButton("Sign In")
        login_btn.setCursor(Qt.PointingHandCursor)
        login_btn.setFixedHeight(42)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #0FA4AF;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #024950;
            }
            QPushButton:pressed {
                background-color: #003135;
            }
        """)
        login_btn.clicked.connect(self.handle_login)
        
        layout.addWidget(login_btn)
        layout.addSpacing(12)
        
        # Divider
        divider_widget = QWidget()
        divider_layout = QHBoxLayout(divider_widget)
        divider_layout.setContentsMargins(0, 0, 0, 0)
        
        line1 = QWidget()
        line1.setFixedHeight(1)
        line1.setStyleSheet("background-color: #AFDDE5;")
        
        or_label = QLabel("OR")
        or_label.setStyleSheet("""
            font-size: 11px;
            color: #024950;
            padding: 0 10px;
        """)
        
        line2 = QWidget()
        line2.setFixedHeight(1)
        line2.setStyleSheet("background-color: #AFDDE5;")
        
        divider_layout.addWidget(line1)
        divider_layout.addWidget(or_label)
        divider_layout.addWidget(line2)
        
        layout.addWidget(divider_widget)
        layout.addSpacing(12)
        
        # Social login buttons
        google_btn = QPushButton("Continue with Google")
        google_btn.setCursor(Qt.PointingHandCursor)
        google_btn.setFixedHeight(42)
        google_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #003135;
                border: 2px solid #AFDDE5;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                border-color: #0FA4AF;
                background-color: #AFDDE5;
            }
        """)
        google_btn.clicked.connect(lambda: self.handle_social_login("Google"))
        
        layout.addWidget(google_btn)
        layout.addSpacing(20)
        
        # Switch to signup
        signup_widget = QWidget()
        signup_layout = QHBoxLayout(signup_widget)
        signup_layout.setAlignment(Qt.AlignCenter)
        signup_layout.setContentsMargins(0, 0, 0, 0)
        
        signup_text = QLabel("Don't have an account?")
        signup_text.setStyleSheet("""
            font-size: 13px;
            color: #024950;
        """)
        
        signup_link = QPushButton("Sign Up")
        signup_link.setFlat(True)
        signup_link.setCursor(Qt.PointingHandCursor)
        signup_link.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #0FA4AF;
                font-size: 13px;
                font-weight: 600;
                padding: 0 5px;
            }
            QPushButton:hover {
                color: #024950;
            }
        """)
        signup_link.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.signup_page))
        
        signup_layout.addWidget(signup_text)
        signup_layout.addWidget(signup_link)
        
        layout.addWidget(signup_widget)
        layout.addStretch()
        
        scroll.setWidget(page)
        return scroll
    
    # -------------------------
    # UI CREATION - SIGNUP PAGE
    # -------------------------
    def create_signup_page(self) -> QScrollArea:
        """Create the signup page UI components.
        
        Returns:
            QScrollArea: Scrollable widget containing the signup form
        """
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #AFDDE5;
            }
            QScrollBar::handle:vertical {
                background: #0FA4AF;
                border-radius: 4px;
            }
        """)
        
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 20, 40, 20)
        layout.setSpacing(10)
        
        # Welcome text
        welcome = QLabel("Create Account")
        welcome.setStyleSheet("""
            font-size: 22px;
            font-weight: 600;
            color: #003135;
        """)
        welcome.setAlignment(Qt.AlignCenter)
        
        subtitle = QLabel("Join AutoReturn to streamline your communication")
        subtitle.setStyleSheet("""
            font-size: 12px;
            color: #024950;
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(welcome)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        
        # Full name input
        name_label = QLabel("Full Name")
        name_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #003135;
        """)
        
        self.signup_name = QLineEdit()
        self.signup_name.setPlaceholderText("John Doe")
        self.signup_name.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QLineEdit:focus {
                border: 2px solid #0FA4AF;
            }
            QLineEdit:hover {
                border: 2px solid #0FA4AF;
            }
        """)
        
        layout.addWidget(name_label)
        layout.addWidget(self.signup_name)
        layout.addSpacing(3)
        
        # Email input
        email_label = QLabel("Email Address")
        email_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #003135;
        """)
        
        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("your.email@example.com")
        self.signup_email.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QLineEdit:focus {
                border: 2px solid #0FA4AF;
            }
            QLineEdit:hover {
                border: 2px solid #0FA4AF;
            }
        """)
        
        layout.addWidget(email_label)
        layout.addWidget(self.signup_email)
        layout.addSpacing(3)
        
        # Password input
        password_label = QLabel("Password")
        password_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #003135;
        """)
        
        self.signup_password = QLineEdit()
        self.signup_password.setPlaceholderText("At least 8 characters")
        self.signup_password.setEchoMode(QLineEdit.Password)
        self.signup_password.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QLineEdit:focus {
                border: 2px solid #0FA4AF;
            }
            QLineEdit:hover {
                border: 2px solid #0FA4AF;
            }
        """)
        
        layout.addWidget(password_label)
        layout.addWidget(self.signup_password)
        layout.addSpacing(3)
        
        # Confirm password input
        confirm_label = QLabel("Confirm Password")
        confirm_label.setStyleSheet("""
            font-size: 12px;
            font-weight: 500;
            color: #003135;
        """)
        
        self.signup_confirm = QLineEdit()
        self.signup_confirm.setPlaceholderText("Re-enter password")
        self.signup_confirm.setEchoMode(QLineEdit.Password)
        self.signup_confirm.setStyleSheet("""
            QLineEdit {
                padding: 10px 14px;
                border: 2px solid #AFDDE5;
                border-radius: 8px;
                font-size: 14px;
                background-color: white;
                color: #003135;
            }
            QLineEdit:focus {
                border: 2px solid #0FA4AF;
            }
            QLineEdit:hover {
                border: 2px solid #0FA4AF;
            }
        """)
        
        layout.addWidget(confirm_label)
        layout.addWidget(self.signup_confirm)
        layout.addSpacing(8)
        
        # Terms checkbox
        self.terms_check = QCheckBox("I agree to the Terms of Service and Privacy Policy")
        self.terms_check.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                color: #024950;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #AFDDE5;
                border-radius: 4px;
                background: white;
            }
            QCheckBox::indicator:checked {
                background: #0FA4AF;
                border-color: #0FA4AF;
            }
        """)
        
        layout.addWidget(self.terms_check)
        layout.addSpacing(8)
        
        # Signup button
        signup_btn = QPushButton("Create Account")
        signup_btn.setCursor(Qt.PointingHandCursor)
        signup_btn.setFixedHeight(42)
        signup_btn.setStyleSheet("""
            QPushButton {
                background-color: #0FA4AF;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #024950;
            }
            QPushButton:pressed {
                background-color: #003135;
            }
        """)
        signup_btn.clicked.connect(self.handle_signup)
        
        layout.addWidget(signup_btn)
        layout.addSpacing(10)
        
        # Divider
        divider_widget = QWidget()
        divider_layout = QHBoxLayout(divider_widget)
        divider_layout.setContentsMargins(0, 0, 0, 0)
        
        line1 = QWidget()
        line1.setFixedHeight(1)
        line1.setStyleSheet("background-color: #AFDDE5;")
        
        or_label = QLabel("OR")
        or_label.setStyleSheet("""
            font-size: 11px;
            color: #024950;
            padding: 0 10px;
        """)
        
        line2 = QWidget()
        line2.setFixedHeight(1)
        line2.setStyleSheet("background-color: #AFDDE5;")
        
        divider_layout.addWidget(line1)
        divider_layout.addWidget(or_label)
        divider_layout.addWidget(line2)
        
        layout.addWidget(divider_widget)
        layout.addSpacing(10)
        
        # Social signup
        google_btn = QPushButton("Sign up with Google")
        google_btn.setCursor(Qt.PointingHandCursor)
        google_btn.setFixedHeight(42)
        google_btn.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #003135;
                border: 2px solid #AFDDE5;
                padding: 10px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                border-color: #0FA4AF;
                background-color: #AFDDE5;
            }
        """)
        google_btn.clicked.connect(lambda: self.handle_social_login("Google"))
        
        layout.addWidget(google_btn)
        layout.addSpacing(15)
        
        # Switch to login
        login_widget = QWidget()
        login_layout = QHBoxLayout(login_widget)
        login_layout.setAlignment(Qt.AlignCenter)
        login_layout.setContentsMargins(0, 0, 0, 0)
        
        login_text = QLabel("Already have an account?")
        login_text.setStyleSheet("""
            font-size: 13px;
            color: #024950;
        """)
        
        login_link = QPushButton("Sign In")
        login_link.setFlat(True)
        login_link.setCursor(Qt.PointingHandCursor)
        login_link.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #0FA4AF;
                font-size: 13px;
                font-weight: 600;
                padding: 0 5px;
            }
            QPushButton:hover {
                color: #024950;
            }
        """)
        login_link.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.login_page))
        
        login_layout.addWidget(login_text)
        login_layout.addWidget(login_link)
        
        layout.addWidget(login_widget)
        layout.addStretch()
        
        scroll.setWidget(page)
        return scroll
    
    # -------------------------
    # AUTHENTICATION HANDLERS
    # -------------------------
    # -------------------------
    # HANDLE LOGIN
    # Validates login form fields and emits authenticated user payload
    # when local checks pass.
    # -------------------------
    def handle_login(self):
        """Handle login button click.
        
        Validates the login form and attempts to authenticate the user.
        Emits the 'authenticated' signal on success.
        """
        email = self.login_email.text().strip()
        password = self.login_password.text()
        
        if not email or not password:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter both email and password."
            )
            return
        
        if not self._is_valid_email(email):
            QMessageBox.warning(
                self,
                "Invalid Email",
                "Please enter a valid email address."
            )
            return

        if len(password) < 8:
            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password must be at least 8 characters long."
            )
            return
        
        # TODO: Implement actual authentication logic here
        # For now, we'll simulate successful login
        user_data = {
            "email": email,
            "name": "Ajwad Ahmed",  # This would come from your backend
            "auth_method": "email"
        }
        
        self.authenticated.emit(user_data)
        self.accept()
    
    # -------------------------
    # HANDLE SIGNUP
    # Validates signup fields, terms acceptance, and password checks
    # before emitting authenticated user payload.
    # -------------------------
    def handle_signup(self):
        """Handle signup button click.
        
        Validates the signup form and attempts to create a new user account.
        Emits the 'authenticated' signal on success.
        """
        name = self.signup_name.text().strip()
        email = self.signup_email.text().strip()
        password = self.signup_password.text()
        confirm = self.signup_confirm.text()
        
        if not all([name, email, password, confirm]):
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in all fields."
            )
            return
        
        if not self._is_valid_email(email):
            QMessageBox.warning(
                self,
                "Invalid Email",
                "Please enter a valid email address."
            )
            return

        if hasattr(self, "terms_check") and not self.terms_check.isChecked():
            QMessageBox.warning(
                self,
                "Terms Not Accepted",
                "Please agree to the Terms of Service and Privacy Policy to create an account."
            )
            return
        
        if password != confirm:
            QMessageBox.warning(
                self,
                "Password Mismatch",
                "Passwords do not match. Please try again."
            )
            return
        
        if len(password) < 8:
            QMessageBox.warning(
                self,
                "Weak Password",
                "Password must be at least 8 characters long."
            )
            return
        
        # TODO: Implement actual registration logic here
        # For now, we'll simulate successful signup
        user_data = {
            "email": email,
            "name": name,
            "auth_method": "email"
        }
        
        QMessageBox.information(
            self,
            "Success",
            f"Welcome to WorkEase, {name}!"
        )
        
        self.authenticated.emit(user_data)
        self.accept()
    
    # -------------------------
    # SOCIAL LOGIN HANDLERS
    # -------------------------
    # -------------------------
    # HANDLE SOCIAL LOGIN
    # Handles provider-based authentication. Currently supports Google OAuth:
    # - ensure client secret JSON
    # - load/refresh token or run auth flow
    # - fetch user profile from Google userinfo endpoint
    # -------------------------
    def handle_social_login(self, provider: str):
        """Handle social login (Google, etc.)
        
        Args:
            provider: Name of the social login provider (e.g., 'Google')
        """
        if provider.lower() != "google":
            QMessageBox.information(
                self,
                f"{provider} Login",
                f"{provider} authentication is not implemented yet."
            )
            return

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
        except Exception:
            QMessageBox.warning(
                self,
                "Google Login",
                "Google OAuth libraries are missing.\nInstall requirements and restart the app."
            )
            return

        scopes = [
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
        ]

        try:
            client_secret_path = self._ensure_google_client_secret()
            if not client_secret_path:
                return

            token_path = self._google_login_token_path()
            os.makedirs(os.path.dirname(token_path), exist_ok=True)

            creds = None
            if os.path.exists(token_path):
                try:
                    creds = Credentials.from_authorized_user_file(token_path, scopes=scopes)
                except Exception:
                    creds = None

            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())

            if not creds or not creds.valid:
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes=scopes)
                creds = flow.run_local_server(
                    host="localhost",
                    port=0,
                    open_browser=True,
                    authorization_prompt_message=(
                        "Your browser has been opened for Google sign in.\n"
                        "Complete sign in, then return to AutoReturn."
                    ),
                )
                with open(token_path, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())

            user_info = self._fetch_google_user_info(creds.token)
            email = (user_info.get("email") or "").strip()
            name = (user_info.get("name") or "").strip()

            if not email:
                QMessageBox.warning(
                    self,
                    "Google Login",
                    "Google login succeeded but email could not be retrieved."
                )
                return

            if not name:
                name = email.split("@")[0].replace(".", " ").title()

            user_data = {
                "email": email,
                "name": name,
                "auth_method": "google",
                "google_sub": user_info.get("sub", "")
            }

            self.authenticated.emit(user_data)
            self.accept()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Google Login Failed",
                f"Authentication failed:\n{exc}"
            )

    # -------------------------
    # GET PROJECT ROOT
    # Resolves repository root relative to this dialog module path.
    # -------------------------
    def _project_root(self) -> str:
        """Get project root path from this file location."""
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    # -------------------------
    # GET GOOGLE CLIENT SECRET PATH
    # Returns canonical path where OAuth client secret is stored for app usage.
    # -------------------------
    def _google_client_secret_path(self) -> str:
        """Path for Google OAuth client secret JSON used by app."""
        return os.path.join(self._project_root(), "data", "gmail_data", "client_secret.json")

    # -------------------------
    # GET GOOGLE LOGIN TOKEN PATH
    # Returns canonical location for persisted Google login token.
    # -------------------------
    def _google_login_token_path(self) -> str:
        """Path for storing Google login token."""
        return os.path.join(self._project_root(), "data", "auth", "google_login_token.json")

    # -------------------------
    # ENSURE GOOGLE CLIENT SECRET
    # Ensures OAuth client JSON exists and is valid. If missing/invalid,
    # prompts user to select a file and copies it into the project data path.
    # -------------------------
    def _ensure_google_client_secret(self) -> Optional[str]:
        """Ensure client secret exists; optionally prompt user to select JSON."""
        target_path = self._google_client_secret_path()
        if os.path.exists(target_path):
            if self._is_valid_google_client_secret(target_path):
                return target_path
            QMessageBox.warning(
                self,
                "Google OAuth Setup",
                "Existing client_secret.json is invalid.\nSelect a valid OAuth Desktop client file."
            )
        else:
            QMessageBox.information(
                self,
                "Google OAuth Setup",
                "Select your Google OAuth Desktop client JSON (client_secret.json)."
            )

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Google OAuth client_secret.json",
            os.path.expanduser("~"),
            "JSON Files (*.json);;All Files (*)",
        )

        file_path = (file_path or "").strip()
        if not file_path:
            return None
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Google OAuth Setup", "Selected file path does not exist.")
            return None
        if not self._is_valid_google_client_secret(file_path):
            QMessageBox.warning(
                self,
                "Google OAuth Setup",
                "Selected JSON is not a valid OAuth Desktop/Web client secret file."
            )
            return None

        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            shutil.copyfile(file_path, target_path)
            return target_path
        except Exception as exc:
            QMessageBox.warning(self, "Google OAuth Setup", f"Could not copy file:\n{exc}")
            return None

    # -------------------------
    # VALIDATE GOOGLE CLIENT SECRET
    # Verifies expected OAuth JSON structure and required keys.
    # -------------------------
    def _is_valid_google_client_secret(self, file_path: str) -> bool:
        """Validate Google OAuth client secret JSON shape."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
            client = data.get("installed") or data.get("web")
            if not isinstance(client, dict):
                return False
            if not client.get("client_id") or not client.get("client_secret"):
                return False
            redirect_uris = client.get("redirect_uris") or []
            return isinstance(redirect_uris, list) and len(redirect_uris) > 0
        except Exception:
            return False

    # -------------------------
    # FETCH GOOGLE USER INFO
    # Calls OpenID userinfo endpoint using access token and returns
    # profile payload (email/name/sub).
    # -------------------------
    def _fetch_google_user_info(self, access_token: str) -> dict:
        """Fetch Google profile (email/name) using access token."""
        req = UrlRequest(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        try:
            with urlopen(req, timeout=15) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise RuntimeError(f"userinfo request failed ({exc.code})") from exc
        except URLError as exc:
            raise RuntimeError(f"Could not reach Google userinfo endpoint: {exc.reason}") from exc

        data = json.loads(body)
        if not isinstance(data, dict):
            raise RuntimeError("Invalid user info response")
        return data
    
    # -------------------------
    # PASSWORD RECOVERY
    # -------------------------
    def show_forgot_password(self):
        """Show forgot password dialog and handle password reset request.
        
        Prompts the user for their email address and initiates the
        password reset process.
        """
        email, ok = self.get_email_input(
            "Reset Password",
            "Enter your email address to reset your password:"
        )
        
        if not ok or not email:
            return

        email = email.strip()

        if not self._is_valid_email(email):
            QMessageBox.warning(
                self,
                "Invalid Email",
                "Please enter a valid email address."
            )
            return

        QMessageBox.information(
            self,
            "Check Your Email",
            f"Password reset instructions have been sent to {email}"
        )
    
    # -------------------------
    # HELPER METHODS
    # -------------------------
    # -------------------------
    # GET EMAIL INPUT
    # Shows an input dialog and returns (email, confirmed).
    # -------------------------
    def get_email_input(self, title: str, message: str) -> Tuple[str, bool]:
        """Display a dialog to get email input from the user.
        
        Args:
            title: Dialog window title
            message: Prompt message to display
            
        Returns:
            tuple: (email_text, ok_clicked) where ok_clicked is True if user clicked OK
        """
        from PySide6.QtWidgets import QInputDialog
        email, ok = QInputDialog.getText(
            self,
            title,
            message,
            QLineEdit.Normal,
            ""
        )
        return email, ok

    # -------------------------
    # VALIDATE EMAIL FORMAT
    # Performs lightweight structural checks for email-like format.
    # -------------------------
    def _is_valid_email(self, email: str) -> bool:
        """Validate email address format.
        
        Args:
            email: Email address to validate
            
        Returns:
            bool: True if email format is valid, False otherwise
        """
        email = (email or "").strip()
        if not email or "@" not in email:
            return False
        local, _, domain = email.partition("@")
        if not local or not domain or "." not in domain:
            return False
        return True
