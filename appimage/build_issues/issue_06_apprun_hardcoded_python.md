# Issue #6 — AppRun Script Had Python Version Hardcoded

## Status
✅ Fixed

## When It Happened
Discovered during build script review before testing on other machines.

## Problem
The generated `AppRun` launcher script had `python3.12` hardcoded in
all environment variable paths:

```bash
export PYTHONPATH="$APPDIR/usr/lib/python3.12/site-packages:..."
export LD_LIBRARY_PATH="$APPDIR/usr/lib/python3.12/site-packages/PySide6:..."
export QT_QPA_PLATFORM_PLUGIN_PATH="$APPDIR/usr/lib/python3.12/site-packages/PySide6/Qt/plugins/platforms"
export QT_PLUGIN_PATH="$APPDIR/usr/lib/python3.12/site-packages/PySide6/Qt/plugins"
```

## Root Cause
The AppRun template used a hardcoded `python3.12` string. This works
on the build machine (Garuda Linux with Python 3.12.3) but would break
on any machine running Python 3.10, 3.11, or a future 3.13.

## Fix Applied
**File:** `appimage/build_appimage.sh` — AppRun generation section

Added dynamic Python version detection at runtime:

```bash
# Detect Python version at runtime
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "3.12")

# Use variable instead of hardcoded version
export PYTHONPATH="$APPDIR/usr/lib/python${PY_VER}/site-packages:..."
export LD_LIBRARY_PATH="$APPDIR/usr/lib/python${PY_VER}/site-packages/PySide6:..."
```

## Lesson
AppImage launchers run on the target machine's Python, not the build
machine's Python. Always detect the runtime Python version dynamically
rather than assuming it matches the build environment.
