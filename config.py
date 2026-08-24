import os
import sys
from pathlib import Path
import dotenv
from dotenv import load_dotenv

# 1. Load defaults from .env.example (tracked in git)
example_defaults = {}
example_env_path = Path(__file__).resolve().parent / ".env.example"
if example_env_path.exists():
    example_defaults = dotenv.dotenv_values(dotenv_path=example_env_path)

# 2. Load overrides from local .env if present
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)

def _get_str_env(key: str, default: str = "") -> str:
    val = os.getenv(key)
    if val is not None and str(val).strip():
        return str(val).strip()
    fallback = example_defaults.get(key, default)
    if fallback is not None and str(fallback).strip() and not str(fallback).strip().startswith("your_"):
        return str(fallback).strip()
    return default

def _get_int_env(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is not None and str(val).strip():
        try:
            return int(str(val).strip())
        except (ValueError, TypeError):
            pass
    fallback = example_defaults.get(key, str(default))
    if fallback is not None and str(fallback).strip():
        try:
            return int(str(fallback).strip())
        except (ValueError, TypeError):
            pass
    return default

# ==========================================
# 🔑 CREDENTIALS & REQUIRED SETTINGS
# ==========================================
SENDER_EMAIL = _get_str_env("SENDER_EMAIL", "")
APP_PASSWORD = _get_str_env("APP_PASSWORD", "")
RECEIVER_EMAIL = _get_str_env("RECEIVER_EMAIL", "")
GEMINI_API_KEY = _get_str_env("GEMINI_API_KEY", "")
GROQ_API_KEY = _get_str_env("GROQ_API_KEY", "")
DATABASE_URL = _get_str_env("DATABASE_URL", "")

# ==========================================
# ⚙️ CUSTOMIZABLE DRILL PREFERENCES
# ==========================================
# Primary LLM Provider: "gemini" or "groq" (auto-fallbacks between both)
LLM_PROVIDER = _get_str_env("LLM_PROVIDER", "gemini").lower()

# Model used for question generation (e.g. gemini-2.5-flash, deepseek-r1-distill-llama-70b, qwen-2.5-32b)
GEMINI_MODEL = _get_str_env("GEMINI_MODEL", "gemini-3.6-flash")
GROQ_MODEL = _get_str_env("GROQ_MODEL", "qwen/qwen3.6-27b")

# Specific topics separated by comma (e.g. "Indus Valley Civilization (IVC), ICT")
# If left blank, general MPPSC Prelims syllabus mix is used.
TOPICS = _get_str_env("TOPICS", "")

# Number of questions per topic (if TOPICS is specified) or total questions
QUESTIONS_PER_TOPIC = _get_int_env("QUESTIONS_PER_TOPIC", 15)
TOTAL_QUESTIONS = _get_int_env("TOTAL_QUESTIONS", 15)

def get_pipeline_configs(only_enabled=True):
    """
    Loads all student pipeline configurations from pipelines.json or PIPELINES_JSON env var.
    Always computes total_questions dynamically based on topics count and questions_per_topic if topics are provided.
    """
    import json
    pipelines = []
    
    # 1. Default pipeline (Aditya / MPPSC)
    default_pipe = {
        "pipeline_id": "mppsc_default",
        "student_name": "Aditya",
        "receiver_email": RECEIVER_EMAIL,
        "exam_name": "MPPSC Prelims",
        "topics": TOPICS,
        "questions_per_topic": QUESTIONS_PER_TOPIC,
        "total_questions": TOTAL_QUESTIONS,
        "language": "english",
        "enabled": True
    }
    
    json_source = os.getenv("PIPELINES_JSON")
    pipelines_file = Path(__file__).resolve().parent / "pipelines.json"
    
    if json_source and json_source.strip():
        try:
            parsed = json.loads(json_source)
            if isinstance(parsed, list):
                pipelines = parsed
        except Exception as e:
            print(f"[WARN] Failed to parse PIPELINES_JSON env var: {e}")
    elif pipelines_file.exists():
        try:
            with open(pipelines_file, "r", encoding="utf-8") as f:
                parsed = json.load(f)
                if isinstance(parsed, list):
                    pipelines = parsed
        except Exception as e:
            print(f"[WARN] Failed to read pipelines.json: {e}")

    # Ensure default pipeline is present if not explicitly included
    has_default = any(p.get("pipeline_id") == "mppsc_default" for p in pipelines)
    if not has_default and RECEIVER_EMAIL:
        pipelines.insert(0, default_pipe)

    # Dynamic computation of total_questions for each pipeline if topics & questions_per_topic are present
    for p in pipelines:
        topics_str = p.get("topics", "")
        q_per_top = p.get("questions_per_topic") or QUESTIONS_PER_TOPIC
        if topics_str:
            t_list = [t.strip() for t in topics_str.split(",") if t.strip()]
            if t_list:
                # If explicit total_questions was NOT set or topic-based calculation is needed:
                # Calculate exactly q_per_top per topic (e.g. 4 topics * 15 = 60 total questions)
                p["calculated_total_questions"] = len(t_list) * q_per_top
                p["questions_per_topic"] = q_per_top

    if only_enabled:
        return [p for p in pipelines if p.get("enabled", True)]
    return pipelines

def get_quiz_prompt_for_pipeline(pipeline_cfg):
    """Builds dynamic token-optimized prompt tailored to exam name, topics, question count, and language medium."""
    exam_name = pipeline_cfg.get("exam_name", "Competitive Exam")
    topics_str = pipeline_cfg.get("topics", "")
    q_per_topic = pipeline_cfg.get("questions_per_topic", QUESTIONS_PER_TOPIC)
    
    lang = pipeline_cfg.get("language", "english").lower()
    
    lang_rule = ""
    if lang == "hindi":
        lang_rule = "IMPORTANT: Write ALL questions, options (A, B, C, D), and explanations in clear Devanagari Hindi (हिन्दी भाषा)."
    else:
        lang_rule = "Write questions, options, and explanations in English."

    token_opt_rule = f"Constraints: Keep questions crisp. Keep explanation ultra-concise (max 15 words). Output pure JSON array only. {lang_rule}"

    if topics_str:
        topic_list = [t.strip() for t in topics_str.split(",") if t.strip()]
        total_q = len(topic_list) * q_per_topic
        topic_bullets = "\n".join([f"- {t}: EXACTLY {q_per_topic} questions" for t in topic_list])
        
        return f"""
Generate exactly {total_q} Multiple Choice Questions strictly for {exam_name}.
CRITICAL REQUIREMENT: Generate EXACTLY {q_per_topic} questions for EACH of the {len(topic_list)} topics below:
{topic_bullets}

Each question's 'topic' field MUST be set to the exact matching topic name from the list above.

{token_opt_rule}

Return ONLY valid JSON matching this schema:
[
  {{
    "q_num": 1,
    "topic": "{topic_list[0]}",
    "question": "Question text strictly on this topic?",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_option": "A",
    "explanation": "Brief context/fact (<=15 words)."
  }}
]
""".strip()
    else:
        return f"""
Generate exactly {total_q} high-yield Multiple Choice Questions strictly for {exam_name}.
Ensure questions cover the full core syllabus of {exam_name}.

{token_opt_rule}

Return ONLY valid JSON matching this schema:
[
  {{
    "q_num": 1,
    "topic": "{exam_name} General Practice",
    "question": "Question text?",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_option": "A",
    "explanation": "Brief context/fact (<=15 words)."
  }}
]
""".strip()

def get_quiz_prompt():
    """Builds dynamic token-optimized prompt for default MPPSC pipeline."""
    default_pipe = {
        "pipeline_id": "mppsc_default",
        "student_name": "Aditya",
        "receiver_email": RECEIVER_EMAIL,
        "exam_name": "MPPSC State Services Prelims",
        "topics": TOPICS,
        "total_questions": TOTAL_QUESTIONS,
        "language": "english",
        "enabled": True
    }
    return get_quiz_prompt_for_pipeline(default_pipe)

# ==========================================
# 🛡️ VALIDATION HELPER
# ==========================================
def validate_config(required_keys=None):
    """
    Validates that required configuration values are non-empty.
    Raises a ValueError with actionable guidance if any configuration is missing.
    """
    if required_keys is None:
        required_keys = ["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "DATABASE_URL"]

    current_config = {
        "SENDER_EMAIL": SENDER_EMAIL,
        "APP_PASSWORD": APP_PASSWORD,
        "RECEIVER_EMAIL": RECEIVER_EMAIL,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "GROQ_API_KEY": GROQ_API_KEY,
        "DATABASE_URL": DATABASE_URL,
    }

    missing = []
    for k in required_keys:
        if k == "AI_KEY":
            if not GEMINI_API_KEY and not GROQ_API_KEY:
                missing.append("GEMINI_API_KEY or GROQ_API_KEY")
        elif k == "GEMINI_API_KEY":
            if not GEMINI_API_KEY and not GROQ_API_KEY:
                missing.append("GEMINI_API_KEY (or GROQ_API_KEY)")
        else:
            if not current_config.get(k):
                missing.append(k)

    if missing:
        error_msg = (
            f"\n[ERROR] Configuration Error: Missing required settings / GitHub Secrets:\n"
            + "\n".join([f"   - {k}" for k in missing])
            + "\n\n[ACTION REQUIRED] Please add these in your GitHub Repo -> Settings -> Secrets and variables -> Actions, or local `.env` file.\n"
        )
        print(error_msg, file=sys.stderr)
        raise ValueError(f"Missing required configuration keys: {', '.join(missing)}")
    return True

