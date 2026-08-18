import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project directory
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# ==========================================
# 🔑 CREDENTIALS & REQUIRED SETTINGS
# ==========================================
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# ==========================================
# ⚙️ CUSTOMIZABLE DRILL PREFERENCES
# ==========================================
# Gemini Model used for question generation (Default: gemini-2.5-flash)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

# Specific topics separated by comma (e.g. "Indus Valley Civilization (IVC), ICT")
# If left blank, general MPPSC Prelims syllabus mix is used.
TOPICS = os.getenv("TOPICS", "").strip()

# Number of questions per topic (if TOPICS is specified) or total questions
QUESTIONS_PER_TOPIC = int(os.getenv("QUESTIONS_PER_TOPIC", "15"))
TOTAL_QUESTIONS = int(os.getenv("TOTAL_QUESTIONS", "15"))

def get_quiz_prompt():
    """Builds dynamic prompt based on specified topics in .env."""
    if TOPICS:
        topic_list = [t.strip() for t in TOPICS.split(",") if t.strip()]
        topic_bullets = "\n".join([f"- {t} ({QUESTIONS_PER_TOPIC} questions)" for t in topic_list])
        total_q = len(topic_list) * QUESTIONS_PER_TOPIC
        return f"""
Generate {total_q} high-yield Multiple Choice Questions strictly for MPPSC State Services Prelims.
Provide exactly {QUESTIONS_PER_TOPIC} questions for EACH of the following topics:
{topic_bullets}

Return ONLY valid JSON matching this schema:
[
  {{
    "q_num": 1,
    "topic": "Topic Name Here",
    "question": "Question text?",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_option": "A",
    "explanation": "Brief context/fact."
  }}
]
""".strip()
    else:
        return f"""
Generate {TOTAL_QUESTIONS} high-yield Multiple Choice Questions strictly for MPPSC State Services Prelims.
Mix: MP GK (History, Geography, Polity, Economy), Unit 9 ICT & Tech, Unit 10 MP Tribes & Culture, Indian Polity, History, Science.

Return ONLY valid JSON matching this schema:
[
  {{
    "q_num": 1,
    "topic": "MP GK - History & Culture",
    "question": "Question text?",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_option": "A",
    "explanation": "Brief context/fact."
  }}
]
""".strip()

# ==========================================
# 🛡️ VALIDATION HELPER
# ==========================================
def validate_config(required_keys=None):
    """
    Validates that required configuration values are non-empty.
    Prints an actionable message if any configuration is missing.
    """
    if required_keys is None:
        required_keys = ["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "DATABASE_URL"]

    current_config = {
        "SENDER_EMAIL": SENDER_EMAIL,
        "APP_PASSWORD": APP_PASSWORD,
        "RECEIVER_EMAIL": RECEIVER_EMAIL,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "DATABASE_URL": DATABASE_URL,
    }

    missing = [k for k in required_keys if not current_config.get(k)]
    if missing:
        print("\n[ERROR] Configuration Error: Missing required settings:")
        for k in missing:
            print(f"   - {k}")
        print("\n[TIP] Please edit your `.env` file in the project folder and fill in the missing values.\n")
        return False
    return True
