# 🚀 AutoReturn - Unified Communication Management

<div align="center">

![AutoReturn Logo](https://img.shields.io/badge/AutoReturn-Unified%20Inbox-0FA4AF?style=for-the-badge&logo=mail&logoColor=white)

**A modern desktop application for managing Gmail and Slack communications in one unified inbox with AI-powered message analysis.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-Qt%20Framework-41CD52?style=flat-square&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![Slack](https://img.shields.io/badge/Slack-Integration-4A154B?style=flat-square&logo=slack&logoColor=white)](https://slack.com)
[![Gmail](https://img.shields.io/badge/Gmail-Integration-EA4335?style=flat-square&logo=gmail&logoColor=white)](https://gmail.com)
[![Ollama](https://img.shields.io/badge/Ollama-AI%20Powered-000000?style=flat-square&logo=ollama&logoColor=white)](https://ollama.ai)

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Project Structure](#-project-structure)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Integrations](#-api-integrations)
- [AI Features](#-ai-features)
- [Development](#-development)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 📬 Unified Inbox
- **Multi-platform messaging**: View Gmail emails and Slack messages in one place
- **Real-time synchronization**: Auto-sync messages from all connected platforms
- **Smart filtering**: Filter by platform, priority, sender, or custom search queries
- **Unified search**: Search across all your communications with advanced filters

### 🤖 AI-Powered Intelligence
- **Automatic summarization**: AI generates concise summaries for all messages
- **Priority detection**: Smart algorithms identify urgent and important messages
- **Task classification**: Automatically categorizes messages (Smart Draft, Auto Reply, Simple Reply, File Attachment)
- **Context-aware insights**: Get AI-powered suggestions for handling each message

### 🔔 Smart Notifications
- **Priority-based alerts**: Get notified only for important messages
- **Quiet hours**: Configure do-not-disturb periods
- **Custom notification rules**: Set up personalized notification preferences
- **Desktop notifications**: Native OS notifications for new messages

### ✉️ Powerful Actions
- **Quick reply**: Respond directly from the inbox
- **Auto-reply**: AI-generated automatic responses
- **Smart draft**: AI-assisted message composition
- **File attachments**: Easy file sharing across platforms
- **Scheduled sending**: Schedule messages for later (coming soon)

---

## 📁 Project Structure

```
AutoReturn/
│
├── main.py                          # Application entry point
├── README.md                        # This file
├── requirement.txt                  # Python dependencies
├── LICENSE                          # License file
│
├── src/                            # Source code
│   ├── __init__.py
│   ├── backend/                    # Backend logic
│   │   ├── __init__.py
│   │   ├── core/                   # Core automation modules
│   │   │   ├── __init__.py
│   │   │   └── AutoReturn_Gmail_Automation.py
│   │   ├── services/               # Service integrations
│   │   │   ├── __init__.py
│   │   │   ├── ai_service.py       # Ollama AI integration
│   │   │   ├── gmail_backend.py    # Gmail API wrapper
│   │   │   └── slack_backend.py    # Slack API wrapper
│   │   └── utils/                  # Utility functions
│   │       └── __init__.py
│   │
│   └── frontend/                   # Frontend UI
│       ├── __init__.py
│       ├── ui/                     # Main UI components
│       │   ├── __init__.py
│       │   ├── autoreturn_app.py   # Main application window
│       │   └── styles.py           # Application styles
│       ├── dialogs/                # Dialog windows
│       │   ├── __init__.py
│       │   ├── auth_dialog.py      # Login/Signup dialog
│       │   ├── notification_dialog.py
│       │   ├── send_gmail_reply_dialog.py
│       │   ├── send_slack_message_dialog.py
│       │   └── settings_dialog.py
│       ├── widgets/                # Custom widgets
│       │   └── __init__.py
│       └── assets/                 # Images and icons
│           ├── Gmail_Logo_32px.png
│           ├── icons8-slack-new-48.png
│           └── notification-bell-red.png
│
├── config/                         # Configuration files
│   └── settings.conf
│
├── data/                          # Application data
│   └── gmail_data/                # Gmail credentials
│       ├── client_secret.json
│       └── token.json
│
├── logs/                          # Application logs
│
├── scripts/                       # Utility scripts
│   ├── debug_slack_ai.py         # Debug Slack+AI integration
│   └── quick_test.py             # Quick test script
│
└── tests/                         # Unit tests
    └── test_ollama.py            # Ollama integration tests
```

---
- **Smart filtering**: Filter messages by source, priority, or search terms
- **Sortable columns**: Sort by sender, subject, time, or priority

### 🤖 AI-Powered Analysis
- **Automatic summarization**: AI generates concise summaries for each message
- **Task classification**: Automatically categorizes messages into:
  - 🎯 **Smart Draft**: Needs a thoughtful, composed reply
  - ⚡ **Auto Reply**: Needs a simple acknowledgement
  - 📝 **Simple Reply**: Informational only, no action needed
  - 📎 **File Attachment**: Sender is requesting a file
- **Priority detection**: Automatically flags urgent/high-priority messages

### 🔗 Platform Integrations
- **Gmail**: Full OAuth2 authentication, read/send emails, draft management
- **Slack**: User token authentication, DM and channel message support
- **Secure storage**: Credentials stored securely using system keyring

### 🎨 Modern UI
- **Beautiful design**: Clean, modern interface with gradient headers
- **Dark/Light theme**: Professional color scheme (#024950, #0FA4AF, #AFDDE5)
- **Responsive layout**: Adapts to different window sizes
- **Desktop notifications**: Get notified of new messages

### ⚙️ Settings & Customization
- **Quiet hours**: Configure times when notifications are muted
- **Priority rules**: Set custom priority rules for senders
- **Profile management**: Manage your user profile and connected accounts

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AUTORETURN APP                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    FRONTEND (PySide6)                    │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │ Auth Dialog │  │  Main App   │  │    Dialogs      │  │   │
│  │  │  - Login    │  │  - Inbox    │  │  - Settings     │  │   │
│  │  │  - Signup   │  │  - Messages │  │  - Notifications│  │   │
│  │  │             │  │  - Search   │  │  - Reply/Send   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   BACKEND SERVICES                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │Gmail Backend│  │Slack Backend│  │   AI Service    │  │   │
│  │  │  - OAuth2   │  │  - WebClient│  │  - Ollama API   │  │   │
│  │  │  - Sync     │  │  - Listener │  │  - Summarize    │  │   │
│  │  │  - Send     │  │  - Send DM  │  │  - Classify     │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   EXTERNAL APIs                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │  Gmail API  │  │  Slack API  │  │   Ollama LLM    │  │   │
│  │  │  (Google)   │  │  (WebClient)│  │   (localhost)   │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

Before installing AutoReturn, ensure you have the following:

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.10+ | Runtime environment |
| **pip** | Latest | Package management |
| **Ollama** | Latest | AI message analysis |
| **Git** | Latest | Version control (optional) |

### Platform-Specific Requirements

| Platform | Additional Requirements |
|----------|------------------------|
| **macOS** | Xcode Command Line Tools |
| **Windows** | Visual C++ Redistributable |
| **Linux** | libxcb, libGL |

---

## 🛠 Installation

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd project_v3
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirement.txt
```

### Step 4: Install Ollama (for AI features)

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# Download from https://ollama.ai/download
```

### Step 5: Pull AI Model

```bash
# Pull the recommended model
ollama pull qwen3:0.6b

# Or pull a larger model for better results
ollama pull llama3.2:3b
```

### Step 6: Start Ollama Server

```bash
ollama serve
```

---

## ⚙️ Configuration

### Gmail Setup

1. **Create Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable the Gmail API

2. **Configure OAuth Consent Screen**
   - Navigate to APIs & Services → OAuth consent screen
   - Select "External" user type
   - Fill in required fields (App name, support email, etc.)
   - Add scopes: `gmail.readonly`, `gmail.modify`, `gmail.send`, `gmail.compose`

3. **Create OAuth Credentials**
   - Navigate to APIs & Services → Credentials
   - Click "Create Credentials" → "OAuth client ID"
   - Select "Desktop application"
   - Download the `client_secret.json` file

4. **Upload to AutoReturn**
   - Open AutoReturn → Settings → Integrations → Gmail
   - Click "Upload client_secret.json"
   - Click "Connect Gmail" to authorize

### Slack Setup

1. **Create Slack App**
   - Go to [Slack API](https://api.slack.com/apps)
   - Click "Create New App" → "From scratch"
   - Name your app and select workspace

2. **Configure OAuth & Permissions**
   - Navigate to OAuth & Permissions
   - Add User Token Scopes:
     - `channels:history`
     - `channels:read`
     - `chat:write`
     - `groups:history`
     - `groups:read`
     - `im:history`
     - `im:read`
     - `im:write`
     - `mpim:history`
     - `mpim:read`
     - `users:read`

3. **Install App to Workspace**
   - Click "Install to Workspace"
   - Copy the "User OAuth Token" (starts with `xoxp-`)

4. **Connect in AutoReturn**
   - Open AutoReturn → Settings → Integrations → Slack
   - Paste your User OAuth Token
   - Click "Connect"

---

## 🚀 Usage

### Starting the Application

```bash
# Make sure virtual environment is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Run the application
python -m frontend.main
```

### First-Time Setup

1. **Login/Signup**: Create an account or login
2. **Connect Services**: Go to Settings → Integrations
3. **Configure Gmail**: Upload credentials and authorize
4. **Configure Slack**: Enter your User OAuth Token
5. **Start Using**: Messages will sync automatically

### Main Interface

```
┌────────────────────────────────────────────────────────────────┐
│  🔵 AutoReturn          🔍 Search...        🔔  ⚙️  👤          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  📥 Inbox (15 messages)                         [Sync All]     │
│  ─────────────────────────────────────────────────────────     │
│  [All] [📧 Gmail] [💬 Slack] [🔴 Urgent] [⭐ Important]        │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ ☐ │ Source │ From        │ Subject      │ Time │ Pri  │   │
│  ├────────────────────────────────────────────────────────┤   │
│  │ ☐ │ 📧     │ John Smith  │ Meeting...   │ 2h   │ 🔴   │   │
│  │ ☐ │ 💬     │ Jane Doe    │ DM: Hey...   │ 3h   │ ⚪   │   │
│  │ ☐ │ 📧     │ Bob Wilson  │ Report...    │ 1d   │ ⭐   │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  📝 AI Summary: The sender is asking about the project...     │
│  🎯 Task: Smart Draft - Needs a thoughtful reply              │
│                                                                │
│  [↩️ Reply] [⚡ Auto Reply] [📝 Smart Draft] [📎 Attach]       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Refresh/Sync all messages |
| `Ctrl+F` | Focus search bar |
| `Ctrl+,` | Open Settings |
| `Escape` | Clear search/selection |

---

## 📁 Project Structure

```
project_v3/
│
├── 📄 requirement.txt          # Python dependencies
├── 📄 README.md                # This file
│
├── 📂 backend/                 # Backend services
│   ├── 📂 core/
│   │   └── 📄 AutoReturn_Gmail_Automation.py  # Gmail API core
│   ├── 📂 services/
│   │   ├── 📄 ai_service.py          # Ollama AI integration
│   │   ├── 📄 gmail_backend.py       # Gmail service wrapper
│   │   └── 📄 slack_backend.py       # Slack service wrapper
│   └── 📂 utils/               # Utility functions
│
├── 📂 frontend/                # GUI application
│   ├── 📄 main.py              # Application entry point
│   ├── 📄 autoreturn_app.py    # Main window (1800+ lines)
│   ├── 📄 auth_dialog.py       # Login/Signup dialog
│   ├── 📄 styles.py            # Qt stylesheets
│   │
│   ├── 📂 dialogs/             # Dialog windows
│   │   ├── 📄 notification_dialog.py
│   │   ├── 📄 send_gmail_reply_dialog.py
│   │   ├── 📄 send_slack_message_dialog.py
│   │   └── 📄 settings_dialog.py
│   │
│   ├── 📂 assets/              # Icons and images
│   │   ├── 🖼️ Gmail_Logo_32px.png
│   │   ├── 🖼️ icons8-slack-new-48.png
│   │   └── 🖼️ notification-bell-red.png
│   │
│   ├── 📂 gmail_data/          # Gmail credentials (local)
│   │   ├── 📄 client_secret.json
│   │   └── 📄 token.json
│   │
│   └── 📂 widgets/             # Custom Qt widgets
│
├── 📂 gmail_data/              # Alternative Gmail data location
│   ├── 📄 client_secret.json
│   └── 📄 token.json
│
├── 📂 scripts/                 # Development/debug scripts
│   ├── 📄 debug_slack_ai.py
│   └── 📄 quick_test.py
│
├── 📂 tests/                   # Test files
│   └── 📄 test_ollama.py
│
└── 📂 venv/                    # Virtual environment
```

---

## 🔌 API Integrations

### Gmail API

| Feature | Endpoint | Scope Required |
|---------|----------|----------------|
| List Messages | `gmail.users.messages.list` | `gmail.readonly` |
| Read Message | `gmail.users.messages.get` | `gmail.readonly` |
| Send Email | `gmail.users.messages.send` | `gmail.send` |
| Create Draft | `gmail.users.drafts.create` | `gmail.compose` |
| Modify Labels | `gmail.users.messages.modify` | `gmail.modify` |

### Slack API

| Feature | Method | Scope Required |
|---------|--------|----------------|
| List Channels | `conversations.list` | `channels:read` |
| Get Messages | `conversations.history` | `channels:history` |
| Send Message | `chat.postMessage` | `chat:write` |
| Get Users | `users.list` | `users:read` |
| Send DM | `chat.postMessage` | `im:write` |

### Ollama API

| Feature | Endpoint | Model |
|---------|----------|-------|
| Generate Summary | `POST /api/generate` | qwen3:0.6b |
| Check Status | `GET /api/tags` | - |

---

## 🤖 AI Features

### Message Summarization

The AI analyzes each message and generates:

1. **Summary**: A 1-2 sentence summary of the message content
2. **Task Classification**: Categorizes the required action

### Supported Models

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `qwen3:0.6b` | 600MB | ⚡⚡⚡ | ⭐⭐ |
| `llama3.2:3b` | 2GB | ⚡⚡ | ⭐⭐⭐ |
| `llama3.2:8b` | 4.5GB | ⚡ | ⭐⭐⭐⭐ |

### Changing AI Model

Edit `frontend/autoreturn_app.py`:

```python
# Line ~92
self.ollama_service = OllamaService(model_name="llama3.2:3b")
```

---

## 🔧 Troubleshooting

### Common Issues

#### ❌ "Cannot connect to Ollama"

```bash
# Solution: Start Ollama server
ollama serve

# Verify it's running
curl http://localhost:11434/api/tags
```

#### ❌ "Gmail authentication failed"

1. Check `client_secret.json` is valid
2. Delete `token.json` and re-authorize
3. Ensure Gmail API is enabled in Google Cloud Console

#### ❌ "Invalid Slack token"

1. Ensure token starts with `xoxp-`
2. Verify all required scopes are added
3. Reinstall the Slack app to workspace

#### ❌ "PySide6 import error"

```bash
# Reinstall PySide6
pip uninstall PySide6 PySide6-Essentials PySide6-Addons
pip install PySide6
```

#### ❌ "Keyring backend not found"

```bash
# macOS - uses system keychain automatically

# Linux - install a backend
pip install keyrings.alt
# or
pip install secretstorage

# Windows - uses Windows Credential Locker automatically
```

### Debug Mode

Run with verbose logging:

```bash
python -m frontend.main 2>&1 | tee debug.log
```

---

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** your changes: `git commit -m 'Add amazing feature'`
4. **Push** to the branch: `git push origin feature/amazing-feature`
5. **Open** a Pull Request

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters
- Add docstrings for all public methods
- Keep functions under 50 lines when possible

---

## 📝 License

This project is developed as part of a Final Year Project (FYP).

---

## 📞 Support

For issues and feature requests, please open an issue on the repository.

---

<div align="center">

**Made with ❤️ for better communication management**

</div>
