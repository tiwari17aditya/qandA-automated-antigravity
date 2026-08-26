# 📋 MPPSC Automated Q&A - Prompts Roadmap & Backlog

This document tracks the prompts and feature enhancements to be implemented step-by-step.

---

## 📌 Task Overview & Progress

- [x] **Prompt 1: Fixing the Answer Parser & Whitespace Shift Bug** (`email_evaluator.py`)
- [ ] **Prompt 2: Preventing Question Bank & Drill-Key Mismatch** (`email_evaluator.py`, `db.py`)
- [ ] **Prompt 3: Unit Test Suite for Pipeline Edge Cases** (`tests/test_evaluator.py`)

---

## 📝 Detailed Prompt Specifications

### Prompt 1: Fixing the Answer Parser & Whitespace Shift Bug
- **Context**: In candidate evaluation pipeline, candidates reply with answer strings (e.g. `DBCBCBBB... BCDBCACB` where spaces/hyphens denote unattempted questions). Currently, string sanitation or regex parsing strips whitespace characters, causing answers after an unattempted question to shift left by one or more positions.
- **Target File**: `email_evaluator.py`
- **Requirements**:
  - **Positional Character Parsing**: Accept raw continuous strings with spaces/hyphens (`ABCD EF--GH`) and delimited/numbered strings (`1.A 2.B 3.  4.C`).
  - **Index Preservation**: Spaces (` `), hyphens (`-`), or `X` must NOT be stripped from sequence. Each position corresponds to 1-based question number ($i \rightarrow$ Question $i+1$).
  - **Padding & Unattempted Mapping**: Map `' '`, `'-'`, `'X'`, or empty tokens to `None` (`UNATTEMPTED`). Normalize options to uppercase (`'A'`, `'B'`, `'C'`, `'D'`). Pad remaining indices if candidate answer count < total question count.
  - **Return Structure**: List of length `total_expected` containing uppercase options or `None`.

---

### Prompt 2: Preventing Question Bank & Drill-Key Mismatch
- **Context**: Prevent evaluation engine from grading submissions against the wrong drill or defaulting to latest DB entry.
- **Target Files**: `email_evaluator.py`, `db.py`
- **Requirements**:
  - **Explicit Key Extraction**: Extract exact `drill_id` (`DRILL-YYYYMMDD` or `DRILL-YYYYMMDD-HHMM`) from subject line or Reply-To header using regex (`r"DRILL-\d{8}(?:-\d+)?"`). Check body metadata headers if missing from subject.
  - **Database Verification Guardrail**: Query `daily_quizzes` specifically by extracted `drill_id`. Strictly prohibit defaulting to `ORDER BY created_at DESC LIMIT 1`. If `drill_id` not found in DB, log alert via `alert_utils.py` and quarantine in `candidate_responses` with status `'UNRESOLVED_DRILL_KEY'`.
  - **Metadata Sanity Check**: Verify total question count matches before scorecard generation.

---

### Prompt 3: Unit Test Suite for Pipeline Edge Cases
- **Target File**: `tests/test_evaluator.py` (and `.agents/commands/test-pipeline`)
- **Requirements**:
  - Whitespace in the middle (`"DBCBCBBBCCCBCCCADAABBBBBBCCBBBBABBCCABBBB BCDBCACB"` $\rightarrow$ Q42 `None`, Q43-Q50 unshifted).
  - Multiple consecutive spaces (`"A   B  C"` $\rightarrow$ indices 2, 3, 5, 6 `None`).
  - Trailing blanks / partial submission (50 answers for 60 questions $\rightarrow$ Q51-Q60 `None`).
  - Formatted numbered inputs (`"1. A\n2. B\n3. \n4. C"`).
  - Drill ID extraction tests for subjects (`Re: Daily Drill - DRILL-20260825` vs invalid).
  - Executable via `pytest` and `/test-pipeline`.
