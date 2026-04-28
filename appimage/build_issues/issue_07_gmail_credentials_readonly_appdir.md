# Issue #7 — Gmail Credentials Written to Read-Only AppDir

## Status
✅ Fixed

## When It Happened
After AppImage launched successfully, Gmail OAuth flow failed to save
`client_secret.json` and `token.json`.

## Root Cause
Both `auth_dialog._project_root()` and `autoreturn_app._get_gmail_data_dir()`
resolved paths relative to the Python source file location:

```python
# auth_dialog.py
return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# resolves to: /tmp/.mount_AutoRe.../usr/src/  ← READ-ONLY inside AppImage

# autoreturn_app.py
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
# resolves to: /tmp/.mount_AutoRe.../usr/src/  ← READ-ONLY inside AppImage
```

AppImage mounts as a read-only squashfs filesystem. Any attempt to write
`client_secret.json`, `token.json`, or user data there silently fails or crashes.

## Fix Applied

### `src/frontend/dialogs/auth_dialog.py` — `_project_root()`
```python
def _project_root(self) -> str:
    if os.environ.get('APPIMAGE'):
        return os.path.join(os.path.expanduser('~'), '.autoreturn')
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
```

### `src/frontend/ui/autoreturn_app.py` — `_get_gmail_data_dir()`
```python
def _get_gmail_data_dir(self):
    if os.environ.get('APPIMAGE'):
        base_root = os.path.join(os.path.expanduser('~'), '.autoreturn')
    else:
        base_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    ...
```

### `src/frontend/ui/autoreturn_app.py` — `_get_ics_output_dir()`
Same pattern applied — ICS exports also go to `~/.autoreturn/data/ics_exports/`.

## Result
When running as AppImage, all user data (credentials, tokens, exports) is
stored in `~/.autoreturn/` which is always writable. When running from source,
behavior is unchanged.
