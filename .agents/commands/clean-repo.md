---
name: clean-repo
description: Clean temporary test PDFs, remove Python bytecode (__pycache__), clear .pytest_cache, prune local log artifacts, organize repository structure, and verify .gitignore hygiene.
---

# 🧹 Repository Hygiene & Cleanup (`/clean-repo`)

Execute this command to remove temporary build artifacts, compiled Python bytecode, pytest caches, and loose scratch PDF files, maintaining a clean and modular repository hierarchy.

## 🛠️ Step-by-Step Cleanup Procedure

### Step 1: Remove Python Bytecode (`__pycache__`, `.pyc`)
Run PowerShell command to remove all compiled `__pycache__` directories recursively:
```powershell
Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
```

### Step 2: Clear Pytest Caches
Remove temporary `.pytest_cache` directories:
```powershell
if (Test-Path ".pytest_cache") { Remove-Item -Path ".pytest_cache" -Recurse -Force }
```

### Step 3: Remove Loose Scratch PDFs & Logs
Clean temporary PDF test outputs in root or `logs/` directory:
```powershell
Get-ChildItem -Path . -Filter "scratch_*.pdf" | Remove-Item -Force
Get-ChildItem -Path "logs" -Filter "*.pdf" -ErrorAction SilentlyContinue | Remove-Item -Force
```

### Step 4: Verify `.gitignore` Enforcement
Ensure temporary folders (`.venv/`, `logs/`, `.pytest_cache/`, `*.pdf`) are covered in `.gitignore`.

### Step 5: Verify Working Tree Hygiene
Confirm working tree is clean:
```powershell
git status
```
