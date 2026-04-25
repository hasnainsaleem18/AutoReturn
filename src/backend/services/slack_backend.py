# -------------------------
# SLACK BACKEND SERVICE
# -------------------------
"""
Module for Slack integration functionality including:
- User authentication and connection management
- Message sending and receiving
- User and channel management
- Real-time message monitoring
"""

# -------------------------
# IMPORTS
# -------------------------
# Standard library imports
import time
from datetime import datetime
from typing import List, Dict, Optional

# Third-party imports
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from PySide6.QtCore import QThread, Signal, QObject

# -------------------------
# UTILITY FUNCTIONS
# -------------------------
def validate_user_token(token: str) -> tuple:
    """Validate Slack user OAuth token format.
    
    Args:
        token: Slack OAuth token to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not token:
        return False, "Token is required"
    if not token.startswith('xoxp-'):
        return False, "User OAuth Token must start with 'xoxp-'"
    parts = token.split('-')
    if len(parts) < 4:
        return False, "Invalid token format"
    return True, ""


# -------------------------
# FORMAT MESSAGE TIME
# Formats output for message time.
# -------------------------
def format_message_time(msg_datetime) -> str:
    """Format message timestamp as a relative time string.
    Args:
        msg_datetime: Timestamp as either float, string, or datetime object

    Returns:
        str: Formatted relative time (e.g., '2h ago', '3d ago')
    """
    if isinstance(msg_datetime, str):
        try:
            msg_datetime = datetime.fromtimestamp(float(msg_datetime))
        except:
            return "Unknown"
    
    if not isinstance(msg_datetime, datetime):
        return "Unknown"
    
    now = datetime.now()
    diff = now - msg_datetime
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    elif seconds < 604800:
        days = int(seconds // 86400)
        return f"{days}d ago"
    else:
        return msg_datetime.strftime("%b %d")


# -------------------------
# SLACK MESSAGE
# -------------------------
class SlackMessage:
    """Represents a Slack message with formatted data for UI display."""
    
    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self, message_data: dict, channel_info: dict, user_cache: dict):
        self.raw_data = message_data
        self.user_id = message_data.get('user', '')
        self.text = message_data.get('text', '')
        self.timestamp = message_data.get('ts', '')
        self.has_attachments = bool(message_data.get('files')) or bool(message_data.get('attachments'))
        
        # Channel info
        self.channel_id = channel_info.get('id', '')
        self.is_dm = channel_info.get('is_im', False)
        self.is_channel = channel_info.get('is_channel', False)
        self.is_group = channel_info.get('is_group', False)
        self.channel_name = channel_info.get('name', '')
        self.dm_user_id = channel_info.get('user', '') if self.is_dm else ''
        
        # Get user info
        user_info = user_cache.get(self.user_id, {})
        
        fallback_name = message_data.get('username') or message_data.get('bot_profile', {}).get('name') or 'Unknown'
        self.user_name = user_info.get('name', fallback_name)
        self.user_real_name = user_info.get('real_name', self.user_name)
        self.user_email = user_info.get('email', '')
        
        # Get DM partner or channel name
        if self.is_dm:
            dm_partner_info = user_cache.get(self.dm_user_id, {})
            self.dm_partner_name = dm_partner_info.get('real_name', 'Unknown')
        elif self.is_channel or self.is_group:
            self.dm_partner_name = f"#{self.channel_name}"
        else:
            self.dm_partner_name = "Unknown"
        
        self.datetime = self._parse_timestamp(self.timestamp)
    
    # -------------------------
    # PARSE TIMESTAMP
    # Extracts and parses timestamp.
    # -------------------------
    def _parse_timestamp(self, ts: str) -> datetime:
        try:
            return datetime.fromtimestamp(float(ts))
        except:
            return datetime.now()
    
    # -------------------------
    # TO DICT
    # Handles to functionality for dict.
    # -------------------------
    def to_dict(self) -> dict:
        if self.is_dm:
            subject = f"DM from {self.dm_partner_name}"
        elif self.is_channel:
            subject = f"#{self.channel_name}"
        elif self.is_group:
            subject = f"Group: {self.channel_name}"
        else:
            subject = "Slack Message"
        
        return {
            'id': self.timestamp,
            'source': 'slack',
            'sender': self.user_real_name,
            'email': f'@{self.user_name}',
            'subject': subject,
            'content_preview': self.text[:500],
            'preview': self.text[:200] + '...' if len(self.text) > 200 else self.text,
            'summary': '',  # Leave empty for AI to generate
            'priority': self._detect_priority(),
            'time': format_message_time(self.datetime),
            'full_content': self.text,
            'channel_id': self.channel_id,
            'user_id': self.user_id,
            'dm_user_id': self.dm_user_id,
            'timestamp': self.datetime.timestamp(),
            'datetime': self.datetime,
            'is_dm': self.is_dm,
            'is_channel': self.is_channel,
            'is_group': self.is_group,
            'channel_name': self.channel_name,
            'has_attachments': self.has_attachments,
            'read': False,
            'ai_insights': None
        }
    
    # -------------------------
    # GENERATE SUMMARY
    # Creates and returns summary.
    # -------------------------
    def _generate_summary(self) -> str:
        words = self.text.split()
        if len(words) <= 15:
            return self.text
        return ' '.join(words[:15]) + '...'
    
    # -------------------------
    # DETECT PRIORITY
    # Handles detect functionality for priority.
    # -------------------------
    def _detect_priority(self) -> str:
        text_lower = self.text.lower()
        urgent_keywords = ['urgent', 'asap', 'emergency', 'critical', 'immediately']
        if any(keyword in text_lower for keyword in urgent_keywords):
            return 'urgent'
        high_keywords = ['important', 'priority', 'deadline', 'soon', 'quick']
        if any(keyword in text_lower for keyword in high_keywords):
            return 'high'
        return 'normal'
    
# -------------------------
# SLACK SERVICE
# -------------------------
class SlackService(QObject):
    """Main service for interacting with Slack API with Qt signal support."""
    
    connection_status = Signal(bool, str)
    new_messages = Signal(list)
    message_sent = Signal(bool, str)
    users_loaded = Signal(list)
    error_occurred = Signal(str)
    
    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self):
        super().__init__()
        self.client = None
        self.user_token = None
        self.is_connected = False
        self.my_user_id = None
        self.my_user_name = None
        self.workspace_name = None
        self.users_cache = {}
        self.dm_channels_cache = {}
        self.processed_messages = set()
    
    # -------------------------
    # CONNECT
    # Establishes connections for the operation.
    # -------------------------
    def connect(self, user_token: str) -> bool:
        try:
            self.user_token = user_token
            self.client = WebClient(token=user_token)
            
            auth_response = self.client.auth_test()
            self.my_user_id = auth_response['user_id']
            self.my_user_name = auth_response['user']
            self.workspace_name = auth_response.get('team', 'Workspace')
            
            self.is_connected = True
            self._load_users()
            
            self.connection_status.emit(
                True,
                f"Connected to {self.workspace_name} as {self.my_user_name}"
            )
            return True
            
        except SlackApiError as e:
            error_msg = f"Connection failed: {e.response.get('error', str(e))}"
            self.error_occurred.emit(error_msg)
            self.connection_status.emit(False, error_msg)
            return False
    
    # -------------------------
    # DISCONNECT
    # Terminates connections for the operation.
    # -------------------------
    def disconnect(self):
        self.client = None
        self.is_connected = False
        self.users_cache.clear()
        self.dm_channels_cache.clear()
        self.processed_messages.clear()
        self.connection_status.emit(False, "Disconnected from Slack")
    
    # -------------------------
    # LOAD USERS
    # Loads data into users.
    # -------------------------
    def _load_users(self):
        if not self.is_connected:
            return
        
        try:
            response = self.client.users_list()
            users_list = []
            
            for user in response['members']:
                if user.get('deleted'):
                    continue

                
                user_info = {
                    'id': user['id'],
                    'name': user['name'],
                    'real_name': user.get('real_name', user['name']),
                    'email': user['profile'].get('email', ''),
                }
                
                self.users_cache[user['id']] = user_info
                
                if user['id'] != self.my_user_id:
                    users_list.append(user_info)
            
            self.users_loaded.emit(users_list)
            
        except SlackApiError as e:
            self.error_occurred.emit(f"Failed to load users: {e.response.get('error', str(e))}")

    # -------------------------
    # FETCH ALL MESSAGES
    # Pulls data for all messages.
    # -------------------------
    def fetch_all_messages(self, limit: int = 200) -> List[dict]:
        if not self.is_connected:
            return []
        
        all_messages = []
        
        try:
            conversations_response = self.client.conversations_list(
                types="public_channel,private_channel,mpim,im"
            )
            conversations = conversations_response['channels']
            
            for conv in conversations:
                channel_id = conv['id']
                
                try:
                    history = self.client.conversations_history(
                        channel=channel_id,
                        limit=limit
                    )
                except SlackApiError:
                    continue  # Skip channels we can't access
                
                messages = history.get('messages', [])
                
                for msg_data in reversed(messages):

                    
                    msg_ts = msg_data.get('ts', '')
                    if msg_ts in self.processed_messages:
                        continue

                    # Fetch thread replies if this message has a thread
                    reply_count = msg_data.get('reply_count', 0)
                    if reply_count > 0:
                        try:
                            replies_resp = self.client.conversations_replies(
                                channel=channel_id,
                                ts=msg_ts,
                                limit=20
                            )
                            # Append reply texts to the message text
                            reply_texts = [
                                r.get('text', '') for r in replies_resp.get('messages', [])[1:]
                                if r.get('text')
                            ]

                            if reply_texts:
                                msg_data = dict(msg_data)  # don't mutate original
                                msg_data['text'] = (msg_data.get('text', '') +
                                                    '\n--- Thread replies ---\n' +
                                                    '\n'.join(reply_texts))
                        except SlackApiError:
                            pass  # Thread fetch failed, use original message
                    
                    message = SlackMessage(msg_data, conv, self.users_cache)
                    all_messages.append(message.to_dict())
                    self.processed_messages.add(msg_ts)
            
            return all_messages
            
        except SlackApiError as e:
            self.error_occurred.emit(f"Failed to fetch messages: {e.response.get('error', str(e))}")
            return []
    
    # -------------------------
    # SYNC ALL MESSAGES
    # Handles sync functionality for all messages.
    # -------------------------
    def sync_all_messages(self, limit: int = 200) -> List[dict]:
        if not self.is_connected:
            return []
        
        self.processed_messages.clear()
        return self.fetch_all_messages(limit)
    
    # -------------------------
    # SEND DM BY ID
    # Handles send functionality for dm by id.
    # -------------------------
    def send_dm_by_id(self, user_id: str, message_text: str, attachments: Optional[List[str]] = None) -> bool:
        if not self.is_connected:
            self.error_occurred.emit("Not connected to Slack")
            return False
        
        try:
            if user_id in self.dm_channels_cache:
                channel_id = self.dm_channels_cache[user_id]
            else:
                dm_response = self.client.conversations_open(users=[user_id])
                channel_id = dm_response['channel']['id']
                self.dm_channels_cache[user_id] = channel_id

            # If attachments exist, upload files and include message as initial_comment
            if attachments:
                for idx, file_path in enumerate(attachments):
                    try:
                        # Try files_upload_v2 if available, fallback to files_upload
                        if hasattr(self.client, "files_upload_v2"):
                            self.client.files_upload_v2(
                                channel=channel_id,
                                file=file_path,
                                initial_comment=message_text if idx == 0 else None
                            )
                        else:
                            self.client.files_upload(
                                channels=channel_id,
                                file=file_path,
                                initial_comment=message_text if idx == 0 else None
                            )
                    except SlackApiError as e:
                        error_msg = f"File upload failed: {e.response.get('error', str(e))}"
                        self.error_occurred.emit(error_msg)
                        self.message_sent.emit(False, error_msg)
                        return False
            else:
                self.client.chat_postMessage(channel=channel_id, text=message_text)
            
            user_info = self.users_cache.get(user_id, {})
            user_name = user_info.get('real_name', user_id)
            
            self.message_sent.emit(True, f"Message sent to {user_name}")
            return True
            
        except SlackApiError as e:
            error_msg = f"Failed to send message: {e.response.get('error', str(e))}"
            self.error_occurred.emit(error_msg)
            self.message_sent.emit(False, error_msg)
            return False
    
    # -------------------------
    # GET ALL USERS
    # Retrieves all users.
    # -------------------------
    def get_all_users(self) -> List[dict]:
        return [
            user for user_id, user in self.users_cache.items()
            if user_id != self.my_user_id
        ]

# -------------------------
# SLACK MESSAGE LISTENER
# -------------------------
class SlackMessageListener(QThread):
    """Background thread for monitoring new Slack messages."""
    new_messages = Signal(list)
    error_occurred = Signal(str)
    
    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self, slack_service: SlackService, poll_interval: int = 10):
        super().__init__()
        self.slack_service = slack_service
        self.poll_interval = poll_interval
        self.is_running = False
    
    # -------------------------
    # RUN
    # Handles run functionality for the operation.
    # -------------------------
    def run(self):
        self.is_running = True
        print(f"Started Slack listener (polling every {self.poll_interval}s)")
        
        while self.is_running:
            try:
                if not self.slack_service.is_connected:
                    time.sleep(self.poll_interval)
                    continue
                
                messages = self.slack_service.fetch_all_messages(limit=10)
                
                if messages:
                    print(f"Received {len(messages)} new messages")
                    self.new_messages.emit(messages)
                
                time.sleep(self.poll_interval)
                
            except Exception as e:
                error_msg = f"Listener error: {str(e)}"
                print(f"{error_msg}")
                self.error_occurred.emit(error_msg)
                time.sleep(self.poll_interval)
    
    # -------------------------
    # STOP
    # Terminates the process for the operation.
    # -------------------------
    def stop(self):
        """Stop monitoring"""
        self.is_running = False
        print("Stopped Slack listener")
        self.wait()
