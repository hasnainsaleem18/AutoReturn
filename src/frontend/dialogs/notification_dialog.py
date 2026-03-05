# -------------------------
# NOTIFICATION DIALOG
# -------------------------
"""
Notification dialog for displaying and managing user notifications.

This module provides a user interface for viewing, marking as read,
and clearing notifications in the AutoReturn application.
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
from typing import List, Dict, Any, Optional

# Third-party imports
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QLabel, QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import QSize, Qt


# -------------------------
# NOTIFICATION DIALOG CLASS
# -------------------------
class NotificationDialog(QDialog):
    """Dialog for displaying and managing user notifications.
    
    This dialog shows a list of notifications with options to mark them as read
    or clear all notifications. Notifications can be sorted by time and are
    visually differentiated based on read/unread status.
    """
    
    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self, notifications: Optional[List[Dict[str, Any]]] = None, parent=None):
        """Initialize the notification dialog.
        
        Args:
            notifications: List of notification dictionaries with 'message', 'time', and 'read' keys
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.setWindowTitle("🔔 Notifications")
        self.setMinimumSize(500, 600)
        
        self.notifications = notifications or []
        
        layout = QVBoxLayout(self)
        
        # Header with unread count
        unread_count = sum(1 for n in self.notifications if not n.get('read', False))
        header_text = f"Notifications ({unread_count} unread)" if unread_count > 0 else "Notifications"
        header = QLabel(header_text)
        header.setStyleSheet("font-size: 20px; font-weight: 600; padding: 16px; color: #0FA4AF;")
        self.header_label = header
        
        # Notification list
        notif_list = QListWidget()
        self.notif_list = notif_list
        
        # Populate notifications
        self.populate_notifications()
        
        notif_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #AFDDE5;
                border-radius: 8px;
                background: white;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #AFDDE5;
                color: #003135;
            }
            QListWidget::item:hover {
                background: #AFDDE5;
            }
            QListWidget::item[read="true"] {
                color: #999;
                background: #f5f5f5;
            }
        """)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        mark_read_btn = QPushButton("Mark All Read")
        mark_read_btn.setObjectName("btnPrimary")
        mark_read_btn.clicked.connect(self.mark_all_read)
        
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("btnSecondary")
        clear_btn.clicked.connect(self.clear_all)
        
        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnSecondary")
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addWidget(mark_read_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(close_btn)
        
        layout.addWidget(header)
        layout.addWidget(notif_list)
        layout.addLayout(btn_layout)
    
    # -------------------------
    # NOTIFICATION MANAGEMENT
    # -------------------------
    def populate_notifications(self) -> None:
        """Populate the notification list with current notifications.
        
        Sorts notifications by time (newest first) and updates the UI.
        Shows an empty state message if no notifications are available.
        """
        self.notif_list.clear()
        
        if not self.notifications:
            # Show empty state
            item = QListWidgetItem("No notifications")
            item.setSizeHint(QSize(400, 40))
            self.notif_list.addItem(item)
            return
        
        # Sort by time (newest first)
        sorted_notifs = sorted(
            self.notifications,
            key=lambda n: n.get('time', ''),
            reverse=True
        )
        
        for notif in sorted_notifs:
            message = notif.get('message', '')
            time = notif.get('time', '')
            is_read = notif.get('read', False)
            
            # Format display text
            display_text = f"{message} • {time}"
            
            item = QListWidgetItem(display_text)
            item.setSizeHint(QSize(400, 50))
            
            # Mark read notifications differently
            if is_read:
                item.setData(1000, "true")  # Custom role for styling
            
            self.notif_list.addItem(item)
    
    def mark_all_read(self) -> None:
        """Mark all notifications as read.
        
        Updates the read status of all notifications and refreshes the UI.
        Shows a confirmation message when complete.
        """
        for notif in self.notifications:
            notif['read'] = True
        
        self.populate_notifications()
        
        # Update header
        self.header_label.setText("Notifications")
        
        QMessageBox.information(self, "Success", "All notifications marked as read!")
    
    def clear_all(self) -> None:
        """Clear all notifications after user confirmation.
        
        Shows a confirmation dialog before clearing all notifications.
        Updates the UI and shows a confirmation message when complete.
        """
        reply = QMessageBox.question(
            self,
            "Clear Notifications",
            "Are you sure you want to clear all notifications?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.notifications.clear()
            self.populate_notifications()
            self.header_label.setText("Notifications")
            QMessageBox.information(self, "Cleared", "All notifications cleared!")