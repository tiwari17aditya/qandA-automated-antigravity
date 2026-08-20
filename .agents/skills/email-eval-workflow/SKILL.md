---
name: email-eval-workflow
description: Workflow for checking Gmail inbox via IMAP, extracting candidate quiz answers, scoring them against the database key, updating mastery statistics, and sending instant scorecard feedback.
---

# Email Evaluation & Grading Workflow

## Overview
Polls Gmail inbox over IMAP SSL, searches for unread replies matching MPPSC daily drills, extracts candidate answers using flexible regex patterns, evaluates accuracy against the stored answer key in Supabase PostgreSQL, and dispatches a detailed breakdown email with cumulative mastery statistics.

## Evaluation Flow

```mermaid
graph TD
    A[IMAP SSL Connect & Login] --> B[Search UNSEEN SUBJECT MPPSC]
    B --> C{Unread Emails Found?}
    C -->|No| D[Close & Exit]
    C -->|Yes| E[Extract Target Date from Subject]
    E --> F[Fetch Test Questions from daily_tests]
    F --> G[Parse Answers from Email Body]
    G --> H[Compare User Answer vs Correct Option]
    H --> I[Upsert Cumulative Stats into topic_stats]
    I --> J[Update daily_tests with Score, Percentage, Breakdown]
    J --> K[Send Instant Feedback Email]
    K --> L[Mark Email as SEEN]
```

## Answer Extraction Rules

1. **Numbered Patterns**: Supports standard reply formats like `1A 2B 3C` or `Q1: A\nQ2: B`.
2. **Compact String Fallback**: Supports compact character strings like `ACDBACDB...` stripping quoted email reply text.
3. **Mastery Tracking**:
   - `🟢 Strong` (>= 80% accuracy)
   - `🟡 Moderate` (60% - 79% accuracy)
   - `🔴 Needs Focus` (< 60% accuracy)

4. **Absent Policy**:
   - Tests older than today that remain `PENDING` are automatically transitioned to `ABSENT` with score 0.
