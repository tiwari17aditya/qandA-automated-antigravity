---
name: update-docs
description: Synchronize project documentation, README.md, environment examples, and agent skill guides with the latest codebase state.
---

# 📚 Documentation & Reference Synchronization (`/update-docs`)

Execute this command whenever environment variables, features, database columns, or workflows are added or modified to keep project documentation 100% accurate.

## 🛠️ Step-by-Step Sync Checklist

### Step 1: Environment Variables Sync (`.env.example`)
1. Review `config.py` for any newly introduced settings or fallbacks.
2. Update `.env.example` with clear comments, default values, and setup instructions.
3. Verify that sensitive keys have placeholder values (`your_...`) and no actual secrets are committed.

### Step 2: Main Documentation (`README.md`)
1. Ensure `README.md` documents:
   - System Overview & Architectural Diagram
   - Feature List (Dual AI failover, topic drilling, auto-grading, calendar streaks, weekly reports)
   - Configuration & Environment Reference
   - GitHub Actions Setup (Secrets, zero-cache schedules)
   - Available Slash Commands (`/packup`, `/modularize`, `/test-pipeline`, etc.)

### Step 3: Agent Skills & Instructions (`.agents/skills/`)
1. Check `.agents/skills/` directories to ensure all procedures match active code implementations.
2. Update references to file paths and schema structures.

### Step 4: Verification
1. Review git diff for documentation changes:
   ```powershell
   git diff README.md .env.example .agents/
   ```
