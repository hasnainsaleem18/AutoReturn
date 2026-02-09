# AutoCom Developer Quick Reference

## 🚀 Daily Development Commands

### Start Development

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Start Ollama (in separate terminal)
ollama serve

# Run application
python main.py

# Run with debug
DEBUG=True python main.py
```

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_orchestrator.py

# Run with coverage
pytest --cov=src tests/

# Run property-based tests
pytest tests/property/
```

---

## 📁 Where to Find Things

### Configuration
- **Environment:** `.env` (your settings)
- **Settings Loader:** `src/backend/config/settings.py`
- **Example:** `.env.example` (template)

### Core Components
- **Orchestrator:** `src/backend/core/orchestrator.py` (THE BRAIN)
- **Gmail Agent:** `src/backend/agents/gmail_agent.py`
- **Slack Agent:** `src/backend/agents/slack_agent.py`
- **Base Agent:** `src/backend/agents/base_agent.py`

### Backend Services
- **Gmail API:** `src/backend/services/gmail_backend.py`
- **Slack API:** `src/backend/services/slack_backend.py`
- **AI Service:** `src/backend/services/ai_service.py`

### UI
- **Main Window:** `src/frontend/ui/autoreturn_app.py`
- **Dialogs:** `src/frontend/dialogs/`
- **Styles:** `src/frontend/ui/styles.py`

### Documentation
- **Master Spec:** `MASTER_REBUILD_SPEC.md` (START HERE)
- **Vision:** `DOCUMENTATION/01_PROJECT_VISION.md`
- **Architecture:** `DOCUMENTATION/04_SYSTEM_ARCHITECTURE.md`
- **Refactoring:** `REFACTORING_PLAN.md`
- **Status:** `IMPLEMENTATION_STATUS.md`

---

## 🎯 Architecture Rules (CRITICAL)

### ✅ DO THIS

```python
# UI talks to orchestrator
response = await self.orchestrator.process_intent("Fetch emails")

# Orchestrator routes to agent
response = await self.gmail_agent.fetch(parameters)

# Agent uses backend service
emails = await self.gmail_backend.fetch_emails()

# Agent adds AI intelligence
email['summary'] = await self.ai_service.summarize(email)
```

### ❌ DON'T DO THIS

```python
# WRONG - UI calling service directly
emails = self.gmail_service.fetch_emails()  # NO!

# WRONG - UI calling AI directly
summary = self.ollama_service.summarize(email)  # NO!

# WRONG - Agent bypassing orchestrator
self.slack_agent.send_message(...)  # NO! (from UI)
```

### The Golden Rule

```
UI → Orchestrator → Agent → Service → API
         ↑            ↑        ↑
       BRAIN    INTELLIGENT  DUMB
                  WORKER    WRAPPER
```

---

## 🔧 Common Tasks

### Add New Feature

1. **Update orchestrator** - Add intent handling
2. **Update agent** - Add intelligence
3. **Update service** - Add API call (if needed)
4. **Update UI** - Add UI elements
5. **Test** - Write tests

### Add AI Capability

```python
# In agent (e.g., gmail_agent.py)
async def analyze_priority(self, email):
    """Use AI to score email priority."""
    prompt = f"Score priority 0-1 for: {email['subject']}"
    response = await self.ai_service.generate(prompt)
    return float(response)
```

### Add New Agent

1. **Create agent file:** `src/backend/agents/new_agent.py`
2. **Extend BaseAgent:** `class NewAgent(BaseAgent)`
3. **Register with orchestrator:** `orchestrator.register_agent("new", new_agent)`
4. **Add intent handling:** Update orchestrator routing

### Debug Issue

```python
# Add debug prints
print(f"DEBUG: {variable}")

# Or use logging
import logging
logging.debug(f"Value: {variable}")

# Check settings
from src.backend.config import settings
settings.print_config()
```

---

## 🐛 Troubleshooting

### Ollama Not Working

```bash
# Check if running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Test model
ollama run kimi-k2.5:cloud "test"

# Check .env
cat .env | grep OLLAMA
```

### Gmail Not Connecting

```bash
# Check credentials exist
ls -la data/gmail_data/client_secret.json

# Check .env paths
cat .env | grep GMAIL

# Delete token and retry
rm data/gmail_data/token.json
python main.py
```

### Slack Not Connecting

```bash
# Check token in .env
cat .env | grep SLACK

# Or check keyring
python -c "import keyring; print(keyring.get_password('autoreturn', 'slack_token'))"

# Test token manually
curl -H "Authorization: Bearer xoxp-YOUR-TOKEN" \
  https://slack.com/api/auth.test
```

### Import Errors

```bash
# Check virtual environment active
which python  # Should show .venv path

# Reinstall dependencies
pip install -r requirements.txt

# Check Python path
python -c "import sys; print(sys.path)"
```

---

## 📝 Code Patterns

### Orchestrator Intent Handling

```python
# In orchestrator.py
async def process_intent(self, user_input: str) -> AgentResponse:
    # Classify intent
    intent = await self.classify_intent(user_input)
    
    # Route to handler
    if intent.action == "fetch":
        return await self.handle_fetch(intent)
    elif intent.action == "send":
        return await self.handle_send(intent)
    
    return AgentResponse(success=False, message="Unknown intent")

async def handle_fetch(self, intent: Intent) -> AgentResponse:
    if intent.target == "gmail":
        return await self.gmail_agent.fetch(intent.parameters)
    elif intent.target == "slack":
        return await self.slack_agent.fetch(intent.parameters)
```

### Agent Pattern

