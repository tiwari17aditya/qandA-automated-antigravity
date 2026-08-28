# 🧠 Project Memory & System Context

> **Last Updated**: August 28, 2026  
> **Repository**: `tiwari17aditya/qandA-automated-antigravity`  
> **Target Exam**: MPPSC (Madhya Pradesh Public Service Commission) State Services Examination  
> **Architecture**: AI-driven, Serverless, Decoupled Python Automation Pipeline with PostgreSQL & GitHub Actions  

---

## 📌 Executive Summary

The **MPPSC Automated Q&A & Drill System** is an end-to-end, zero-cache, token-optimized automation pipeline designed for MPPSC Prelims preparation. It automatically generates daily bilingual (Hindi & English) multiple-choice questions (MCQs), emails interactive HTML drill papers with PDF attachments to candidates, parses answer replies from Gmail via IMAP, grades candidate responses in real-time, maintains topic-wise mastery analytics in PostgreSQL (Supabase), and dispatches weekly AI mentor strategy reports.

---

## 🏗️ Core Module Architecture & Design

The project strictly follows single-responsibility decoupling and zero-cache execution:

| Module / File | Responsibility & Details |
| :--- | :--- |
| **[`config.py`](file:///d:/mppsc/QandA-automated-antigravity/config.py)** | Centralized configuration loader for env variables, topics, target limits, and structured AI prompt builders (bilingual MPPSC MCQs, strict JSON output schemas, $\le 15$ words per explanation). Default models: `gemini-2.5-flash` and `qwen/qwen3.8-27b`. |
| **[`db.py`](file:///d:/mppsc/QandA-automated-antigravity/db.py)** | PostgreSQL / Supabase connection manager with connection pooling, retries, and automatic migrations for 4 core tables. |
| **[`alert_utils.py`](file:///d:/mppsc/QandA-automated-antigravity/alert_utils.py)** | Multi-provider AI invoker with active failover pools (`gemini-2.5-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`, `qwen/qwen3.8-27b`, `groq/compound`), 3-tier fault-tolerant JSON parser `parse_ai_json_output()`, and admin error alert email dispatching. |
| **[`daily_quiz_sender.py`](file:///d:/mppsc/QandA-automated-antigravity/daily_quiz_sender.py)** | Daily drill pipeline: generates MCQs via AI, assigns unique `DRILL-YYYYMMDD` ID, stores key in PostgreSQL, renders responsive HTML + PDF (Hindi Unicode font support), and emails candidate. |
| **[`email_evaluator.py`](file:///d:/mppsc/QandA-automated-antigravity/email_evaluator.py)** | Candidate reply processing: polls Gmail IMAP inbox, extracts candidate answers using regex, scores against answer key in DB, updates `mastery_stats`, and emails instant scorecard. |
| **[`weekly_report_sender.py`](file:///d:/mppsc/QandA-automated-antigravity/weekly_report_sender.py)** | Analytics aggregator: computes 7-day attendance, accuracy KPIs, topic accuracy breakdowns, identifies weak topics (<70%), generates AI mentor review, and sends HTML weekly report. |
| **[`pdf_font_utils.py`](file:///d:/mppsc/QandA-automated-antigravity/pdf_font_utils.py)** | Utility for registering Hindi Unicode fonts (Devanagari support) in ReportLab PDFs. |
| **[`logger_utils.py`](file:///d:/mppsc/QandA-automated-antigravity/logger_utils.py)** | Standardized color-coded logging configuration. |

---

## 🗄️ Database Schema (PostgreSQL / Supabase)

1. **`daily_quizzes`**: `drill_id` (PK), `date`, `topic`, `questions_json` (bilingual MCQs, correct options, explanations), `created_at`.
2. **`candidate_responses`**: `id` (PK), `drill_id` (FK), `candidate_email`, `received_at`, `raw_text`, `parsed_answers_json`, `score`, `total_questions`, `percentage`, `topic_breakdown_json`.
3. **`mastery_stats`**: `candidate_email` + `topic` (Composite PK), `total_attempted`, `total_correct`, `accuracy_percentage`, `last_updated`.
4. **`weekly_reports`**: `report_id` (PK), `candidate_email`, `start_date`, `end_date`, `overall_accuracy`, `quizzes_completed`, `weak_topics_json`, `mentor_feedback_text`, `created_at`.

---

## 🛡️ Key Constraints & System Rules

### 1. Storage & Zero-Cache Policy
- **No GitHub Actions Caching**: Workflows (`daily_quiz.yml`, `check_replies.yml`, `weekly_report.yml`) explicitly omit caching (`cache: ''`).
- **No Bytecode Overhead**: Execution uses `PYTHONDONTWRITEBYTECODE=1` and `python -B`. `pip install` uses `--no-cache-dir`.
- **Shallow Git Fetch**: GitHub actions check out code with `fetch-depth: 1`.

### 2. AI Token Optimization & Multi-Provider Resilience
- **Strict JSON Output Schemas**: All AI prompts enforce `response_mime_type="application/json"`.
- **Concise Explanations**: MCQ explanations are strictly capped at $\le 15$ words per question to save output tokens.
- **Active Failover Chain**: Google Gemini (`gemini-2.5-flash` $\rightarrow$ `gemini-3.6-flash` $\rightarrow$ `gemini-3.5-flash`) as primary, Groq (`qwen/qwen3.8-27b` $\rightarrow$ `qwen/qwen3.6-27b` $\rightarrow$ `groq/compound`) as fallback upon 429/5xx error.
- **Fault-Tolerant Parsing**: Multi-tier `parse_ai_json_output` recovers from trailing commas, codeblock fences, or truncated reasoning blocks.

### 3. Automated Git Packup
- Any task completion requires cleaning bytecode, committing with clear messages, and pushing to `origin/main`.

---

## ⚙️ CI/CD Workflows (`.github/workflows/`)

- **`daily_quiz.yml`**: Cron `30 2 * * *` (08:00 AM IST daily) → executes `daily_quiz_sender.py`.
- **`check_replies.yml`**: Cron `30 5,9,13,17 * * *` (11:00 AM, 03:00 PM, 07:00 PM, 11:00 PM IST daily) → executes `email_evaluator.py`.
- **`weekly_report.yml`**: Cron `30 14 * * 0` (Sunday 08:00 PM IST) → executes `weekly_report_sender.py`.

---

## ⚡ Slash Commands & Agent Skills

### Commands (`.agents/commands/`)
- `/clean-repo` — Remove bytecode (`__pycache__`), clear `.pytest_cache`, prune local PDFs/logs, and maintain repo hierarchy.
- `/daily-drill` — Generate and email today's drill on demand.
- `/eval-replies` — Poll IMAP inbox and evaluate candidate responses.
- `/weekly-report` — Aggregate 7-day progress and send AI mentor strategy report.
- `/test-pipeline` — Run complete dry-run diagnostic tests for config, DB, AI, unit tests, and email.
- `/modularize` — Audit modular structure and enforce zero-cache rules.
- `/packup` — Stage, commit, bytecode clean, and push to `origin/main`.
- `/update-docs` — Re-synchronize `.env.example`, `README.md`, and skill documents.

### Skills (`.agents/skills/`)
- `project-structure-cleaner` — Folder hierarchy maintenance, bytecode purging, and scratch file pruning.
- `token-optimized-mppsc` — Core zero-cache & Gemini token budget guidelines.
- `mppsc-quiz-pipeline` — MCQ generation & failover logic.
- `email-eval-workflow` — IMAP polling & response regex extraction runbook.
- `weekly-report-generator` — Analytics & AI study recommendations procedure.
- `code-modularizer` — Python decoupling & linting guidelines.
- `git-packup-sync` — Git sync workflow.

---

## 🚀 Recommended Next Steps / Roadmap for Continuation

1. **Multi-Candidate Expansion**: Extend DB queries and email dispatch loops to support multiple candidates from a subscriber list table.
2. **Interactive Web Dashboard**: Build a Next.js / Vite dashboard to display real-time mastery stats, accuracy charts, and drill archives.
3. **Instant Messaging Notifications**: Add Telegram / WhatsApp bot webhooks for instant drill alerts alongside email.
4. **Adaptive Difficulty Engine**: Dynamically weight MCQ selection towards weak topics (<70% accuracy) from candidate mastery history.
