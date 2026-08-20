---
name: weekly-report-generator
description: Workflow for aggregating weekly drill performance from PostgreSQL, computing attendance and accuracy KPIs, synthesizing AI mentor feedback, and dispatching weekly HTML reports.
---

# Weekly Performance Report & Analytics

## Overview
Runs on a weekly cycle (typically Sunday evening) to analyze the candidate's drill consistency and question accuracy over the preceding 7 days. It queries `daily_tests` and `topic_stats` from Supabase PostgreSQL, generates personalized mentor strategy recommendations via Gemini/Groq, logs the summary to `weekly_reports`, and emails a rich HTML dashboard.

## Key Metrics Computed

1. **Attendance Rate**:
   $$\text{Attendance Rate (\%)} = \left(\frac{\text{Completed Tests}}{\text{Assigned Tests}}\right) \times 100$$
2. **Weekly Accuracy**:
   $$\text{Accuracy (\%)} = \left(\frac{\text{Total Score}}{\text{Total Possible Score}}\right) \times 100$$
3. **Missed / Absent Tests**:
   Count of tests marked `ABSENT`.
4. **Weak Topics Threshold**:
   Any topic with cumulative accuracy $< 70\%$ is flagged as a high-priority revision focus for the AI mentor recommendation.

## Report Dashboard Sections

- **7-Day Streak & Daily Progress Bar**: Visual daily activity badges showing completion status and scores (`✅ 13/15 (87%)`, `❌ Absent`, `⏳ Pending`).
- **KPI Cards**: Color-coded Attendance %, Overall Accuracy %, and Missed Drills count.
- **AI Mentor Study Review & Strategy**:
  - Weekly Performance Verdict (evaluating drill consistency, streak, and score progression)
  - High-Priority Revision Areas (addressing weak topics < 70%)
  - Strategic Advice for Next Week
- **Day-by-Day Activity & Scores Table**: Date, topic focus, completion status, exact score / percentage.
- **Topic Mastery Table**: Cumulative topic attempts, correct answers, and mastery level badges (`🟢 Strong`, `🟡 Moderate`, `🔴 Needs Focus`).

