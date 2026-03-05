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
    QFileDialog, QApplication, QStyle, QSizePolicy, QSpacerItem, QComboBox
)
from PySide6.QtCore import Qt, QSize, QTimer, QThread, Signal, Slot, QObject, QEvent, QUrl
from PySide6.QtGui import (QColor, QIcon, QPixmap, QFont, QFontMetrics, 
                          QPainter, QPen, QAction, QKeySequence, QDesktopServices)

# Local application imports
from src.frontend.ui.styles import get_stylesheet
from src.frontend.dialogs.notification_dialog import NotificationDialog
from src.frontend.dialogs.settings_dialog import SettingsDialog
from src.frontend.dialogs.send_slack_message_dialog import SendSlackMessageDialog
from src.frontend.dialogs.event_review_dialog import EventReviewDialog

# Backend services
from src.backend.services.slack_backend import SlackService, SlackMessage
from src.backend.services.gmail_backend import GmailIntegrationService
from src.backend.services.ai_service import OllamaService, QueueSummaryGenerator
from src.backend.services.calendar_service import CalendarService
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
        self.setMinimumSize(1100, 700)
        
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
        self.calendar_service = CalendarService(self._get_gmail_data_dir())
        self.ics_output_dir = self._get_ics_output_dir()
        
        # Slack listener
        self.slack_listener = None
        self.slack_users = []
        
        # Connect service signals (still using services for signals until full migration)
        self._connect_slack_signals()
        self._connect_gmail_signals()
        
        # Summary generation queue
        self.queue_summary_generator = QueueSummaryGenerator(self.ollama_service, max_concurrent=5)
        self.queue_summary_generator.summary_generated.connect(self.on_summary_generated)
        self.queue_summary_generator.progress_update.connect(self.on_summary_progress)
        self.queue_summary_generator.batch_complete.connect(self.on_batch_summary_complete)
        self.summary_threads = {}  # Track active summary generation threads
        
        self.active_workers = []  # Track all active agent workers to prevent GC
        self._is_syncing_gmail = False # Flag to prevent overlapping syncs
        self.messages = []
        self.notifications = []
        self.selected_message_keys = set()
        self.current_page = 1
        self.rows_per_page = 15
        self.rows_per_page_options = [10, 15, 25, 50]
        self._current_page_messages = []
        self._is_compact_ui = False
        self._is_ultra_compact_ui = False
        
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
        # Check every 15 seconds for near real-time Gmail updates
        self.gmail_refresh_timer.start(15000)
        
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

    def _get_ics_output_dir(self):
        """Get directory for ICS exports."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        output_dir = os.path.join(project_root, "data", "ics_exports")
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as exc:
            print(f"Failed to prepare ICS export dir: {exc}")
        return output_dir

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
            initial_messages = self.slack_service.sync_all_messages(limit=200)
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
    
    def _normalize_priority(self, raw_priority: str) -> str:
        """Normalize any priority value to High / Medium / Low.
        
        Maps: urgent, high -> High
              medium       -> Medium
              everything else -> Low
        """
        raw = str(raw_priority or '').strip().lower()
        if raw in ('urgent', 'high'):
            return 'High'
        elif raw == 'medium':
            return 'Medium'
        return 'Low'

    def on_slack_new_messages(self, new_messages: list):
        """Handle new messages received from Slack.
        
        Args:
            new_messages (list): List of new message dictionaries
        """
        if not new_messages:
            return

        print(f"Processing {len(new_messages)} new messages")

        # Run priority classification on messages that don't have it yet
        if hasattr(self, 'orchestrator') and hasattr(self.orchestrator, 'agents'):
            slack_agent = self.orchestrator.agents.get('slack')
            if slack_agent and hasattr(slack_agent, 'priority_engine'):
                for msg in new_messages:
                    if not msg.get('priority') or msg.get('priority') == 'normal':
                        msg['priority'] = slack_agent.priority_engine.calculate_priority(msg)
                    # Normalize priority so urgent -> High etc.
                    msg['priority'] = self._normalize_priority(msg.get('priority', 'Low'))
                    # Classify task if not already done
                    if not msg.get('ai_tasks') and hasattr(slack_agent, '_classify_task'):
                        msg['ai_tasks'] = slack_agent._classify_task(msg)
            self._enrich_slack_messages_with_schedule(new_messages)

        # Filter out duplicates
        existing_ids = {msg.get('id') for msg in self.messages}
        unique_new_messages = [m for m in new_messages if m.get('id') not in existing_ids]
        
        if not unique_new_messages:
            return

        self.messages.extend(unique_new_messages)
        # Sort by Priority (Rank) then Timestamp
        p_map = {'High': 3, 'Medium': 2, 'Low': 1}
        self.messages.sort(key=lambda x: (p_map.get(self._normalize_priority(x.get('priority', 'Low')), 1), float(x.get('timestamp', 0))), reverse=True)
        self._schedule_table_refresh()
        
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
            self._notify_desktop("Slack Message", notif_message)

        unread_count = sum(1 for n in self.notifications if not n.get('read', False))
        if hasattr(self, 'notif_badge'):
            self.notif_badge.setText(str(unread_count))

    def _enrich_slack_messages_with_schedule(self, messages: list):
        """Extract schedule suggestions for Slack messages that don't have them yet."""
        if not messages:
            return
        if not hasattr(self, 'orchestrator') or not getattr(self, 'orchestrator', None):
            return

        slack_agent = self.orchestrator.agents.get('slack') if hasattr(self.orchestrator, 'agents') else None
        extractor = getattr(slack_agent, 'event_extractor', None)
        if not extractor:
            return

        pending = [m for m in messages if 'ai_events' not in m]
        if not pending:
            return

        async def _extract_batch():
            return await asyncio.gather(
                *(extractor.extract_from_message(m) for m in pending),
                return_exceptions=True
            )

        try:
            loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(loop)
                results = loop.run_until_complete(_extract_batch())
            finally:
                asyncio.set_event_loop(None)
                loop.close()
        except Exception as exc:
            print(f"⚠️ Slack schedule enrichment failed: {exc}")
            return

        for msg, result in zip(pending, results):
            if isinstance(result, Exception):
                msg['ai_events'] = []
                msg['ai_events_count'] = 0
                continue
            msg['ai_events'] = [e.model_dump(mode="json") for e in result] if result else []
            msg['ai_events_count'] = len(msg['ai_events'])
    
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
        
        self.slack_listener = SlackMessageListener(self.slack_service, poll_interval=5)
        self.slack_listener.new_messages.connect(self.on_slack_new_messages)
        self.slack_listener.error_occurred.connect(self.on_slack_error)
        self.slack_listener.start()
        print("Slack listener started (5s interval)")

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
        if self._is_syncing_gmail:
            self.show_status_message("A sync is already in progress...")
            print("⏳ All-Sync skipped: Previous sync still running")
            return

        # Reset filters so new messages are visible
        self.active_filter = 'all'
        self.search_filters = None
        self.search_field.clear()
        
        self.show_status_message("Syncing all messages via Orchestrator...")
        self._is_syncing_gmail = True
        
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
        self._is_syncing_gmail = False
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
        preselected_files = message_data.get('_attachments', [])
        
        if source == 'slack':
            if not self.slack_service.is_connected:
                QMessageBox.warning(self, "Not Connected", "Please connect to Slack first.")
                return
            
            if not self.slack_users:
                QMessageBox.warning(self, "Loading", "Slack users are still loading. Please wait.")
                return
            
            # NEW: Use enhanced Slack message dialog with tone features
            dialog = SendSlackMessageDialog(
                users=self.slack_users, 
                parent=self,
                orchestrator=self.orchestrator,
                original_message=message_data
            )
            
            if message_data.get('is_dm'):
                sender = message_data.get('sender', '')
                for user in self.slack_users:
                    if user.get('real_name') == sender:
                        dialog.user_combo.setCurrentText(f"{user['real_name']} (@{user['name']})")
                        break
            
            if preselected_files:
                dialog.set_attachments(preselected_files)

            if dialog.exec() == QDialog.Accepted:
                selected_user = dialog.get_selected_user()
                message_text = dialog.get_message_text()
                selected_tone = dialog.get_selected_tone()
                attachments = dialog.get_attachments()
                
                if selected_user and (message_text or attachments):
                    if message_text:
                        message_with_tone = f"[{selected_tone.value if selected_tone else 'Default'}] {message_text}".strip()
                    else:
                        message_with_tone = ""
                    self.slack_service.send_dm_by_id(selected_user['id'], message_with_tone, attachments=attachments)
                    QMessageBox.information(self, "Message Sent", 
                        f"Message sent with {selected_tone.value if selected_tone else 'Default'} tone!")
        
        elif source == 'gmail':
            if not self.gmail_service.is_connected:
                QMessageBox.warning(self, "Gmail", "Please connect to Gmail first.\n\nGo to Settings → Integrations → Gmail")
                return
            to_email = message_data.get('email', '')
            subject = message_data.get('subject', '(No Subject)')
            # NEW: Use enhanced Gmail reply dialog with tone features
            dialog = SendGmailReplyDialog(
                to_email=to_email, 
                subject=subject, 
                parent=self,
                orchestrator=self.orchestrator,
                original_message=message_data
            )
            if preselected_files:
                dialog.set_attachments(preselected_files)

            if dialog.exec() == QDialog.Accepted:
                reply_text = dialog.get_message_text()
                selected_tone = dialog.get_selected_tone()
                attachments = dialog.get_attachments()
                
                if reply_text or attachments:
                    if reply_text:
                        reply_with_tone = f"[{selected_tone.value if selected_tone else 'Default'}] {reply_text}".strip()
                    else:
                        reply_with_tone = "Please see attached file."
                    success, msg = self.gmail_service.reply_to_message(message_data, reply_with_tone, attachments=attachments)
                    
                    # NEW: Show tone usage feedback
                    QMessageBox.information(self, "Reply Sent", 
                        f"Reply sent with {selected_tone.value if selected_tone else 'Default'} tone!")
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
        
        existing_by_id = {msg.get('id'): msg for msg in self.messages if msg.get('id')}
        new_items = []
        needs_summary_items = []

        for msg in messages:
            msg_id = msg.get('id')
            if msg_id and msg_id in existing_by_id:
                existing = existing_by_id[msg_id]
                incoming = dict(msg)

                # Preserve already-generated summary if new sync returns blank summary.
                incoming_summary = (incoming.get('summary') or "").strip()
                existing_summary = (existing.get('summary') or "").strip()
                if not incoming_summary and existing_summary:
                    incoming.pop('summary', None)

                incoming_analysis = (incoming.get('ai_analysis') or "").strip()
                existing_analysis = (existing.get('ai_analysis') or "").strip()
                if not incoming_analysis and existing_analysis:
                    incoming.pop('ai_analysis', None)

                existing.update(incoming)
                if not self._summary_for_table(existing):
                    needs_summary_items.append(existing)
            else:
                new_items.append(msg)
                self.messages.append(msg)

        print(f"   - {len(new_items)} are new, {len(messages) - len(new_items)} updated")

        # Desktop notifications for new Gmail messages
        for msg in new_items:
            sender = msg.get('sender', 'Unknown')
            subject = msg.get('subject', 'No Subject')
            notif_message = f"New Gmail from {sender}: {subject}"
            self.notifications.append({
                'message': notif_message,
                'time': msg.get('time', 'just now'),
                'read': False,
                'priority': msg.get('priority', 'normal')
            })
            self._notify_desktop("Gmail Message", notif_message)

        unread_count = sum(1 for n in self.notifications if not n.get('read', False))
        if hasattr(self, 'notif_badge'):
            self.notif_badge.setText(str(unread_count))
        # Sort by Priority (Rank) then Timestamp
        p_map = {'High': 3, 'Medium': 2, 'Low': 1}
        self.messages.sort(key=lambda x: (p_map.get(self._normalize_priority(x.get('priority', 'Low')), 1), float(x.get('timestamp', 0))), reverse=True)
        self.populate_table()
        
        # Queue for background AI summarization (progressive loading)
        if hasattr(self, 'queue_summary_generator'):
            queue_candidates = {m.get('id'): m for m in (new_items + needs_summary_items) if m.get('id')}
            to_queue = list(queue_candidates.values())
            print(f"🧠 Queueing {len(to_queue)} Gmail messages for background summarization...")
            if to_queue:
                self.queue_summary_generator.add_to_queue(to_queue)
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
        
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select File to Attach",
            "",
            "All Files (*.*)"
        )
        
        if file_paths:
            message_data = dict(message_data)
            message_data["_attachments"] = file_paths
            self.show_send_message_dialog(message_data)
    
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
        QTimer.singleShot(0, self.apply_responsive_table_layout)
    
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
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        
        sync_btn = QPushButton("Sync")
        sync_btn.setObjectName("btnSecondary")
        sync_btn.clicked.connect(self.sync_all_messages)
        
        generate_summaries_btn = QPushButton("🤖 Generate Summaries")
        generate_summaries_btn.setObjectName("btnSecondary")
        generate_summaries_btn.clicked.connect(self.generate_all_summaries)
        generate_summaries_btn.setToolTip("Generate AI summaries for all messages using Ollama")

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

        right_controls = QWidget()
        right_controls_layout = QVBoxLayout(right_controls)
        right_controls_layout.setContentsMargins(0, 0, 0, 0)
        right_controls_layout.setSpacing(6)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)
        buttons_row.addStretch()
        buttons_row.addWidget(generate_summaries_btn)
        buttons_row.addWidget(sync_btn)

        rows_row = QHBoxLayout()
        rows_row.setSpacing(8)
        rows_row.addStretch()
        rows_label = QLabel("Rows per page:")
        rows_label.setObjectName("rowsPerPageLabel")
        self.rows_per_page_combo = QComboBox()
        self.rows_per_page_combo.setObjectName("rowsPerPageCombo")
        for option in self.rows_per_page_options:
            self.rows_per_page_combo.addItem(str(option))
        self.rows_per_page_combo.setCurrentText(str(self.rows_per_page))
        self.rows_per_page_combo.currentTextChanged.connect(self.on_rows_per_page_changed)
        rows_row.addWidget(rows_label)
        rows_row.addWidget(self.rows_per_page_combo)

        right_controls_layout.addLayout(buttons_row)
        right_controls_layout.addLayout(rows_row)

        header_layout.addLayout(filter_layout)
        header_layout.addStretch()
        header_layout.addWidget(right_controls)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(10)

        self.selection_label = QLabel("")
        self.selection_label.setObjectName("selectionInfo")
        self.selection_label.hide()

        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.setObjectName("dangerBtn")
        self.delete_selected_btn.clicked.connect(self.delete_selected_messages)
        self.delete_selected_btn.hide()

        toolbar_layout.addWidget(self.selection_label)
        toolbar_layout.addWidget(self.delete_selected_btn)
        toolbar_layout.addStretch()
        
        self.table = QTableWidget()
        self.table.setObjectName("messageTable")
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "", "Source", "Sender", "Content Preview", "AI Summary", "Priority", "Time", "Actions"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        
        self.table.setColumnWidth(0, 40)
        self.table.setMinimumWidth(0)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(620)

        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table.setWordWrap(True)
        
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by_column)
        self.table.cellClicked.connect(self.on_table_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)

        pagination_layout = QHBoxLayout()
        pagination_layout.setSpacing(8)

        self.prev_page_btn = QPushButton("Previous")
        self.prev_page_btn.setObjectName("paginationBtn")
        self.prev_page_btn.clicked.connect(lambda: self.change_page(self.current_page - 1))

        self.next_page_btn = QPushButton("Next")
        self.next_page_btn.setObjectName("paginationBtn")
        self.next_page_btn.clicked.connect(lambda: self.change_page(self.current_page + 1))

        self.page_buttons_layout = QHBoxLayout()
        self.page_buttons_layout.setSpacing(6)
        self.page_status_label = QLabel("Page 1 of 1")
        self.page_status_label.setObjectName("paginationStatus")

        pagination_layout.addWidget(self.page_status_label)
        pagination_layout.addStretch()
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addLayout(self.page_buttons_layout)
        pagination_layout.addWidget(self.next_page_btn)
        
        layout.addLayout(header_layout)
        layout.addLayout(toolbar_layout)
        layout.addWidget(self.table)
        layout.addLayout(pagination_layout)
        
        return content

    def resizeEvent(self, event):
        """Adapt layout for different window sizes."""
        super().resizeEvent(event)
        self.apply_responsive_table_layout()

    def apply_responsive_table_layout(self):
        """Make the inbox table adapt for desktop/laptop widths."""
        if not hasattr(self, "table"):
            return

        window_width = self.width()
        compact = window_width < 1320
        ultra_compact = window_width < 1080
        self._is_compact_ui = compact
        self._is_ultra_compact_ui = ultra_compact

        # Keep key information visible; progressively hide lower-priority columns.
        self.table.setColumnHidden(1, ultra_compact)   # Source icon
        self.table.setColumnHidden(4, ultra_compact)   # Keep AI summary visible on normal compact sizes

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        if not ultra_compact:
            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        if not compact:
            header.setSectionResizeMode(4, QHeaderView.Stretch)

        self.table.setColumnWidth(0, 40)
        if ultra_compact:
            self.table.setColumnWidth(7, 190)
        elif compact:
            self.table.setColumnWidth(7, 235)
        else:
            self.table.setColumnWidth(7, 280)
    
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
            ("Urgent: 0", "statusItem"),
            # NEW: Add tone status indicator
            ("Tone: Formal", "toneStatusItem")
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
            self.apply_responsive_table_layout()

            all_keys = {self._message_key(m) for m in self.messages}
            self.selected_message_keys.intersection_update(all_keys)

            filtered = [m for m in self.messages if self.filter_message(m)]
            paged, total_pages = self._get_paginated_messages(filtered)
            self._current_page_messages = paged
            print(
                f"📋 Populating table with {len(paged)} items "
                f"(Filtered: {len(filtered)}, Total: {len(self.messages)})"
            )
            
            # Log breakdown
            sources = {}
            for m in paged:
                s = m.get('source', 'unknown')
                sources[s] = sources.get(s, 0) + 1
            if paged:
                print(f"   Sources: {sources}")
            
            self.update_status_bar()

            for row, msg in enumerate(paged):
                row_idx = self.table.rowCount()
                self.table.insertRow(row_idx)
                
                is_read = msg.get('read', False)
                msg_key = self._message_key(msg)
                
                checkbox = QCheckBox()
                checkbox.setChecked(msg_key in self.selected_message_keys)
                checkbox.stateChanged.connect(
                    lambda state, key=msg_key: self.on_message_checkbox_toggled(key, state)
                )
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
                
                full_summary = self._summary_for_table(msg)
                max_summary_len = 80
                display_summary = full_summary if len(full_summary) <= max_summary_len else full_summary[:max_summary_len - 3] + "..."
                summary_label = QLabel(display_summary)
                summary_label.setObjectName("summaryText")
                summary_label.setWordWrap(True)
                if full_summary:
                    summary_label.setToolTip("Click to view full summary")
                    summary_label.setCursor(Qt.PointingHandCursor)
                self.table.setCellWidget(row_idx, 4, summary_label)
                
                priority_val = self._normalize_priority(msg.get('priority', 'Low'))
                priority_order = {'High': 3, 'Medium': 2, 'Low': 1}
                
                display_label = priority_val.upper()
                priority_item = QTableWidgetItem(display_label)
                priority_item.setTextAlignment(Qt.AlignCenter)
                priority_item.setData(Qt.UserRole, priority_order.get(priority_val, 1))
                
                if priority_val == 'High':
                    priority_item.setBackground(QColor(255, 229, 224))
                    priority_item.setForeground(QColor(150, 71, 52))
                elif priority_val == 'Medium':
                    priority_item.setBackground(QColor(212, 244, 247))
                    priority_item.setForeground(QColor(2, 73, 80))
                else:
                    priority_item.setBackground(QColor(175, 221, 229))
                    priority_item.setForeground(QColor(0, 49, 53))
                
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
                reply_btn.setFixedHeight(30)
                reply_btn.setMinimumWidth(58)
                reply_btn.clicked.connect(lambda checked, m=msg: self.show_send_message_dialog(m))

                auto_reply_btn = QPushButton("Auto" if self._is_compact_ui else "Auto Reply")
                auto_reply_btn.setObjectName("actionBtn")
                auto_reply_btn.setFixedHeight(30)
                auto_reply_btn.setMinimumWidth(58 if self._is_compact_ui else 86)
                auto_reply_btn.setToolTip("Auto Reply")
                auto_reply_btn.clicked.connect(lambda checked, m=msg: self.auto_reply_message(m))

                smart_draft_btn = QPushButton("Draft")
                smart_draft_btn.setObjectName("actionBtn")
                smart_draft_btn.setFixedHeight(30)
                smart_draft_btn.setMinimumWidth(58)
                smart_draft_btn.setToolTip("Smart Draft")
                smart_draft_btn.clicked.connect(lambda checked, m=msg: self.smart_draft_message(m))

                actions_layout.addWidget(reply_btn)
                actions_layout.addWidget(auto_reply_btn)
                if not self._is_ultra_compact_ui:
                    actions_layout.addWidget(smart_draft_btn)
                actions_layout.addStretch()

                self.table.setCellWidget(row_idx, 7, actions_widget)
                
                self.table.setRowHeight(row_idx, 58 if self._is_compact_ui else 64)
                
                if not is_read:
                    for col in range(8):
                        item = self.table.item(row_idx, col)
                        if item:
                            item.setBackground(QColor("#E6F7F9"))
            self._update_selection_controls()
            self._refresh_pagination_controls(total_pages, len(filtered))
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

    def _message_key(self, msg: dict) -> str:
        """Build a stable key for row selection/deletion."""
        message_id = msg.get('id')
        if message_id:
            return str(message_id)
        return "|".join(
            [
                str(msg.get('source', '')),
                str(msg.get('timestamp', '')),
                str(msg.get('sender', '')),
                str(msg.get('subject', '')),
                str(msg.get('preview', ''))[:40],
            ]
        )

    def _summary_for_table(self, msg: dict) -> str:
        """Get the best available short summary text for table display."""
        summary = (msg.get('summary') or "").strip()
        if summary:
            return summary

        ai_analysis = (msg.get('ai_analysis') or "").strip()
        if not ai_analysis:
            return ""

        if "Task:" in ai_analysis:
            ai_analysis = ai_analysis.split("Task:", 1)[0]
        return ai_analysis.replace("Summary:", "").strip()

    def _get_paginated_messages(self, filtered: List[dict]) -> Tuple[List[dict], int]:
        total_items = len(filtered)
        total_pages = max(1, (total_items + self.rows_per_page - 1) // self.rows_per_page)
        self.current_page = min(max(1, self.current_page), total_pages)

        start = (self.current_page - 1) * self.rows_per_page
        end = start + self.rows_per_page
        return filtered[start:end], total_pages

    def _clear_page_buttons(self):
        while self.page_buttons_layout.count():
            item = self.page_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_pagination_controls(self, total_pages: int, filtered_count: int):
        self.page_status_label.setText(f"Page {self.current_page} of {total_pages} ({filtered_count} items)")
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)

        self._clear_page_buttons()
        if total_pages <= 1:
            return

        window = 2
        start = max(1, self.current_page - window)
        end = min(total_pages, self.current_page + window)
        for page in range(start, end + 1):
            btn = QPushButton(str(page))
            btn.setObjectName("pageBtn")
            if page == self.current_page:
                btn.setProperty("active", "true")
                btn.setStyle(btn.style())
            btn.clicked.connect(lambda _, p=page: self.change_page(p))
            self.page_buttons_layout.addWidget(btn)

    def on_rows_per_page_changed(self, text: str):
        try:
            self.rows_per_page = max(1, int(text))
        except ValueError:
            self.rows_per_page = 15
        self.current_page = 1
        self.populate_table()

    def change_page(self, page: int):
        if page < 1:
            return
        self.current_page = page
        self.populate_table()

    def on_message_checkbox_toggled(self, message_key: str, state: int):
        if state == Qt.Checked:
            self.selected_message_keys.add(message_key)
        else:
            self.selected_message_keys.discard(message_key)
        self._update_selection_controls()

    def _update_selection_controls(self):
        selected_count = len(self.selected_message_keys)
        if selected_count > 0:
            self.selection_label.setText(f"{selected_count} selected")
            self.selection_label.show()
            self.delete_selected_btn.show()
        else:
            self.selection_label.hide()
            self.delete_selected_btn.hide()

    def delete_selected_messages(self):
        """Delete all selected messages after confirmation."""
        selected_count = len(self.selected_message_keys)
        if selected_count == 0:
            return

        confirm = QMessageBox.question(
            self,
            "Delete Messages",
            f"Delete {selected_count} selected message(s)? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        before = len(self.messages)
        self.messages = [m for m in self.messages if self._message_key(m) not in self.selected_message_keys]
        deleted = before - len(self.messages)
        self.selected_message_keys.clear()

        self.current_page = 1
        self.populate_table()
        self.show_status_message(f"Deleted {deleted} message(s).")
    
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
        self.current_page = 1
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
            filter_match = msg.get('priority') in ['High', 'urgent']
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
        self.current_page = 1
        
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
        if row >= len(self._current_page_messages):
            return

        msg = self._current_page_messages[row]

        # Checkbox and action columns are interactive controls.
        if column in (0, 7):
            return

        if column == 2:
            self.show_sender_details_dialog(msg)
            return

        if column == 3:
            self.show_full_message_dialog(msg)
            return

        if column == 4:
            self.show_full_summary_dialog(msg)
            return

        if column == 5:
            self.show_priority_details_dialog(msg)
            return
        return

    def on_table_cell_double_clicked(self, row, column):
        """Handle double-clicks on table cells.
        
        Args:
            row (int): Row index that was clicked
            column (int): Column index that was clicked
        """
        if row >= len(self._current_page_messages):
            return

        msg = self._current_page_messages[row]
        self.on_table_cell_clicked(row, column)

    def show_full_summary_dialog(self, msg):
        """Show AI summary with task classification badges and recommended actions."""
        # Support both old (string) and new (dict) call signatures
        if isinstance(msg, str):
            summary_text = msg
            msg = {}
        else:
            summary_text = msg.get('summary') or "No AI summary available yet."

        dialog = QDialog(self)
        dialog.setWindowTitle("AI Summary & Task Classification")
        dialog.resize(720, 540)
        dialog.setMinimumSize(580, 420)

        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#title {
                color: #003135;
                font-weight: 700;
                font-size: 17px;
            }
            QLabel#sectionHeader {
                color: #003135;
                font-size: 14px;
                font-weight: 700;
                margin-top: 4px;
            }
            QLabel#detailMeta {
                color: #024950;
                font-size: 13px;
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
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        # --- Title ---
        title_label = QLabel("AI Summary & Classification")
        title_label.setObjectName("title")
        layout.addWidget(title_label)

        # --- Badges Row ---
        if isinstance(msg, dict) and msg:
            badge_row = QHBoxLayout()
            badge_row.setSpacing(8)

            # Priority Badge
            priority = self._normalize_priority(msg.get('priority', 'Low'))
            priority_colors = {
                'High': ('#964734', '#FFE5E0'),
                'Medium': ('#8B6914', '#FFF8E0'),
                'Low': ('#2E7D32', '#E8F5E9'),
            }
            fg, bg = priority_colors.get(priority, ('#555', '#eee'))
            priority_badge = QLabel(f"  ⚡ {priority.upper()} Priority  ")
            priority_badge.setStyleSheet(f"""
                background-color: {bg}; color: {fg};
                padding: 4px 12px; border-radius: 10px;
                font-size: 12px; font-weight: 700;
            """)
            badge_row.addWidget(priority_badge)

            # Task Classification Badge
            ai_tasks = msg.get('ai_tasks', [])
            task_label = ai_tasks[0] if ai_tasks else 'Informational'
            task_colors = {
                'File Attachment Required': ('#6A1B9A', '#F3E5F5'),
                'Draft Generation': ('#1565C0', '#E3F2FD'),
                'Auto Reply': ('#2E7D32', '#E8F5E9'),
                'Simple Reply Required': ('#E65100', '#FFF3E0'),
                'Informational': ('#455A64', '#ECEFF1'),
            }
            t_fg, t_bg = task_colors.get(task_label, ('#555', '#eee'))
            task_icon = {
                'File Attachment Required': '📎',
                'Draft Generation': '✍️',
                'Auto Reply': '⚡',
                'Simple Reply Required': '💬',
                'Informational': 'ℹ️',
            }.get(task_label, 'ℹ️')
            task_badge = QLabel(f"  {task_icon} {task_label}  ")
            task_badge.setStyleSheet(f"""
                background-color: {t_bg}; color: {t_fg};
                padding: 4px 12px; border-radius: 10px;
                font-size: 12px; font-weight: 700;
            """)
            badge_row.addWidget(task_badge)
            badge_row.addStretch()
            layout.addLayout(badge_row)

            # --- Recommended Actions ---
            actions_header = QLabel("📋 Recommended Actions")
            actions_header.setObjectName("sectionHeader")
            layout.addWidget(actions_header)

            action_text = self._get_recommended_action(task_label, priority, msg)
            action_label = QLabel(action_text)
            action_label.setWordWrap(True)
            action_label.setStyleSheet("""
                background-color: #F0FAFB;
                border: 1px solid #AFDDE5;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                color: #024950;
                line-height: 1.5;
            """)
            layout.addWidget(action_label)

        # --- Summary Section ---
        summary_header = QLabel("📝 AI Summary")
        summary_header.setObjectName("sectionHeader")
        layout.addWidget(summary_header)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(summary_text)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnSecondary")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(close_btn)

        layout.addWidget(text_edit)
        layout.addLayout(btn_layout)
        dialog.exec()

    def show_sender_details_dialog(self, msg: dict):
        """Show sender-focused information only."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Sender Details")
        dialog.resize(680, 420)
        dialog.setMinimumSize(560, 360)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#detailTitle {
                color: #003135;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#detailMeta {
                color: #024950;
                font-size: 13px;
            }
            QTextEdit {
                border: 1px solid #AFDDE5;
                border-radius: 8px;
                background-color: #F8FCFC;
                color: #003135;
                padding: 8px;
                font-size: 13px;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        sender = msg.get('sender', 'Unknown')
        sender_email = msg.get('email', '') or msg.get('channel_name', '')
        source = str(msg.get('source', '')).upper() or "UNKNOWN"

        title = QLabel(sender)
        title.setObjectName("detailTitle")
        meta = QLabel(f"Source: {source}")
        meta.setObjectName("detailMeta")

        if sender_email:
            contact_line = QLabel(f"Contact: {sender_email}")
            contact_line.setObjectName("detailMeta")
        else:
            contact_line = QLabel("Contact: not available")
            contact_line.setObjectName("detailMeta")

        stats = self.compute_sender_stats(sender, msg.get('email', ''))
        stats_label = QLabel(
            f"Activity with this sender  |  Last week: {stats['last_week']}  Last month: {stats['last_month']}  Last 7 weeks: {stats['last_7_weeks']}"
        )
        stats_label.setObjectName("detailMeta")
        stats_label.setWordWrap(True)

        recent_title = QLabel("Recent messages from this sender")
        recent_title.setObjectName("detailMeta")
        recent_title.setStyleSheet("font-weight: 700;")

        recent_box = QTextEdit()
        recent_box.setReadOnly(True)
        recent_box.setMinimumHeight(180)
        recent_box.setPlainText(self._build_sender_recent_messages(msg))

        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnSecondary")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addWidget(title)
        layout.addWidget(meta)
        layout.addWidget(contact_line)
        layout.addWidget(stats_label)
        layout.addWidget(recent_title)
        layout.addWidget(recent_box)
        layout.addLayout(btn_layout)

        dialog.exec()

    def show_full_message_dialog(self, msg: dict):
        """Show AI Analysis dialog with task classification, priority, and calendar info."""
        dialog = QDialog(self)
        dialog.setWindowTitle("AI Analysis")
        dialog.resize(860, 680)
        dialog.setMinimumSize(700, 520)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#detailTitle {
                color: #003135;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#detailMeta {
                color: #024950;
                font-size: 13px;
            }
            QLabel#sectionHeader {
                color: #003135;
                font-size: 14px;
                font-weight: 700;
                margin-top: 6px;
            }
            QTextEdit {
                border: 1px solid #AFDDE5;
                border-radius: 8px;
                background-color: #F8FCFC;
                color: #003135;
                padding: 8px;
                font-size: 13px;
            }
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        source = str(msg.get('source', '')).upper() or "UNKNOWN"
        sender = msg.get('sender', 'Unknown')
        subject = msg.get('subject', msg.get('content_preview', 'No Subject'))
        timestamp = msg.get('time', '')
        priority = self._normalize_priority(msg.get('priority', 'Low'))

        # --- Title ---
        title = QLabel(subject or "No Subject")
        title.setObjectName("detailTitle")
        meta_top = QLabel(f"From: {sender}  |  Source: {source}  |  Time: {timestamp}")
        meta_top.setObjectName("detailMeta")
        meta_top.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(meta_top)

        # --- Badges Row (Priority + Task Classification) ---
        badge_row = QHBoxLayout()
        badge_row.setSpacing(8)

        # Priority Badge
        priority_colors = {
            'High': ('#964734', '#FFE5E0'),
            'Medium': ('#8B6914', '#FFF8E0'),
            'Low': ('#2E7D32', '#E8F5E9'),
        }
        fg, bg = priority_colors.get(priority, ('#555', '#eee'))
        priority_badge = QLabel(f"  ⚡ {priority.upper()} Priority  ")
        priority_badge.setStyleSheet(f"""
            background-color: {bg}; color: {fg};
            padding: 4px 12px; border-radius: 10px;
            font-size: 12px; font-weight: 700;
        """)
        badge_row.addWidget(priority_badge)

        # Task Classification Badge
        ai_tasks = msg.get('ai_tasks', [])
        task_label = ai_tasks[0] if ai_tasks else 'Informational'
        task_colors = {
            'File Attachment Required': ('#6A1B9A', '#F3E5F5'),
            'Draft Generation': ('#1565C0', '#E3F2FD'),
            'Auto Reply': ('#2E7D32', '#E8F5E9'),
            'Simple Reply Required': ('#E65100', '#FFF3E0'),
            'Informational': ('#455A64', '#ECEFF1'),
        }
        t_fg, t_bg = task_colors.get(task_label, ('#555', '#eee'))
        task_icon = {
            'File Attachment Required': '📎',
            'Draft Generation': '✍️',
            'Auto Reply': '⚡',
            'Simple Reply Required': '💬',
            'Informational': 'ℹ️',
        }.get(task_label, 'ℹ️')
        task_badge = QLabel(f"  {task_icon} {task_label}  ")
        task_badge.setStyleSheet(f"""
            background-color: {t_bg}; color: {t_fg};
            padding: 4px 12px; border-radius: 10px;
            font-size: 12px; font-weight: 700;
        """)
        badge_row.addWidget(task_badge)

        # Event count badge (if events detected)
        event_count = len(msg.get('ai_events', []))
        if event_count > 0:
            event_badge = QLabel(f"  📅 {event_count} Event{'s' if event_count > 1 else ''} Detected  ")
            event_badge.setStyleSheet("""
                background-color: #E8F5E9; color: #1B5E20;
                padding: 4px 12px; border-radius: 10px;
                font-size: 12px; font-weight: 700;
            """)
            badge_row.addWidget(event_badge)

        badge_row.addStretch()
        layout.addLayout(badge_row)

        # --- Recommended Actions Section ---
        actions_header = QLabel("📋 Recommended Actions")
        actions_header.setObjectName("sectionHeader")
        layout.addWidget(actions_header)

        action_text = self._get_recommended_action(task_label, priority, msg)
        action_label = QLabel(action_text)
        action_label.setObjectName("detailMeta")
        action_label.setWordWrap(True)
        action_label.setStyleSheet("""
            background-color: #F0FAFB;
            border: 1px solid #AFDDE5;
            border-radius: 8px;
            padding: 10px 14px;
            font-size: 13px;
            color: #024950;
            line-height: 1.5;
        """)
        layout.addWidget(action_label)

        # --- Calendar Schedule Suggestions ---
        schedule_items = msg.get('ai_events') or []
        if schedule_items:
            schedule_title = QLabel("📅 Calendar Events Detected")
            schedule_title.setObjectName("sectionHeader")
            layout.addWidget(schedule_title)

            schedule_box = QTextEdit()
            schedule_box.setReadOnly(True)
            schedule_box.setMaximumHeight(100)
            schedule_box.setPlainText(self._format_schedule_items(schedule_items))
            layout.addWidget(schedule_box)

            review_schedule_btn = QPushButton("Review & Add to Calendar")
            review_schedule_btn.setObjectName("btnSecondary")
            review_schedule_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0FA4AF; color: white;
                    border: none; padding: 6px 16px;
                    border-radius: 6px; font-size: 12px; font-weight: 600;
                }
                QPushButton:hover { background-color: #024950; }
            """)
            review_schedule_btn.clicked.connect(lambda: (dialog.accept(), self.show_event_review_dialog(msg)))
            layout.addWidget(review_schedule_btn, alignment=Qt.AlignLeft)

        # --- Message Content ---
        body_title = QLabel("📄 Message Content")
        body_title.setObjectName("sectionHeader")
        layout.addWidget(body_title)

        body_widget = QTextEdit()
        body_widget.setReadOnly(True)
        body_widget.setPlainText(msg.get('full_content', msg.get('preview', '')))
        body_widget.setMinimumHeight(180)
        layout.addWidget(body_widget)

        # --- Close ---
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnSecondary")
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        dialog.exec()

    def _get_recommended_action(self, task_label: str, priority: str, msg: dict) -> str:
        """Generate a contextual recommended action based on task classification."""
        sender = msg.get('sender', 'the sender')
        actions = {
            'File Attachment Required': (
                f"📎 {sender} is requesting a file or document.\n"
                "→ Locate the requested file and attach it in your reply.\n"
                "→ If the file isn't ready, send an acknowledgement with an ETA."
            ),
            'Draft Generation': (
                f"✍️ This message from {sender} requires a detailed, composed reply.\n"
                "→ Use the 'Smart Draft' feature to generate a starting draft.\n"
                "→ Review and personalize the draft before sending."
            ),
            'Auto Reply': (
                "⚡ This appears to be an automated or transactional message.\n"
                "→ A simple acknowledgement (e.g., 'Noted', 'Thank you') is sufficient.\n"
                "→ Consider using Auto-Reply to respond instantly."
            ),
            'Simple Reply Required': (
                f"💬 {sender} is expecting a quick response or confirmation.\n"
                "→ Reply with a brief, direct answer.\n"
                "→ Keep your response concise and actionable."
            ),
            'Informational': (
                "ℹ️ This message is informational — no action is strictly required.\n"
                "→ Read and archive, or flag for later reference if relevant."
            ),
        }
        base = actions.get(task_label, actions['Informational'])
        if priority == 'High':
            base = "🔴 HIGH PRIORITY — Respond as soon as possible.\n\n" + base
        return base

    def show_priority_details_dialog(self, msg: dict):
        """Show a simple explanation of message priority."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Priority Details")
        dialog.resize(520, 300)
        dialog.setMinimumSize(460, 260)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        level = self._normalize_priority(msg.get('priority', 'Low')).upper()
        if level == "HIGH":
            advice = "Handle this message first. It likely has a time-sensitive or important request."
        elif level == "MEDIUM":
            advice = "Review this message soon. It contains useful information or an action to take."
        else:
            advice = "This message is not urgent. You can review it later."

        title = QLabel(f"Priority: {level}")
        title.setObjectName("detailTitle")
        context = QLabel(
            f"From: {msg.get('sender', 'Unknown')}  |  Subject: {msg.get('subject', msg.get('content_preview', 'No Subject'))}"
        )
        context.setObjectName("detailMeta")
        context.setWordWrap(True)

        explanation = QTextEdit()
        explanation.setReadOnly(True)
        explanation.setPlainText(advice)
        explanation.setMinimumHeight(120)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnSecondary")
        close_btn.clicked.connect(dialog.accept)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)

        layout.addWidget(title)
        layout.addWidget(context)
        layout.addWidget(explanation)
        layout.addLayout(btn_layout)
        dialog.exec()

    def _format_schedule_items(self, items: List[dict]) -> str:
        if not items:
            return (
                "No schedule suggestions were found from this message.\n"
                "Tip: clearer date/time phrases (for example: 'tomorrow at 7 PM') improve extraction."
            )

        lines = []
        for idx, item in enumerate(items, start=1):
            label = "To-do" if str(item.get("item_type", "")).lower() == "task" else "Meeting"
            start = self._fmt_schedule_dt(item.get("start_dt"))
            end = self._fmt_schedule_dt(item.get("end_dt"))
            confidence = float(item.get("confidence", 0.0))
            title = item.get("title", "Untitled")
            lines.append(
                f"{idx}. {title}\n"
                f"   Type: {label} | Starts: {start} | Ends: {end} | Confidence: {confidence:.2f}"
            )
        return "\n\n".join(lines)

    def _fmt_schedule_dt(self, value: Any) -> str:
        if not value:
            return "-"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %I:%M %p")
        try:
            return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %I:%M %p")
        except Exception:
            return str(value)

    def _build_sender_recent_messages(self, msg: dict) -> str:
        sender = msg.get('sender', '')
        email = msg.get('email', '')
        related = []
        for item in self.messages:
            if sender and item.get('sender') == sender:
                related.append(item)
            elif email and item.get('email') == email:
                related.append(item)

        def _safe_ts(entry: dict) -> float:
            try:
                return float(entry.get('timestamp', 0))
            except Exception:
                return 0.0

        related.sort(key=_safe_ts, reverse=True)
        lines = []
        for idx, item in enumerate(related[:8], start=1):
            subject = item.get('subject', item.get('content_preview', 'No Subject'))
            time_text = item.get('time', '')
            lines.append(f"{idx}. {subject} ({time_text})")

        return "\n".join(lines) if lines else "No previous messages from this sender."

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
            self.current_page = 1
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
        
        # NEW: Update tone status indicator
        if hasattr(self, 'orchestrator') and self.orchestrator:
            try:
                default_tone = self.orchestrator.tone_manager.user_profile.default_tone
                tone_display = default_tone.value.title() if default_tone else "None"
                self.status_labels.get("Tone").setText(f"Tone: {tone_display}")
            except Exception as e:
                print(f"Error updating tone status: {e}")
                self.status_labels.get("Tone").setText("Tone: Error")

    def show_status_message(self, message: str, timeout: int = 5000):
        """Display a temporary message in the status region (fallback to console)."""
        print(f"📊 {message}")
        # If we have a status bar label, update it
        if hasattr(self, 'status_labels') and 'Total Messages' in self.status_labels:
            original_text = self.status_labels['Total Messages'].text()
            self.status_labels['Total Messages'].setText(f"ℹ️ {message}")
            # Restore after timeout if possible, but for now just leave it or use a timer
        pass

    def _notify_desktop(self, title: str, message: str):
        """Send a desktop notification if supported (plyer)."""
        try:
            from plyer import notification
            notification.notify(title=title, message=message, timeout=6)
        except Exception as exc:
            print(f"Notification error: {exc}")

    def _schedule_table_refresh(self, delay_ms: int = 200):
        """Debounced table refresh to keep UI responsive."""
        if not hasattr(self, '_table_refresh_timer'):
            self._table_refresh_timer = QTimer()
            self._table_refresh_timer.setSingleShot(True)
            self._table_refresh_timer.timeout.connect(self.populate_table)
        self._table_refresh_timer.start(delay_ms)


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
        # Do not repopulate table here; it clears the expanded view.

    def toggle_message_expand(self, msg: dict):
        """Legacy handler kept for compatibility; opens details dialog."""
        self.show_full_message_dialog(msg)
    
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

        # Event review status + button
        events = msg.get('ai_events') or []
        events_label = QLabel(f"Events detected: {len(events)}")
        events_label.setStyleSheet("font-size: 12px; color: #024950;")
        ai_layout.addWidget(events_label)

        if len(events) > 0:
            review_btn = QPushButton("Review Events")
            review_btn.setObjectName("btnSecondary")
            review_btn.clicked.connect(lambda _, m=msg: self.show_event_review_dialog(m))
            ai_layout.addWidget(review_btn)
        
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

    def show_event_review_dialog(self, msg: dict):
        """Show extracted schedule suggestions for review and calendar insertion."""
        events = msg.get('ai_events', []) or []
        if not events:
            QMessageBox.information(
                self,
                "Schedule Suggestions",
                "No schedule suggestions were found for this message yet."
            )
            return

        dialog = EventReviewDialog(
            events=events,
            calendar_service=self.calendar_service,
            auto_select_threshold=0.85,
            auto_add_high_confidence=False,
            ics_output_dir=self.ics_output_dir,
            parent=self
        )
        dialog.exec()

    # -------------------------
    # SETTINGS
    # -------------------------
    # -------------------------
    # SETTINGS DIALOG
    # -------------------------
    def show_settings(self):
        """Show the application settings dialog."""
        gmail_status = self.gmail_service.get_status_snapshot()
        # NEW: Use enhanced settings dialog with tone features
        dialog = SettingsDialog(
            user_data=self.user_data, 
            parent=self, 
            gmail_status=gmail_status,
            orchestrator=self.orchestrator
        )
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
