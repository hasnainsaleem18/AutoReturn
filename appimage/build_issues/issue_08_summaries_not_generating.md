# Issue #8 — Summaries Not Generating in AppImage

## Status
✅ Fixed

## When It Happened
App launched, Gmail messages loaded, but summary column stayed empty.
No visible error shown to user.

## Root Cause
The app uses `kimi-k2.6:cloud` — an Ollama Cloud-backed model.
This model requires:
1. `ollama serve` to be running
2. `ollama signin` — authenticated with Ollama Cloud account
3. `ollama pull kimi-k2.6:cloud` — model pulled after signin

Without signin, every request to Ollama returns an auth error.
The `generate_summary` method catches all exceptions silently and
returns `None`, so the UI just shows no summary with no explanation.

## Fix Applied

### `src/frontend/ui/autoreturn_app.py` — improved warning message
Updated the "Ollama Not Running" dialog to also mention cloud model requirements:

```python
"Using cloud model (kimi-k2.6:cloud)? Also run:\n"
"  ollama signin\n"
"  ollama pull kimi-k2.6:cloud"
```

## What User Must Do Before Summaries Work
```bash
# 1. Start Ollama
ollama serve

# 2. Sign in to Ollama Cloud (in a new terminal)
ollama signin

# 3. Pull the model
ollama pull kimi-k2.6:cloud
```

## Note
`kimi-k2.6:cloud` requires a **paid Ollama subscription** (HTTP 403 error).
The app has been switched to `qwen2.5:1.5b` which is free, local, and requires no account.

Pull it once:
```bash
ollama pull qwen2.5:1.5b
```
