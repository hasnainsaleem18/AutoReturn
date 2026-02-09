# AutoCom Implementation Checklist

## 📋 Complete Step-by-Step Guide

Use this checklist to rebuild AutoCom from scratch. Check off each item as you complete it.

---

## Phase 1: Foundation Setup (Day 1-2)

### Environment Setup
- [ ] Create project directory `autocom/`
- [ ] Create virtual environment: `python -m venv .venv`
- [ ] Activate virtual environment
- [ ] Create `requirements.txt` (copy from MASTER_REBUILD_SPEC.md)
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Create `.gitignore` file
- [ ] Initialize git: `git init`

### Configuration Files
- [ ] Create `.env.example` (copy from MASTER_REBUILD_SPEC.md)
- [ ] Create `.env` from `.env.example`
- [ ] Edit `.env` - set `OLLAMA_MODEL=kimi-k2.5:cloud`
- [ ] Edit `.env` - set `OLLAMA_BASE_URL=http://localhost:11434`
- [ ] Test Ollama: `curl http://localhost:11434/api/tags`

### Project Structure
- [ ] Create `src/` directory
- [ ] Create `src/__init__.py`
- [ ] Create `src/backend/` directory
- [ ] Create `src/backend/__init__.py`
- [ ] Create `src/backend/config/` directory
- [ ] Create `src/backend/config/__init__.py`
- [ ] Create `src/backend/config/settings.py` (copy from MASTER_REBUILD_SPEC.md)
- [ ] Create `src/frontend/` directory
- [ ] Create `src/frontend/__init__.py`
- [ ] Create `data/` directory
- [ ] Create `data/gmail_data/` directory
- [ ] Create `tests/` directory

### Test Configuration
- [ ] Test settings loader: `python -c "from src.backend.config import settings; settings.print_config()"`
- [ ] Verify Ollama model is correct
- [ ] Verify paths are correct

**Checkpoint:** Settings load correctly, Ollama accessible

---

## Phase 2: Backend Services (Day 3-5)

### AI Service (Ollama Wrapper)
- [ ] Create `src/backend/services/` directory
- [ ] Create `src/backend/services/__init__.py`
- [ ] Create `src/backend/services/ai_service.py`
- [ ] Implement `OllamaService` class
  - [ ] `__init__(model_name, base_url)`
  - [ ] `check_connection()` method
  - [ ] `generate(prompt)` method
  - [ ] `summarize(text)` method
- [ ] Test AI service independently
- [ ] Write unit test for AI service

### Gmail Backend Service
- [ ] Create `src/backend/services/gmail_backend.py`
- [ ] Implement `GmailBackendService` class
  - [ ] `__init__(data_dir)` method
  - [ ] `connect()` method (OAuth flow)
  - [ ] `has_token()` method
  - [ ] `fetch_emails(max_results)` method
  - [ ] `send_email(to, subject, body)` method
  - [ ] `reply_to_message(message, reply_text)` method
- [ ] Download `client_secret.json` from Google Cloud Console
- [ ] Place in `data/gmail_data/client_secret.json`
- [ ] Test Gmail service independently
- [ ] Write unit test for Gmail service

### Slack Backend Service
- [ ] Create `src/backend/services/slack_backend.py`
- [ ] Implement `SlackService` class
  - [ ] `__init__()` method
  - [ ] `connect(user_token)` method
  - [ ] `disconnect()` method
  - [ ] `fetch_all_messages(limit)` method
  - [ ] `send_dm_by_id(user_id, text)` method
  - [ ] `get_users()` method
- [ ] Implement `SlackMessageListener` class (real-time)
- [ ] Get Slack token from https://api.slack.com/apps
- [ ] Test Slack service independently
- [ ] Write unit test for Slack service

**Checkpoint:** All services work independently

---

## Phase 3: Orchestrator & Agents (Day 6-10)

### Data Models
- [ ] Create `src/backend/models/` directory
- [ ] Create `src/backend/models/__init__.py`
- [ ] Create `src/backend/models/agent_models.py`
- [ ] Implement `AgentResponse` model
- [ ] Implement `Intent` model
- [ ] Implement `TargetService` enum

