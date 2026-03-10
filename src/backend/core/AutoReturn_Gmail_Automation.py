# -------------------------
# AUTO RETURN GMAIL AUTOMATION
# -------------------------
"""
Module for Gmail automation functionality including:
- Email listing and searching
- Reading and sending emails
- Draft management
- Scheduled emails
- Gmail API integration
"""

# -------------------------
# IMPORTS
# -------------------------
import os
import json
import time
import base64
from email import message_from_bytes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import threading
from datetime import datetime

try:
    from plyer import notification
except ImportError:  # pragma: no cover - optional dependency
    notification = None

# Google API imports
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# -------------------------
# CONFIGURATION
# -------------------------
TOKEN_PATH = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"
POLL_INTERVAL = 5
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # read emails
    "https://www.googleapis.com/auth/gmail.modify",    # mark read/unread, delete
    "https://www.googleapis.com/auth/gmail.send",      # send emails
    "https://www.googleapis.com/auth/gmail.compose",   # create drafts, send
    "https://www.googleapis.com/auth/calendar"         # calendar events
]

# -------------------------
# CUSTOM EXCEPTIONS
# -------------------------
class GmailServiceError(Exception):
    """Domain-level exception for Gmail automation service failures."""
    pass

# -------------------------
# MESSAGE PARSER
# -------------------------
class MessageParser:
    """Utility class for parsing and decoding email messages."""
    
    @staticmethod
    def decode_message(payload):
        """Decode email message payload into readable text.
        
        Args:
            payload: Raw message payload from Gmail API
            
        Returns:
            str: Decoded message content
        """
        try:
            data = payload.get("body", {}).get("data")
            if data:
                decoded_bytes = base64.urlsafe_b64decode(data)
                email_msg = message_from_bytes(decoded_bytes)
                return email_msg.get_payload()

            parts = payload.get("parts", [])
            if parts:
                for part in parts:
                    mime_type = part.get("mimeType", "")
                    if mime_type == "text/plain":
                        data = part.get("body", {}).get("data")
                        if data:
                            return base64.urlsafe_b64decode(data).decode("utf-8")
                    elif mime_type.startswith("multipart/"):
                        text = MessageParser.decode_message(part)
                        if text:
                            return text
            return "(No Content)"
        except Exception as e:
            return f"(Failed to parse message: {e})"

    @staticmethod
    def extract_header(headers, name):
        """Extract a specific header value from email headers.
        
        Args:
            headers: List of header dictionaries
            name: Header name to extract (case-insensitive)
            
        Returns:
            str: Header value or 'Unknown' if not found
        """
        for h in headers:
            if h["name"].lower() == name.lower():
                return h["value"]
        return "Unknown"

# -------------------------
# POPUP MANAGER
# -------------------------
class PopupManager:
    """Handles desktop notifications for new emails."""
    
    @staticmethod
    def show(title, message):
        """Display a desktop notification.
        
        Args:
            title: Notification title
            message: Notification message content
        """
        try:
            notification.notify(title=title, message=message, timeout=8)
        except Exception:
            pass

# -------------------------
# OAUTH MANAGER
# -------------------------
class OAuthManager:
    # -------------------------
    # INIT
    # Stores OAuth file paths/scopes and runtime credentials holder.
    # -------------------------
    def __init__(self, client_secret_path=CLIENT_SECRET_FILE, token_path=TOKEN_PATH, scopes=None):
        self.creds = None
        self.client_secret_path = client_secret_path
        self.token_path = token_path
        self.scopes = scopes or SCOPES

    # -------------------------
    # LOAD OR GENERATE TOKEN
    # Authentication flow:
    # 1) Load existing token if present.
    # 2) Validate required scopes.
    # 3) If needed and allowed, run interactive OAuth flow.
    # 4) Persist token.json for future runs.
    # -------------------------
    def load_or_generate_token(self, allow_flow=True, force_reauth: bool = False):
        if os.path.exists(self.token_path) and not force_reauth:
            with open(self.token_path, "r") as f:
                data = json.load(f)
                self.creds = Credentials.from_authorized_user_info(data, self.scopes)
                print("[OAuth] Loaded existing token.")
                # Ensure token has required scopes
                if self.creds.scopes and not set(self.scopes).issubset(set(self.creds.scopes)):
                    print("[OAuth] Token missing required scopes. Re-auth needed.")
                    if not allow_flow:
                        return False
                else:
                    return True

        if not allow_flow:
            print("[OAuth] Token not found and interactive flow is disabled.")
            return False

        if not os.path.exists(self.client_secret_path):
            print(f"[OAuth] ERROR: {self.client_secret_path} not found!")
            print("\n=== Beginner Setup Instructions ===")
            print("1. Open https://console.cloud.google.com/apis/credentials")
            print("2. Click 'Create Credentials' -> 'OAuth Client ID'")
            print("3. Select 'Desktop App', name it, click 'Create'")
            print("4. Download JSON and save as 'client_secret.json'")
            print("5. Run this script again")
            return False

        print("[OAuth] No token found. Running authorization flow...")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(self.client_secret_path, self.scopes)
            self.creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as f:
                f.write(self.creds.to_json())
            print(f"[OAuth] Token generated and saved as {os.path.basename(self.token_path)}\n")
            return True
        except Exception as e:
            print(f"[OAuth] Failed to generate token: {e}")
            return False

