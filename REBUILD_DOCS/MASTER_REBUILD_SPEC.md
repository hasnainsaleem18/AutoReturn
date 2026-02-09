# AutoCom Master Rebuild Specification

## 📋 Document Purpose

This document provides a complete, consolidated specification for rebuilding the AutoCom project from scratch. It combines all scattered documentation into a single source of truth for clean implementation.

---

## 🎯 Project Overview

**Project Name:** AutoCom (formerly AutoReturn)  
**Tagline:** "Automate Everything. From Voice to Victory."  
**Type:** Desktop Application (Python + PyQt6)  
**AI Model:** Local Ollama (kimi-k2.5:cloud)

### What AutoCom Does

AutoCom is a **unified communication platform** that brings Gmail and Slack together in one intelligent interface with local AI processing.

**Core Features:**
1. **Unified Inbox** - Gmail + Slack messages in one view
2. **AI Intelligence** - Local Ollama for smart features
3. **Orchestrator-Centric** - Central brain coordinates everything
4. **Intelligent Agents** - Gmail/Slack agents with AI capabilities
5. **Privacy-First** - All AI processing stays local

---

## 🏗️ Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                        │
│                    (PyQt6 Desktop UI)                        │
│                                                              │
│  ❌ NO direct service calls                                  │
│  ✅ ONLY talks to Orchestrator                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Commands (natural language or structured)
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (BRAIN)                      │
│                  (orchestrator.py)                           │
│                                                              │
│  ✅ Intent Classification (Pydantic AI)                      │
│  ✅ Command Routing                                          │
│  ✅ Context Management                                       │
│  ✅ High-level AI Decisions                                  │
│  ✅ Coordination of all agents                               │
│  ✅ Event Management                                         │
│                                                              │
│  Uses: Ollama Model (kimi-k2.5:cloud)                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Routes to appropriate agent
                         │
        ┌────────────────┼────────────────┬──────────────┐
        │                │                │              │
        ▼                ▼                ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌─────────┐  ┌──────────┐
│ Gmail Agent  │  │ Slack Agent  │  │  Task   │  │  Draft   │
│ (AI-capable) │  │ (AI-capable) │  │Extractor│  │ Manager  │
│              │  │              │  │         │  │          │
│ ✅ Fetch     │  │ ✅ Fetch     │  │ ✅ AI   │  │ ✅ AI    │
│ ✅ Send      │  │ ✅ Send      │  │ Extract │  │ Generate │
│ ✅ Summarize │  │ ✅ Summarize │  │ Tasks   │  │ Drafts   │
│ ✅ Draft     │  │ ✅ Draft     │  │         │  │          │
│ ✅ Smart     │  │ ✅ Smart     │  │         │  │          │
│              │  │              │  │         │  │          │
│ Can make     │  │ Can make     │  │         │  │          │
│ decisions    │  │ decisions    │  │         │  │          │
└──────┬───────┘  └──────┬───────┘  └────┬────┘  └────┬─────┘
       │                 │                │            │
       │                 │                │            │
       ▼                 ▼                ▼            ▼
┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐
│Gmail Backend │  │Slack Backend │  │   Ollama Model          │
│   Service    │  │   Service    │  │ (kimi-k2.5:cloud)    │
│              │  │              │  │                         │
│ (API calls)  │  │ (API calls)  │  │ (AI Intelligence)       │
└──────┬───────┘  └──────┬───────┘  └─────────────────────────┘
       │                 │
       ▼                 ▼
