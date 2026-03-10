#!/usr/bin/env python3
"""
AutoReturn - Unified Communication Management Application
Main Entry Point
"""

import sys
import os

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from src.frontend.ui.autoreturn_app import AutoReturnApp
from src.frontend.dialogs.auth_dialog import AuthDialog


# -------------------------
# MAIN
# Handles main functionality for the operation.
# -------------------------
def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application-wide font
    font = QFont()
    if sys.platform == "darwin":  # macOS
        font.setFamily(".AppleSystemUIFont")
    else:  # Windows/Linux
        font.setFamily("Segoe UI")
    app.setFont(font)
    
    # Show authentication dialog first
    auth_dialog = AuthDialog()
    
    # -------------------------
    # ON AUTHENTICATED
    # Event handler triggered when authenticated.
    # -------------------------
    def on_authenticated(user_data):
        """Callback when user is authenticated"""
        global main_window
        
        print(f" User authenticated: {user_data.get('email', 'Unknown')}")
        
        # Create and show main application window
        main_window = AutoReturnApp()
        main_window.set_user_info(user_data)
        main_window.show()
    
    # Connect authentication signal
    auth_dialog.authenticated.connect(on_authenticated)
    
    # Show auth dialog and exit if user cancels
    if auth_dialog.exec() != AuthDialog.Accepted:
        print("Authentication cancelled")
        sys.exit(0)
    
    # Start the application event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()