# -------------------------
# GMAIL SERVICE
# -------------------------
class GmailService:
    # -------------------------
    # INIT
    # Builds authenticated Gmail API client and configures retry/error behavior.
    # -------------------------
    def __init__(self, creds, propagate_errors: bool = False, max_retries: int = 2):
        self.service = build("gmail", "v1", credentials=creds)
        self.propagate_errors = propagate_errors
        self.max_retries = max(0, max_retries)

    # -------------------------
    # ERROR HANDLER
    # Centralized error policy:
    # - log + fallback in non-strict mode
    # - raise GmailServiceError in strict mode
    # -------------------------
    def _handle_error(self, prefix: str, error: Exception, fallback):
        print(f"{prefix}: {error}")
        if self.propagate_errors:
            raise GmailServiceError(str(error)) from error
        return fallback

    # -------------------------
    # LIST MESSAGES
    # Queries Gmail for message ids matching a search query.
    # Returns lightweight message references (not full payloads).
    # -------------------------
    def list_messages(self, query="", max_results=20):
        try:
            res = (
                self.service
                .users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute(num_retries=self.max_retries)
            )
            return res.get("messages", [])
        except Exception as e:
            return self._handle_error("[Error] Failed to list messages", e, [])

    # -------------------------
    # READ MESSAGE
    # Fetches full Gmail payload and normalizes it into a UI-friendly dict.
    # Includes decoded body, snippet, thread metadata, and attachment flag.
    # -------------------------
    def read_message(self, msg_id):
        try:
            msg = (
                self.service
                .users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute(num_retries=self.max_retries)
            )
            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            body = MessageParser.decode_message(payload)
            snippet = (body[:100] + "...") if body and len(body) > 100 else (body or "(No Content)")
            has_attachments = self._has_attachments(payload)
            return {
                "id": msg_id,
                "from": MessageParser.extract_header(headers, "From") or "(Unknown)",
                "subject": MessageParser.extract_header(headers, "Subject") or "(No Subject)",
                "message_id_header": MessageParser.extract_header(headers, "Message-ID") or "",
                "references_header": MessageParser.extract_header(headers, "References") or "",
                "body": body or "(No Content)",
                "snippet": snippet,
                "threadId": msg.get("threadId"),
                "internalDate": msg.get("internalDate"),
                "labelIds": msg.get("labelIds", []),
                "historyId": msg.get("historyId"),
                "has_attachments": has_attachments,
            }
        except Exception as e:
            return self._handle_error(
                f"[Warning] Failed to read message {msg_id}",
                e,
                {
                    "id": msg_id,
                    "from": "(Error)",
                    "subject": "(Error)",
                    "body": "(Error reading message)",
                    "snippet": "(Error)",
                    "threadId": None,
                    "internalDate": None,
                    "labelIds": [],
                    "historyId": None
                }
            )

    # -------------------------
    # ATTACHMENT PRESENCE CHECK
    # Recursively inspects payload parts to detect whether any attachment exists.
    # -------------------------
    def _has_attachments(self, payload):
        try:
            if not payload:
                return False

            filename = payload.get("filename")
            if filename:
                return True

            body = payload.get("body", {})
            if body.get("attachmentId"):
                return True

            parts = payload.get("parts") or []
            for part in parts:
                if self._has_attachments(part):
                    return True

            return False
        except Exception:
            return False

    # -------------------------
    # MARK AS READ
    # Removes UNREAD label from a specific message.
    # -------------------------
    def mark_as_read(self, msg_id):
        try:
            (
                self.service
                .users()
                .messages()
                .modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]})
                .execute(num_retries=self.max_retries)
            )
        except Exception as e:
            self._handle_error("[Error] Could not mark as read", e, None)

    # -------------------------
    # MARK AS UNREAD
    # Adds UNREAD label back to a specific message.
    # -------------------------
    def mark_as_unread(self, msg_id):
        try:
            (
                self.service
                .users()
                .messages()
                .modify(userId="me", id=msg_id, body={"addLabelIds": ["UNREAD"]})
                .execute(num_retries=self.max_retries)
            )
        except Exception as e:
            self._handle_error("[Error] Could not mark as unread", e, None)

    # -------------------------
    # BUILD MIME MESSAGE
    # Creates RFC-compliant MIME payload with optional file attachments,
    # then returns base64-url encoded raw content for Gmail send API.
    # -------------------------
    def _build_mime_message(self, to: str, subject: str, message: str, attachments: list = None):
        """Build a MIME message with optional attachments."""
        msg = MIMEMultipart()
        msg["to"] = to
        msg["subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        for file_path in attachments or []:
            ctype, encoding = mimetypes.guess_type(file_path)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)

            with open(file_path, "rb") as f:
                part = MIMEBase(maintype, subtype)
                part.set_payload(f.read())
                encoders.encode_base64(part)

            filename = os.path.basename(file_path)
            part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return raw

    # -------------------------
    # SEND NEW EMAIL
    # Sends a fresh outbound email (with or without attachments).
    # -------------------------
    def send_email(self, to, subject, message, attachments: list = None):
        if attachments:
            raw = self._build_mime_message(to, subject, message, attachments)
        else:
            msg = MIMEText(message)
            msg["to"] = to
            msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        try:
            return (
                self.service
                .users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute(num_retries=self.max_retries)
            )
        except Exception as e:
            return self._handle_error("[Error] Failed to send email", e, None)

    # -------------------------
    # REPLY IN THREAD
    # Sends an email reply anchored to an existing Gmail thread.
    # Supports reply headers and optional attachments.
    # -------------------------
    def reply(
        self,
        thread_id,
        to,
        message,
        subject: str = "",
        attachments: list = None,
        in_reply_to: str = "",
        references: str = "",
    ):
        if attachments:
            raw = self._build_mime_message(to, subject or "Re:", message, attachments)
        else:
            msg = MIMEText(message)
            msg["to"] = to
            if subject:
                msg["subject"] = subject
            if in_reply_to:
                msg["In-Reply-To"] = in_reply_to
            if references:
                msg["References"] = references
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        try:
            return (
                self.service
                .users()
                .messages()
                .send(userId="me", body={"raw": raw, "threadId": thread_id})
                .execute(num_retries=self.max_retries)
            )
        except Exception as e:
            return self._handle_error("[Error] Failed to send reply", e, None)

    # -------------------------
    # DELETE MESSAGE
    # Permanently removes a message by id from Gmail mailbox.
    # -------------------------
    def delete_message(self, msg_id):
        try:
            (
                self.service
                .users()
                .messages()
                .delete(userId="me", id=msg_id)
                .execute(num_retries=self.max_retries)
            )
        except Exception as e:
            self._handle_error("[Error] Could not delete message", e, None)

    # -------------------------
    # CREATE DRAFT
    # Creates a Gmail draft and returns the generated draft id.
    # -------------------------
    def create_draft(self, to, subject, message):
        msg = MIMEText(message)
        msg["to"] = to
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        body = {"message": {"raw": raw}}
        draft = self.service.users().drafts().create(userId="me", body=body).execute()
        draft_id = draft.get("id")
        if not draft_id:
            raise GmailServiceError(f"Draft creation response missing id: {draft}")
        print(f"[Info] Draft created with ID: {draft_id}")
        return draft_id

    # -------------------------
    # LIST DRAFTS
    # Lists current drafts and prints a compact index with recipient + subject.
    # -------------------------
    def list_drafts(self):
        try:
            res = self.service.users().drafts().list(userId="me").execute()
            drafts = res.get("drafts", [])
            if not drafts:
                print("[Info] No drafts found.")
                return []
            print("Drafts:")
            for idx, d in enumerate(drafts, 1):
                draft_msg = self.service.users().drafts().get(userId="me", id=d["id"]).execute()
                headers = draft_msg["message"]["payload"]["headers"]
                subject = MessageParser.extract_header(headers, "Subject")
                to = MessageParser.extract_header(headers, "To")
                print(f"{idx}. ID: {d['id']}, To: {to}, Subject: {subject}")
            return drafts
        except Exception as e:
            print(f"[Error] Failed to list drafts: {e}")
            return []

    # -------------------------
    # SEND DRAFT
    # Sends a draft by id and returns API response payload.
    # -------------------------
    def send_draft(self, draft_id):
        try:
            sent_msg = self.service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
            print(f"[Info] Draft sent: Message ID {sent_msg['id']}")
            return sent_msg
        except Exception as e:
            print(f"[Error] Failed to send draft: {e}")

    # -------------------------
    # SCHEDULE EMAIL VIA DRAFT
    # Drafts immediately, then uses a background daemon thread
    # to send the draft at the requested future timestamp.
    # -------------------------
    def schedule_email(self, to, subject, message, send_time: datetime):
        delay = (send_time - datetime.now()).total_seconds()
        if delay <= 0:
            print("[Error] Scheduled time must be in the future.")
            return
        draft_id = self.create_draft(to, subject, message)
        print(f"[Info] Email scheduled to be sent at {send_time} using draft {draft_id}")

        def send_later():
            time.sleep(delay)
            self.send_draft(draft_id)
            print(f"[Info] Scheduled email sent to {to} at {datetime.now()}")

        threading.Thread(target=send_later, daemon=True).start()

