# AutoReturn AppImage - Build Issues Log

---

## Issue #1 — `shiboken6` Not Found
**Error:**
```
PySide6/__init__.py: Unable to import Shiboken
ModuleNotFoundError: No module named 'shiboken6'
```
**Cause:** `pip install --no-deps` was used, which skipped transitive dependencies. `shiboken6` is a required dependency of PySide6 but wasn't installed.

**Fix:** Removed `--no-deps` flag from pip install in `build_appimage.sh` so all transitive dependencies are installed properly.

---

## Issue #2 — spaCy `en_core_web_md` Model Not Found
**Error:**
```
OSError: [E050] Can't find model 'en_core_web_md'. It doesn't seem to be a Python package or a valid path to a data directory.
```
**Cause:** The spaCy model was not being correctly located and bundled into the AppDir. The old approach used `spacy.util.get_data_path()` which points to a data directory, not the installed Python package.

**Fix:** Changed bundling to use `import en_core_web_md; print(os.path.dirname(en_core_web_md.__file__))` which correctly finds the installed model package and copies it into the AppDir site-packages.

---

## Issue #3 — `ToneEngine` Crashes When spaCy Unavailable
**Error:**
```
OSError: [E050] Can't find model 'en_core_web_md'
(crash in ToneEngine.__init__ → ToneDetector.__init__ → _load_shared_nlp)
```
**Cause:** `_load_shared_nlp()` was raising an exception instead of returning `None` when the model failed to load. All downstream methods (`analyze_message`, `_score_token`, `_compute_centroids`) assumed `self.nlp` was never `None`.

**Fix:**
- `_load_shared_nlp()` now returns `None` on failure instead of raising
- `_compute_centroids()` returns zero vectors if `nlp is None`
- `_score_token()` skips embedding fallback if `nlp is None`
- `analyze_message()` routes to new `_lexicon_only_analyze()` fallback when `nlp is None`
- Added `_lexicon_only_analyze()` — a full tone analysis using only the lexicon + regex patterns, no spaCy embeddings needed

---

## Issue #4 — Wrong Ollama Model Hardcoded
**Error:**
```
Orchestrator initialized with model gpt-oss:120b-cloud
(model doesn't exist locally, all AI features fail)
```
**Cause:** `src/frontend/ui/autoreturn_app.py` had `Orchestrator(ollama_model="gpt-oss:120b-cloud")` hardcoded — an old/incorrect model name.

**Fix:** Changed to `Orchestrator(ollama_model="qwen2.5:1.5b")` which matches `config/settings.conf` and `src/backend/core/orchestrator.py` defaults.

---

## Issue #5 — Hardcoded Mac File Path in Settings
**File:** `data/automation_settings.json`
**Problem:**
```json
"file_access_paths": ["/Users/hasnainsaleem/Desktop/fyp/code/AutoReturn"]
```
This was Hasnain's Mac path. On any other machine this folder doesn't exist, causing the Attachment Resolver to silently fail.

**Fix:** Cleared to `[]`. Users can add their own paths via the Settings UI.

---

## Issue #6 — AppRun Hardcoded Python Version
**Problem:** AppRun script had `python3.12` hardcoded in all paths, meaning it would break on machines with a different Python version.

**Fix:** AppRun now dynamically detects the Python version at runtime using:
```bash
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
```
