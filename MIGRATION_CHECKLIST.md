# AutoReturn Project Restructuring - Migration Checklist

## ✅ Completed Tasks

### 1. Directory Structure Creation
- [x] Created `src/` directory as main source root
- [x] Created `src/backend/core/` for core automation logic
- [x] Created `src/backend/services/` for service integrations
- [x] Created `src/backend/utils/` for utility functions
- [x] Created `src/frontend/ui/` for main UI components
- [x] Created `src/frontend/dialogs/` for dialog windows
- [x] Created `src/frontend/widgets/` for custom widgets
- [x] Created `src/frontend/assets/` for images and icons
- [x] Created `config/` for configuration files
- [x] Created `data/` for application data
- [x] Created `data/gmail_data/` for Gmail credentials
- [x] Created `logs/` for application logs
- [x] Kept `scripts/` for utility scripts
- [x] Kept `tests/` for test files

### 2. File Migration
- [x] Moved backend files:
  - `AutoReturn_Gmail_Automation.py` → `src/backend/core/`
  - `ai_service.py` → `src/backend/services/`
  - `gmail_backend.py` → `src/backend/services/`
  - `slack_backend.py` → `src/backend/services/`
  
- [x] Moved frontend files:
  - `autoreturn_app.py` → `src/frontend/ui/`
  - `styles.py` → `src/frontend/ui/`
  - `auth_dialog.py` → `src/frontend/dialogs/`
  - `notification_dialog.py` → `src/frontend/dialogs/`
  - `send_gmail_reply_dialog.py` → `src/frontend/dialogs/`
  - `send_slack_message_dialog.py` → `src/frontend/dialogs/`
  - `settings_dialog.py` → `src/frontend/dialogs/`
  
- [x] Moved assets:
  - All PNG files → `src/frontend/assets/`
  
- [x] Moved main entry point:
  - `main.py` → project root

### 3. Package Structure
- [x] Created `__init__.py` in `src/`
- [x] Created `__init__.py` in `src/backend/`
- [x] Created `__init__.py` in `src/backend/core/`
- [x] Created `__init__.py` in `src/backend/services/`
- [x] Created `__init__.py` in `src/backend/utils/`
- [x] Created `__init__.py` in `src/frontend/`
- [x] Created `__init__.py` in `src/frontend/ui/`
- [x] Created `__init__.py` in `src/frontend/dialogs/`
- [x] Created `__init__.py` in `src/frontend/widgets/`

### 4. Import Statement Updates
- [x] Updated `main.py`:
  - Added `sys.path` setup
  - Changed to `from src.frontend.ui.autoreturn_app import AutoReturnApp`
  
- [x] Updated `src/frontend/ui/autoreturn_app.py`:
  - Changed to `from src.frontend.ui.styles import *`
  - Changed to `from src.frontend.dialogs.*`
  - Changed to `from src.backend.services.*`
  
- [x] Updated `src/backend/services/gmail_backend.py`:
  - Changed to `from src.backend.services.ai_service import analyze_email_with_ollama`
  
- [x] Updated `src/frontend/dialogs/settings_dialog.py`:
  - Changed to `from src.backend.services.gmail_backend import GmailIntegrationService`
  - Changed to `from src.backend.services.slack_backend import SlackIntegrationService`
  
- [x] Updated `scripts/debug_slack_ai.py`:
  - Added `sys.path` setup
  - Changed to `from src.backend.services.*`
  
- [x] Updated `scripts/quick_test.py`:
  - Added `sys.path` setup
  - Changed to `from src.backend.services.*`
  
- [x] Updated `tests/test_ollama.py`:
  - Added `sys.path` setup
  - Changed to `from src.backend.services.*`

### 5. Path Configuration Updates
- [x] Updated `_get_gmail_data_dir()` in `autoreturn_app.py`:
  - Changed from relative path to use project root
  - Now stores data in `data/gmail_data/`
  
- [x] Updated asset loading:
  - All asset paths use relative paths from their modules
  - Assets correctly located in `src/frontend/assets/`

### 6. Configuration Files
- [x] Created `config/settings.conf` for application settings
- [x] Updated `README.md` with new structure and instructions

### 7. Verification
- [x] All Python files compile without syntax errors
- [x] Import paths are consistent across all modules
- [x] Directory structure matches the planned layout
- [x] No hardcoded absolute paths remain

## 📋 Post-Migration Steps

### To Complete the Migration:

1. **Install Dependencies**
   ```bash
   pip install -r requirement.txt
   ```

2. **Set Up Gmail OAuth**
   - Place your `client_secret.json` in `data/gmail_data/`
   - The app will create `token.json` automatically on first run

3. **Configure Application**
   - Edit `config/settings.conf` with your preferences
   - Set Slack tokens, API keys, etc.

4. **Test the Application**
   ```bash
   python main.py
   ```

5. **Run Tests**
   ```bash
   python tests/test_ollama.py
   ```

6. **Test Scripts**
   ```bash
   python scripts/quick_test.py
   python scripts/debug_slack_ai.py
   ```

## 🔍 Key Changes Summary

### Import Pattern Change
**Old:**
```python
from gmail_backend import GmailIntegrationService
from services.ai_service import analyze_email_with_ollama
```

**New:**
```python
from src.backend.services.gmail_backend import GmailIntegrationService
from src.backend.services.ai_service import analyze_email_with_ollama
```

### Data Directory Change
**Old:** `frontend/gmail_data/`  
**New:** `data/gmail_data/`

### Asset Directory
**Old:** `frontend/assets/`  
**New:** `src/frontend/assets/`

### Entry Point
**Location:** `main.py` at project root  
**Purpose:** Single, clear entry point for the application

## 📁 Final Structure

```
AutoReturn/
├── main.py                          # Application entry point
├── README.md                        # Documentation
├── requirement.txt                  # Python dependencies
├── config/                          # Configuration files
│   └── settings.conf               # App settings
├── data/                            # Application data
│   └── gmail_data/                 # Gmail credentials and tokens
├── logs/                            # Application logs
├── src/                             # Source code
│   ├── backend/                    # Backend services
│   │   ├── core/                   # Core automation logic
│   │   ├── services/               # Integration services
│   │   └── utils/                  # Utility functions
│   └── frontend/                   # Frontend UI
│       ├── ui/                     # Main UI components
│       ├── dialogs/                # Dialog windows
│       ├── widgets/                # Custom widgets
│       └── assets/                 # Images and icons
├── scripts/                         # Utility scripts
└── tests/                           # Test files
```

## ✨ Benefits of New Structure

1. **Clear Separation of Concerns**: Backend and frontend are clearly separated
2. **Standard Python Package**: Follows Python packaging best practices
3. **Easy Import Management**: All imports start with `src.`
4. **Scalability**: Easy to add new modules and components
5. **Testing**: Clear structure for test organization
6. **Configuration**: Centralized configuration management
7. **Data Management**: Clear location for application data

## 🚀 Next Steps

1. Test all functionality to ensure everything works correctly
2. Add logging configuration to use the `logs/` directory
3. Consider adding a `.gitignore` file to exclude:
   - `__pycache__/`
   - `*.pyc`
   - `data/gmail_data/*.json`
   - `logs/*.log`
   - `config/settings.conf` (if it contains secrets)
4. Add more comprehensive tests
5. Consider adding a `setup.py` or `pyproject.toml` for proper package installation

---

**Migration Completed:** ✅  
**Status:** Ready for testing and deployment
