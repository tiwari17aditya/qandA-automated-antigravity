# 🎯 MPPSC Automated Q&A & Drill System

An AI-driven, serverless, token-optimized daily drill, auto-grading, and analytics pipeline tailored for **MPPSC State Services Examination** preparation.

---

## 🏗️ Architecture & Module Structure

The codebase is built on a decoupled, single-responsibility architecture:

```
├── .agents/
│   ├── commands/                 # ⚡ Custom Slash Commands
│   │   ├── packup.md             # /packup: Git stage, commit & push sync
│   │   ├── modularize.md         # /modularize: Code modularity & refactor
│   │   ├── test-pipeline.md      # /test-pipeline: Diagnostics & health checks
│   │   ├── update-docs.md        # /update-docs: Doc & env synchronization
│   │   ├── daily-drill.md        # /daily-drill: Generate & send daily quiz
│   │   ├── eval-replies.md       # /eval-replies: Check inbox & grade answers
│   │   └── weekly-report.md      # /weekly-report: 7-day progress & AI mentor review
│   └── skills/                   # 🧠 Agent Procedures & Runbooks
│       ├── token-optimized-mppsc/
│       ├── mppsc-quiz-pipeline/
│       ├── email-eval-workflow/
│       ├── weekly-report-generator/
│       ├── code-modularizer/
│       └── git-packup-sync/
├── .github/workflows/            # ⚙️ GitHub Actions (Zero-Cache Scheduled Jobs)
│   ├── daily_quiz.yml            # 07:00 AM IST Daily Drill
│   ├── check_replies.yml         # Hourly Candidate Reply Evaluation
│   └── weekly_report.yml         # Sunday 08:00 PM IST Weekly Analytics
├── config.py                     # ⚙️ Centralized configuration & prompt generator
├── db.py                         # 🗄️ PostgreSQL (Supabase) access & auto-migrations
├── alert_utils.py                # 🛡️ Multi-provider AI caller & error email alert
├── daily_quiz_sender.py          # 📤 Daily MCQ generation & email dispatcher
├── email_evaluator.py            # 📥 IMAP reply parsing & instant scorecard grading
└── weekly_report_sender.py       # 📊 7-day progress analysis & AI study strategist
```

---

## ⚡ Slash Commands (`.agents/commands/`)

| Command | File | Description |
| :--- | :--- | :--- |
| **`/packup`** | [packup.md](file:///.agents/commands/packup.md) | Cleans bytecode (`__pycache__`), syncs docs, stages all changes, creates conventional commit, and pushes to `origin/main`. |
| **`/modularize`** | [modularize.md](file:///.agents/commands/modularize.md) | Audits code structure after feature addition, decouples logic, enforces zero-cache constraints, and verifies imports. |
| **`/test-pipeline`** | [test-pipeline.md](file:///.agents/commands/test-pipeline.md) | Runs end-to-end dry-run diagnostics for config, database, AI providers, and email handlers. |
| **`/update-docs`** | [update-docs.md](file:///.agents/commands/update-docs.md) | Keeps `.env.example`, `README.md`, and skill guides in sync with codebase changes. |
| **`/daily-drill`** | [daily-drill.md](file:///.agents/commands/daily-drill.md) | Generates and sends today's MPPSC quiz email on demand. |
| **`/eval-replies`** | [eval-replies.md](file:///.agents/commands/eval-replies.md) | Polls IMAP inbox, grades pending quiz replies, and sends scorecard emails. |
| **`/weekly-report`** | [weekly-report.md](file:///.agents/commands/weekly-report.md) | Compiles 7-day performance metrics and dispatches weekly AI mentor study report. |

---

## 🧠 Agent Skills (`.agents/skills/`)

- **[token-optimized-mppsc](file:///.agents/skills/token-optimized-mppsc/SKILL.md)**: Zero-cache GitHub Actions, strict token quotas (explanation $\le 15$ words), and auto-sync rules.
- **[mppsc-quiz-pipeline](file:///.agents/skills/mppsc-quiz-pipeline/SKILL.md)**: Daily quiz generation with Gemini/Groq dual failover and PostgreSQL persistence.
- **[email-eval-workflow](file:///.agents/skills/email-eval-workflow/SKILL.md)**: IMAP email polling, answer regex extraction, and scoring against test keys.
- **[weekly-report-generator](file:///.agents/skills/weekly-report-generator/SKILL.md)**: 7-day performance aggregation, weak topic detection (<70%), and HTML report creation.
- **[code-modularizer](file:///.agents/skills/code-modularizer/SKILL.md)**: Architectural standards, decoupling rules, and import verification.
- **[git-packup-sync](file:///.agents/skills/git-packup-sync/SKILL.md)**: Standardized commit and remote push procedures.

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` for local execution or configure as GitHub Actions Secrets:

```ini
SENDER_EMAIL=your_email@gmail.com
APP_PASSWORD=your_gmail_app_password
RECEIVER_EMAIL=candidate_email@gmail.com

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/postgres

# AI API Keys
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key

# Custom Drill Preferences
LLM_PROVIDER=gemini
GEMINI_MODEL=gemini-2.5-flash
GROQ_MODEL=deepseek-r1-distill-llama-70b
TOPICS=Indus Valley Civilization, ICT
QUESTIONS_PER_TOPIC=15
TOTAL_QUESTIONS=15
```

---

## 🛡️ Zero-Cache & Token Optimization Policies

1. **Zero-Cache CI/CD**: All GitHub Actions workflows run without actions cache (`cache: ''`) and install with `--no-cache-dir`.
2. **Bytecode Prevention**: Python bytecode is suppressed with `PYTHONDONTWRITEBYTECODE=1` and `python -B`.
3. **AI Failover**: Multi-provider resilience automatically switches between Google Gemini and Groq open-source models with exponential backoff and jitter.
