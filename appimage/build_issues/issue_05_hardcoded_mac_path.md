# Issue #5 — Hardcoded Mac File Path in `automation_settings.json`

## Status
✅ Fixed

## When It Happened
Discovered during pre-build project analysis.

## Problem
`data/automation_settings.json` contained a hardcoded absolute path
from a developer's Mac machine:

```json
"file_access_paths": [
    "/Users/hasnainsaleem/Desktop/fyp/code/AutoReturn"
]
```

## Root Cause
This path was left in from development on Hasnain's MacBook.
The `file_access_paths` setting is used by the **Attachment Resolver** —
when a sender asks for a file (e.g. "send me the Q3 report"), the app
searches these directories to find and auto-attach it.

On any other machine (Linux, Windows, another Mac), this path does not
exist. The Attachment Resolver would search a non-existent directory
and silently return no results for every attachment request.

## Fix Applied
**File:** `data/automation_settings.json`

```json
// Before
"file_access_paths": [
    "/Users/hasnainsaleem/Desktop/fyp/code/AutoReturn"
]

// After
"file_access_paths": []
```

Cleared to an empty array. Users can add their own folder paths
through the Settings UI in the app, which writes back to this file.

## Lesson
Never commit machine-specific absolute paths to version control.
Default config files should always use empty values or relative paths.
