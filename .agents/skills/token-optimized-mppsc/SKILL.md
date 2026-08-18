---
name: token-optimized-mppsc
description: Enforces zero-cache GitHub Actions execution and Gemini token-optimized quiz generation workflows for MPPSC preparation.
---

# Token-Optimized MPPSC Automation Workflow

## Objective
Maintains a 100% serverless, zero-cache, and token-efficient MPPSC daily drill pipeline.

## Storage Preservation Protocol
1. **GitHub Storage Protection**:
   - Workflows disable action caching via `cache: ''`.
   - Dependencies installed strictly with `--no-cache-dir`.
   - Python bytecode disabled with `PYTHONDONTWRITEBYTECODE=1`.
   - Git shallow checkouts with `fetch-depth: 1`.

2. **Gemini API Token Optimization**:
   - Dynamic prompt generator in `config.py` enforces `< 15 words` explanation per MCQ.
   - Structured JSON schema response (`application/json`) minimizes overhead tokens.
   - Rate-limit resilient caller (`alert_utils.py`) handles exponential backoff.
