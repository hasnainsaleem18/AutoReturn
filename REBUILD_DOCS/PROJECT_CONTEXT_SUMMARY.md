# AutoCom Project Context Summary

## 🎯 What This Document Is

This is a **context summary** for anyone (including future you) who needs to understand this project quickly. It answers the key questions: What? Why? How?

---

## 📖 Project Story

### The Problem
Users juggle multiple communication apps (Gmail, Slack) leading to:
- Context switching (40% productivity loss)
- Missed action items (60% forgotten)
- Notification fatigue
- Privacy concerns with cloud AI

### The Solution: AutoCom
A **unified communication platform** that:
1. Brings Gmail + Slack into ONE inbox
2. Uses **local AI** (Ollama) for intelligence
3. Has an **orchestrator-centric architecture**
4. Provides **intelligent agents** (not just API wrappers)
5. Keeps everything **private** (no cloud AI)

### The Vision
"Automate Everything. From Voice to Victory."

Future features: Voice control, calendar integration, visual analytics, tone adjustment, auto-foldering.

---

## 🏗️ Architecture Philosophy

### The Core Principle

```
UI → Orchestrator → Agents → Services → APIs
      (BRAIN)    (INTELLIGENT) (DUMB)
                  (WORKERS)   (WRAPPERS)
```

### Why This Architecture?

**Problem with old approach:**
```
UI → Service → API  (UI has too much logic)
UI → AI Service     (Direct AI calls everywhere)
```

**New approach:**
```
UI → Orchestrator → Agent → Service → API
     ↑              ↑        ↑
   Central      Intelligent  Simple
   Brain        Worker       Wrapper
```

**Benefits:**
1. **Single source of truth** - Orchestrator knows everything
2. **Intelligent agents** - Can make domain-specific decisions
3. **Clean separation** - Each layer has clear responsibility
4. **Easy to extend** - Add new agents without changing UI
5. **Testable** - Each layer can be tested independently

---

## 🧠 Key Concepts

### 1. Orchestrator (The Brain)

**What it does:**
- Receives commands from UI (natural language or structured)
- Classifies intent using Pydantic AI
- Routes to appropriate agent
- Maintains global context
- Coordinates between agents
- Makes high-level decisions

**Example:**
```python
# User says: "Fetch my urgent emails"
orchestrator.process_intent("Fetch my urgent emails")
  → Classifies: Intent(action="fetch", target="gmail", filter="urgent")
  → Routes to: gmail_agent.fetch({"filter": "urgent"})
  → Returns: AgentResponse with emails
```

### 2. Agents (Intelligent Workers)

**What they are:**
- NOT just API wrappers
- Have AI capabilities for their domain
- Can make autonomous decisions
- Report to orchestrator
- Learn from user feedback

**Example:**
```python
class GmailAgent:
    async def fetch(self, parameters):
        # 1. Use backend service for API call
        emails = await self.backend.fetch_emails()
        
        # 2. Add AI intelligence
        for email in emails:
            email['priority'] = await self.analyze_priority(email)
            email['summary'] = await self.generate_summary(email)
            email['tasks'] = await self.extract_tasks(email)
        
        # 3. Return intelligent response
        return AgentResponse(success=True, data={'emails': emails})
```

### 3. Services (Dumb Wrappers)

**What they are:**
- Simple API wrappers
- No AI logic
- No business logic
- Just API calls

**Example:**
```python
class GmailBackendService:
    async def fetch_emails(self, max_results=10):
        # Just call Gmail API
        results = self.service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()
        return results.get('messages', [])
```

---

## 🎨 Design Patterns

### Pattern 1: Command Flow

```
User Action (UI)
  ↓
Orchestrator.process_intent("command")
  ↓
Orchestrator.classify_intent() → Intent
  ↓
Orchestrator.route_to_agent(intent)
  ↓
Agent.execute(parameters)
  ↓
Agent uses Service for API call
  ↓
Agent adds AI intelligence
  ↓
Agent returns AgentResponse
  ↓
Orchestrator returns to UI
  ↓
UI displays result
```

### Pattern 2: Agent Intelligence

```
Agent receives request
  ↓
Use backend service (API call)
  ↓
Add AI capabilities:
  - Priority scoring
  - Summarization
  - Task extraction
  - Sentiment analysis
  - Draft generation
  ↓
Return enriched data
```

### Pattern 3: No Direct Calls

