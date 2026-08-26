---
name: project-structure-cleaner
description: Standard guidelines and procedures for maintaining a clean, decoupled, zero-cache repository layout, pruning loose scratch files, and enforcing strict directory boundaries.
---

# 🧹 Project Structure & Repository Hygiene Skill

This runbook defines standards for keeping the MPPSC Automation repository clean, organized, and free of orphan test files or bytecode.

---

## 📌 Directory Hierarchy Standards

```
.
├── .agents/
│   ├── commands/                 # ⚡ Custom Slash Commands (/clean-repo, /packup, /test-pipeline, etc.)
│   └── skills/                   # 🧠 Agent Procedures & Runbooks
├── .github/workflows/            # ⚙️ GitHub Actions Zero-Cache Workflows
├── tests/                        # 🧪 Automated Pytest Unit Test Suite (test_evaluator.py)
├── logs/                         # 📁 Ignored Local Execution Logs & Dry-Run Artifacts
├── config.py                     # ⚙️ Centralized Configuration & Prompt Generator
├── db.py                         # 🗄️ PostgreSQL Database Connection & Migrations
├── alert_utils.py                # 🛡️ Multi-Provider AI Failover & Admin Error Alerts
├── daily_quiz_sender.py          # 📤 Daily MCQ Generation & Email Dispatcher
├── email_evaluator.py            # 📥 IMAP Reply Evaluation & Scorecard Reporter
├── weekly_report_sender.py       # 📊 7-Day Analytics & AI Mentor Strategy Reporter
├── pdf_font_utils.py             # 🔤 Devanagari Hindi Unicode PDF Font Helper
├── logger_utils.py               # 🎨 Colorized Pipeline Logger
├── PROJECT_MEMORY.md             # 🧠 Snapshot Context Memory for AI Assistants
├── PROMPTS_ROADMAP.md            # 📋 Prompts & Features Progress Checklist
├── README.md                     # 📖 Repository Documentation
└── requirements.txt              # 📦 Python Dependencies
```

---

## 🛡️ Hygiene Rules

1. **No Scratch Files in Root**: Never commit temporary PDF outputs (e.g. `scratch_*.pdf` or `dryrun_*.pdf`) to root directory. Keep dry-run outputs in `logs/` (which is git-ignored).
2. **Zero-Cache Enforcement**: Never leave `__pycache__` folders or `.pytest_cache` checked into git.
3. **Single Responsibility**: Each root Python file must handle a single pipeline responsibility (`config.py`, `db.py`, `alert_utils.py`, `daily_quiz_sender.py`, `email_evaluator.py`, `weekly_report_sender.py`).
4. **Automated Unit Tests in `tests/`**: All `pytest` unit test files must reside in the `tests/` directory.

---

## 🛠️ Automated Cleanup Command

Execute the PowerShell cleanup command anytime:
```powershell
python -c "import pathlib, shutil; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.pytest_cache')]"
```
