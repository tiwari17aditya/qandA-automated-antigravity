---
name: token-optimized-mppsc
description: Enforces zero-cache GitHub Actions execution, Gemini token-optimized quiz generation, and automatic git synchronization workflows for MPPSC preparation.
---

# Token-Optimized MPPSC Automation Workflow

## Objective
Maintains a 100% serverless, zero-cache, token-efficient, and auto-synchronized MPPSC daily drill pipeline.

## Protocols

### 1. Storage Preservation Protocol
- **GitHub Storage Protection**:
  - Workflows disable action caching via `cache: ''`.
  - Dependencies installed strictly with `--no-cache-dir`.
  - Python bytecode disabled with `PYTHONDONTWRITEBYTECODE=1` and `python -B`.
  - Git shallow checkouts with `fetch-depth: 1`.

### 2. Gemini API Token Optimization
- Dynamic prompt generator in `config.py` enforces `<= 15 words` explanation per MCQ.
- Structured JSON schema response (`application/json`) minimizes overhead tokens.
- Rate-limit resilient caller (`alert_utils.py`) handles exponential backoff and jitter.

### 3. Automatic Git Synchronization (Packup Rule)
- Upon completion of any task, change, or user session wrap-up:
  1. Verify workspace status with `git status`.
  2. Stage all changed/created files with `git add .`.
  3. Create a clear, concise commit message.
  4. Push directly to remote repository (`origin/main`).