```python
# In gmail_agent.py
class GmailAgent(BaseAgent):
    def __init__(self):
        super().__init__("gmail")
        self.backend = GmailBackendService()
        self.ai_service = OllamaService()
    
    async def fetch(self, parameters: Dict) -> AgentResponse:
        # Use backend for API call
        emails = await self.backend.fetch_emails()
        
        # Add AI intelligence
        for email in emails:
            email['priority'] = await self.analyze_priority(email)
            email['summary'] = await self.generate_summary(email)
        
        return AgentResponse(
            success=True,
            data={'emails': emails},
            message=f"Fetched {len(emails)} emails"
        )
    
    async def analyze_priority(self, email: Dict) -> float:
        """AI-powered priority scoring."""
        prompt = f"Score 0-1: {email['subject']}"
        score = await self.ai_service.generate(prompt)
        return float(score)
```

### Service Pattern

```python
# In gmail_backend.py
class GmailBackendService:
    """Dumb API wrapper - no AI logic here."""
    
    def __init__(self):
        self.service = None
    
    def connect(self):
        """OAuth connection."""
        # OAuth flow
        pass
    
    async def fetch_emails(self, max_results=10):
        """Fetch emails from Gmail API."""
        # API call
        results = self.service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()
        
        return results.get('messages', [])
```

### UI Pattern

```python
# In autoreturn_app.py
class AutoReturnApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize orchestrator (NOT services directly)
        self.orchestrator = Orchestrator()
        
        # Register agents
        self.gmail_agent = GmailAgent()
        self.slack_agent = SlackAgent()
        self.orchestrator.register_agent("gmail", self.gmail_agent)
        self.orchestrator.register_agent("slack", self.slack_agent)
    
    async def sync_messages(self):
        """Sync messages through orchestrator."""
        # Call orchestrator (NOT service directly)
        response = await self.orchestrator.process_intent("Fetch all messages")
        
        if response.success:
            self.display_messages(response.data['messages'])
        else:
            QMessageBox.warning(self, "Error", response.message)
```

---

## 🧪 Testing Patterns

### Unit Test

```python
# tests/unit/test_gmail_agent.py
import pytest
from src.backend.agents.gmail_agent import GmailAgent

@pytest.mark.asyncio
async def test_fetch_emails():
    agent = GmailAgent()
    response = await agent.fetch({'max_results': 10})
    
    assert response.success
    assert 'emails' in response.data
    assert len(response.data['emails']) <= 10
```

### Property Test

```python
# tests/property/test_priority_scoring.py
from hypothesis import given, strategies as st
from src.backend.agents.gmail_agent import GmailAgent

@given(email=st.dictionaries(
    st.text(),
    st.text(),
    min_size=1
))
@pytest.mark.asyncio
async def test_priority_score_range(email):
    """Priority score must be 0.0 to 1.0."""
    agent = GmailAgent()
    score = await agent.analyze_priority(email)
    
    assert 0.0 <= score <= 1.0
```

---

## 📊 Project Status

### What's Working (40%)
- ✅ Gmail integration
- ✅ Slack integration
- ✅ Basic orchestrator
- ✅ Basic agents
- ✅ Desktop UI
- ✅ AI summarization

### What's Missing (60%)
- ❌ Context/memory system
- ❌ Learning engine
- ❌ Priority scoring
- ❌ Task extraction
- ❌ Sentiment analysis
- ❌ Voice pipeline

### Current Phase
**Phase 3:** Orchestrator & Agents (in progress)

**Next:** Phase 4 - UI Integration

---

## 🎯 Quick Wins

### Easy Features to Add

1. **Priority Scoring** (2 hours)
   - Add to gmail_agent.py
   - Use AI to score 0-1
   - Display in UI

2. **Task Extraction** (3 hours)
   - Add to gmail_agent.py
   - Use AI to find tasks
   - Display in UI

3. **Smart Drafts** (4 hours)
   - Add to agents
   - Use AI to generate
   - Show in reply dialog

---

## 💡 Tips

### Performance
- Use async/await everywhere
- Cache AI results
- Batch API calls
- Limit concurrent AI requests

### Debugging
- Use `print()` liberally
- Check .env settings
- Test services independently
- Use pytest for regression

### Code Quality
- Follow existing patterns
- Keep functions small
- Add docstrings
- Write tests

### Git Workflow
```bash
# Create feature branch
git checkout -b feature/priority-scoring

# Commit often
git add .
git commit -m "Add priority scoring to Gmail agent"

# Push and create PR
git push origin feature/priority-scoring
```

---

## 📚 Key Files to Read

**Before coding:**
1. `MASTER_REBUILD_SPEC.md` - Overall architecture
2. `REFACTORING_PLAN.md` - Orchestrator pattern
3. `src/backend/core/orchestrator.py` - See how it works

**When stuck:**
1. `IMPLEMENTATION_STATUS.md` - What's done
2. `specs/intelligent-ai-agents/design.md` - Detailed design
3. Existing code - See patterns

---

## 🚨 Remember

1. **UI → Orchestrator → Agent → Service** (ALWAYS)
2. **Agents are intelligent** (not just wrappers)
3. **All AI stays local** (Ollama only)
4. **Test after every change**
5. **Read existing code** for patterns

---

## 🎓 Learning Path

**Day 1:** Read MASTER_REBUILD_SPEC.md  
**Day 2:** Set up environment, run app  
**Day 3:** Understand orchestrator pattern  
**Day 4:** Study existing agents  
**Day 5:** Make first small change  
**Week 2:** Add new feature  
**Week 3:** Implement intelligent features  

---

## ✅ Daily Checklist

- [ ] Virtual environment activated
- [ ] Ollama running
- [ ] .env configured
- [ ] Tests passing
- [ ] Code follows patterns
- [ ] Changes committed

---

**Need help?** Check `MASTER_REBUILD_SPEC.md` or existing code for patterns!
