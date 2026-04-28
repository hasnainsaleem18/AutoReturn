# 🚀 AutoReturn - Unified AI Intelligence Hub

<div align="center">

![AutoReturn Logo](https://img.shields.io/badge/AutoReturn-Orchestrator--Agent-red?style=for-the-badge&logo=ai&logoColor=white)

**A high-performance Unified Inbox powered by a custom Orchestrator-Agent architecture. Manage Gmail, Slack, and Local AI in one lightning-fast interface.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Architecture](https://img.shields.io/badge/Architecture-Orchestrator--Agent-blueviolet?style=flat-square)](https://github.com/hasnainsaleem18/AutoReturn)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black?style=flat-square&logo=ollama&logoColor=white)](https://ollama.ai)
[![AppImage](https://img.shields.io/badge/Linux-AppImage-orange?style=flat-square&logo=linux&logoColor=white)](https://appimage.org)
[![Deb](https://img.shields.io/badge/Linux-DEB%20Package-red?style=flat-square&logo=debian&logoColor=white)](https://www.debian.org)

</div>

---

## Project Overview

AutoReturn is not just another email client; it is a **Unified AI Intelligence Hub**. It centralizes communication from **Gmail and Slack** into a single, high-speed interface. Rather than relying entirely on slow, expensive cloud AI models, AutoReturn uses a hybrid of **Local LLMs (via Ollama)** and **Custom Deterministic Algorithms** (written in raw Python) to process, rank, classify, and summarize incoming messages instantly.

This project was built from the ground up to solve the problem of *information overload*, specifically targeting professionals who lose hours every day switching between tabs and figuring out which messages to reply to first.

---

## 📦 Installation & Distribution

AutoReturn ships as a fully packaged Linux desktop application. Choose the format that suits your system.

### Option 1 — AppImage (Recommended, Any Linux Distro)

No installation required. Download, make executable, and run.

```bash
# Make executable
chmod +x AutoReturn-x86_64.AppImage

# Run
./AutoReturn-x86_64.AppImage
```

> Works on any Linux distribution — Garuda, Arch, Ubuntu, Fedora, etc.

### Option 2 — DEB Package (Ubuntu / Debian-based)

```bash
# Install
sudo dpkg -i autoreturn_1.0.0_amd64.deb

# Run from terminal or app launcher
autoreturn

# Uninstall
sudo dpkg -r autoreturn
```

### Option 3 — Run from Source

```bash
# Clone the repository
git clone https://github.com/kashan-miankhel14/AutoReturn.git
cd AutoReturn

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install spaCy NLP model
python -m spacy download en_core_web_md

# Launch
./run.sh
```

---

## ⚙️ Prerequisites (All Installation Methods)

Regardless of how you install AutoReturn, **Ollama must be running** for AI features to work.

### 1. Install Ollama

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Start Ollama

```bash
ollama serve
```

### 3. Pull the AI Model

```bash
ollama pull qwen2.5:1.5b
```

### 4. Configure Supabase (Authentication)

Create a `.env` file at the project root (or `~/.autoreturn/.env` for packaged installs):

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-publishable-anon-key
```

> Supabase is used for user authentication only. No message data is stored in Supabase.

---

## 🔨 Building from Source

### Build AppImage

```bash
# Install build dependency
sudo pacman -S appimagetool-bin librsvg   # Arch/Garuda
# or: sudo apt install appimagetool librsvg2-bin  # Ubuntu

# Build
bash appimage/build_appimage.sh
```

Output: `AutoReturn-x86_64.AppImage`

### Build DEB Package

```bash
# Install dpkg tools
sudo pacman -S dpkg   # Arch/Garuda
# or already available on Ubuntu/Debian

# Build
bash packaging/build_deb.sh
```

Output: `autoreturn_1.0.0_amd64.deb`

### Build Notes

- Build artifacts (`*.AppImage`, `build_appimage/`, `build_deb/`, `*.deb`) are excluded from git
- The spaCy `en_core_web_md` model is automatically bundled into both packages
- Voice features are disabled in packaged builds (whisper/sounddevice not bundled)
- All user data is stored in `~/.autoreturn/` for packaged installs (writable, persists across updates)

---

## Software Architecture

AutoReturn uses a **Decoupled Orchestrator-Agent Architecture**.

### 1. The Orchestrator (`orchestrator.py`)

The "Central Brain". Receives intents from the UI, classifies commands, and routes them to the correct agent. Holds shared instances of `ToneEngine` and `AiService` to avoid memory waste.

### 2. Intelligent Agents (`gmail_agent.py`, `slack_agent.py`)

Specialized workers bridging remote APIs.

* Perform parallel network requests via `asyncio`
* Pipe data through **Priority Engine**, **Tone Engine**, and **Task Classifier** before returning to UI
* UI never lags during heavy data processing

### 3. Progressive Loading UI

Messages are fetched and displayed instantly (<1s). Heavy AI tasks (summaries) are layered on top in a non-blocking background queue — inbox appears immediately, AI intelligence populates row-by-row.

---

## Core Engines & Algorithms

### The 4-Part Priority Algorithm (`priority_engine.py`)

Scores every message 0.0–10.0 → **High / Medium / Low** urgency.

1. **Algorithm 01 (Master Engine)**: `Urgency = (w1 × Keyword) + (w2 × Deadline) + (w3 × Sender)`
2. **Algorithm 02 (Keyword Engine)**: spaCy NLP with negation detection — *"NOT urgent"* won't trigger high score
3. **Algorithm 03 (Deadline Engine)**: Regex extracts absolute dates and relative deadlines, 24h bonus
4. **Algorithm 04 (Sender Engine)**: User-configurable priority sender list

### AI Task Classification System

Every message is categorized into one of 5 actionable types:

1. **File Attachment Required** — Sender requesting a document
2. **Draft Generation** — Needs a composed reply
3. **Auto Reply** — Simple acknowledgement needed
4. **Simple Reply Required** — Quick confirmation expected
5. **Informational** — No action needed

### Advanced Tone Detection (`tone_engine.py`)

Lightning-fast (<5ms) hybrid tone analysis:

* 60+ word emotional lexicon + spaCy embedding similarity
* 9-stage pipeline: tokenization → scoring → negation → intensifier scaling
* 80% accuracy on real-world corpus
* Graceful fallback to lexicon-only mode if spaCy model unavailable

### Event & Calendar Extractor (`event_extractor.py`)

* Regex base layer for speed
* LLM fallback for ambiguous date phrasing
* Exports structured `.ics` files for Google/Apple Calendar

---

## Automation & Workflow Control

### DND & Reply Policy Engine

* **DND OFF**: Standard mode — review and send replies manually
* **DND ON + Auto Reply OFF**: AI generates drafts silently in background, tagged "Draft Ready"
* **DND ON + Auto Reply ON**: Full automation — sends replies automatically to allowlisted senders

### Attachment Resolver

* Searches user-configured `file_access_paths` for requested files
* Ambiguity blocking — halts if multiple matching files found, prompts user to choose

---

## UI & Frontend

Built on **PySide6 (Qt for Python)**, styled with custom CSS.

* **Unified Data Table**: Priority badges, AI summaries, event icons, task badges
* **Tone Selector Widget**: Override AI tone (Formal/Informal) before draft generation
* **Review Dialogs**: Edit drafts, attach files, preview before sending

---

## Project Structure

Current tracked project structure. Local/generated folders such as `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, and ignored OAuth credential files are intentionally not shown.

```text
AutoReturn/
|-- .gitignore
|-- .python-version
|-- README.md
|-- appimage
|   |-- AutoReturn.desktop
|   |-- BUILD_ISSUES_LOG.md
|   |-- autoreturn.svg
|   |-- build_appimage.sh
|   |-- build_issues
|   |   |-- README.md
|   |   |-- issue_01_shiboken6_missing.md
|   |   |-- issue_02_spacy_model_not_bundled.md
|   |   |-- issue_03_tone_engine_crash.md
|   |   |-- issue_04_wrong_ollama_model.md
|   |   |-- issue_05_hardcoded_mac_path.md
|   |   |-- issue_06_apprun_hardcoded_python.md
|   |   |-- issue_07_gmail_credentials_readonly_appdir.md
|   |   `-- issue_08_summaries_not_generating.md
|   |-- entrypoint.py
|   `-- requirements-appimage.txt
|-- config
|   |-- settings.conf
|   `-- tone_detection_rules.json
|-- data
|   |-- automation_audit.jsonl
|   |-- automation_settings.json
|   |-- gmail_data
|   |   `-- .gitkeep
|   |-- ics_exports
|   |   |-- autoreturn_events_20260311_100107.ics
|   |   |-- autoreturn_events_20260311_101413.ics
|   |   `-- autoreturn_events_20260311_102453.ics
|   |-- priority_dataset.json
|   |-- tone_profile.json
|   `-- voice_activity.jsonl
|-- docs
|   |-- Tone_Detection_Algorithm.md
|   |-- backend_architecture.md
|   |-- test_statistics_and_evaluation.md
|   |-- test_statistics_and_evaluation_presentation.tex
|   `-- test_statistics_tables_frames_only.tex
|-- logs
|   `-- .gitkeep
|-- main.py
|-- packaging
|   `-- build_deb.sh
|-- requirements.txt
|-- run.sh
|-- src
|   |-- __init__.py
|   |-- backend
|   |   |-- __init__.py
|   |   |-- agents
|   |   |   |-- __init__.py
|   |   |   |-- base_agent.py
|   |   |   |-- gmail_agent.py
|   |   |   `-- slack_agent.py
|   |   |-- core
|   |   |   |-- AutoReturn_Gmail_Automation.py
|   |   |   |-- __init__.py
|   |   |   |-- attachment_resolver.py
|   |   |   |-- automation_coordinator.py
|   |   |   |-- draft_manager.py
|   |   |   |-- event_extractor.py
|   |   |   |-- orchestrator.py
|   |   |   |-- priority_engine.py
|   |   |   |-- reply_policy_engine.py
|   |   |   `-- tone_engine.py
|   |   |-- models
|   |   |   |-- __init__.py
|   |   |   |-- agent_models.py
|   |   |   |-- automation_models.py
|   |   |   |-- event_models.py
|   |   |   `-- tone_models.py
|   |   |-- services
|   |   |   |-- __init__.py
|   |   |   |-- ai_service.py
|   |   |   |-- automation_settings_service.py
|   |   |   |-- calendar_service.py
|   |   |   |-- gmail_backend.py
|   |   |   |-- slack_backend.py
|   |   |   |-- supabase_auth_service.py
|   |   |   |-- tone_service.py
|   |   |   |-- voice_intent_service.py
|   |   |   `-- voice_service.py
|   |   `-- utils
|   |       |-- __init__.py
|   |       |-- desktop_notifications.py
|   |       |-- message_analysis_cache.py
|   |       `-- timezone_utils.py
|   `-- frontend
|       |-- __init__.py
|       |-- assets
|       |   |-- Gmail_Logo_32px.png
|       |   |-- icons8-slack-new-48.png
|       |   `-- notification-bell-red.png
|       |-- dialogs
|       |   |-- __init__.py
|       |   |-- auth_dialog.py
|       |   |-- event_review_dialog.py
|       |   |-- notification_dialog.py
|       |   |-- plain_reply_review_dialog.py
|       |   |-- send_gmail_reply_dialog.py
|       |   |-- send_slack_message_dialog.py
|       |   `-- settings_dialog.py
|       |-- ui
|       |   |-- __init__.py
|       |   |-- autoreturn_app.py
|       |   `-- styles.py
|       `-- widgets
|           |-- __init__.py
|           |-- tone_detection_display.py
|           `-- tone_selector.py
|-- testing_formal
|   |-- FINAL_RESULTS_TEMPLATE.md
|   |-- METRICS_FRAMEWORK.md
|   |-- PRELIMINARY_RESULTS.md
|   |-- README.md
|   |-- TEST_CASE_MATRIX.md
|   |-- TEST_PLAN.md
|   |-- conftest.py
|   |-- manual
|   |   `-- SYSTEM_TEST_CHECKLIST.md
|   |-- metrics
|   |   |-- final_results_template.csv
|   |   `-- preliminary_results_template.csv
|   |-- pytest.ini
|   |-- requirements-test.txt
|   |-- results
|   |   |-- full_suite_20260308_195757.csv
|   |   |-- full_suite_20260308_195757.json
|   |   |-- full_suite_20260308_200345.csv
|   |   |-- full_suite_20260308_200345.json
|   |   |-- full_suite_20260308_200629.csv
|   |   |-- full_suite_20260308_200629.json
|   |   |-- full_suite_20260310_234651.csv
|   |   |-- full_suite_20260310_234651.json
|   |   |-- full_suite_20260311_045324.csv
|   |   |-- full_suite_20260311_045324.json
|   |   |-- preliminary_20260308_192937.csv
|   |   |-- preliminary_20260308_192937.json
|   |   `-- preliminary_20260311_045301.json
|   |-- scripts
|   |   |-- export_results_csv.py
|   |   |-- run_full_formal_suite.py
|   |   `-- run_preliminary_tests.py
|   `-- tests
|       |-- __init__.py
|       |-- integration
|       |   |-- __init__.py
|       |   |-- test_agents_fetch_integration_formal.py
|       |   `-- test_summary_queue_integration.py
|       |-- qt_utils.py
|       `-- unit
|           |-- __init__.py
|           |-- test_agents_orchestrator_formal.py
|           |-- test_ai_service_formal.py
|           |-- test_attachment_resolver_formal.py
|           |-- test_autoreturn_app_utils_formal.py
|           |-- test_calendar_service_formal.py
|           |-- test_desktop_notifications_formal.py
|           |-- test_draft_manager_formal.py
|           |-- test_event_extractor_formal.py
|           |-- test_frontend_dialogs_widgets_formal.py
|           |-- test_gmail_automation_core_formal.py
|           |-- test_gmail_backend_formal.py
|           |-- test_message_analysis_cache_formal.py
|           |-- test_models_formal.py
|           |-- test_orchestrator_init_formal.py
|           |-- test_policy_and_settings_formal.py
|           |-- test_priority_engine_formal.py
|           |-- test_project_wide_static_formal.py
|           |-- test_settings_and_main_formal.py
|           |-- test_slack_backend_formal.py
|           |-- test_timezone_utils_formal.py
|           |-- test_tone_detector_formal.py
|           |-- test_tone_engine_formal.py
|           |-- test_tone_service_formal.py
|           `-- test_voice_service_formal.py
`-- tests
    |-- test_event_extractor.py
    |-- test_ollama.py
    `-- test_tone_selector.py
```

---

## App Configuration

### Authentication

Supabase email/password auth. Add to `.env`:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your-publishable-key
```

Google OAuth login is also supported independently.

### Integrations

* **Gmail**: Upload `client_secret.json` via Settings → run OAuth flow → `token.json` auto-generated
* **Slack**: Paste `xoxp-...` User OAuth Token in Settings (requires `history` + `read` scopes)
* **Per-user scoping**: Each AutoReturn account has its own Gmail/Slack connection

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
* [x] **AppImage Package (Linux universal)**
* [x] **DEB Package (Ubuntu/Debian)**
* [ ] Universal Smart Draft generation expansion
* [ ] Multi-language Support Integration

---

<div align="center">
<b>Built as a Final Year Project at NUCES FAST Peshawar</b><br>
<i>Developed by Kashan Saeed, Alishba Tariq & Hasnain Saleem</i>
</div>
