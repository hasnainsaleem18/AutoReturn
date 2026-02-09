# Cleanup Old Directory Structure

## ⚠️ IMPORTANT: Backup First!

Before running the cleanup, make sure you have:
1. Tested the new structure (`python main.py`)
2. Committed your changes to git
3. Created a backup of the project

## Old Directories to Remove

The following old directories can be safely removed as all files have been migrated to `src/`:

```
backend/
├── core/
│   └── AutoReturn_Gmail_Automation.py (→ src/backend/core/)
└── services/
    ├── ai_service.py (→ src/backend/services/)
    ├── gmail_backend.py (→ src/backend/services/)
    └── slack_backend.py (→ src/backend/services/)

frontend/
├── assets/ (→ src/frontend/assets/)
├── autoreturn_app.py (→ src/frontend/ui/)
├── dialogs/ (→ src/frontend/dialogs/)
├── main.py (→ root main.py)
└── styles.py (→ src/frontend/ui/)
```

## Cleanup Commands

### Option 1: Manual Cleanup (Recommended)
Review the files first, then delete:

```bash
# Navigate to project root
cd /Users/hasnainsaleem/Desktop/fyp/code/AutoReturn

# Check what will be deleted
ls -la backend/
ls -la frontend/

# Remove old directories
rm -rf backend/
rm -rf frontend/
```

### Option 2: Automated Cleanup Script
Run this script to automatically remove old directories:

```bash
#!/bin/bash
# cleanup_old_structure.sh

cd /Users/hasnainsaleem/Desktop/fyp/code/AutoReturn

echo "⚠️  This will permanently delete the old backend/ and frontend/ directories"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

echo "Removing old backend/ directory..."
rm -rf backend/

echo "Removing old frontend/ directory..."
rm -rf frontend/

echo "✅ Cleanup complete!"
echo ""
echo "Remaining structure:"
ls -la

echo ""
echo "Verify the app still works:"
echo "  python main.py"
```

To use the script:
```bash
chmod +x cleanup_old_structure.sh
./cleanup_old_structure.sh
```

## Verification After Cleanup

After removing the old directories, verify that:

1. **The app still runs**:
   ```bash
   python main.py
   ```

2. **Tests still work**:
   ```bash
   python tests/test_ollama.py
   ```

3. **Scripts still work**:
   ```bash
   python scripts/quick_test.py
   ```

4. **Expected structure**:
   ```bash
   tree -L 2 -I '__pycache__|*.pyc'
   ```

## Final Structure

After cleanup, your directory should look like:

```
AutoReturn/
├── main.py
├── README.md
├── SETUP.md
├── MIGRATION_CHECKLIST.md
├── COMPLETED.md
├── CLEANUP.md
├── .gitignore
├── requirement.txt
├── config/
├── data/
├── logs/
├── src/              # ← Only this contains code now
│   ├── backend/
│   └── frontend/
├── scripts/
└── tests/
```

## Rollback (If Needed)

If something goes wrong after cleanup:

1. **If you have git**:
   ```bash
   git checkout backend/ frontend/
   ```

2. **If you have a backup**:
   ```bash
   cp -r /path/to/backup/backend .
   cp -r /path/to/backup/frontend .
   ```

## Notes

- The old `backend/` and `frontend/` directories are **exact duplicates** of what's now in `src/`
- All imports have been updated to use the new `src/` structure
- No functionality depends on the old directories
- Removing them will clean up the project and prevent confusion

## Safety Checklist

Before running cleanup:
- [ ] Tested `python main.py` successfully
- [ ] Verified all imports work
- [ ] Committed changes to git (or created backup)
- [ ] Reviewed the files to be deleted
- [ ] Understand how to rollback if needed

---

**When ready**: Run the cleanup commands above to finalize the restructuring.
