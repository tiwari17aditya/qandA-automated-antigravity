# MPPSC Automation Agent Guidelines

## 1. Storage & Zero-Cache Policy
- **Never enable GitHub Actions caching** (`actions/cache` or `cache: 'pip'`).
- Always run `pip install --no-cache-dir -r requirements.txt`.
- Prevent `.pyc` and `__pycache__` creation using `PYTHONDONTWRITEBYTECODE=1` and `python -B`.
- Use shallow git checkouts (`fetch-depth: 1`) to preserve minimal disk and GitHub quota.

## 2. Gemini AI Token Optimization
- Enforce strict JSON output schemas (`config={"response_mime_type": "application/json"}`).
- Limit explanation lengths to <=15 words per MCQ to minimize completion token consumption.
- Use `gemini_generate_with_retry` with exponential backoff and jitter to protect against rate limits (429/ResourceExhausted).
- Never send multi-turn history when single-turn completion is sufficient.

## 3. Automated Git Synchronization & Packup
- **Automatic Packup & Push**: Whenever a task, refactoring, or feature is completed, automatically stage all modified files, create a descriptive commit, and push changes to git/GitHub (`origin/main`).
- Never leave pending unpushed changes upon wrap up.
