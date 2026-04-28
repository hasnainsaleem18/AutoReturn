# AppImage Build Issues

This directory documents every issue encountered during the AppImage build process.
Each issue has its own file with full details — error, cause, and fix applied.

---

## Index

| # | File | Issue Summary | Status |
|---|------|---------------|--------|
| 1 | `issue_01_shiboken6_missing.md` | `shiboken6` module not found on launch | ✅ Fixed |
| 2 | `issue_02_spacy_model_not_bundled.md` | `en_core_web_md` not found inside AppImage | ✅ Fixed |
| 3 | `issue_03_tone_engine_crash.md` | `ToneEngine` crashes when spaCy unavailable | ✅ Fixed |
| 4 | `issue_04_wrong_ollama_model.md` | Wrong Ollama model hardcoded in app | ✅ Fixed |
| 5 | `issue_05_hardcoded_mac_path.md` | Hardcoded Mac file path in settings | ✅ Fixed |
| 6 | `issue_06_apprun_hardcoded_python.md` | AppRun had Python version hardcoded | ✅ Fixed |
| 7 | `issue_07_gmail_credentials_readonly_appdir.md` | Gmail credentials written to read-only AppDir | ✅ Fixed |
| 8 | `issue_08_summaries_not_generating.md` | Summaries not generating — Ollama Cloud signin required | ✅ Fixed |
