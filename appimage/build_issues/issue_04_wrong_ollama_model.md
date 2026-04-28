# Issue #4 — Wrong Ollama Model Hardcoded in App

## Status
✅ Fixed

## When It Happened
Spotted in the crash traceback from Issue #3 — even before the spaCy crash,
the Orchestrator was being initialized with the wrong model name.

## Evidence in Traceback
```
File ".../autoreturn_app.py", line 148, in __init__
    self.orchestrator = Orchestrator(ollama_model="gpt-oss:120b-cloud")
```

## Root Cause
`src/frontend/ui/autoreturn_app.py` had an outdated/incorrect model name
hardcoded: `"gpt-oss:120b-cloud"`.

This model does not exist locally. All AI features (summaries, drafts,
tone suggestions) would silently fail because Ollama would return a 404
for every request.

The correct model used everywhere else in the codebase is `qwen2.5:1.5b`:
- `src/backend/services/ai_service.py` default: `"qwen2.5:1.5b"`
- `src/backend/core/orchestrator.py` default: `"qwen2.5:1.5b"`
- `config/settings.conf`: `ollama_model = qwen2.5:1.5b`

## Fix Applied
**File:** `src/frontend/ui/autoreturn_app.py`

```python
# Before (wrong)
self.orchestrator = Orchestrator(ollama_model="gpt-oss:120b-cloud")

# After (correct)
self.orchestrator = Orchestrator(ollama_model="kimi-k2.6:cloud")
```

## Lesson
Model names should be read from `config/settings.conf` rather than hardcoded
in the UI layer. This prevents inconsistencies when the model is updated.