# -------------------------
# GMAIL LISTENER
# -------------------------
class GmailListener:
    """Monitors Gmail for new messages and triggers notifications."""
    
    # -------------------------
    # INIT
    # Stores Gmail and popup services and initializes in-memory dedupe set.
    # -------------------------
    def __init__(self, gmail_service, popup_manager):
        """Initialize with Gmail service and popup manager.
        
        Args:
            gmail_service: Instance of GmailService
            popup_manager: Instance of PopupManager
        """
        self.gmail = gmail_service
        self.popup = popup_manager
        self.seen_ids = set()

    # -------------------------
    # START LISTENER LOOP
    # Polls unread emails continuously and raises desktop popups for new ids.
    # -------------------------
    def start(self):
        while True:
            messages = self.gmail.list_messages(query="is:unread", max_results=5)
            for msg in messages:
                if msg["id"] not in self.seen_ids:
                    details = self.gmail.read_message(msg["id"])
                    popup_text = f"From: {details['from']}\nSubject: {details['subject']}\n{details['snippet']}"
                    self.popup.show("New Email", popup_text)
                    self.seen_ids.add(msg["id"])
            time.sleep(POLL_INTERVAL)

# -------------------------
# MENU SYSTEM
# -------------------------
def menu(gmail_service):
    """Display interactive command-line menu for Gmail operations.
    
    Args:
        gmail_service: Authenticated GmailService instance
    """
    message_ids = []

    # Main interactive CLI loop for manual Gmail operations.
    while True:
        print("\n==== AutoReturn Gmail Menu ====")
        print("1. List unread messages")
        print("2. List all messages")
        print("3. Read a message")
        print("4. Reply to a message")
        print("5. Send new email")
        print("6. Delete a message")
        print("7. Mark a message as unread")
        print("8. Search messages")
        print("9. Create Draft")
        print("10. Schedule Email")
        print("11. Exit")
        print("12. View Drafts")
        print("13. Send Draft manually")
        choice = input("Enter your choice: ").strip()

        # LIST/SEARCH FLOW
        # Fetches message ids first, then resolves sender/subject for display.
        if choice in ["1", "2", "8"]:
            query = ""
            if choice == "1":
                query = "is:unread"
            elif choice == "8":
                query = input("Enter search query: ").strip()
            messages = gmail_service.list_messages(query=query, max_results=20)
            if not messages:
                print("No messages found.")
                message_ids = []
            else:
                print("Messages:")
                message_ids = []
                for idx, msg in enumerate(messages, 1):
                    details = gmail_service.read_message(msg["id"])
                    print(f"{idx}. From: {details['from']}, Subject: {details['subject']}")
                    message_ids.append(msg["id"])

        # READ FLOW
        # Reads one selected message from the most recently listed ids.
        elif choice == "3":
            if not message_ids:
                print("No messages to read. Please list messages first.")
                continue
            num = input(f"Enter message number (1-{len(message_ids)}): ").strip()
            if not num.isdigit() or int(num) < 1 or int(num) > len(message_ids):
                print("Invalid number.")
                continue
            msg_id = message_ids[int(num)-1]
            details = gmail_service.read_message(msg_id)
            print(f"From: {details['from']}\nSubject: {details['subject']}\nBody:\n{details['body']}")

        # REPLY FLOW
        # Replies in-thread to a selected message id.
        elif choice == "4":
            if not message_ids:
                print("No messages to reply. Please list messages first.")
                continue
            num = input(f"Enter message number to reply (1-{len(message_ids)}): ").strip()
            if not num.isdigit() or int(num) < 1 or int(num) > len(message_ids):
                print("Invalid number.")
                continue
            msg_id = message_ids[int(num)-1]
            details = gmail_service.read_message(msg_id)
            reply_text = input("Enter reply message: ")
            gmail_service.reply(details["threadId"], details["from"], reply_text)
            print("[Info] Reply sent.")

        # SEND NEW EMAIL FLOW
        elif choice == "5":
            to = input("Recipient email: ")
            subject = input("Subject: ")
            body = input("Message body: ")
            gmail_service.send_email(to, subject, body)
            print("[Info] Email sent.")

        # DELETE FLOW
        elif choice == "6":
            if not message_ids:
                print("No messages to delete. Please list messages first.")
                continue
            num = input(f"Enter message number to delete (1-{len(message_ids)}): ").strip()
            if not num.isdigit() or int(num) < 1 or int(num) > len(message_ids):
                print("Invalid number.")
                continue
            msg_id = message_ids[int(num)-1]
            gmail_service.delete_message(msg_id)
            print("[Info] Message deleted.")

        # MARK UNREAD FLOW
        elif choice == "7":
            if not message_ids:
                print("No messages to mark as unread. Please list messages first.")
                continue
            num = input(f"Enter message number to mark as unread (1-{len(message_ids)}): ").strip()
            if not num.isdigit() or int(num) < 1 or int(num) > len(message_ids):
                print("Invalid number.")
                continue
            msg_id = message_ids[int(num)-1]
            gmail_service.mark_as_unread(msg_id)
            print("[Info] Message marked as unread.")

        # CREATE DRAFT FLOW
        elif choice == "9":
            to = input("Recipient email for draft: ")
            subject = input("Draft subject: ")
            body = input("Draft body: ")
            gmail_service.create_draft(to, subject, body)

        # SCHEDULE FLOW
        elif choice == "10":
            to = input("Recipient email: ")
            subject = input("Subject: ")
            body = input("Message body: ")
            send_time_str = input("Enter send time (YYYY-MM-DD HH:MM:SS): ")
            try:
                send_time = datetime.strptime(send_time_str, "%Y-%m-%d %H:%M:%S")
                gmail_service.schedule_email(to, subject, body, send_time)
            except Exception as e:
                print(f"[Error] Invalid time format: {e}")

        # LIST DRAFTS FLOW
        elif choice == "12":
            gmail_service.list_drafts()

        # SEND DRAFT FLOW
        elif choice == "13":
            draft_id = input("Enter draft ID to send: ").strip()
            gmail_service.send_draft(draft_id)

        elif choice == "11":
            print("Exiting...")
            break

        else:
            print("Invalid choice, try again.")

# -------------------------
# MAIN ENTRY POINT
# -------------------------
def main():
    """Main entry point for the Gmail automation script.
    
    Handles OAuth authentication and starts the interactive menu.
    """
    print("\n=== AutoReturn Gmail Automation ===\n")
    print("Note: For first-time setup, follow beginner instructions.\n")

    oauth = OAuthManager()
    if not oauth.load_or_generate_token():
        print("OAuth token setup failed. Exiting...")
        return

    gmail = GmailService(oauth.creds)

    # listener = GmailListener(gmail, PopupManager())
    # threading.Thread(target=listener.start, daemon=True).start()

    menu(gmail)

if __name__ == "__main__":
    main()