### Base Agent
- [ ] Create `src/backend/agents/` directory
- [ ] Create `src/backend/agents/__init__.py`
- [ ] Create `src/backend/agents/base_agent.py`
- [ ] Implement `BaseAgent` class
  - [ ] `__init__(service_name)` method
  - [ ] `connect()` abstract method
  - [ ] `disconnect()` abstract method
  - [ ] `fetch(parameters)` abstract method
  - [ ] `send(parameters)` abstract method
- [ ] Write unit test for BaseAgent

### Gmail Agent
- [ ] Create `src/backend/agents/gmail_agent.py`
- [ ] Implement `GmailAgent(BaseAgent)` class
  - [ ] `__init__()` - initialize backend service and AI service
  - [ ] `connect()` method
  - [ ] `disconnect()` method
  - [ ] `fetch(parameters)` method
  - [ ] `send(parameters)` method
  - [ ] `summarize(parameters)` method
  - [ ] `generate_draft(original_message)` method
- [ ] Test Gmail agent independently
- [ ] Write unit test for Gmail agent

### Slack Agent
- [ ] Create `src/backend/agents/slack_agent.py`
- [ ] Implement `SlackAgent(BaseAgent)` class
  - [ ] `__init__()` - initialize backend service and AI service
  - [ ] `connect(token)` method
  - [ ] `disconnect()` method
  - [ ] `fetch(parameters)` method
  - [ ] `send(parameters)` method
  - [ ] `summarize(parameters)` method
  - [ ] `generate_draft(original_message)` method
- [ ] Test Slack agent independently
- [ ] Write unit test for Slack agent

### Orchestrator
- [ ] Create `src/backend/core/` directory
- [ ] Create `src/backend/core/__init__.py`
- [ ] Create `src/backend/core/orchestrator.py`
- [ ] Implement `Orchestrator` class
  - [ ] `__init__(model_name, ollama_base_url)` method
  - [ ] `register_agent(name, agent)` method
  - [ ] `classify_intent(user_input)` method (Pydantic AI)
  - [ ] `process_intent(user_input)` method
  - [ ] `handle_fetch(intent)` method
  - [ ] `handle_send(intent)` method
  - [ ] `handle_summarize(intent)` method
- [ ] Test orchestrator with agents
- [ ] Write unit test for orchestrator

**Checkpoint:** Orchestrator routes commands to agents

---

## Phase 4: UI Development (Day 11-15)

### UI Foundation
- [ ] Create `src/frontend/ui/` directory
- [ ] Create `src/frontend/ui/__init__.py`
- [ ] Create `src/frontend/ui/styles.py`
- [ ] Implement `get_stylesheet()` function
- [ ] Create `src/frontend/assets/` directory
- [ ] Add UI assets (icons, images)

### Main Window
- [ ] Create `src/frontend/ui/autoreturn_app.py`
- [ ] Implement `AutoReturnApp(QMainWindow)` class
  - [ ] `__init__()` - initialize orchestrator and agents
  - [ ] `setup_ui()` - create UI layout
  - [ ] `setup_header()` - top bar with logo, search, notifications
  - [ ] `setup_filters()` - filter buttons (All, Gmail, Slack, Urgent)
  - [ ] `setup_table()` - message table
  - [ ] `populate_table()` - display messages
  - [ ] `sync_all_messages()` - sync through orchestrator
  - [ ] `show_send_message_dialog()` - compose message
- [ ] Test UI displays correctly
- [ ] Test UI connects to orchestrator (NOT services directly)

### Dialogs
- [ ] Create `src/frontend/dialogs/` directory
- [ ] Create `src/frontend/dialogs/__init__.py`
- [ ] Create `src/frontend/dialogs/auth_dialog.py`
- [ ] Create `src/frontend/dialogs/settings_dialog.py`
- [ ] Create `src/frontend/dialogs/notification_dialog.py`
- [ ] Create `src/frontend/dialogs/send_gmail_reply_dialog.py`
- [ ] Create `src/frontend/dialogs/send_slack_message_dialog.py`
- [ ] Test all dialogs

### Main Entry Point
- [ ] Create `main.py` in project root
- [ ] Implement main application entry point
  - [ ] Create QApplication
  - [ ] Show auth dialog
  - [ ] Create and show main window
  - [ ] Start event loop
- [ ] Test application starts
- [ ] Test authentication flow
- [ ] Test main window displays

