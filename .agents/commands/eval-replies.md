---
name: eval-replies
description: Poll IMAP inbox for candidate drill replies, grade answers against DB key, record scores, and send feedback reports.
---

# 📥 Email Reply Evaluation & Grading (`/eval-replies`)

Execute this command to check the Gmail inbox for unread drill replies, evaluate candidate answers against the database key, update mastery statistics, and send instant feedback emails.

## 🛠️ Step-by-Step Procedure

### Step 1: Check & Process Replies
1. Run the evaluation script:
   ```powershell
   python -B email_evaluator.py
   ```
2. Verify execution logs:
   - Expired unsubmitted tests marked as `ABSENT`.
   - IMAP searched for unread subject containing `MPPSC`.
   - Answers parsed (supports format `1A 2B 3C` or compact `ABCD...`).
   - Detailed question-by-question breakdown compiled.
   - `daily_tests` status updated to `EVALUATED`.
   - `topic_stats` table updated with cumulative accuracy.
   - Scorecard feedback email dispatched with color-coded topic tags.

### Step 2: Cleanup Bytecode
```powershell
Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
```
