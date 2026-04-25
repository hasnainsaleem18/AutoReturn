# Issue #1 — `shiboken6` Module Not Found

## Status
✅ Fixed

## When It Happened
First launch of the AppImage after initial build.

## Full Error
```
PySide6/__init__.py: Unable to import Shiboken from /tmp/.mount_AutoRes.../usr/src/src, ...
Traceback (most recent call last):
  File ".../entrypoint.py", line 60, in <module>
    from main import main
  File ".../main.py", line 13, in <module>
    from PySide6.QtWidgets import QApplication
  File ".../PySide6/__init__.py", line 143, in <module>
    _setupQtDirectories()
  File ".../PySide6/__init__.py", line 66, in _setupQtDirectories
    from shiboken6 import Shiboken
ModuleNotFoundError: No module named 'shiboken6'
```

## Root Cause
The build script used `pip install --no-deps` which intentionally skips all
transitive dependencies. `shiboken6` is a required sub-package of PySide6
(it provides the C++ binding layer) but it is a separate PyPI package.
With `--no-deps` it was never installed into the AppDir.

## Fix Applied
**File:** `appimage/build_appimage.sh`

Removed `--no-deps` from the pip install command:

```bash
# Before (broken)
pip3 install \
    --target="$SITE_PACKAGES" \
    --no-deps \
    -r "$SCRIPT_DIR/requirements-appimage.txt"

# After (fixed)
pip3 install \
    --target="$SITE_PACKAGES" \
    -r "$SCRIPT_DIR/requirements-appimage.txt"
```

## Lesson
Never use `--no-deps` when bundling a full application.
It is only safe for single-package installs where you manually manage all deps.