**Checkpoint:** Full UI working through orchestrator

---

## Phase 5: AI Intelligence (Day 16-20)

### Priority Scoring
- [ ] Add `analyze_priority(email)` to GmailAgent
- [ ] Use AI to score 0.0 to 1.0
- [ ] Display priority in UI
- [ ] Test priority scoring
- [ ] Write property test for priority range

### Task Extraction
- [ ] Create `src/backend/core/task_extractor.py`
- [ ] Implement `TaskExtractor` class
  - [ ] `extract_tasks(message)` method
  - [ ] Use AI to find action items
- [ ] Add task extraction to agents
- [ ] Display tasks in UI
- [ ] Test task extraction
- [ ] Write unit test for task extractor

### Sentiment Analysis
- [ ] Create `src/backend/core/sentiment_analyzer.py`
- [ ] Implement `SentimentAnalyzer` class
  - [ ] `analyze(message)` method
  - [ ] Detect urgency and tone
- [ ] Add sentiment analysis to agents
- [ ] Display sentiment in UI
- [ ] Test sentiment analysis
- [ ] Write unit test for sentiment analyzer

### Smart Drafts
- [ ] Create `src/backend/core/draft_manager.py`
- [ ] Implement `DraftManager` class
  - [ ] `generate_draft(message, context)` method
  - [ ] Match tone to original
- [ ] Add draft generation to agents
- [ ] Show drafts in reply dialog
- [ ] Test draft generation
- [ ] Write unit test for draft manager

### AI Summary Queue
- [ ] Implement `QueueSummaryGenerator` in ai_service.py
- [ ] Add batch processing
- [ ] Add progress tracking
- [ ] Connect to UI
- [ ] Test summary generation
- [ ] Test concurrent processing

**Checkpoint:** AI features working

---

## Phase 6: Advanced Features (Day 21-25)

### Context Manager
- [ ] Create `src/backend/agents/context_manager.py`
- [ ] Implement `ContextManager` class
  - [ ] `add_message(message)` method
  - [ ] `get_conversation(thread_id)` method
  - [ ] `update_relationship(entity_id, interaction)` method
  - [ ] `learn_pattern(pattern)` method
- [ ] Add to agents
- [ ] Test context management
- [ ] Write unit test for context manager

### Learning Engine
- [ ] Create `src/backend/agents/learning_engine.py`
- [ ] Implement `LearningEngine` class
  - [ ] `record_feedback(decision, feedback)` method
  - [ ] `observe_action(action)` method
  - [ ] `update_models()` method
  - [ ] `get_preference(context)` method
- [ ] Add to agents
- [ ] Test learning
- [ ] Write unit test for learning engine

### Database (SQLite)
- [ ] Create database schema
- [ ] Implement database connection
- [ ] Add context storage
- [ ] Add pattern storage
- [ ] Add preference storage
- [ ] Test database operations
- [ ] Write unit test for database

**Checkpoint:** Advanced features working

---

## Phase 7: Testing & Polish (Day 26-30)

### Unit Tests
- [ ] Write tests for all services
- [ ] Write tests for all agents
- [ ] Write tests for orchestrator
- [ ] Write tests for UI components
- [ ] Achieve 80%+ code coverage
- [ ] Run: `pytest --cov=src tests/`

### Property-Based Tests
- [ ] Write property tests for priority scoring
- [ ] Write property tests for task extraction
- [ ] Write property tests for context management
- [ ] Write property tests for learning engine
- [ ] Run: `pytest tests/property/`

### Integration Tests
- [ ] Test Gmail-Slack coordination
- [ ] Test learning feedback loop
- [ ] Test end-to-end workflows
- [ ] Run: `pytest tests/integration/`

### Performance
- [ ] Profile application
- [ ] Optimize slow operations
- [ ] Add caching where needed
- [ ] Test with large message volumes
- [ ] Verify < 2s response time

### Error Handling
- [ ] Add try-catch blocks
- [ ] Add error logging
- [ ] Add user-friendly error messages
- [ ] Test error scenarios
- [ ] Add retry logic

### Documentation
- [ ] Update README.md
- [ ] Add code comments
- [ ] Add docstrings
- [ ] Create user guide
- [ ] Create API documentation

**Checkpoint:** Production-ready application

---