┌──────────────┐  ┌──────────────┐
│  Gmail API   │  │  Slack API   │
└──────────────┘  └──────────────┘
```

### Key Architectural Principles

1. **Orchestrator = Central Brain**
   - All coordination and high-level AI decisions
   - Maintains global context
   - Routes commands to agents

2. **Agents = Intelligent Workers**
   - Not just API wrappers
   - Have AI capabilities for domain-specific tasks
   - Can make autonomous decisions
   - Report to orchestrator

3. **No Direct UI → Service Calls**
   - Everything goes through orchestrator
   - Clean separation of concerns

4. **Privacy-First**
   - All AI processing uses local Ollama
   - No cloud AI services
   - Data stays on device

---

## 📁 Project Structure

```
autocom/
├── .env                          # Environment configuration (not in git)
├── .env.example                  # Template for .env
├── .gitignore                    # Git ignore rules
├── main.py                       # Application entry point
├── requirements.txt              # Python dependencies
│
├── config/
│   └── settings.conf             # Application settings
│
├── data/
│   └── gmail_data/               # Gmail OAuth tokens
│       ├── client_secret.json    # Gmail API credentials
│       └── token.json            # OAuth token (auto-generated)
│
├── src/
│   ├── __init__.py
│   │
│   ├── backend/
│   │   ├── __init__.py
│   │   │
│   │   ├── config/               # Configuration management
│   │   │   ├── __init__.py
│   │   │   └── settings.py       # Environment variable loader
│   │   │
│   │   ├── core/                 # Core business logic
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py   # Central orchestrator (THE BRAIN)
│   │   │   ├── task_extractor.py # AI task extraction
│   │   │   ├── draft_manager.py  # AI draft generation
│   │   │   └── sentiment_analyzer.py # AI sentiment analysis
│   │   │
│   │   ├── agents/               # Intelligent agents
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py     # Base agent interface
│   │   │   ├── gmail_agent.py    # Gmail intelligent agent
│   │   │   ├── slack_agent.py    # Slack intelligent agent
│   │   │   ├── context_manager.py # Agent context/memory
│   │   │   └── learning_engine.py # Agent learning system
│   │   │
│   │   ├── services/             # Backend API services
│   │   │   ├── __init__.py
│   │   │   ├── gmail_backend.py  # Gmail API wrapper
│   │   │   ├── slack_backend.py  # Slack API wrapper
│   │   │   └── ai_service.py     # Ollama service
│   │   │
│   │   ├── models/               # Data models
│   │   │   ├── __init__.py
│   │   │   ├── agent_models.py   # Agent data models
│   │   │   ├── gmail_models.py   # Gmail-specific models
│   │   │   ├── slack_models.py   # Slack-specific models
│   │   │   └── event_models.py   # Event bus models
│   │   │
│   │   └── utils/                # Utility functions
│   │       └── __init__.py
│   │
│   └── frontend/                 # UI layer
│       ├── __init__.py
│       │
│       ├── ui/                   # Main UI components
│       │   ├── __init__.py
│       │   ├── autoreturn_app.py # Main window
│       │   └── styles.py         # UI styling
│       │
│       ├── dialogs/              # Dialog windows
│       │   ├── __init__.py
│       │   ├── auth_dialog.py
│       │   ├── settings_dialog.py
│       │   ├── notification_dialog.py
│       │   ├── send_gmail_reply_dialog.py
│       │   └── send_slack_message_dialog.py
│       │
│       ├── widgets/              # Custom widgets
│       │   └── __init__.py
│       │
│       └── assets/               # UI assets
│           ├── Gmail_Logo_32px.png
│           ├── icons8-slack-new-48.png
│           └── notification-bell-red.png
│
├── tests/                        # Test suite
│   ├── unit/                     # Unit tests
│   ├── property/                 # Property-based tests
│   └── integration/              # Integration tests
│
├── docs/                         # Documentation
│   └── (various documentation files)
│
└── specs/                        # Feature specifications
    └── intelligent-ai-agents/    # Intelligent agents spec
        ├── requirements.md
        ├── design.md
        └── tasks.md
```

---

## 🔧 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **UI** | PyQt6/PySide6 | Desktop interface |
| **Backend** | Python 3.10+ | Core logic |
| **Async** | asyncio | Non-blocking I/O |
| **AI Framework** | Pydantic AI | Agent framework |
| **LLM** | Ollama | Local AI (kimi-k2.5:cloud) |
| **Database** | SQLite | Local storage (future) |
| **Gmail** | google-auth, Gmail API | Email integration |
| **Slack** | slack-sdk | Chat integration |
| **Testing** | pytest, Hypothesis | Unit & property tests |

---

## 📦 Dependencies (requirements.txt)

```txt
# UI Framework
PySide6>=6.5.0

# AI and ML
pydantic-ai>=0.0.13
pydantic>=2.0.0
ollama>=0.1.0

# Gmail Integration
google-auth>=2.16.0
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.0
google-api-python-client>=2.80.0

# Slack Integration
slack-sdk>=3.19.0

