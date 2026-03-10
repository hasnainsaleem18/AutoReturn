# 🚀 AutoReturn - Unified AI Intelligence Hub

<div align="center">

![AutoReturn Logo](https://img.shields.io/badge/AutoReturn-Orchestrator--Agent-red?style=for-the-badge&logo=ai&logoColor=white)

**A high-performance Unified Inbox powered by a custom Orchestrator-Agent architecture. Manage Gmail, Slack, and Local AI in one lightning-fast interface.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Architecture](https://img.shields.io/badge/Architecture-Orchestrator--Agent-blueviolet?style=flat-square)](https://github.com/hasnainsaleem18/AutoReturn)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black?style=flat-square&logo=ollama&logoColor=white)](https://ollama.ai)

</div>

---

## Project Overview

AutoReturn is not just another email client; it is a **Unified AI Intelligence Hub**. It centralizes communication from **Gmail and Slack** into a single, high-speed interface. Rather than relying entirely on slow, expensive cloud AI models, AutoReturn uses a hybrid of **Local LLMs (via Ollama)** and **Custom Deterministic Algorithms** (written in raw Python) to process, rank, classify, and summarize incoming messages instantly.

This project was built from the ground up to solve the problem of *information overload*, specifically targeting professionals who lose hours every day switching between tabs and figuring out which messages to reply to first.

---

## Software Architecture

AutoReturn moved away from traditional monolithic design to a highly optimized **Decoupled Orchestrator-Agent Architecture**.

### 1. The Orchestrator (`orchestrator.py`)

The "Central Brain" of the application. The orchestrator receives intents layer from the UI (like "Fetch Messages" or "Generate Draft"), classifies the command, and routes it to the correct downstream agent. It holds the shared instances of the `ToneEngine` and `AiService` so that memory is not wasted.

### 2. Intelligent Agents (`gmail_agent.py`, `slack_agent.py`)

These are specialized worker classes acting as bridges to remote APIs.

* They perform parallel network requests via `asyncio`.
* They automatically pipe incoming data through the **Priority Engine**, **Tone Engine**, and **Task Classifier** before ever sending the data back to the UI.
* This is why the UI never lags during heavy data processing.

### 3. Progressive Loading UI

A revolutionary UI approach where messages are fetched from APIs instantly (<1s) and displayed on the screen immediately. Meanwhile, heavy AI tasks (like generating summaries) are "layered" on top in the background using a non-blocking queue. The user sees their inbox instantly, and the AI intelligence populates row-by-row as it finishes.

---

## Core Engines & Algorithms

AutoReturn’s true power lies in its custom-built backend engines.

### The 4-Part Priority Algorithm (`priority_engine.py`)

A fast, custom-built deterministic algorithm that scores every message from 0.0 to 10.0 and classifies it as **High**, **Medium**, or **Low** urgency. It relies on four sub-systems:

1. **Algorithm 01 (Master Engine)**: Uses a weighted mathematical formula `Urgency = (w1 × Keyword) + (w2 × Deadline) + (w3 × Sender)` to compute the final score.
2. **Algorithm 02 (Keyword Engine)**: Scans for Direct Urgency, Time Pressure, and Action Calls. It uses `spaCy` NLP for semantic context checking to understand **negations** (ensuring that the phrase *"this is NOT urgent"* does not trigger a high score).
3. **Algorithm 03 (Deadline Engine)**: Uses complex Regex matching to extract absolute dates (e.g., `12/25/2026`) and relative deadlines (e.g., `by tomorrow`). If the deadline is within 24 hours, it applies a massive point bonus.
4. **Algorithm 04 (Sender Engine)**: Checks the sender and CC lists against a user-configurable "Priority List" (e.g., marking emails from your boss as instant 10.0s).

### AI Task Classification System

Rather than just showing you a message, AutoReturn tells you *what to do with it*. Every message is passed through a keyword heuristic matrix and categorized into one of 5 actionable types:

1. **File Attachment Required** — Sender is explicitly requesting a document.
2. **Draft Generation** — The email requires a detailed, composed reply.
3. **Auto Reply** — Transactional message requiring a simple acknowledgement.
4. **Simple Reply Required** — Quick response or confirmation expected.
5. ℹ**Informational** — No action needed, read-and-archive.

### Advanced Tone Detection (`tone_engine.py`)

A lightning-fast (<5ms) algorithm that analyzes the tone of incoming text.

* **Hybrid Approach**: Combines a 60+ word emotional lexicon with `spaCy` embedding similarity.
* **9-Stage Pipeline**: Handles tokenization, scoring, normalizations, negation checking, and intensifier multiplier scaling.
* **Accuracy**: Tested at 80% accuracy on real-world corpuses. It classifies messages as `formal`, `informal`, or `neutral` and then uses this data to **suggest the proper tone** for your AI-generated drafts.

### Event & Calendar Extractor (`event_extractor.py`)

Scans message bodies for evidence of meetings, appointments, or deadlines.

* Uses a base layer of Regex for speed, but seamlessly falls back to a **Local LLM extraction prompt** if the date phrasing is ambiguous or complex.
* Returns structured JSON data representing the Event, and powers the UI feature allowing the user to **Export to .ics** and add the meeting directly to Google/Apple Calendar.

---

## Automation & Workflow Control

AutoReturn is a fully autonomous assistant when you are away from your desk.

### DND & Reply Policy Engine

Controlled via the Settings menu, AutoReturn manages how incoming messages are handled:

* **DND OFF**: Standard mode. You read messages, you click "Reply", and a Pre-Send Review Dialog appears where you can generate AI drafts naturally.
* **DND ON + Auto Reply OFF**: The app suppresses OS desktop notifications. When messages arrive, the AI quietly generates **Drafts** in the background and tags the rows as "Draft Ready". You return to your desk and just click "Send" on the pre-written drafts.
* **DND ON + Auto Reply ON (Allowlist Mode)**: Total automation. The app checks if the sender is on your trusted Allowlist. If they are, it generates a reply, **sends it via the API automatically**, and logs the action.

### Attachment Resolver & Ambiguity Handling

* Reads your `file_access_paths` setting to know where it is allowed to look for files on your hard drive.
* If a sender asks for "the Q3 report", AutoReturn searches your allowed folders, finds the file, and auto-attaches it to the draft.
* **Ambiguity Blocking**: If it finds *two* files named "Q3 Report", it halts the automation and prompts the user to manually select the correct one, ensuring no confidential data is sent by mistake.

---

##  UI & Frontend Engineering

Built on **PySide6 (Qt for Python)**, the UI is styled entirely with custom CSS.

* **Unified Data Table**: A customized `QTableWidget` displays standard columns (Sender, Subject, Platform) alongside AI-enriched data (Priority Badges, Summary cell, Event Icons, Task Badges).
* **Tone Selector Widget**: A modular, reusable UI component that allows users to override the AI's default tone (Formal vs Informal) before generating a draft.
* **Review Dialogs**: Polished popups for both Gmail and Slack that allow users to edit AI drafts, attach files, and preview the final payload securely before it hits the API.

---

## Project Structure

The AutoReturn codebase is **fully documented with inline presentation-ready comments detailing every single algorithm and class functionality**. You can open any file in `src/backend/core/` and read exactly how the math works in plain English.

```text
AutoReturn/
├── main.py                  # Application entry point
├── run.sh                   # Startup shell wrapper
├── auto_commenter.py        # Custom AST scripting tool for documentation
├── config/                  # Settings definitions
├── data/                    # JSON Databases (Audits, Priority Config, Tone Profiles)
├── src/
│   ├── backend/
│   │   ├── core/            # The Brain (Algorithms, Tone Engine, Event Extractor)
│   │   ├── agents/          # Platform Interfaces (GmailAgent, SlackAgent)
│   │   ├── services/        # AI Service, Backend APIs, Settings Coordinators
│   │   └── models/          # Pydantic data schemas for type-safe routing
│   └── frontend/
│       ├── ui/              # Main PyQt/PySide Window (autoreturn_app.py)
│       ├── dialogs/         # Send replies, View events, App settings
│       └── widgets/         # Pluggable modular UI elements (Tone selector)
└── docs/                    # Technical architecture diagrams and algorithms
```

---

## Setup & Installation

### 1. Prerequisites

* **Python 3.10+** (Recommended 3.12)
* **Ollama** (Download from [ollama.ai](https://ollama.ai))

### 2. Quick Start

```bash
# Clone the repository
git clone https://github.com/hasnainsaleem18/AutoReturn.git
cd AutoReturn

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install all Python dependencies
pip install -r requirements.txt

# Install the spaCy model used for Semantic NLP Context Analysis
python -m spacy download en_core_web_md

# Pull the primary AI model used by the orchestrator
ollama pull kimi-k2.5:cloud

# Authenticate with Ollama Cloud (required for cloud-backed local models)
ollama signin

# Launch the application
./run.sh
```

---

## App Configuration

All configuration is handled safely via the **Settings menu** in the UI, which writes to `data/automation_settings.json`.

* **Gmail Authorization**: Requires a valid Google Cloud `client_secret.json` to be placed in the project root. The app will launch an OAuth browser flow on first run.
* **Slack Authorization**: Requires a valid Slack App User Token (`xoxp-...`) with `history` and `read` scopes, pasted into the Settings menu.

---

## Development Roadmap & Status

* [x] Custom Orchestrator-Agent Architecture
* [x] Progressive Application Loading / Async Data Fetching
* [x] Background AI Threading & Non-blocking Queues
* [x] Hybrid Tone Detection Engine (Lexicon + Embeddings)
* [x] **4-Part Priority Ranking Algorithm (Alg 01 - 04)**
* [x] **Dynamic Priority Rules Editor in GUI**
* [x] **5-Category AI Task Classification System**
* [x] **Calendar & Event Extraction (Regex + LLM Fallback)**
* [x] Event JSON to `.ics` Export capability
* [x] User Preference Learning & Tone History profiles
* [x] Real-time UI Tone Detection and AI Suggestions
* [x] Autonomous DND Policy Engine and Workflow Routing
* [x] Sub-thread Gmail Auto-reply Matching
* [x] Secure File Attachment Context Resolver
* [x] Fully Documented Codebase (Presentation-Ready)
* [ ] Universal Smart Draft generation expansion
* [ ] Multi-language Support Integration

---
<div align="center">
<b>Built as a Final Year Project at NUCES FAST Peshawar</b><br>
<i>Developed by Kashan Saeed, Alishba Tariq & Hasnain Saleem</i>
</div>