## Phase 8: Deployment (Day 31+)

### Packaging
- [ ] Create setup.py
- [ ] Test installation: `pip install -e .`
- [ ] Create executable with PyInstaller
- [ ] Test executable on clean system
- [ ] Create installer

### Distribution
- [ ] Create GitHub repository
- [ ] Push code to GitHub
- [ ] Create release
- [ ] Write release notes
- [ ] Publish

### Maintenance
- [ ] Set up CI/CD
- [ ] Set up issue tracking
- [ ] Create contribution guidelines
- [ ] Monitor for bugs
- [ ] Plan next features

**Checkpoint:** Application deployed

---

## Verification Checklist

### Functionality
- [ ] App starts without errors
- [ ] Ollama connects successfully
- [ ] Gmail OAuth works
- [ ] Slack token authentication works
- [ ] Messages display in unified inbox
- [ ] Can reply to Gmail
- [ ] Can reply to Slack
- [ ] AI summaries generate
- [ ] Priority scoring works
- [ ] Task extraction works
- [ ] Sentiment analysis works
- [ ] Smart drafts generate

### Architecture
- [ ] UI only talks to orchestrator
- [ ] Orchestrator routes to agents
- [ ] Agents use backend services
- [ ] No direct UI → service calls
- [ ] All AI uses local Ollama
- [ ] Agents have AI capabilities

### Quality
- [ ] All tests pass
- [ ] Code coverage > 80%
- [ ] No critical bugs
- [ ] Performance acceptable
- [ ] Error handling robust
- [ ] Documentation complete

---

## Daily Progress Tracking

### Week 1: Foundation
- [ ] Day 1: Environment setup
- [ ] Day 2: Configuration and structure
- [ ] Day 3: AI service
- [ ] Day 4: Gmail service
- [ ] Day 5: Slack service

### Week 2: Core Architecture
- [ ] Day 6: Data models and base agent
- [ ] Day 7: Gmail agent
- [ ] Day 8: Slack agent
- [ ] Day 9: Orchestrator
- [ ] Day 10: Integration testing

### Week 3: UI Development
- [ ] Day 11: UI foundation
- [ ] Day 12: Main window
- [ ] Day 13: Dialogs
- [ ] Day 14: Main entry point
- [ ] Day 15: UI testing

### Week 4: AI Intelligence
- [ ] Day 16: Priority scoring
- [ ] Day 17: Task extraction
- [ ] Day 18: Sentiment analysis
- [ ] Day 19: Smart drafts
- [ ] Day 20: AI summary queue

### Week 5: Advanced Features
- [ ] Day 21: Context manager
- [ ] Day 22: Learning engine
- [ ] Day 23: Database
- [ ] Day 24: Integration
- [ ] Day 25: Testing

### Week 6: Polish & Deploy
- [ ] Day 26-27: Testing
- [ ] Day 28: Performance
- [ ] Day 29: Documentation
- [ ] Day 30: Packaging
- [ ] Day 31+: Deployment

---

## Success Metrics

### MVP (Minimum Viable Product)
- [ ] App runs on clean system
- [ ] Connects to Gmail and Slack
- [ ] Shows unified inbox
- [ ] Can send messages
- [ ] AI summaries work
- [ ] Orchestrator pattern implemented

### Full Feature Set
- [ ] All MVP features
- [ ] Priority scoring
- [ ] Task extraction
- [ ] Sentiment analysis
- [ ] Smart drafts
- [ ] Context/memory
- [ ] Learning engine
- [ ] 80%+ test coverage

---

## Notes Section

Use this space to track issues, decisions, and learnings:

```
Date: ___________
Issue: 
Solution:
Notes:

---

Date: ___________
Issue:
Solution:
Notes:

---
```

---

## Quick Reference

**Start coding:** Phase 1, Day 1  
**First milestone:** Phase 2 complete (services working)  
**Second milestone:** Phase 3 complete (orchestrator working)  
**Third milestone:** Phase 4 complete (UI working)  
**MVP complete:** Phase 5 complete  
**Production ready:** Phase 7 complete  

**Stuck?** Check:
1. MASTER_REBUILD_SPEC.md
2. DEVELOPER_QUICK_REFERENCE.md
3. Existing code for patterns
4. Documentation files

**Good luck! 🚀**