# Utilities
python-dotenv>=1.0.0
keyring>=24.0.0
aiosqlite>=0.19.0  # For future SQLite async

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
hypothesis>=6.82.0
```

---

## ⚙️ Environment Configuration

### .env File Structure

```env
# ==============================================
# OLLAMA CONFIGURATION (REQUIRED)
# ==============================================
OLLAMA_MODEL=kimi-k2.5:cloud
OLLAMA_BASE_URL=http://localhost:11434

# ==============================================
# SLACK CONFIGURATION (OPTIONAL)
# ==============================================
# Leave empty to connect via UI
# Token will be saved to system keyring after first connect
SLACK_USER_TOKEN=

# ==============================================
# GMAIL CONFIGURATION (OPTIONAL)
# ==============================================
# Paths for Gmail OAuth files
GMAIL_CLIENT_SECRET_PATH=./data/gmail_data/client_secret.json
GMAIL_TOKEN_PATH=./data/gmail_data/token.json
GMAIL_DATA_DIR=./data/gmail_data

# ==============================================
# APPLICATION SETTINGS
# ==============================================
DEBUG=False
AUTO_CONNECT_SLACK=True
AUTO_CONNECT_GMAIL=True
SLACK_SYNC_INTERVAL=10
GMAIL_SYNC_INTERVAL=60
AI_SUMMARY_MAX_CONCURRENT=2
AI_SUMMARY_ENABLED=True

