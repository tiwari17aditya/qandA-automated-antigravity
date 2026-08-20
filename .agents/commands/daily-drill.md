---
name: daily-drill
description: Trigger generation and dispatch of today's MPPSC daily quiz drill with automatic topic filtering and DB logging.
---

# 🎯 Daily Quiz Dispatcher (`/daily-drill`)

Execute this command to immediately generate and dispatch today's MPPSC prelims drill email.

## 🛠️ Step-by-Step Procedure

### Step 1: Pre-run Validation
1. Verify configuration:
   ```powershell
   python -B -c "import config; config.validate_config()"
   ```

### Step 2: Execute Daily Quiz Sender
1. Run the quiz generator script:
   ```powershell
   python -B daily_quiz_sender.py
   ```
2. Verify output logs:
   - Database tables initialized and auto-migrated.
   - Questions generated via Gemini (or Groq failover) adhering to <=15 words explanation rule.
   - Questions stored in `daily_tests` table with `status = 'PENDING'`.
   - HTML drill email delivered to receiver address.

### Step 3: Cleanup Bytecode
```powershell
Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
```