```
❌ WRONG:
UI → Service.fetch()
UI → AI.summarize()

✅ RIGHT:
UI → Orchestrator.process_intent()
     ↓
     Agent.fetch()
       ↓
       Service.fetch()
       AI.summarize()
```

---

## 🔑 Critical Rules

### Rule 1: UI Only Talks to Orchestrator
```python
# ❌ NEVER DO THIS
class UI:
    def sync(self):
        emails = self.gmail_service.fetch()  # WRONG!

# ✅ ALWAYS DO THIS
class UI:
    async def sync(self):
        response = await self.orchestrator.process_intent("Fetch emails")
```

### Rule 2: Agents Are Intelligent
```python
# ❌ WRONG - Dumb wrapper
class GmailAgent:
    async def fetch(self):
        return await self.backend.fetch_emails()

# ✅ RIGHT - Intelligent agent
class GmailAgent:
    async def fetch(self):
        emails = await self.backend.fetch_emails()
        for email in emails:
            email['priority'] = await self.analyze_priority(email)
            email['summary'] = await self.generate_summary(email)
        return AgentResponse(data={'emails': emails})
```

### Rule 3: All AI Stays Local
```python
# ❌ WRONG - Cloud AI
response = requests.post("https://api.openai.com/...", ...)

# ✅ RIGHT - Local Ollama
response = await self.ollama_service.generate(prompt)
```

### Rule 4: Services Are Dumb
```python
# ❌ WRONG - Service has AI logic
class GmailService:
    def fetch(self):
        emails = self.api.fetch()
        for email in emails:
            email['summary'] = self.ai.summarize(email)  # NO!
        return emails

# ✅ RIGHT - Service just calls API
class GmailService:
    def fetch(self):
        return self.api.fetch()  # Just API call
```

---

## 📊 Current State

### What's Working (40%)
- Gmail integration (OAuth, fetch, send)
- Slack integration (token, fetch, send, real-time)
- Basic orchestrator (Pydantic AI intent classification)
- Basic agents (wrap services, add AI summaries)
- Desktop UI (unified inbox, message display)
- AI service (Ollama integration)

### What's Missing (60%)
- Context/memory system (SQLite)
- Learning engine (learn from feedback)
- Priority scoring (AI-based)
- Task extraction (AI-based)
- Sentiment analysis (AI-based)
- Smart draft generation (AI-based)
- Voice pipeline (future)
- Advanced features (auto-foldering, tone adjustment, calendar)

### Architecture Status
- ✅ Orchestrator exists
- ✅ Agents exist
- ✅ Services exist
- ⚠️ UI still has some direct service calls (needs refactoring)
- ❌ Context manager not implemented
- ❌ Learning engine not implemented

---

## 🗺️ Roadmap

### Phase 1: Foundation (DONE)
- Project structure
- Environment configuration
- Basic services

### Phase 2: Core Architecture (IN PROGRESS)
- Orchestrator
- Agents
- Service integration

### Phase 3: UI Integration (NEXT)
- Remove direct service calls from UI
- Connect UI to orchestrator
- Test full flow

### Phase 4: AI Intelligence (FUTURE)
- Priority scoring
- Task extraction
- Sentiment analysis
- Smart drafts
- Context/memory
- Learning engine

### Phase 5: Advanced Features (FUTURE)
- Voice control
- Auto-foldering
- Tone adjustment
- Calendar integration
- Visual analytics

---

## 🛠️ Technology Choices

### Why PyQt6?
- Native desktop performance
- Cross-platform (Windows, Mac, Linux)
- Rich widget library
- Good documentation

### Why Ollama?
- **Privacy-first** - runs locally
- No API costs
- No data sent to cloud
- Fast inference
- Easy to use

### Why Pydantic AI?
- Type-safe agent framework
- Structured outputs
- Easy intent classification
- Good integration with Pydantic models

### Why SQLite?
- Serverless (no setup)
- Local storage (privacy)
- Fast for single-user
- Built into Python

### Why Python?
- Rapid development
- Great AI/ML libraries
- Good UI frameworks
- Easy to maintain

---

## 📚 Key Documents

### For Understanding
1. **MASTER_REBUILD_SPEC.md** - Complete specification
2. **PROJECT_CONTEXT_SUMMARY.md** - This document
3. **DOCUMENTATION/01_PROJECT_VISION.md** - Project vision
4. **DOCUMENTATION/04_SYSTEM_ARCHITECTURE.md** - Architecture details

