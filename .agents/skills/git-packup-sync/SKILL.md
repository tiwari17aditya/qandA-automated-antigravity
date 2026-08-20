---
name: git-packup-sync
description: Standardized procedure for verifying changes, cleaning bytecode, committing with conventional messages, and pushing to remote git repository.
---

# Git Packup & Remote Synchronization Skill

## Objective
Enforces zero unpushed or pending changes at the conclusion of tasks, guaranteeing the remote repository (`origin/main`) is in full sync with the local workspace.

## Packup Workflow

### 1. Bytecode & Cache Removal
Remove all `__pycache__` and `.pyc` files:
```powershell
Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
Get-ChildItem -Path . -Include *.pyc -Recurse -File | Remove-Item -Force
```

### 2. Documentation Audit
Verify that `.env.example`, `README.md`, or relevant skill guides reflect any newly added features, variables, or command updates.

### 3. Stage & Commit
```powershell
git status
git add .
git commit -m "<type>: <descriptive message>"
```

### 4. Push to Origin
```powershell
git push origin main
git status
```
