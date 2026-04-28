# Issue #2 — spaCy `en_core_web_md` Model Not Found Inside AppImage

## Status
✅ Fixed

## When It Happened
After fixing Issue #1, app launched but failed during Orchestrator initialization.

## Full Error
```
PriorityEngine: Loading Semantic Analysis model (en_core_web_md)...
Semantic Analysis model failed to load: [E050] Can't find model 'en_core_web_md'.
It doesn't seem to be a Python package or a valid path to a data directory.

OSError: [E050] Can't find model 'en_core_web_md'.
It doesn't seem to be a Python package or a valid path to a data directory.
```

## Root Cause
The original build script tried to find the spaCy model using:
```bash
SPACY_DATA=$(python3 -c "import spacy; print(spacy.util.get_data_path())")
```
This returns spaCy's internal data directory (e.g. `/home/user/.local/lib/python3.12/site-packages/spacy/data`)
which is NOT where the `en_core_web_md` model package is installed.

The model is installed as a regular Python package at:
`/home/user/.local/lib/python3.12/site-packages/en_core_web_md/`

So the copy command was copying the wrong directory and the model was never
actually bundled into the AppDir.

## Fix Applied
**File:** `appimage/build_appimage.sh`

Changed model detection to use Python's import system to find the actual package path:

```bash
# Before (broken - wrong path)
SPACY_DATA=$(python3 -c "import spacy; print(spacy.util.get_data_path())")
cp -r "$SPACY_DATA"/* "$SITE_PACKAGES/spacy/data/"

# After (fixed - correct path)
SPACY_MODEL_PATH=$(python3 -c "
import os
try:
    import en_core_web_md
    print(os.path.dirname(en_core_web_md.__file__))
except:
    pass
")
cp -r "$SPACY_MODEL_PATH" "$SITE_PACKAGES/en_core_web_md"
```

## Lesson
spaCy models are installed as standalone Python packages, not inside spaCy's
own data directory. Always use `import <model>; print(model.__file__)` to
locate them reliably.
