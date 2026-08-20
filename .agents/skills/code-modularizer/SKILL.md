---
name: code-modularizer
description: Best practices and instructions for keeping python automation scripts decoupled, modular, zero-cache compliant, and maintainable after adding new features.
---

# Code Modularizer & Architecture Standards

## Objective
Ensures that all enhancements, bug fixes, or new integrations maintain clean boundaries, strict single-responsibility separation, zero disk caching, and centralized resilience.

## Architectural Boundaries

1. **Config Layer (`config.py`)**:
   - Reads environment variables with safe defaults and `.env.example` fallbacks.
   - Dynamic prompt generators and topic selectors.
   - Centralized validation (`validate_config`).
   - No DB queries or direct network calls in this module.

2. **Data Layer (`db.py`)**:
   - Encapsulates all PostgreSQL connections (`psycopg2`).
   - Handles schema creation and incremental migrations (`init_and_migrate_db`).
   - Contains database lifecycle helpers (`mark_expired_tests_absent`).
   - Clean connection and cursor teardown in `finally` or explicit closes.

3. **AI & Network Resilience Layer (`alert_utils.py`)**:
   - Houses `generate_ai_completion` with multi-provider failover (Gemini primary/fallback, Groq open-source pool).
   - Sanitizes AI responses with `clean_ai_json_output` (strips `<think>` tags and markdown code fences).
   - Dispatches emergency error alert emails with tracebacks (`send_error_alert`).

4. **Task Scripts (`daily_quiz_sender.py`, `email_evaluator.py`, `weekly_report_sender.py`)**:
   - Pure orchestration pipelines.
   - Top-level `try/except` wrapping with `send_error_alert`.
   - Never implement ad-hoc DB connections, email protocols, or AI retries directly; always delegate to the core helper layers.

## Modularity Verification

Always verify syntax and imports after refactoring:
```powershell
python -B -c "import config, db, alert_utils, daily_quiz_sender, email_evaluator, weekly_report_sender; print('Modularity check passed!')"
```
