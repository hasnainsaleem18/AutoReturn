# -------------------------
# GMAIL BACKEND SERVICE
# -------------------------
"""
Module for Gmail integration functionality including:
- OAuth2 authentication flow
- Email synchronization
- Message processing and management
- Integration with Gmail API
"""

# -------------------------
# IMPORTS
# -------------------------
import os
import re
import shutil
import threading
from datetime import datetime
from email.utils import parseaddr
from typing import List, Optional

from PySide6.QtCore import QObject, Signal

# Local imports
from src.backend.core.AutoReturn_Gmail_Automation import OAuthManager, GmailService as GmailAPIService, GmailServiceError


# -------------------------
# GMAIL INTEGRATION SERVICE
# -------------------------
class GmailIntegrationService(QObject):
    """
    Service for Gmail integration that provides a Qt-compatible interface
    to the Gmail API with support for background operations and signals.
    """

    connection_status = Signal(bool, str)
    new_messages = Signal(list)
    error_occurred = Signal(str)

    # -------------------------
    # INITIALIZATION
    # -------------------------
    def __init__(self, data_dir: str):
        """Initialize the Gmail integration service with the specified data directory.
        
        Args:
            data_dir: Directory to store authentication tokens and configuration
        """
        super().__init__()
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        # Authentication file paths
        self.client_secret_path = os.path.join(self.data_dir, "client_secret.json")
        self.token_path = os.path.join(self.data_dir, "token.json")

        # Service state
        self.oauth_manager: Optional[OAuthManager] = None
        self.gmail_api: Optional[GmailAPIService] = None
        self.is_connected: bool = False
        self._api_lock = threading.Lock()

    # -------------------------
    # AUTHENTICATION METHODS
    # -------------------------
    def configure_client_secret(self, source_path: str) -> str:
        """Configure the Gmail API client secret file.
        
        Args:
            source_path: Path to the client secret JSON file
            
        Returns:
            str: Path to the configured client secret file
            
        Raises:
            ValueError: If the provided file is not a JSON file
        """
        if not source_path.lower().endswith(".json"):
            raise ValueError("Please select a valid JSON credentials file.")

        shutil.copyfile(source_path, self.client_secret_path)
        return self.client_secret_path

    # -------------------------
    # HAS CLIENT SECRET
    # Checks if the system has client secret.
    # -------------------------
    def has_client_secret(self) -> bool:
        """Check if client secret file exists."""
        return os.path.exists(self.client_secret_path)

    # -------------------------
    # GET CLIENT SECRET DISPLAY
    # Retrieves client secret display.
    # -------------------------
    def get_client_secret_display(self) -> Optional[str]:
        """Get the display name of the client secret file if it exists."""
        if self.has_client_secret():
            return os.path.basename(self.client_secret_path)
        return None

    # -------------------------
    # HAS TOKEN
    # Checks if the system has token.
    # -------------------------
    def has_token(self) -> bool:
        """Check if an authentication token exists."""
        return os.path.exists(self.token_path)

    # -------------------------
    # CONNECTION MANAGEMENT
    # -------------------------
    def connect(self, allow_flow: bool = True) -> tuple[bool, str]:
        """Establish connection to Gmail API.
        
        Args:
            allow_flow: If True, allows OAuth flow for token generation
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.has_client_secret():
            message = "Upload your client_secret.json to start Gmail setup."
            self.error_occurred.emit(message)
            self.connection_status.emit(False, message)
            return False, message

        self.oauth_manager = OAuthManager(
            client_secret_path=self.client_secret_path,
            token_path=self.token_path
        )

        success = self.oauth_manager.load_or_generate_token(allow_flow=allow_flow)
        if not success:
            message = "Gmail authentication failed. Please try again."
            self.connection_status.emit(False, message)
            return False, message

        self.gmail_api = GmailAPIService(self.oauth_manager.creds, propagate_errors=True)
        self.is_connected = True
        message = "Connected to Gmail inbox"
        self.connection_status.emit(True, message)
        return True, message

    # -------------------------
    # DISCONNECT
    # Terminates connections for the operation.
    # -------------------------
    def disconnect(self):
        """Disconnect from Gmail API and clean up resources."""
        self.gmail_api = None
        self.is_connected = False
        self.connection_status.emit(False, "Disconnected from Gmail")

    # -------------------------
    # GET STATUS SNAPSHOT
    # Retrieves status snapshot.
    # -------------------------
    def get_status_snapshot(self) -> dict:
        """Get current connection and authentication status.
        
        Returns:
            dict: Status information including connection state and auth status
        """
        return {
            "has_client_secret": self.has_client_secret(),
            "client_secret_name": self.get_client_secret_display(),
            "has_token": self.has_token(),
            "is_connected": self.is_connected,
        }

    # -------------------------
    # MESSAGE OPERATIONS
    # -------------------------
    def sync_messages(self, max_results: int = 25, query: str = "in:inbox") -> List[dict]:
        """Fetch messages and emit them via new_messages signal.
        
        Args:
            max_results: Maximum number of messages to fetch
            query: Gmail search query string
            
        Returns:
            List[dict]: List of parsed message dictionaries
        """
        messages = self.fetch_messages(max_results=max_results, query=query)
        if messages:
            self.new_messages.emit(messages)
        return messages

    # -------------------------
    # FETCH MESSAGES
    # Pulls data for messages.
    # -------------------------
    def fetch_messages(self, max_results: int = 25, query: str = "in:inbox") -> List[dict]:
        """Fetch messages from Gmail API.
        
        Args:
            max_results: Maximum number of messages to fetch
            query: Gmail search query string
            
        Returns:
            List[dict]: List of parsed message dictionaries
        """
        if not self.gmail_api:
            message = "Connect to Gmail before syncing messages."
            self.error_occurred.emit(message)
            return []

        with self._api_lock:
            try:
                message_refs = self.gmail_api.list_messages(query=query, max_results=max_results)
            except GmailServiceError as exc:  # pragma: no cover - network
                message = str(exc)
                if "timed out" in message.lower():
                    message = (
                        "Gmail request timed out. This is usually a network issue.\n\n"
                        "Please check your internet connection, VPN, or firewall. "
                        "If you're on a restricted network, Gmail API calls may be blocked."
                    )
                self.error_occurred.emit(message)
                return []
            except Exception as exc:  # pragma: no cover - network
                self.error_occurred.emit(str(exc))
                return []

            if not message_refs:
                return []

            parsed_messages = []
            for ref in message_refs:
                msg_id = ref.get("id")
                if not msg_id:
                    continue
                try:
                    details = self.gmail_api.read_message(msg_id)
                except GmailServiceError as exc:  # pragma: no cover - network
                    self.error_occurred.emit(str(exc))
                    continue
                except Exception as exc:  # pragma: no cover - network
                    self.error_occurred.emit(str(exc))
                    continue

                if not details:
                    continue
                parsed_messages.append(self._to_inbox_message(details))

            return parsed_messages

    # -------------------------
    # MESSAGE OPERATIONS (CONTINUED)
    # -------------------------
    def reply_to_message(self, ui_message: dict, reply_body: str, attachments: list = None) -> tuple[bool, str]:
        """Send a reply to a message.
        
        Args:
            ui_message: The original message to reply to
            reply_body: The content of the reply
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if not self.gmail_api:
            message = "Connect to Gmail before replying."
            self.error_occurred.emit(message)
            return False, message

        thread_id = ui_message.get("thread_id") or ui_message.get("threadId")
        to_email = ui_message.get("email", "")

        if not thread_id or not to_email:
            message = "Missing thread or recipient information for this email."
            self.error_occurred.emit(message)
            return False, message

        try:
            raw_subject = (ui_message.get("subject", "") or "").strip()
            subject = raw_subject if raw_subject.lower().startswith("re:") else (f"Re: {raw_subject}" if raw_subject else "Re:")
            in_reply_to = (ui_message.get("message_id_header", "") or "").strip()
            references = (ui_message.get("references_header", "") or "").strip()
            if in_reply_to:
                references = f"{references} {in_reply_to}".strip() if references else in_reply_to
            with self._api_lock:
                self.gmail_api.reply(
                    thread_id,
                    to_email,
                    reply_body,
                    subject=subject,
                    attachments=attachments or [],
                    in_reply_to=in_reply_to,
                    references=references,
                )
            return True, "Reply sent successfully."
        except Exception as exc:
            message = str(exc)
            self.error_occurred.emit(message)
            return False, message

    # -------------------------
    # CREATE DRAFT FOR MESSAGE
    # Instantiates and creates draft for message.
    # -------------------------
    def create_draft_for_message(self, ui_message: dict, draft_body: str) -> tuple[bool, str]:
        """Create a Gmail draft reply for the specified message."""
        if not self.gmail_api:
            message = "Connect to Gmail before creating drafts."
            self.error_occurred.emit(message)
            return False, message

        to_email = ui_message.get("email", "")
        subject = ui_message.get("subject", "")

        if not to_email:
            message = "Missing recipient information for draft creation."
            self.error_occurred.emit(message)
            return False, message

        try:
            with self._api_lock:
                draft_id = self.gmail_api.create_draft(to_email, f"Re: {subject}" if subject else "Re:", draft_body)
            return True, draft_id
        except Exception as exc:
            message = str(exc)
            self.error_occurred.emit(message)
            return False, message

    # -------------------------
    # HELPER METHODS
    # -------------------------
    def _to_inbox_message(self, raw_message: dict) -> dict:
        """Convert raw Gmail API message to standardized inbox message format.
        
        Args:
            raw_message: Raw message data from Gmail API
            
        Returns:
            dict: Standardized message dictionary
        """
        sender_display, sender_email = self._parse_sender(raw_message.get("from", ""))
        internal_ts = raw_message.get("internalDate")
        dt = self._internaldate_to_datetime(internal_ts)
        timestamp_value = dt.timestamp() if dt else 0.0

        labels = raw_message.get("labelIds", [])
        is_unread = "UNREAD" in labels if labels else False

        priority = self._detect_priority(raw_message)

        raw_subject = raw_message.get("subject", "(No Subject)")
        raw_snippet = raw_message.get("snippet", "(No Content)")
        raw_body = raw_message.get("body", "")

        subject = self._clean_display_text(raw_subject) or "(No Subject)"
        snippet = self._clean_display_text(raw_snippet) or subject
        body = self._clean_display_text(raw_body)

        return {
            "id": raw_message.get("id"),
            "source": "gmail",
            "sender": sender_display or sender_email or "Unknown",
            "email": sender_email or "",
            "subject": subject,
            "content_preview": snippet,
            "preview": snippet,
            "full_content": body or snippet,
            "summary": "",
            "priority": priority,
            "time": self._format_relative_time(dt),
            "timestamp": timestamp_value,
            "datetime": dt,
            "read": not is_unread,
            "thread_id": raw_message.get("threadId"),
            "message_id_header": raw_message.get("message_id_header", ""),
            "references_header": raw_message.get("references_header", ""),
            "label_ids": labels,
            "history_id": raw_message.get("historyId"),
            "has_attachments": bool(raw_message.get("has_attachments")),
            "ai_insights": None
        }

    # -------------------------
    # CLEAN DISPLAY TEXT
    # Handles clean functionality for display text.
    # -------------------------
    def _clean_display_text(self, text: Optional[str]) -> str:
        """Clean and format message text for display.
        
        Args:
            text: Raw text to clean
            
        Returns:
            str: Cleaned and formatted text
        """
        if not text:
            return ""

        cleaned = text

        cleaned = re.sub(r"\[image:[^\]]*\]", "", cleaned, flags=re.IGNORECASE)

        cleaned = " ".join(cleaned.split())

        return cleaned.strip()

    # -------------------------
    # PARSE SENDER
    # Extracts and parses sender.
    # -------------------------
    def _parse_sender(self, sender_value: str) -> tuple[str, str]:
        """Parse sender information from email header.
        
        Args:
            sender_value: Raw sender string from email header
            
        Returns:
            tuple: (display_name: str, email_address: str)
        """
        name, email_addr = parseaddr(sender_value)
        return name, email_addr

    # -------------------------
    # INTERNALDATE TO DATETIME
    # Handles internaldate functionality for to datetime.
    # -------------------------
    def _internaldate_to_datetime(self, internal_date: Optional[str]) -> Optional[datetime]:
        """Convert Gmail's internal date string to datetime object.
        
        Args:
            internal_date: Gmail's internal date string (milliseconds since epoch)
            
        Returns:
            datetime: Parsed datetime object, or None if invalid
        """
        try:
            if internal_date:
                return datetime.fromtimestamp(int(internal_date) / 1000)
        except (TypeError, ValueError):
            return None
        return None

    # -------------------------
    # FORMAT RELATIVE TIME
    # Formats output for relative time.
    # -------------------------
    def _format_relative_time(self, msg_datetime: Optional[datetime]) -> str:
        """Format datetime as a relative time string (e.g., '2 hours ago').
        
        Args:
            msg_datetime: Datetime to format
            
        Returns:
            str: Formatted relative time string
        """
        if not msg_datetime:
            return "Unknown"

        diff = datetime.now() - msg_datetime
        seconds = diff.total_seconds()

        if seconds < 60:
            return f"{int(seconds)}s ago"
        if seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        if seconds < 604800:
            days = int(seconds // 86400)
            return f"{days}d ago"
        return msg_datetime.strftime("%b %d")

    # -------------------------
    # DETECT PRIORITY
    # Handles detect functionality for priority.
    # -------------------------
    def _detect_priority(self, raw_message: dict) -> str:
        """Determine message priority based on various factors.
        
        Args:
            raw_message: Raw message data
            
        Returns:
            str: Priority level ('high', 'medium', or 'low')
        """
        subject = (raw_message.get("subject") or "").lower()
        snippet = (raw_message.get("snippet") or "").lower()
        text = f"{subject} {snippet}"

        urgent_keywords = ["urgent", "immediately", "critical", "asap"]
        high_keywords = ["important", "priority", "follow up", "deadline"]

        if any(word in text for word in urgent_keywords):
            return "urgent"
        if any(word in text for word in high_keywords):
            return "high"
        return "normal"