### For Implementation
1. **IMPLEMENTATION_CHECKLIST.md** - Step-by-step tasks
2. **DEVELOPER_QUICK_REFERENCE.md** - Daily development guide
3. **REFACTORING_PLAN.md** - Orchestrator pattern details
4. **specs/intelligent-ai-agents/** - Intelligent agents spec

### For Status
1. **IMPLEMENTATION_STATUS.md** - What's done, what's not
2. **REFACTORING_PLAN.md** - What to deprecate, what to keep

---

## 🎓 Learning the Codebase

### Day 1: Read These
1. This document (PROJECT_CONTEXT_SUMMARY.md)
2. MASTER_REBUILD_SPEC.md
3. DEVELOPER_QUICK_REFERENCE.md

### Day 2: Understand Architecture
1. Read REFACTORING_PLAN.md
2. Study orchestrator.py
3. Study gmail_agent.py
4. Study slack_agent.py

### Day 3: See It Work
1. Set up .env
2. Run the app
3. Connect Gmail and Slack
4. See messages in unified inbox
5. Try AI summaries

### Day 4: Make First Change
1. Pick a small feature (e.g., priority scoring)
2. Add to agent
3. Test it
4. See it work in UI

---

## 🔍 Common Questions

### Q: Why not just use the services directly from UI?
**A:** Because then UI has too much logic. Orchestrator provides:
- Single point of control
- Easy to add features
- Easy to test
- Clean separation

### Q: Why are agents "intelligent"?
**A:** Because they can:
- Make domain-specific decisions
- Use AI for their service
- Learn from feedback
- Provide rich responses

### Q: Why local AI (Ollama)?
**A:** Privacy! All data stays on device. No cloud AI = no data leaks.

### Q: Can I add a new service (e.g., Discord)?
**A:** Yes! Just:
1. Create DiscordBackendService (API wrapper)
2. Create DiscordAgent (intelligent wrapper)
3. Register with orchestrator
4. Done!

### Q: Where does AI processing happen?
**A:** In agents! They use OllamaService to add intelligence to their responses.

### Q: What if I want to add a new AI feature?
**A:** Add it to the agent:
```python
class GmailAgent:
    async def new_ai_feature(self, email):
        result = await self.ai_service.generate(prompt)
        return result
```

---

## 🎯 Success Criteria

### You Understand the Project When:
- [ ] You can explain the orchestrator pattern
- [ ] You know why agents are intelligent
- [ ] You can add a new feature to an agent
- [ ] You understand the command flow
- [ ] You know where AI processing happens

### The Project Is Successful When:
- [ ] App runs on clean system
- [ ] Gmail and Slack work
- [ ] Unified inbox displays messages
- [ ] AI features work (summaries, priority, tasks)
- [ ] Orchestrator coordinates everything
- [ ] No direct UI → service calls
- [ ] All AI stays local

---

## 💡 Key Insights

### Insight 1: Orchestrator Is The Key
Everything flows through orchestrator. It's the single source of truth.

### Insight 2: Agents Add Value
Agents aren't just wrappers - they add AI intelligence to their domain.

### Insight 3: Privacy Matters
Local AI (Ollama) means user data never leaves their device.

### Insight 4: Clean Architecture Scales
This architecture makes it easy to add new services and features.

### Insight 5: AI Everywhere
Every agent can use AI for domain-specific intelligence.

---

## 🚀 Getting Started

### Absolute Beginner?
1. Read this document
2. Read MASTER_REBUILD_SPEC.md
3. Follow IMPLEMENTATION_CHECKLIST.md

### Experienced Developer?
1. Skim this document
2. Read REFACTORING_PLAN.md
3. Study orchestrator.py and agents
4. Start coding!

### Just Want to Run It?
1. Copy .env.example to .env
2. Set OLLAMA_MODEL=kimi-k2.5:cloud
3. Run: python main.py
4. Connect services via UI

---

## 📝 Final Notes

### Remember
- **Orchestrator = Brain** (coordinates everything)
- **Agents = Intelligent Workers** (add AI to their domain)
- **Services = Dumb Wrappers** (just API calls)
- **UI → Orchestrator → Agent → Service** (always this flow)
- **All AI stays local** (Ollama only)

### When Stuck
1. Check DEVELOPER_QUICK_REFERENCE.md
2. Check existing code for patterns
3. Check MASTER_REBUILD_SPEC.md
4. Ask questions!

### Have Fun!
This is a cool project with clean architecture. Enjoy building it! 🎉

---

**Last Updated:** [Date]  
**Version:** 1.0  
**Status:** Ready for implementation
