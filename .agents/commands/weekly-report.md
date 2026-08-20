---
name: weekly-report
description: Aggregate past 7-day drill metrics, generate AI mentor review and actionable strategy, and dispatch the weekly performance report.
---

# 📊 Weekly Progress & Strategy Report (`/weekly-report`)

Execute this command to compile the 7-day performance summary, compute attendance & accuracy metrics, generate personalized AI mentor study advice, and email the weekly report.

## 🛠️ Step-by-Step Procedure

### Step 1: Run Weekly Report Sender
1. Execute the weekly report script:
   ```powershell
   python -B weekly_report_sender.py
   ```
2. Verify execution logs:
   - Past 7 days of `daily_tests` queried.
   - Attendance rate %, overall accuracy %, and absent counts calculated.
   - Weak topics identified (< 70% accuracy threshold).
   - AI study strategy synthesized via Gemini/Groq.
   - Record logged to `weekly_reports` table.
   - HTML performance report with KPI cards and tables emailed.

### Step 2: Cleanup Bytecode
```powershell
Get-ChildItem -Path . -Include __pycache__ -Recurse -Directory | Remove-Item -Recurse -Force
```
