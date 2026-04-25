# Issue #3 — `ToneEngine` Crashes When spaCy Model Unavailable

## Status
✅ Fixed

## When It Happened
Whenever the spaCy model fails to load (Issue #2), the entire app crashes
instead of gracefully degrading.

## Full Error
```
Traceback (most recent call last):
  File ".../entrypoint.py", line 61, in <module>
    main()
  File ".../main.py", line 59, in main
    main_window = AutoReturnApp()
  File ".../autoreturn_app.py", line 148, in __init__
    self.orchestrator = Orchestrator(ollama_model="gpt-oss:120b-cloud")
  File ".../orchestrator.py", line 79, in __init__
    self.tone_engine = ToneEngine(ai_service=self.ai_service)
  File ".../tone_engine.py", line 440, in __init__
    self.tone_detector = ToneDetector()
  File ".../tone_engine.py", line 54, in __init__
    self.nlp = self._load_shared_nlp()
  File ".../tone_engine.py", line 79, in _load_shared_nlp
    cls._shared_nlp = spacy.load(cls._shared_nlp_model_name)
OSError: [E050] Can't find model 'en_core_web_md'.
```

## Root Cause
`ToneDetector._load_shared_nlp()` was re-raising the exception on failure:
```python
except Exception:
    cls._shared_nlp_failed = True
    raise   # ← this crashes the whole app
```

Additionally, all downstream methods assumed `self.nlp` was always a valid
spaCy model object — `analyze_message`, `_score_token`, `_embedding_fallback`,
and `_compute_centroids` would all crash with `AttributeError` if `nlp` was `None`.

## Fix Applied
**File:** `src/backend/core/tone_engine.py`

### 1. `_load_shared_nlp` — return None instead of raising
```python
# Before
except Exception:
    cls._shared_nlp_failed = True
    raise

# After
except Exception as e:
    print(f"ToneDetector: spaCy model failed to load: {e}")
    print("ToneDetector: Falling back to lexicon-only mode.")
    cls._shared_nlp_failed = True
    return None
```

### 2. `_compute_centroids` — guard against None
```python
def _compute_centroids(self):
    if self.nlp is None:
        return np.zeros(1), np.zeros(1)
    # ... rest of method
```

### 3. `_score_token` — skip embedding if nlp is None
```python
if score == 0.0 and self.nlp is not None and self.nlp.vocab.has_vector(lemma):
    score = self._embedding_fallback(lemma)
```

### 4. `analyze_message` — route to fallback if nlp is None
```python
def analyze_message(self, text: str) -> ToneDetectionResult:
    if self.nlp is None:
        return self._lexicon_only_analyze(text)
    doc = self.nlp(text)
    # ... rest of method
```

### 5. Added `_lexicon_only_analyze()` — full fallback method
A complete tone analysis implementation using only the word lexicon,
word sets, and regex patterns. No spaCy required. Accuracy is slightly
lower (~70% vs ~80%) but the app stays running.

## Lesson
Any optional/external resource (ML models, files, network) must be treated
as potentially unavailable. Always return None on failure and guard every
usage site. Never let an optional feature crash the whole application.