# ==============================================
# ORCHESTRATOR SETTINGS
# ==============================================
ORCHESTRATOR_INTENT_CONFIDENCE_THRESHOLD=0.7
AGENT_TIMEOUT=30
UI_REFRESH_INTERVAL=60000
```

### Settings Loader (src/backend/config/settings.py)

```python
"""
Environment configuration loader using python-dotenv.
Loads settings from .env file with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

class Settings:
    """Application settings loaded from environment variables."""
    
    # Ollama Configuration
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    
    # Slack Configuration
    SLACK_USER_TOKEN = os.getenv('SLACK_USER_TOKEN', '')
    
    # Gmail Configuration
    GMAIL_CLIENT_SECRET_PATH = os.getenv('GMAIL_CLIENT_SECRET_PATH', './data/gmail_data/client_secret.json')
    GMAIL_TOKEN_PATH = os.getenv('GMAIL_TOKEN_PATH', './data/gmail_data/token.json')
    GMAIL_DATA_DIR = os.getenv('GMAIL_DATA_DIR', './data/gmail_data')
    
    # Application Settings
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    AUTO_CONNECT_SLACK = os.getenv('AUTO_CONNECT_SLACK', 'True').lower() == 'true'
    AUTO_CONNECT_GMAIL = os.getenv('AUTO_CONNECT_GMAIL', 'True').lower() == 'true'
    SLACK_SYNC_INTERVAL = int(os.getenv('SLACK_SYNC_INTERVAL', '10'))
    GMAIL_SYNC_INTERVAL = int(os.getenv('GMAIL_SYNC_INTERVAL', '60'))
    AI_SUMMARY_MAX_CONCURRENT = int(os.getenv('AI_SUMMARY_MAX_CONCURRENT', '2'))
    AI_SUMMARY_ENABLED = os.getenv('AI_SUMMARY_ENABLED', 'True').lower() == 'true'
    
    # Orchestrator Settings
    ORCHESTRATOR_INTENT_CONFIDENCE_THRESHOLD = float(os.getenv('ORCHESTRATOR_INTENT_CONFIDENCE_THRESHOLD', '0.7'))
    AGENT_TIMEOUT = int(os.getenv('AGENT_TIMEOUT', '30'))
    UI_REFRESH_INTERVAL = int(os.getenv('UI_REFRESH_INTERVAL', '60000'))
    
    @classmethod
    def print_config(cls):
        """Print current configuration (masks sensitive values)."""
        print("=" * 60)
        print("AutoCom Configuration")
        print("=" * 60)
        print(f"Ollama Model: {cls.OLLAMA_MODEL}")
        print(f"Ollama URL: {cls.OLLAMA_BASE_URL}")
        print(f"Slack Token: {'***' + cls.SLACK_USER_TOKEN[-4:] if cls.SLACK_USER_TOKEN else 'Not set'}")
        print(f"Gmail Data Dir: {cls.GMAIL_DATA_DIR}")
        print(f"Auto-connect Slack: {cls.AUTO_CONNECT_SLACK}")
        print(f"Auto-connect Gmail: {cls.AUTO_CONNECT_GMAIL}")
        print(f"Debug Mode: {cls.DEBUG}")
        print(f"AI Summary Enabled: {cls.AI_SUMMARY_ENABLED}")
        print("=" * 60)

# Global settings instance
settings = Settings()
```

---

## 🎯 Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Get basic app running with environment setup

**Tasks:**
1. Set up project structure
2. Create .env configuration
3. Implement settings loader
4. Create main.py entry point
5. Basic PyQt6 UI skeleton
6. Test Ollama connection

**Deliverable:** App starts, connects to Ollama

---

### Phase 2: Backend Services (Week 2)
**Goal:** Implement Gmail and Slack API wrappers

**Tasks:**
1. Implement Gmail backend service
   - OAuth flow
   - Fetch emails
   - Send emails
2. Implement Slack backend service
   - Token authentication
   - Fetch messages
   - Send messages
3. Implement AI service (Ollama wrapper)
4. Test all services independently

**Deliverable:** Services work independently

---

### Phase 3: Orchestrator & Agents (Week 3-4)
**Goal:** Build orchestrator-centric architecture

**Tasks:**
1. Implement base agent interface
2. Implement orchestrator with Pydantic AI
   - Intent classification
   - Command routing
   - Context management
3. Implement Gmail agent (wraps Gmail service)
4. Implement Slack agent (wraps Slack service)
5. Connect orchestrator to agents

**Deliverable:** Orchestrator coordinates agents

---

### Phase 4: UI Integration (Week 5)
**Goal:** Connect UI to orchestrator

**Tasks:**
1. Build unified inbox UI
2. Connect UI to orchestrator (NOT directly to services)
3. Implement message display
4. Implement message actions (reply, etc.)
5. Add AI summary generation

**Deliverable:** Full UI working through orchestrator

---

### Phase 5: Intelligent Features (Week 6-8)
**Goal:** Add AI intelligence to agents

**Tasks:**
1. Implement context manager
2. Implement learning engine
3. Add priority scoring
4. Add task extraction
5. Add sentiment analysis
6. Add smart drafts

**Deliverable:** Intelligent agents with AI capabilities

---

### Phase 6: Polish & Testing (Week 9-10)
**Goal:** Production-ready application

**Tasks:**
1. Write unit tests
2. Write property-based tests
3. Performance optimization
4. Error handling
5. Documentation
6. Packaging

**Deliverable:** Production-ready app

---

## 🚀 Quick Start Guide

### Step 1: Clone/Setup Project

```bash
# Create project directory
mkdir autocom
cd autocom

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env - set your Ollama model
nano .env
```

Minimum .env:
```env
OLLAMA_MODEL=kimi-k2.5:cloud
OLLAMA_BASE_URL=http://localhost:11434
```

### Step 3: Set Up Gmail (Optional)

1. Go to Google Cloud Console
2. Create project and enable Gmail API
3. Download `client_secret.json`
4. Place in `./data/gmail_data/client_secret.json`

### Step 4: Get Slack Token (Optional)

1. Go to https://api.slack.com/apps
2. Create app or use existing
3. Get User OAuth Token (starts with `xoxp-`)
4. Either:
   - Add to .env: `SLACK_USER_TOKEN=xoxp-...`
   - Or connect via UI (token saved to keyring)

### Step 5: Run Application

```bash
# Make sure Ollama is running
ollama serve

# Run AutoCom
python main.py
```

---

## 📚 Key Implementation Details

### Orchestrator Pattern

```python
# UI calls orchestrator
response = await orchestrator.process_intent("Fetch all emails")

# Orchestrator routes to agent
if intent.target == "gmail":
    response = await gmail_agent.fetch(intent.parameters)

# Agent uses backend service
emails = await gmail_backend.fetch_emails()

# Agent adds AI intelligence
for email in emails:
    email['priority'] = await self.analyze_priority(email)
    email['summary'] = await self.generate_summary(email)

# Return to orchestrator, then to UI
return response
```

### Agent Intelligence

```python
class GmailAgent(BaseAgent):
    """Intelligent Gmail agent with AI capabilities."""
    
    def __init__(self):
        self.backend = GmailBackendService()
        self.ai_service = OllamaService()
        self.context_manager = ContextManager()
        self.learning_engine = LearningEngine()
    
    async def fetch(self, parameters):
        # Use backend service for API calls
        emails = await self.backend.fetch_emails()
        
        # Add AI intelligence
        for email in emails:
            # Priority scoring
            email['priority'] = await self.analyze_priority(email)
            
            # AI summary
            email['summary'] = await self.generate_summary(email)
            
            # Task extraction
            email['tasks'] = await self.extract_tasks(email)
        
        return AgentResponse(success=True, data={'emails': emails})
```

### No Direct UI → Service Calls

```python
# ❌ BAD - Direct service call
class UI:
    def sync_messages(self):
        messages = self.slack_service.fetch_all_messages()  # WRONG!

# ✅ GOOD - Through orchestrator
class UI:
    async def sync_messages(self):
        response = await self.orchestrator.process_intent("Fetch all messages")
        if response.success:
            self.display_messages(response.data['messages'])
```

---

## 🎓 Learning Resources

### Understanding the Architecture

1. **Read:** `DOCUMENTATION/01_PROJECT_VISION.md` - Understand the vision
2. **Read:** `DOCUMENTATION/04_SYSTEM_ARCHITECTURE.md` - Understand architecture
3. **Read:** `REFACTORING_PLAN.md` - Understand orchestrator pattern
4. **Read:** `specs/intelligent-ai-agents/requirements.md` - Understand intelligent agents

### Implementation Guides

1. **ENV Setup:** `ENV_SETUP_GUIDE.md`
2. **Orchestrator:** `docs/ORCHESTRATOR_ARCHITECTURE.md`
3. **Implementation Status:** `IMPLEMENTATION_STATUS.md`

---

## ✅ Success Criteria

### Minimum Viable Product (MVP)

- [ ] App starts and connects to Ollama
- [ ] Can connect to Gmail (OAuth)
- [ ] Can connect to Slack (token)
- [ ] Unified inbox shows messages from both
- [ ] Can reply to messages
- [ ] AI summaries generate for messages
- [ ] Orchestrator routes all commands
- [ ] Agents wrap services with AI

### Full Feature Set

- [ ] All MVP features
- [ ] Priority scoring
- [ ] Task extraction
- [ ] Sentiment analysis
- [ ] Smart draft generation
- [ ] Context/memory system
- [ ] Learning from user feedback
- [ ] Agent collaboration
- [ ] Voice control (future)

---

## 🐛 Common Issues & Solutions

### Issue: Ollama not connecting

**Solution:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve

# Test your model
ollama run kimi-k2.5:cloud "Hello"
```

### Issue: Gmail OAuth fails

**Solution:**
1. Check `client_secret.json` exists
2. Check path in .env is correct
3. Delete `token.json` and try again
4. Check Google Cloud Console API is enabled

### Issue: Slack token invalid

**Solution:**
1. Token must start with `xoxp-`
2. Check no spaces in .env
3. Verify token in Slack API dashboard
4. Try regenerating token

### Issue: UI not connecting to orchestrator

**Solution:**
1. Check orchestrator is initialized in UI
2. Check agents are registered with orchestrator
3. Check no direct service calls in UI
4. Review `REFACTORING_PLAN.md`

---

## 📝 Next Steps

1. **Read this document completely**
2. **Set up environment** (Step 1-2 of Quick Start)
3. **Start with Phase 1** (Foundation)
4. **Follow implementation phases** sequentially
5. **Test after each phase**
6. **Refer to existing code** for patterns
7. **Ask questions** when stuck

---

## 🎯 Summary

**What You're Building:**
- Desktop app with unified Gmail + Slack inbox
- Orchestrator-centric architecture
- Intelligent AI agents (not just API wrappers)
- Local AI processing (privacy-first)
- Clean, maintainable codebase

**Key Principles:**
1. Orchestrator = Brain
2. Agents = Intelligent Workers
3. UI → Orchestrator → Agents → Services
4. All AI stays local (Ollama)
5. Privacy-first design

**Start Here:**
1. Set up .env with Ollama config
2. Run `python main.py`
3. Connect services via UI
4. Build from Phase 1 → Phase 6

Good luck! 🚀
