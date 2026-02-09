# -------------------------
# AUTO RETURN MAIN APPLICATION
# -------------------------
"""
Main application window for AutoReturn, providing a unified inbox interface
for managing emails and messages across multiple services.
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple

# Third-party imports
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QSizePolicy, QMessageBox, QDialog, QTextEdit,
    QFileDialog, QApplication, QStyle, QSizePolicy, QSpacerItem
)
from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, Slot, QObject, QEvent, QUrl
from PySide6.QtGui import (QColor, QIcon, QPixmap, QFont, QFontMetrics, 
                          QPainter, QPen, QAction, QKeySequence, QDesktopServices)

# Local application imports
from src.frontend.ui.styles import get_stylesheet
from src.frontend.dialogs.notification_dialog import NotificationDialog
from src.frontend.dialogs.settings_dialog import SettingsDialog
from src.frontend.dialogs.send_slack_message_dialog import SendSlackMessageDialog

# Backend services
from src.backend.services.slack_backend import SlackService, SlackMessage
from src.backend.services.gmail_backend import GmailIntegrationService
from src.backend.services.ai_service import OllamaService, QueueSummaryGenerator
from src.frontend.dialogs.send_gmail_reply_dialog import SendGmailReplyDialog
from src.frontend.ui.styles import get_stylesheet

# Backend service imports
from src.backend.services.slack_backend import (
    SlackService,
    SlackMessageListener,
    validate_user_token,
    format_message_time
)

from src.backend.services.ai_service import (
    OllamaService,
    SummaryGeneratorThread,
    QueueSummaryGenerator
)

import asyncio
from src.backend.services.gmail_backend import GmailIntegrationService
from src.backend.models.agent_models import AgentRequest, AgentResponse, Intent


# -------------------------
# AGENT WORKER THREAD
# -------------------------
class AgentWorker(QThread):
    """Worker thread for running async agent requests without blocking the UI."""
    result_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, coro):
        super().__init__()
        self.coro = coro

    def run(self):
        print(f"⚙️ AgentWorker: Starting background task...")
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Run the async agent call
            response = loop.run_until_complete(self.coro)
            
            # Emit result
            print(f"✅ AgentWorker: Task complete, emitting result...")
            self.result_ready.emit(response)
        except Exception as e:
            print(f"❌ AgentWorker: Task failed: {e}")
            self.error_occurred.emit(str(e))
        finally:
            loop.close()
            print(f"🛑 AgentWorker: Loop closed")


# -------------------------
# MAIN APPLICATION CLASS
# -------------------------

class AutoReturnApp(QMainWindow):
    """Main application window for AutoReturn.
    
    This class serves as the primary interface for the AutoReturn application,
    integrating email and messaging services with a unified inbox view.
    """
    
    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self):
        """Initialize the AutoReturn application window."""
        super().__init__()
        self.user_data = None
        self.setWindowTitle("AutoReturn - Unified Inbox")
        self.setMinimumSize(1400, 900)
        
        # -------------------------
        # ORCHESTRATOR INITIALIZATION (NEW ARCHITECTURE)
        # -------------------------
        from src.backend.core.orchestrator import Orchestrator
        
        # Initialize orchestrator (the brain that coordinates everything)
        self.orchestrator = Orchestrator(ollama_model="kimi-k2.5:cloud")
        
        # Get agents from orchestrator (not direct services)
        self.gmail_agent = self.orchestrator.get_agent("gmail")
        self.slack_agent = self.orchestrator.get_agent("slack")
        
        # Get underlying services for backward compatibility with existing UI code
        # (These will be phased out as we migrate to agent-based calls)
        self.slack_service = self.slack_agent.backend
        self.gmail_service = self.gmail_agent.backend
        self.ollama_service = self.orchestrator.ai_service
        
        # Slack listener
        self.slack_listener = None
        self.slack_users = []
        
        # Connect service signals (still using services for signals until full migration)
        self._connect_slack_signals()
        self._connect_gmail_signals()
        
        # Summary generation queue
        self.queue_summary_generator = QueueSummaryGenerator(self.ollama_service, max_concurrent=2)
        self.queue_summary_generator.summary_generated.connect(self.on_summary_generated)
        self.queue_summary_generator.progress_update.connect(self.on_summary_progress)
        self.queue_summary_generator.batch_complete.connect(self.on_batch_summary_complete)
        self.summary_threads = {}  # Track active summary generation threads
        
        self.active_workers = []  # Track all active agent workers to prevent GC
        self._is_syncing_gmail = False # Flag to prevent overlapping syncs
        self.messages = []
        self.notifications = []
        
        self.active_filter = 'all'
        self.current_sort_column = None
        self.sort_order = Qt.AscendingOrder
        self.expanded_row = None
        self.search_query = ""
        self.search_filters = None
        
        self.setup_ui()
        self.setStyleSheet(get_stylesheet())
        
        self.time_refresh_timer = QTimer()
        self.time_refresh_timer.timeout.connect(self.refresh_message_times)
        self.time_refresh_timer.start(60000)
        
        self.gmail_refresh_timer = QTimer()
        self.gmail_refresh_timer.timeout.connect(self.auto_sync_gmail)
        # Check every 30 seconds to allow time for AI processing without overload
        self.gmail_refresh_timer.start(30000)
        
        self._try_auto_connect_slack()
        self._try_auto_connect_gmail()
    


    
    # -------------------------
    # SIGNAL CONNECTIONS
    # -------------------------
    # -------------------------
    # SIGNAL CONNECTIONS
    # -------------------------
    # -------------------------
    # SLACK INTEGRATION - SIGNAL HANDLING
    # -------------------------
    def _connect_slack_signals(self):
        """Connect signals from Slack service to application slots."""
        self.slack_service.connection_status.connect(self.on_slack_connection_status)
        self.slack_service.new_messages.connect(self.on_slack_new_messages)
        self.slack_service.message_sent.connect(self.on_slack_message_sent)
        self.slack_service.users_loaded.connect(self.on_slack_users_loaded)
        self.slack_service.error_occurred.connect(self.on_slack_error)
    
    # -------------------------
    # SLACK INTEGRATION
    # -------------------------
    # -------------------------
    # SLACK INTEGRATION - CONNECTION MANAGEMENT
    # -------------------------
    def _try_auto_connect_slack(self):
        """Attempt to automatically connect to Slack using stored credentials."""
        try:
            import keyring
            token = keyring.get_password("autoreturn", "slack_token")
            if token:
                print("Auto-connecting to Slack...")
                self.connect_slack(token)
        except:
            pass

    # -------------------------
    # HELPER METHODS
    # -------------------------
    # -------------------------
    # HELPER METHODS
    # -------------------------
    # -------------------------
    # FILE SYSTEM UTILITIES
    # -------------------------
    def _get_gmail_data_dir(self):
        """Get the directory path for storing Gmail data.
        
        Returns:
            str: Path to the Gmail data directory
        """
        # Use the data directory at the project root
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        base_dir = os.path.join(project_root, "data", "gmail_data")
        try:
            os.makedirs(base_dir, exist_ok=True)
        except Exception as exc:
            print(f"Failed to prepare Gmail data dir: {exc}")
        return base_dir

    # -------------------------
    # GMAIL INTEGRATION - SIGNAL HANDLING
    # -------------------------
    def _connect_gmail_signals(self):
        """Connect signals from Gmail service to application slots."""
        self.gmail_service.connection_status.connect(self.on_gmail_connection_status)
        self.gmail_service.new_messages.connect(self.on_gmail_new_messages)
        self.gmail_service.error_occurred.connect(self.on_gmail_error)

    # -------------------------
    # GMAIL INTEGRATION
    # -------------------------
    # -------------------------
    # GMAIL INTEGRATION - CONNECTION MANAGEMENT
    # -------------------------
    def _try_auto_connect_gmail(self):
        """Attempt to automatically connect to Gmail using stored credentials."""
        if self.gmail_service.has_token():
            success, message = self.gmail_service.connect(allow_flow=False)
            print(f"Gmail: {message}")
            if success:
                self.handle_gmail_sync(quiet=True)
    
    # -------------------------
    # USER MANAGEMENT
    # -------------------------
    def set_user_info(self, user_data):
        """Set the current user's information.
        
        Args:
            user_data (dict): Dictionary containing user information
        """
        self.user_data = user_data
        if 'connected_accounts' not in self.user_data:
            self.user_data['connected_accounts'] = {
                'gmail': False,
                'slack': False
            }

        if self.slack_service.is_connected:
            self.user_data['connected_accounts']['slack'] = True
        if self.gmail_service.is_connected:
            self.user_data['connected_accounts']['gmail'] = True

        if hasattr(self, 'user_name_label'):
            self.user_name_label.setText(self.user_data.get('name', 'User'))
    
    # -------------------------
    # SLACK EVENT HANDLERS
    # -------------------------
    # -------------------------
    # SLACK EVENT HANDLERS
    # -------------------------
    def on_slack_connection_status(self, connected: bool, message: str):
        """Handle Slack connection status changes.
        
        Args:
            connected (bool): Whether the connection was successful
            message (str): Status message
        """
        print(f"Slack: {message}")
        
        if connected:
            if self.user_data:
                if 'connected_accounts' not in self.user_data:
                    self.user_data['connected_accounts'] = {}
                self.user_data['connected_accounts']['slack'] = True
            
            self.start_slack_listener()
            
            print("Fetching initial messages...")
            initial_messages = self.slack_service.fetch_all_messages(limit=50)
            if initial_messages:
                self.on_slack_new_messages(initial_messages)
            
            self.notifications.append({
                'message': f"Connected to Slack: {message}",
                'time': 'just now',
                'read': False,
                'priority': 'normal'
            })
            
            unread_count = sum(1 for n in self.notifications if not n.get('read', False))
            if hasattr(self, 'notif_badge'):
                self.notif_badge.setText(str(unread_count))
    
    def on_slack_new_messages(self, new_messages: list):
        """Handle new messages received from Slack.
        
        Args:
            new_messages (list): List of new message dictionaries
        """
        if not new_messages:
            return

        print(f"Processing {len(new_messages)} new messages")

        self.messages.extend(new_messages)
        self.messages.sort(key=lambda x: float(x.get('timestamp', 0)), reverse=True)
        
        self.populate_table()
        
        # Generate AI summaries for new messages
        self.generate_summaries_for_messages(new_messages)
        
        for msg in new_messages:
            sender = msg.get('sender', 'Unknown')
            preview = msg.get('preview', '')[:50]
            time = msg.get('time', 'just now')
            priority = msg.get('priority', 'normal')
            
            notif_message = f"New message from {sender}: {preview}"
            if priority == 'urgent':
                notif_message = f"URGENT - {notif_message}"
            
            self.notifications.append({
                'message': notif_message,
                'time': time,
                'read': False,
                'priority': priority
            })
            
            print(f"{notif_message}")

        unread_count = sum(1 for n in self.notifications if not n.get('read', False))
        if hasattr(self, 'notif_badge'):
            self.notif_badge.setText(str(unread_count))
    
    def on_slack_message_sent(self, success: bool, message: str):
        """Handle completion of a Slack message send operation.
        
        Args:
            success (bool): Whether the message was sent successfully
            message (str): Status message
        """
        if success:
            QMessageBox.information(self, "Message Sent", message)
        else:
            QMessageBox.warning(self, "Send Failed", message)
    
    def on_slack_users_loaded(self, users: list):
        """Handle when Slack users are loaded.
        
        Args:
            users (list): List of user dictionaries
        """
        self.slack_users = users
        print(f"👥 Loaded {len(users)} Slack users")
    
    def on_slack_error(self, error_message: str):
        """Handle errors from the Slack service.
        
        Args:
            error_message (str): Error message
        """
        print(f"{error_message}")
        if "connection" in error_message.lower() or "auth" in error_message.lower():
            QMessageBox.warning(self, "Slack Error", error_message)
    
    # -------------------------
    # SLACK INTEGRATION - MESSAGE HANDLING
    # -------------------------
    def start_slack_listener(self):
        """Start listening for real-time Slack messages."""
        if self.slack_listener:
            self.slack_listener.stop()
        
        self.slack_listener = SlackMessageListener(self.slack_service, poll_interval=10)
        self.slack_listener.new_messages.connect(self.on_slack_new_messages)
        self.slack_listener.error_occurred.connect(self.on_slack_error)
        self.slack_listener.start()
        print("Slack listener started (10s interval)")

    def stop_slack_listener(self):
        """Stop listening for real-time Slack messages."""
        if self.slack_listener:
            self.slack_listener.stop()
            self.slack_listener = None
    
    def connect_slack(self, user_token: str) -> bool:
        is_valid, error_msg = validate_user_token(user_token)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Token", error_msg)
            return False
        
        success = self.slack_service.connect(user_token)
        
        if success:
            try:
                import keyring
                keyring.set_password("autoreturn", "slack_token", user_token)
            except:
                pass
        
        return success
    
    def disconnect_slack(self):
        """Disconnect from Slack and clean up resources."""
        self.stop_slack_listener()
        self.slack_service.disconnect()
        
        self.messages = [msg for msg in self.messages if msg.get('source') != 'slack']
        self.populate_table()
        
        try:
            import keyring
            keyring.delete_password("autoreturn", "slack_token")
        except:
            pass
    
    def sync_all_messages(self):
        """Synchronize all messages from connected services using the Orchestrator."""
        # Reset filters so new messages are visible
        self.active_filter = 'all'
        self.search_filters = None
        self.search_bar.clear()
        
        self.show_status_message("Syncing all messages via Orchestrator...")
        
        # We can use a natural language command or direct routing
        # For simplicity in code, let's use the natural language entry point
        worker = AgentWorker(self.orchestrator.process_user_command("sync all messages"))
        worker.result_ready.connect(self.on_all_sync_complete)
        worker.error_occurred.connect(self.on_agent_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        
        # Keep alive by storing in list
        self.active_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        """Clean up finished worker thread."""
        if worker in self.active_workers:
            self.active_workers.remove(worker)
        worker.deleteLater()

    def on_all_sync_complete(self, response: AgentResponse):
        """Handle completion of unified sync from Orchestrator."""
        if response.success:
            messages = response.data.get("messages", [])
            errors = response.data.get("errors", [])
            
            if errors:
                error_msg = "\n".join(errors)
                print(f"⚠️ Sync warnings: {error_msg}")
                self.show_status_message(f"Sync complete with errors (see log)")
            
            if messages:
                # Separate by source for current UI handlers
                gmail_msgs = [m for m in messages if m.get('source') == 'gmail']
                slack_msgs = [m for m in messages if m.get('source') == 'slack']
                
                if gmail_msgs:
                    self.on_gmail_new_messages(gmail_msgs)
                if slack_msgs:
                    self.on_slack_new_messages(slack_msgs)
                
                self.show_status_message(f"Fetched {len(messages)} total messages")
            else:
                self.show_status_message("No new messages found")
        else:
            self.on_agent_error(response.error or "Sync failed")


    def on_agent_error(self, error_message: str):
        """Handle errors from agent workers."""
        self._is_syncing_gmail = False
        print(f"❌ Agent Error: {error_message}")
        self.show_status_message(f"Error: {error_message}")
        # QMessageBox.warning(self, "Agent Error", error_message)

    
    # -------------------------
    # AI SUMMARY GENERATION
    # -------------------------
    def generate_all_summaries(self):
        """Manually trigger summary generation for all messages."""
        """Manually trigger summary generation for all messages"""
        if not self.ollama_service.check_connection():
            QMessageBox.warning(
                self, 
                "Ollama Not Running", 
                "Ollama is not running or not accessible.\n\n"
                "Please make sure Olloma is running:\n"
                "1. Open terminal\n"
                "2. Run: olloma serve\n\n"
                "Or check if it's already running in the background."
            )
            return
        
        if not self.messages:
            QMessageBox.information(
                self,
                "No Messages",
                "There are no messages to generate summaries for."
            )
            return
        
        # Generate summaries for all messages
        self.generate_summaries_for_messages(self.messages)
        
        QMessageBox.information(
            self,
            "Generating Summaries",
            f"Started generating AI summaries for {len(self.messages)} messages.\n\n"
            "This may take a few moments. Summaries will appear as they are generated."
        )

    # -------------------------
    # MESSAGE COMPOSITION
    # -------------------------
    def show_send_message_dialog(self, message_data):
        """Display the dialog for sending a new message.
        
        Args:
            message_data (dict): Message data for pre-filling the dialog
        """
        source = message_data.get('source', '')
        
        if source == 'slack':
            if not self.slack_service.is_connected:
                QMessageBox.warning(self, "Not Connected", "Please connect to Slack first.")
                return
            
            if not self.slack_users:
                QMessageBox.warning(self, "Loading", "Slack users are still loading. Please wait.")
                return
            
            dialog = SendSlackMessageDialog(self.slack_users, self)
            
            if message_data.get('is_dm'):
                sender = message_data.get('sender', '')
                for user in self.slack_users:
                    if user.get('real_name') == sender:
                        dialog.user_combo.setCurrentText(f"{user['real_name']} (@{user['name']})")
                        break
            
            if dialog.exec() == QDialog.Accepted:
                selected_user = dialog.get_selected_user()
                message_text = dialog.get_message_text()
                
                if selected_user and message_text:
                    self.slack_service.send_dm_by_id(selected_user['id'], message_text)
        
        elif source == 'gmail':
            if not self.gmail_service.is_connected:
                QMessageBox.warning(self, "Gmail", "Please connect to Gmail first.\n\nGo to Settings → Integrations → Gmail")
                return
            to_email = message_data.get('email', '')
            subject = message_data.get('subject', '(No Subject)')
            dialog = SendGmailReplyDialog(to_email, subject, self)
            if dialog.exec() == QDialog.Accepted:
                reply_text = dialog.get_message_text()
                if reply_text:
                    success, msg = self.gmail_service.reply_to_message(message_data, reply_text)
                    if success:
                        QMessageBox.information(self, "Gmail Reply", msg)
                    else:
                        QMessageBox.warning(self, "Gmail Reply", msg)
        else:
            QMessageBox.warning(self, "Unknown Source", f"Cannot send to: {source}")

    # -------------------------
    # GMAIL EVENT HANDLERS
    # -------------------------
    # -------------------------
    # GMAIL EVENT HANDLERS
    # -------------------------
    def on_gmail_connection_status(self, connected: bool, message: str):
        """Handle Gmail connection status changes.
        
        Args:
            connected (bool): Whether the connection was successful
            message (str): Status message
        """
        print(f"Gmail: {message}")
        if connected and self.user_data:
            self.user_data.setdefault('connected_accounts', {})['gmail'] = True
        if not connected and self.user_data:
            self.user_data.setdefault('connected_accounts', {})['gmail'] = False

    def on_gmail_new_messages(self, messages: list):
        """Handle new messages received from Gmail."""
        if not messages:
            print("ℹ️ Gmail Handler: Received empty message list")
            return
            
        print(f"📥 Gmail Handler: Syncing {len(messages)} messages...")
        
        existing_ids = {msg.get('id') for msg in self.messages}
        new_items = [msg for msg in messages if msg.get('id') not in existing_ids]
        
        print(f"   - {len(new_items)} are new, {len(messages) - len(new_items)} already exist")
        
        if not new_items:
            return
            
        self.messages.extend(new_items)
        self.messages.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        self.populate_table()
        
        # Queue for background AI summarization (progressive loading)
        if hasattr(self, 'queue_summary_generator'):
            print(f"🧠 Queueing {len(new_items)} messages for background summarization...")
            self.queue_summary_generator.add_to_queue(new_items)
        # Summaries are now handled by the Agent, so no need to call generate_summaries_for_messages again
        # but if we want to be safe, we can check if they have summaries
        # self.generate_summaries_for_messages(new_items)


    def on_gmail_error(self, error_message: str):
        """Handle errors from the Gmail service.
        
        Args:
            error_message (str): Error message
        """
        print(f"Gmail Error: {error_message}")
        QMessageBox.warning(self, "Gmail", error_message)

    # -------------------------
    # GMAIL INTEGRATION - CREDENTIAL MANAGEMENT
    # -------------------------
    def upload_gmail_credentials(self, file_path: str):
        """Upload Gmail API credentials from a file.
        
        Args:
            file_path (str): Path to the credentials file
        """
        try:
            saved_path = self.gmail_service.configure_client_secret(file_path)
            return True, f"client_secret.json uploaded to {saved_path}"
        except Exception as exc:
            return False, f"Failed to upload: {exc}"

    def authorize_gmail(self):
        """Initiate the Gmail OAuth authorization flow."""
        success, message = self.gmail_service.connect(allow_flow=True)
        if success:
            self.handle_gmail_sync(quiet=True)
        return success, message

    # -------------------------
    # GMAIL INTEGRATION - MESSAGE SYNCHRONIZATION
    # -------------------------
    def handle_gmail_sync(self, quiet: bool = False):
        """Synchronize messages from Gmail using the intelligent agent."""
        if not self.gmail_service.is_connected:
            if not quiet:
                QMessageBox.warning(self, "Gmail Not Connected", "Please connect to Gmail first.")
            return
            
        if self._is_syncing_gmail:
            if not quiet:
                self.show_status_message("Sync already in progress...")
            print("⏳ Gmail sync skipped: Previous sync still running")
            return

        if not quiet:
            self.show_status_message("Syncing Gmail via Intelligent Agent...")
        
        self._is_syncing_gmail = True
        
        # Create request for the agent
        request = AgentRequest(
            intent=Intent.FETCH_MESSAGES, 
            parameters={"max_results": 25, "add_ai_analysis": True}
        )
        
        # Use AgentWorker to run the async request
        worker = AgentWorker(self.orchestrator.route_request("gmail", request))
        worker.result_ready.connect(lambda res: self.on_gmail_sync_complete(res, quiet))
        worker.error_occurred.connect(self.on_agent_error)
        worker.finished.connect(lambda: self._cleanup_worker(worker))
        
        self.active_workers.append(worker)
        worker.start()

    def on_gmail_sync_complete(self, response: AgentResponse, quiet: bool):
        """Handle completion of Gmail sync from agent."""
        self._is_syncing_gmail = False
        if response.success:
            messages = response.data.get("messages", []) if response.data else []
            if messages:
                self.on_gmail_new_messages(messages)
                if not quiet:
                    self.show_status_message(f"Fetched {len(messages)} Gmail messages with AI analysis")
            else:
                if not quiet:
                    self.show_status_message("No new Gmail messages found")
        else:
            self.on_agent_error(response.error or "Gmail sync failed")

    
    # -------------------------
    # MESSAGE ACTIONS
    # -------------------------
    def auto_reply_message(self, message_data):
        """Generate and send an auto-reply to the specified message.
        
        Args:
            message_data (dict): The message to reply to
        """
        QMessageBox.information(
            self, 
            "Auto Reply", 
            f"Auto-generating smart reply for message from {message_data.get('sender', 'Unknown')}...\n\n"
            "This feature uses AI to analyze the message and generate an appropriate response.\n\n"
            "(Coming soon!)"
        )
    
    def smart_draft_message(self, message_data):
        """Generate a smart draft response to the specified message.
        
        Args:
            message_data (dict): The message to draft a response to
        """
        QMessageBox.information(
            self, 
            "Smart Draft", 
            f"Generating smart draft suggestions for message from {message_data.get('sender', 'Unknown')}...\n\n"
            "This feature provides AI-powered draft suggestions you can edit before sending.\n\n"
            "(Coming soon!)"
        )
    
    def attach_file_message(self, message_data):
        """Attach a file to a message.
        
        Args:
            message_data (dict): The message to attach a file to
        """
        from PySide6.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File to Attach",
            "",
            "All Files (*.*)"
        )
        
        if file_path:
            QMessageBox.information(
                self,
                "File Selected",
                f"File selected: {file_path}\n\n"
                f"Will be attached to reply to {message_data.get('sender', 'Unknown')}\n\n"
                "(Full implementation coming soon!)"
            )
    
    # -------------------------
    # AI SUMMARY GENERATION
    # -------------------------
    # -------------------------
    # AI SUMMARY GENERATION - BATCH PROCESSING
    # -------------------------
    def generate_summaries_for_messages(self, messages: list):
        """Generate AI summaries for a list of messages.
        
        Args:
            messages (list): List of message dictionaries to summarize
        """
        """Generate AI summaries for a list of messages"""
        if not self.ollama_service.check_connection():
            print("⚠️ Ollama is not running. Summaries will not be generated.")
            return
        
        # Add messages to the queue processor
        # This handles concurrency and rate limiting automatically
        self.queue_summary_generator.add_to_queue(messages)
    
    # -------------------------
    # AI SUMMARY GENERATION - EVENT HANDLERS
    # -------------------------
    def on_summary_generated(self, message_id: str, summary: str):
        """Handle completion of summary generation for a message.
        
        Args:
            message_id (str): ID of the message
            summary (str): Generated summary text
        """
        """Handle when a summary is generated"""
        print(f"✅ Summary generated for message {message_id[:8]}...")
        
        # Update the message with the summary
        for msg in self.messages:
            if msg.get('id') == message_id:
                # Parse the AI response to separate Summary and Task
                # Expected format: "Summary: ... \n\nTask: ..."
                
                full_analysis = summary
                clean_summary = summary
                
                if "Summary:" in summary and "Task:" in summary:
                    try:
                        # Extract just the summary part for the table
                        parts = summary.split("Task:")
                        summary_part = parts[0].replace("Summary:", "").strip()
                        clean_summary = summary_part
                    except:
                        pass
                
                msg['summary'] = clean_summary
                msg['ai_analysis'] = full_analysis
                break
        
        # Refresh the table row specifically instead of full heavy reload
        # For now, full reload is safer but we can optimize later
        # self.populate_table() 
        
        # Actually, let's keep it simple: just trigger a repaint or reload
        # We'll use a delayed timer to batch UI updates so we don't flash too much
        if not hasattr(self, '_update_timer'):
            self._update_timer = QTimer()
            self._update_timer.setSingleShot(True)
            self._update_timer.timeout.connect(self.populate_table)
        
        self._update_timer.start(200) # Buffer updates by 200ms
        
        # Clean up thread
        if message_id in self.summary_threads:
            del self.summary_threads[message_id]
    
    def on_summary_error(self, message_id: str, error: str):
        """Handle errors during summary generation.
        
        Args:
            message_id (str): ID of the message that failed summarization
            error (str): Error message
        """
        """Handle summary generation error"""
        print(f"❌ Error generating summary for {message_id[:8]}: {error}")
        
        # Clean up thread
        if message_id in self.summary_threads:
            del self.summary_threads[message_id]
    
    def on_summary_progress(self, current: int, total: int):
        """Update progress of batch summary generation.
        
        Args:
            current (int): Current message being processed
            total (int): Total number of messages to process
        """
        """Handle batch summary progress updates"""
        print(f"📊 Summary progress: {current}/{total}")
    
    def on_batch_summary_complete(self, count: int):
        """Handle completion of a batch summary generation.
        
        Args:
            count (int): Number of summaries generated
        """
        """Handle batch summary completion"""
        print(f"✅ Batch summary complete: {count} summaries generated")
        self.populate_table()
    
    # -------------------------
    # UI UPDATES
    # -------------------------
    def refresh_message_times(self):
        """Refresh relative time display for all messages (e.g., '5 minutes ago')."""
        """Refresh time display dynamically every 60 seconds"""
        for msg in self.messages:
            if 'datetime' in msg:
                msg['time'] = format_message_time(msg['datetime'])
        
        if self.table.isVisible() and self.expanded_row is None:
            current_scroll = self.table.verticalScrollBar().value()
            self.populate_table()
            self.table.verticalScrollBar().setValue(current_scroll)
    
    def auto_sync_gmail(self):
        """Periodically synchronize Gmail messages."""
        if self.gmail_service.is_connected:
            self.handle_gmail_sync(quiet=True)
    
    # -------------------------
    # NOTIFICATION HANDLING
    # -------------------------
    def show_notifications(self):
        """Display any pending notifications to the user."""
        dialog = NotificationDialog(self.notifications, self)
        dialog.exec()
        
        unread_count = sum(1 for n in self.notifications if not n.get('read', False))
        if hasattr(self, 'notif_badge'):
            self.notif_badge.setText(str(unread_count))
    
    # -------------------------
    # UI SETUP
    # -------------------------
    # -------------------------
    # UI SETUP
    # -------------------------
    def setup_ui(self):
        """Set up the main application UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        main_layout.addWidget(self.create_header())
        main_layout.addWidget(self.create_main_content(), 1)
        main_layout.addWidget(self.create_status_bar())
    
    # -------------------------
    # UI COMPONENT CREATION
    # -------------------------
    def create_header(self):
        """Create the application header with title and controls."""
        header = QWidget()
        header.setObjectName("header")
        header.setFixedHeight(80)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 12, 24, 12)
        
        logo = QLabel("AutoReturn")
        logo.setObjectName("logo")
        
        self.search_field = QLineEdit()
        self.search_field.setObjectName("searchInput")
        self.search_field.setPlaceholderText("Search messages, people, or use voice commands...")
        self.search_field.setFixedHeight(50)
        self.search_field.setMaximumWidth(500)
        self.search_field.textChanged.connect(self.on_search_changed)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        voice_btn = QPushButton("Voice")
        voice_btn.setObjectName("btnVoice")
        
        notif_btn = QPushButton("🔔")
        notif_btn.setObjectName("iconBtn")
        notif_btn.setFixedSize(40, 40)
        notif_btn.clicked.connect(self.show_notifications)
        
        badge = QLabel("3")
        badge.setObjectName("notificationBadge")
        badge.setParent(notif_btn)
        badge.move(20, 2)
        self.notif_badge = badge
        
        self.user_name_label = QLabel("User")
        self.user_name_label.setObjectName("userNameLabel")
        
        settings_btn = QPushButton("⚙️")
        settings_btn.setObjectName("iconBtn")
        settings_btn.clicked.connect(self.show_settings)
        
        layout.addWidget(logo)
        layout.addWidget(spacer)
        layout.addWidget(self.search_field)
        layout.addWidget(spacer)
        layout.addWidget(voice_btn)
        layout.addWidget(notif_btn)
        layout.addWidget(self.user_name_label)
        layout.addWidget(settings_btn)
        
        return header
    
    def create_main_content(self):
        """Create the main content area of the application."""
        content = QWidget()
        content.setObjectName("mainContent")
        
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        header_layout = QHBoxLayout()
        
        title = QLabel("Unified Inbox")
        title.setObjectName("inboxTitle")
        
        sync_btn = QPushButton("Sync")
        sync_btn.setObjectName("btnSecondary")
        sync_btn.clicked.connect(self.sync_all_messages)
        
        generate_summaries_btn = QPushButton("🤖 Generate Summaries")
        generate_summaries_btn.setObjectName("btnSecondary")
        generate_summaries_btn.clicked.connect(self.generate_all_summaries)
        generate_summaries_btn.setToolTip("Generate AI summaries for all messages using Ollama")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(generate_summaries_btn)
        header_layout.addWidget(sync_btn)
        
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        filter_buttons = [
            ("All", "all", None),
            ("Gmail", "gmail", os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Gmail_Logo_32px.png")),
            ("Slack", "slack", os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons8-slack-new-48.png")),
            ("Urgent", "urgent", os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "notification-bell-red.png"))
        ]
        
        for text, filter_id, icon_path in filter_buttons:
            btn = QPushButton(text)
            btn.setObjectName("filterBtn")
            btn.setProperty("filter_id", filter_id)
            
            if icon_path:
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(18, 18))
            
            btn.clicked.connect(lambda checked, f=filter_id: self.apply_filter(f))
            
            if filter_id == 'all':
                btn.setProperty("active", "true")
                btn.setStyle(btn.style())
            
            filter_layout.addWidget(btn)
        
        filter_layout.addStretch()
        
        self.table = QTableWidget()
        self.table.setObjectName("messageTable")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "", "Source", "Sender", "Content Preview", "AI Summary", "Priority", "Time", "Actions"
        ])
        
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        
        self.table.setColumnWidth(0, 40)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(4, 200)
        self.table.setColumnWidth(5, 90)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 260)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by_column)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        
        layout.addLayout(header_layout)
        layout.addLayout(filter_layout)
        layout.addWidget(self.table)
        
        return content
    
    def create_status_bar(self):
        """Create and configure the status bar."""
        status_bar = QWidget()
        status_bar.setObjectName("statusBar")
        status_bar.setFixedHeight(40)
        
        layout = QHBoxLayout(status_bar)
        layout.setContentsMargins(24, 8, 24, 8)
        
        status_items = [
            ("Total Messages: 0", "statusItem"),
            ("Gmail: 0", "statusItem"),
            ("Slack: 0", "statusItem"),
            ("Urgent: 0", "statusItem")
        ]
        
        self.status_labels = {}
        for text, obj_name in status_items:
            label = QLabel(text)
            label.setObjectName(obj_name)
            layout.addWidget(label)
            self.status_labels[text.split(':')[0]] = label
        
        layout.addStretch()
        
        return status_bar
    
    # -------------------------
    # MESSAGE HANDLING
    # -------------------------
    # -------------------------
    # MESSAGE TABLE MANAGEMENT
    # -------------------------
    def populate_table(self):
        """Populate the message table with current messages."""
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            
            filtered = [m for m in self.messages if self.filter_message(m)]
            print(f"📋 Populating table with {len(filtered)} items (Total: {len(self.messages)})")
            
            # Log breakdown
            sources = {}
            for m in filtered:
                s = m.get('source', 'unknown')
                sources[s] = sources.get(s, 0) + 1
            if filtered:
                print(f"   Sources: {sources}")
            
            self.update_status_bar()

            
            for row, msg in enumerate(filtered):
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)
                
                is_read = msg.get('read', False)
                
                checkbox = QCheckBox()
                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row_idx, 0, checkbox_widget)
                
                source_label = QLabel()
                source_label.setAlignment(Qt.AlignCenter)
                if msg.get('source') == 'gmail':
                    pixmap = QPixmap(os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Gmail_Logo_32px.png"))
                else:
                    pixmap = QPixmap(os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "icons8-slack-new-48.png"))
                pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                source_label.setPixmap(pixmap)
                self.table.setCellWidget(row_idx, 1, source_label)
                
                from_widget = QWidget()
                from_layout = QVBoxLayout(from_widget)
                from_layout.setContentsMargins(8, 4, 8, 4)
                from_layout.setSpacing(2)
                
                if msg.get('is_channel') or msg.get('is_group'):
                    from_name = QLabel(f"#{msg.get('channel_name', 'channel')}")
                    from_name.setObjectName("fromName")
                    from_email = QLabel(f"from {msg.get('sender', 'Unknown')}")
                    from_email.setObjectName("fromEmail")
                else:
                    from_name = QLabel(msg.get('sender', 'Unknown'))
                    from_name.setObjectName("fromName")
                    from_email = QLabel(msg.get('email', ''))
                    from_email.setObjectName("fromEmail")
                
                from_layout.addWidget(from_name)
                from_layout.addWidget(from_email)
                self.table.setCellWidget(row_idx, 2, from_widget)
                
                subject_widget = QWidget()
                subject_layout = QVBoxLayout(subject_widget)
                subject_layout.setContentsMargins(8, 4, 8, 4)
                subject_layout.setSpacing(4)

                if msg.get('source') == 'gmail':
                    raw_subject = msg.get('subject', 'No Subject')
                    raw_preview = msg.get('content_preview', msg.get('preview', '')) or ''
                else:
                    raw_subject = msg.get('content_preview', msg.get('subject', 'No Subject'))
                    raw_preview = msg.get('preview', '') or ''

                max_subject_len = 60
                subject_display = raw_subject if len(raw_subject) <= max_subject_len else raw_subject[:max_subject_len - 3] + "..."
                subject_text = QLabel(subject_display)
                subject_text.setObjectName("subjectText")

                max_preview_len = 80
                preview_display = raw_preview[:max_preview_len]
                if len(raw_preview) > max_preview_len:
                    preview_display += "..."
                preview_text = QLabel(preview_display)
                preview_text.setObjectName("previewText")
                
                subject_layout.addWidget(subject_text)
                subject_layout.addWidget(preview_text)
                self.table.setCellWidget(row_idx, 3, subject_widget)
                
                full_summary = msg.get('summary', '')
                max_summary_len = 80
                display_summary = full_summary if len(full_summary) <= max_summary_len else full_summary[:max_summary_len - 3] + "..."
                summary_label = QLabel(display_summary)
                summary_label.setObjectName("summaryText")
                summary_label.setWordWrap(True)
                if full_summary:
                    summary_label.setToolTip("Click to view full summary")
                    summary_label.setCursor(Qt.PointingHandCursor)
                self.table.setCellWidget(row_idx, 4, summary_label)
                
                priority = msg.get('priority', 'normal')
                priority_icons = {'urgent': '', 'high': '', 'normal': ''}
                priority_order = {'urgent': 3, 'high': 2, 'normal': 1}
                
                priority_item = QTableWidgetItem(f"{priority_icons[priority]} {priority.upper()}")
                priority_item.setTextAlignment(Qt.AlignCenter)
                priority_item.setData(Qt.UserRole, priority_order[priority])
                
                if priority == 'urgent':
                    priority_item.setBackground(QColor(255, 229, 224))
                    priority_item.setForeground(QColor(150, 71, 52))
                elif priority == 'high':
                    priority_item.setBackground(QColor(212, 244, 247))
                    priority_item.setForeground(QColor(2, 73, 80))
                else:
                    priority_item.setBackground(QColor(175, 221, 229))
                    priority_item.setForeground(QColor(0, 49, 53))
                
                font = priority_item.font()
                font.setBold(True)
                priority_item.setFont(font)
                
                self.table.setItem(row_idx, 5, priority_item)
                
                time_item = QTableWidgetItem(msg.get('time', ''))
                time_item.setTextAlignment(Qt.AlignCenter)
                time_item.setForeground(QColor("#003135"))
                
                time_value = self.parse_time_to_minutes(msg.get('time', ''))
                time_item.setData(Qt.UserRole, time_value)
                
                self.table.setItem(row_idx, 6, time_item)
                
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(4, 4, 4, 4)
                actions_layout.setSpacing(4)

                reply_btn = QPushButton("Reply")
                reply_btn.setObjectName("actionBtn")
                reply_btn.setFixedSize(64, 28)
                reply_btn.clicked.connect(lambda checked, m=msg: self.show_send_message_dialog(m))

                auto_reply_btn = QPushButton("Auto")
                auto_reply_btn.setObjectName("actionBtn")
                auto_reply_btn.setFixedSize(56, 28)
                auto_reply_btn.setToolTip("Auto Reply")
                auto_reply_btn.clicked.connect(lambda checked, m=msg: self.auto_reply_message(m))

                smart_draft_btn = QPushButton("Draft")
                smart_draft_btn.setObjectName("actionBtn")
                smart_draft_btn.setFixedSize(56, 28)
                smart_draft_btn.setToolTip("Smart Draft")
                smart_draft_btn.clicked.connect(lambda checked, m=msg: self.smart_draft_message(m))

                attach_btn = QPushButton("📎")
                attach_btn.setObjectName("actionBtn")
                attach_btn.setFixedSize(32, 28)
                attach_btn.setToolTip("Attach File")
                attach_btn.clicked.connect(lambda checked, m=msg: self.attach_file_message(m))

                actions_layout.addWidget(reply_btn)
                actions_layout.addWidget(auto_reply_btn)
                actions_layout.addWidget(smart_draft_btn)
                actions_layout.addWidget(attach_btn)
                actions_layout.addStretch()

                self.table.setCellWidget(row_idx, 7, actions_widget)
                
                self.table.setRowHeight(row_idx, 64)
                
                if not is_read:
                    for col in range(8):
                        item = self.table.item(row_idx, col)
                        if item:
                            item.setBackground(QColor("#E6F7F9"))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
    
    # -------------------------
    # SEARCH FUNCTIONALITY
    # -------------------------
    def on_search_changed(self, text: str):
        """Handle changes to the search input.
        
        Args:
            text (str): Current search text
        """
        raw_text = text.strip()
        self.search_query = raw_text
        self.search_filters = self._parse_search_query(raw_text.lower())
        self.populate_table()

    def _parse_search_query(self, query: str):
        """Parse the search query into filter components.
        
        Args:
            query (str): Raw search query string
            
        Returns:
            dict: Parsed search filters
        """
        filters = {
            'raw': query,
            'terms': [],
            'date_from': None,
            'date_to': None,
            'require_attachments': False,
        }

        if not query:
            return filters

        text = query

        now = datetime.now()

        if 'last 7 weeks' in text:
            filters['date_from'] = now - timedelta(weeks=7)
            text = text.replace('last 7 weeks', ' ')
        if 'last week' in text:
            filters['date_from'] = now - timedelta(days=7)
            text = text.replace('last week', ' ')
        if 'last month' in text:
            filters['date_from'] = now - timedelta(days=30)
            text = text.replace('last month', ' ')

        if 'attachment' in text:
            filters['require_attachments'] = True
            text = text.replace('with file attachment', ' ')
            text = text.replace('with attachment', ' ')
            text = text.replace('with attachments', ' ')
            text = text.replace('file attachment', ' ')

        cleaned_tokens = [t for t in text.split() if t]
        filters['terms'] = cleaned_tokens

        return filters
    
    def parse_time_to_minutes(self, time_str: str) -> int:
        try:
            if 's ago' in time_str:
                return int(time_str.split('s')[0]) // 60
            elif 'm ago' in time_str:
                return int(time_str.split('m')[0])
            elif 'h ago' in time_str:
                return int(time_str.split('h')[0]) * 60
            elif 'd ago' in time_str:
                return int(time_str.split('d')[0]) * 24 * 60
            else:
                return 999999
        except:
            return 999999
    
    # -------------------------
    # MESSAGE FILTERING
    # -------------------------
    def filter_message(self, msg):
        """Determine if a message matches the current filters.
        
        Args:
            msg (dict): Message to check
            
        Returns:
            bool: True if message matches filters, False otherwise
        """
        if self.active_filter == 'all':
            filter_match = True
        elif self.active_filter == 'gmail':
            filter_match = msg.get('source') == 'gmail'
        elif self.active_filter == 'slack':
            filter_match = msg.get('source') == 'slack'
        elif self.active_filter == 'urgent':
            filter_match = msg.get('priority') == 'urgent'
        else:
            filter_match = True
        
        filters = self.search_filters or {}
        raw_query = filters.get('raw', '').strip()

        if raw_query:
            date_from = filters.get('date_from')
            if date_from is not None:
                msg_dt = msg.get('datetime')
                if not isinstance(msg_dt, datetime) or msg_dt < date_from:
                    return False

            if filters.get('require_attachments'):
                if not msg.get('has_attachments'):
                    return False

            terms = filters.get('terms') or []
            if terms:
                sender_text = msg.get('sender', '').lower()
                email_text = msg.get('email', '').lower()
                content_preview_text = msg.get('content_preview', '').lower()
                preview_text = msg.get('preview', '').lower()
                summary_text = msg.get('summary', '').lower()
                full_content_text = msg.get('full_content', '').lower()
                channel_name_text = msg.get('channel_name', '').lower()

                def matches_term(term: str) -> bool:
                    return (
                        term in sender_text or
                        term in email_text or
                        term in content_preview_text or
                        term in preview_text or
                        term in summary_text or
                        term in full_content_text or
                        term in channel_name_text
                    )

                for term in terms:
                    if not matches_term(term):
                        return False

            search_match = True
        else:
            search_match = True
        
        return filter_match and search_match
    
    def apply_filter(self, filter_id):
        """Apply the specified filter to the message list.
        
        Args:
            filter_id (str): ID of the filter to apply
        """
        self.active_filter = filter_id
        
        for btn in self.findChildren(QPushButton):
            if btn.property("filter_id"):
                if btn.property("filter_id") == filter_id:
                    btn.setProperty("active", "true")
                else:
                    btn.setProperty("active", "false")
                btn.setStyle(btn.style())
        
        self.populate_table()
    
    # -------------------------
    # UI EVENT HANDLERS
    # -------------------------
    def on_table_cell_clicked(self, row, column):
        """Handle clicks on table cells.
        
        Args:
            row (int): Row index that was clicked
            column (int): Column index that was clicked
        """
        """Handle clicks on table cells"""
        filtered = [m for m in self.messages if self.filter_message(m)]
        if row >= len(filtered):
            return

        msg = filtered[row]

        # Column 4 is "AI Summary" → show full AI analysis
        if column == 4:
            full_text = msg.get('ai_analysis') or msg.get('summary', '')
            if full_text:
                self.show_full_summary_dialog(full_text)
        # Sender (2) or Content Preview (3) → show full message content
        elif column in (2, 3):
            self.show_full_message_dialog(msg)

    def show_full_summary_dialog(self, summary_text):
        """Show a dialog with the full summary text.
        
        Args:
            summary_text (str): The full summary text to display
        """
        """Show a dialog with the full summary text, beautifully styled"""
        dialog = QDialog(self)
        dialog.setWindowTitle("AI Analysis")
        dialog.setMinimumWidth(500)
        dialog.setMinimumHeight(400)
        
        # Apply app theme to dialog
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border: 2px solid #0FA4AF;
                border-radius: 12px;
            }
            QLabel {
                color: #003135;
                font-weight: bold;
                font-size: 18px;
            }
            QTextEdit {
                background-color: #f8fcfc;
                border: 1px solid #AFDDE5;
                border-radius: 8px;
                padding: 12px;
                color: #003135;
                font-size: 14px;
                line-height: 1.6;
            }
            QPushButton {
                background-color: #0FA4AF;
                color: white;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 600;
                font-size: 14px;
                border: none;
            }
            QPushButton:hover {
                background-color: #024950;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Header
        header_layout = QHBoxLayout()
        icon_label = QLabel("✨")
        icon_label.setStyleSheet("font-size: 24px; background: transparent;")
        title_label = QLabel("AI Insight & Analysis")
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Format text with HTML for beauty
        formatted_text = summary_text.replace("\n", "<br>")
        formatted_text = formatted_text.replace("Summary:", "<b style='color: #024950; font-size: 16px;'>📝 Summary</b><br>")
        formatted_text = formatted_text.replace("Task:", "<br><br><b style='color: #024950; font-size: 16px;'>⚡ Task Classification</b><br>")
        
        # Content Area
        text_edit = QTextEdit()
        text_edit.setHtml(f"""
            <div style='font-family: sans-serif;'>
                {formatted_text}
            </div>
        """)
        text_edit.setReadOnly(True)
        
        # Close Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(header_layout)
        layout.addWidget(text_edit)
        layout.addLayout(btn_layout)
        
        dialog.exec()

    def show_full_message_dialog(self, msg: dict):
        """Show a dialog with the full message content.
        
        Args:
            msg (dict): Message data to display
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Full Message")
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(400)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QLabel(f"From: {msg.get('sender', 'Unknown')}")
        header.setObjectName("messageHeader")

        subject_label = QLabel(f"Subject: {msg.get('subject', 'No Subject')}")
        subject_label.setWordWrap(True)

        sender_name = msg.get('sender', '') or ''
        sender_email = msg.get('email', '') or ''
        stats = self.compute_sender_stats(sender_name, sender_email)
        stats_text = (
            f"Last week: {stats['last_week']}  |  "
            f"Last month: {stats['last_month']}  |  "
            f"Last 7 weeks: {stats['last_7_weeks']}"
        )
        stats_label = QLabel(stats_text)
        stats_label.setWordWrap(True)

        body_widget = QTextEdit()
        body_widget.setReadOnly(True)
        body_widget.setPlainText(msg.get('full_content', msg.get('preview', '')))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(header)
        layout.addWidget(subject_label)
        layout.addWidget(stats_label)
        layout.addWidget(body_widget)
        layout.addLayout(btn_layout)

        dialog.exec()

    # -------------------------
    # ANALYTICS & INSIGHTS
    # -------------------------
    def compute_sender_stats(self, sender_name: str, sender_email: str):
        """Compute statistics for a message sender.
        
        Args:
            sender_name (str): Name of the sender
            sender_email (str): Email address of the sender
            
        Returns:
            dict: Statistics about the sender
        """
        stats = {
            'last_week': 0,
            'last_month': 0,
            'last_7_weeks': 0,
        }

        if not sender_name and not sender_email:
            return stats

        now = datetime.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        seven_weeks_ago = now - timedelta(weeks=7)

        for m in self.messages:
            m_sender = m.get('sender', '') or ''
            m_email = m.get('email', '') or ''

            if sender_name and m_sender == sender_name:
                matched = True
            elif sender_email and m_email == sender_email:
                matched = True
            else:
                matched = False

            if not matched:
                continue

            msg_dt = m.get('datetime')
            if not isinstance(msg_dt, datetime):
                continue

            if msg_dt >= seven_weeks_ago:
                stats['last_7_weeks'] += 1
            if msg_dt >= month_ago:
                stats['last_month'] += 1
            if msg_dt >= week_ago:
                stats['last_week'] += 1

        return stats
    
    # -------------------------
    # SORTING
    # -------------------------
    def sort_by_column(self, column):
        """Sort the message table by the specified column.
        
        Args:
            column (int): Column index to sort by
        """
        if column in [0, 1, 7]:
            return
        
        if self.current_sort_column == column:
            self.sort_order = Qt.DescendingOrder if self.sort_order == Qt.AscendingOrder else Qt.AscendingOrder
        else:
            self.current_sort_column = column
            self.sort_order = Qt.AscendingOrder
        
        sort_keys = {
            2: 'sender',
            3: 'subject',
            4: 'summary',
            5: 'priority',
            6: 'timestamp'
        }
        
        if column in sort_keys:
            reverse = (self.sort_order == Qt.DescendingOrder)
            self.messages.sort(key=lambda x: x.get(sort_keys[column], ''), reverse=reverse)
            self.populate_table()
    
    # -------------------------
    # STATUS UPDATES
    # -------------------------
    def update_status_bar(self):
        """Update the status bar with current application state."""
        total = len(self.messages)
        gmail_count = sum(1 for m in self.messages if m.get('source') == 'gmail')
        slack_count = sum(1 for m in self.messages if m.get('source') == 'slack')
        urgent_count = sum(1 for m in self.messages if m.get('priority') == 'urgent')
        
        self.status_labels.get("Total Messages").setText(f"Total Messages: {total}")
        self.status_labels.get("Gmail").setText(f"Gmail: {gmail_count}")
        self.status_labels.get("Slack").setText(f"Slack: {slack_count}")
        self.status_labels.get("Urgent").setText(f"Urgent: {urgent_count}")

    def show_status_message(self, message: str, timeout: int = 5000):
        """Display a temporary message in the status region (fallback to console)."""
        print(f"📊 {message}")
        # If we have a status bar label, update it
        if hasattr(self, 'status_labels') and 'Total Messages' in self.status_labels:
            original_text = self.status_labels['Total Messages'].text()
            self.status_labels['Total Messages'].setText(f"ℹ️ {message}")
            # Restore after timeout if possible, but for now just leave it or use a timer
        pass


    # -------------------------
    # ROW INTERACTION
    # -------------------------
    def on_row_clicked(self, row, column):
        """Handle clicks on message rows.
        
        Args:
            row (int): Row index that was clicked
            column (int): Column index that was clicked
        """
        filtered = [m for m in self.messages if self.filter_message(m)]
        
        if row >= len(filtered):
            return
        
        msg = filtered[row]
        
        for m in self.messages:
            if m.get('id') == msg.get('id'):
                m['read'] = True
                break
        
        if self.expanded_row == row:
            self.collapse_row(row)
            self.expanded_row = None
        else:
            if self.expanded_row is not None:
                self.collapse_row(self.expanded_row)
            
            self.expand_row(row, msg)
            self.expanded_row = row
        
        self.populate_table()
    
    def expand_row(self, row, msg):
        """Expand a row to show message details.
        
        Args:
            row (int): Row index to expand
            msg (dict): Message data to display
        """
        current_height = self.table.rowHeight(row)
        self.table.setRowHeight(row, current_height + 400)
        
        expanded_widget = QWidget()
        expanded_widget.setObjectName("expandedContent")
        
        layout = QVBoxLayout(expanded_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        email_widget = QWidget()
        email_widget.setObjectName("emailFull")
        email_layout = QVBoxLayout(email_widget)
        email_layout.setContentsMargins(16, 16, 16, 16)
        
        full_content = QLabel(msg.get('full_content', msg.get('preview', '')))
        full_content.setObjectName("emailBody")
        full_content.setWordWrap(True)
        
        email_layout.addWidget(full_content)
        
        ai_widget = QWidget()
        ai_widget.setObjectName("aiAnalysis")
        ai_layout = QVBoxLayout(ai_widget)
        ai_layout.setContentsMargins(16, 16, 16, 16)
        
        ai_header = QLabel("AI Insights")
        ai_header.setObjectName("aiHeader")
        
        insights = msg.get('ai_insights')
        if not insights:
            insights = self.generate_ai_insights(msg)
        
        insights_label = QLabel(insights)
        insights_label.setWordWrap(True)
        
        ai_layout.addWidget(ai_header)
        ai_layout.addWidget(insights_label)
        
        replies_layout = QHBoxLayout()
        replies = [
            "Sounds good!",
            "Let me check my schedule",
            "Can we discuss this further?"
        ]
        
        for reply_text in replies:
            reply_widget = QWidget()
            reply_widget.setObjectName("replyOption")
            reply_layout = QVBoxLayout(reply_widget)
            reply_layout.setContentsMargins(12, 12, 12, 12)
            
            reply_label = QLabel(reply_text)
            reply_label.setObjectName("replyText")
            reply_label.setWordWrap(True)
            
            use_btn = QPushButton("Use")
            use_btn.setObjectName("btnPrimary")
            
            reply_layout.addWidget(reply_label)
            reply_layout.addWidget(use_btn)
            
            replies_layout.addWidget(reply_widget)
        
        layout.addWidget(email_widget)
        layout.addWidget(ai_widget)
        layout.addLayout(replies_layout)
        
        self.table.setCellWidget(row, 3, expanded_widget)
    
    def collapse_row(self, row):
        """Collapse an expanded row.
        
        Args:
            row (int): Row index to collapse
        """
        self.table.setRowHeight(row, 70)
        
        filtered = [m for m in self.messages if self.filter_message(m)]
        if row < len(filtered):
            msg = filtered[row]
            
            subject_widget = QWidget()
            subject_layout = QVBoxLayout(subject_widget)
            subject_layout.setContentsMargins(8, 4, 8, 4)
            subject_layout.setSpacing(2)
            
            subject_label = QLabel(msg.get('subject', 'No Subject'))
            subject_label.setObjectName("subjectText")
            
            preview_label = QLabel(msg.get('preview', '')[:100])
            preview_label.setObjectName("previewText")
            preview_label.setWordWrap(True)
            
            subject_layout.addWidget(subject_label)
            subject_layout.addWidget(preview_label)
            
            self.table.setCellWidget(row, 3, subject_widget)
    
    def generate_ai_insights(self, msg):
        """Generate AI-powered insights for a message.
        
        Args:
            msg (dict): Message to analyze
        """
        priority = msg.get('priority', 'normal')
        
        if priority == 'urgent':
            return "This message requires immediate attention. Contains time-sensitive information."
        elif priority == 'high':
            return "Important message that should be addressed soon. Contains action items or deadlines."
        else:
            return "Standard message. Review when convenient."

    # -------------------------
    # SETTINGS
    # -------------------------
    # -------------------------
    # SETTINGS DIALOG
    # -------------------------
    def show_settings(self):
        """Show the application settings dialog."""
        gmail_status = self.gmail_service.get_status_snapshot()
        dialog = SettingsDialog(self.user_data, self, gmail_status=gmail_status)
        dialog.connect_slack_callback = self.connect_slack
        dialog.upload_gmail_json_callback = self.upload_gmail_credentials
        dialog.connect_gmail_callback = self.authorize_gmail
        dialog.sync_gmail_callback = lambda: self.handle_gmail_sync(quiet=False)
        dialog.get_gmail_status_callback = self.gmail_service.get_status_snapshot
        dialog.profile_updated.connect(self.on_profile_updated)
        dialog.refresh_gmail_status()
        dialog.exec()

    def on_profile_updated(self, updated_user: dict):
        """Handle updates to the user's profile.
        
        Args:
            updated_user (dict): Updated user data
        """
        self.user_data = updated_user
        if hasattr(self, 'user_name_label'):
            self.user_name_label.setText(self.user_data.get('name', 'User'))
    
    # -------------------------
    # WINDOW EVENTS
    # -------------------------
    # -------------------------
    # WINDOW EVENTS
    # -------------------------
    # -------------------------
    # APPLICATION LIFECYCLE
    # -------------------------
    def closeEvent(self, event):
        """Handle application close event.
        
        Args:
            event: Close event
        """
        print("Shutting down AutoReturn...")
        
        # Stop timers
        self.time_refresh_timer.stop()
        self.gmail_refresh_timer.stop()
        
        # Stop summary generator threads (CRITICAL - prevents crash)
        if hasattr(self, 'queue_summary_generator') and self.queue_summary_generator:
            print("Stopping summary generator...")
            self.queue_summary_generator.stop_all()
            # Give threads time to finish
            QApplication.processEvents()
        
        # Stop any individual summary threads
        if hasattr(self, 'summary_threads'):
            for thread_id, thread in list(self.summary_threads.items()):
                if thread and thread.isRunning():
                    print(f"Stopping summary thread {thread_id}...")
                    thread.quit()
                    thread.wait(1000)  # Wait max 1 second
        
        # Stop Slack listener
        self.stop_slack_listener()
        
        # Disconnect services
        if self.slack_service.is_connected:
            self.slack_service.disconnect()
        
        event.accept()
        print("Shutdown complete")