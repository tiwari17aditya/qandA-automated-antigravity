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

- **KPI Cards**: Color-coded Attendance, Overall Accuracy, and Missed Drills count.
- **AI Mentor Study Review & Strategy**:
  - Weekly Performance Verdict
  - High-Priority Revision Areas
  - Strategic Advice for Next Week
- **Day-by-Day Activity Table**: Date, topic focus, completion status, score.
- **Topic Mastery Table**: Cumulative topic attempts, correct answers, and mastery level badges.
