---
name: packup
description: Pack up workspace, clean temporary artifacts, synchronize documentation, stage all changes, commit, and push to origin/main.
---

# 📦 Automated Git Packup & Sync Workflow (`/packup`)

Execute this command whenever a task, feature addition, bug fix, or user session is completed to ensure zero uncommitted or unpushed changes.

## 🛠️ Step-by-Step Procedure

### Step 1: Pre-packup Cleanup & Validation
1. Remove all Python bytecache artifacts:
   ```powershell
   Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
   Get-ChildItem -Path . -Include *.pyc -Recurse -File | Remove-Item -Force
   ```
2. Verify Python syntax across all core files:
   ```powershell
   python -B -m py_compile config.py db.py alert_utils.py daily_quiz_sender.py email_evaluator.py weekly_report_sender.py
   ```

### Step 2: Documentation & Env Synchronization
1. Check if any new environment variables or features were added:
   - Ensure `.env.example` has all configuration variables documented with clean placeholder values.
   - Ensure `README.md` reflects current architecture, commands, and workflow schedules.

### Step 3: Git Status & Stage
1. Check repository status:
   ```powershell
   git status
   ```
2. Stage all modified and untracked files (excluding secret `.env` which is in `.gitignore`):
   ```powershell
   git add .
   ```

### Step 4: Descriptive Commit & Remote Push
1. Create a clear conventional commit message (e.g., `feat: ...`, `fix: ...`, `refactor: ...`, `docs: ...`):
   ```powershell
   git commit -m "<type>: <concise description of changes>"
   ```
2. Push directly to remote `origin/main`:
   ```powershell
   git push origin main
   ```
3. Verify remote sync status with `git status`.
