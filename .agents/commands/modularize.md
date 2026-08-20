---
name: modularize
description: Review codebase modularity, decouple responsibilities into dedicated modules, enforce zero-cache rules, and verify import integrity.
---

# 🧩 Code Modularization & Architecture Refactor (`/modularize`)

Execute this command after adding any new feature, workflow, or algorithm to ensure the codebase remains clean, modular, decoupled, and adheres to the project's single-responsibility principles.

## 🎯 Modular Architecture Principles

The project follows a strict decoupled architecture:

| Module Layer | Primary File | Core Responsibility |
| :--- | :--- | :--- |
| **Config & Env** | `config.py` | Environment variable parsing, dynamic prompt generation, topic loading, configuration validation. |
| **Database Access** | `db.py` | PostgreSQL connection management, schema initialization, auto-migrations, expired test handling. |
| **Resilience & AI** | `alert_utils.py` | Multi-provider AI generation (Gemini + Groq failover), JSON output sanitization, email error alerting. |
| **Quiz Engine** | `daily_quiz_sender.py` | AI question generation, question persistence in DB, responsive HTML email formatting and delivery. |
| **Evaluation Engine** | `email_evaluator.py` | IMAP inbox polling, candidate reply parsing, answer scoring, topic analytics updating, scorecard email dispatch. |
| **Analytics Engine** | `weekly_report_sender.py` | 7-day metric aggregation, weakness analysis, AI study recommendation generation, weekly HTML report dispatch. |

## 🛠️ Step-by-Step Modularization Workflow

### Step 1: Modularity Audit
1. Inspect modified files for:
   - **Monolithic functions**: Functions > 50 lines that mix I/O, DB calls, AI calls, or formatting.
   - **Duplicated logic**: Shared helpers (email sending, DB queries, retry logic) placed directly inside task scripts instead of shared modules.
   - **Hardcoded constants**: Move any magic numbers, strings, or prompts to `config.py` or `.env.example`.
   - **Missing Error Boundaries**: Ensure any critical top-level function is wrapped in `try/except` with `send_error_alert`.

### Step 2: Decoupling & Refactoring
1. Extract helper functions into their respective domain modules:
   - Move database queries to `db.py`.
   - Move AI fallback and network resilience logic to `alert_utils.py`.
   - Move dynamic prompt templates and configuration logic to `config.py`.
2. Ensure pure function design where possible (functions take explicit parameters and return processed results).

### Step 3: Zero-Cache & Token Optimization Compliance
1. Verify no disk caching or bytecache creation:
   - Do NOT introduce file-based caches or local temp states.
   - Ensure AI prompts enforce concise explanations (`<=15 words`).
   - Ensure AI callers request `response_mime_type: application/json` or Groq `json_object` format.

### Step 4: Verification & Smoke Test
1. Run syntax and import check:
   ```powershell
   python -B -c "import config, db, alert_utils, daily_quiz_sender, email_evaluator, weekly_report_sender; print('All modules decoupled and imported cleanly!')"
   ```
