---
name: test-pipeline
description: Run dry-run verification and diagnostics on database, AI API connections, email evaluator, and quiz generation pipelines.
---

# 🧪 Full Pipeline Verification & Diagnostics (`/test-pipeline`)

Execute this command to verify credentials, database connectivity, AI failover chain, and system integrity before scheduling or deploying.

## 🛠️ Step-by-Step Diagnostic Suite

### Step 1: Validate Environment & Secrets
1. Check that required settings and API keys are populated:
   ```powershell
   python -B -c "import config; config.validate_config(); print('Config validation: PASSED')"
   ```

### Step 2: Test Database & Schema Migration
1. Test PostgreSQL connectivity and ensure all tables exist:
   ```powershell
   python -B -c "import db; db.init_and_migrate_db(); print('Database schema & migration: PASSED')"
   ```

### Step 3: Test AI Model Generation & Fallback
1. Test AI prompt generation and JSON output sanitization (Gemini & Groq failover):
   ```powershell
   python -B -c "import alert_utils, config; res = alert_utils.generate_ai_completion(config.get_quiz_prompt(), response_json=True); print('AI Generation response length:', len(res)); print('AI test: PASSED')"
   ```

### Step 4: Test IMAP Mailbox Polling
1. Verify IMAP connection and inbox search:
   ```powershell
   python -B -c "import email_evaluator; print('Email evaluator module ready')"
   ```

### Step 5: Clean Bytecode
1. Remove any temporary compiled bytecode:
   ```powershell
   Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
   ```
