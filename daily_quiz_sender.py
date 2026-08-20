import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

from config import (
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    GEMINI_API_KEY,
    TOTAL_QUESTIONS,
    GEMINI_MODEL,
    TOPICS,
    QUESTIONS_PER_TOPIC,
    get_quiz_prompt,
    validate_config,
)
from db import get_db_connection, init_and_migrate_db, mark_expired_tests_absent, get_previous_test_data
from alert_utils import send_error_alert, generate_ai_completion, clean_ai_json_output

def generate_questions():
    prompt = get_quiz_prompt()
    topic_desc = TOPICS if TOPICS else "General MPPSC Mix"
    print(f"[2/4] Generating questions with AI for: {topic_desc}...")
    
    raw_response = generate_ai_completion(
        prompt=prompt,
        response_json=True
    )
    cleaned_json = clean_ai_json_output(raw_response)
    questions = json.loads(cleaned_json)
    print(f"      Generated {len(questions)} questions successfully.")
    return questions

def render_previous_day_section(prev_test):
    """
    Renders yesterday's / prior drill score, answers, and explanations
    to reinforce learning before attempting today's drill.
    """
    if not prev_test or not prev_test.get("questions"):
        return ""
    
    p_date = prev_test.get("test_date", "")
    p_status = prev_test.get("status", "UNKNOWN")
    p_score = prev_test.get("score", 0)
    p_total = prev_test.get("total_questions") or len(prev_test.get("questions", []))
    p_pct = prev_test.get("percentage", 0.0)
    p_questions = prev_test.get("questions", [])
    p_user_answers = prev_test.get("user_answers") or []
    p_topics = prev_test.get("topics", "General Mix")

    if p_status == "EVALUATED":
        badge_bg = "#c6f6d5" if p_pct >= 75 else "#fefcbf" if p_pct >= 50 else "#fed7d7"
        badge_color = "#22543d" if p_pct >= 75 else "#744210" if p_pct >= 50 else "#742a2a"
        status_banner = f"""
        <div style="background: {badge_bg}; color: {badge_color}; padding: 8px 12px; border-radius: 6px; font-weight: bold; font-size: 14px; margin-bottom: 12px;">
            🎯 Score: {p_score}/{p_total} ({p_pct:.1f}%) &bull; Status: Evaluated
        </div>
        """
    elif p_status == "ABSENT":
        status_banner = f"""
        <div style="background: #fed7d7; color: #742a2a; padding: 8px 12px; border-radius: 6px; font-weight: bold; font-size: 14px; margin-bottom: 12px;">
            ❌ Marked Absent (0/{p_total} unsubmitted)
        </div>
        """
    else:
        status_banner = f"""
        <div style="background: #edf2f7; color: #4a5568; padding: 8px 12px; border-radius: 6px; font-weight: bold; font-size: 14px; margin-bottom: 12px;">
            ⏳ Status: Pending Evaluation
        </div>
        """

    solutions_html = ""
    for idx, q in enumerate(p_questions):
        q_num = q.get("q_num", idx + 1)
        topic = q.get("topic", "General")
        q_text = q.get("question", "")
        options = q.get("options", {})
        correct_opt = str(q.get("correct_option", "")).upper()
        explanation = q.get("explanation", "")
        
        user_ans = (p_user_answers[idx] if idx < len(p_user_answers) else None) if p_user_answers else None
        
        if p_status == "EVALUATED" and user_ans:
            is_correct = (str(user_ans).upper() == correct_opt)
            user_badge = f"<span style='color: {'#38a169' if is_correct else '#e53e3e'}; font-weight: bold;'>{'✅ Correct' if is_correct else '❌ Incorrect'} (Your Answer: {user_ans})</span>"
        elif p_status == "ABSENT":
            user_badge = "<span style='color: #e53e3e; font-style: italic;'>Unanswered (Absent)</span>"
        else:
            user_badge = ""

        correct_opt_text = options.get(correct_opt, "") if isinstance(options, dict) else ""

        solutions_html += f"""
        <div style="border-left: 4px solid #3182ce; background: #ffffff; padding: 10px 12px; margin-bottom: 10px; border-radius: 4px; border: 1px solid #e2e8f0; border-left-width: 4px;">
            <div style="font-size: 11px; font-weight: bold; color: #4a5568; margin-bottom: 4px;">
                Q{q_num} &bull; {topic} {f'&bull; {user_badge}' if user_badge else ''}
            </div>
            <div style="font-size: 14px; font-weight: 600; color: #2d3748; margin-bottom: 6px;">
                {q_text}
            </div>
            <div style="font-size: 13px; color: #2d3748; line-height: 1.4; margin-bottom: 4px;">
                <strong style="color: #2b6cb0;">Correct: ({correct_opt})</strong> {correct_opt_text}
            </div>
            {f'<div style="font-size: 12px; color: #4a5568; margin-top: 4px; background: #f7fafc; padding: 6px; border-radius: 4px;">💡 <em>{explanation}</em></div>' if explanation else ''}
        </div>
        """

    return f"""
    <!-- PREVIOUS DAY REVIEW SECTION -->
    <div style="background: #f8fafc; border: 1px solid #cbd5e0; border-radius: 8px; padding: 16px; margin-bottom: 25px;">
        <div style="border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; margin-bottom: 12px;">
            <h3 style="color: #2b6cb0; margin: 0; font-size: 16px;">⏮️ Yesterday's Drill Solutions & Score ({p_date})</h3>
            <p style="color: #718096; margin: 3px 0 0 0; font-size: 12px;">Topics: {p_topics}</p>
        </div>
        {status_banner}
        <details style="margin-top: 6px;">
            <summary style="cursor: pointer; font-weight: bold; color: #3182ce; font-size: 13px; padding: 4px 0;">
                🔍 View Solutions & Explanations ({len(p_questions)} Questions)
            </summary>
            <div style="margin-top: 12px;">
                {solutions_html}
            </div>
        </details>
    </div>
    """

def create_html_email(date_str, questions, topic_desc, prev_test=None):
    prev_review_html = render_previous_day_section(prev_test) if prev_test else ""

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 650px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 2px solid #3182ce; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="color: #2b6cb0; margin: 0;">🎯 MPPSC Daily Prelims Drill</h2>
                <p style="color: #718096; margin: 5px 0 0 0;">Date: {date_str} &bull; {len(questions)} Questions &bull; Focus: {topic_desc}</p>
            </div>

            {prev_review_html}

            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 20px; font-size: 14px;">
                <strong>📌 Today's Drill Submission:</strong> Click <strong>Reply</strong> to this email, type your answers (e.g. <code>1A 2C 3B...</code> or <code>ACDBACDB...</code>), and send!
                <br><small style="color: #4a5568;">⏰ Please submit before midnight so your drill is evaluated and not marked absent.</small>
            </div>
    """
    for q in questions:
        html += f"""
            <div style="border: 1px solid #edf2f7; border-radius: 6px; padding: 14px; margin-bottom: 14px; background: #fafafa;">
                <div style="font-size: 11px; font-weight: bold; color: #4a5568; text-transform: uppercase; margin-bottom: 4px;">Q{q['q_num']} &bull; {q['topic']}</div>
                <div style="font-size: 15px; font-weight: 600; margin-bottom: 8px; color: #1a202c;">{q['question']}</div>
                <div style="font-size: 14px; line-height: 1.6;">
                    (A) {q['options']['A']}<br>
                    (B) {q['options']['B']}<br>
                    (C) {q['options']['C']}<br>
                    (D) {q['options']['D']}
                </div>
            </div>
        """
    html += "</div></body></html>"
    return html

def send_email(subject, html_content):
    print(f"[4/4] Sending quiz email to {RECEIVER_EMAIL}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print("      Email sent successfully!")

def main():
    try:
        validate_config(["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "GEMINI_API_KEY", "DATABASE_URL"])

        # 1. Initialize & migrate DB schema
        print("[1/4] Initializing PostgreSQL database tables & checking pending tests...")
        init_and_migrate_db()
        absents = mark_expired_tests_absent()
        if absents > 0:
            print(f"      Marked {absents} previous unreplied test(s) as ABSENT.")

        today_str = datetime.now().strftime("%Y-%m-%d")
        test_id = f"MPPSC_{today_str}"
        topic_desc = TOPICS if TOPICS else "General MPPSC Mix"

        # Fetch previous day's test for solutions & score review
        prev_test = get_previous_test_data(today_str)
        if prev_test:
            print(f"      Loaded previous drill solutions from {prev_test['test_date']} (Status: {prev_test['status']}).")

        # 2. Generate questions via Gemini
        questions = generate_questions()

        # 3. Save to database
        print("[3/4] Saving questions to database...")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_tests (test_id, test_date, topics, questions_json, evaluated, status, total_questions)
            VALUES (%s, %s, %s, %s, FALSE, 'PENDING', %s)
            ON CONFLICT (test_date) DO UPDATE SET 
                topics = EXCLUDED.topics,
                questions_json = EXCLUDED.questions_json,
                total_questions = EXCLUDED.total_questions,
                status = 'PENDING';
        """, (test_id, today_str, topic_desc, json.dumps(questions), len(questions)))
        conn.commit()
        cursor.close()
        conn.close()
        print("      Saved to daily_tests table as PENDING.")

        # 4. Dispatch Email
        subject = f"🎯 MPPSC Daily Prelims Drill - {today_str}"
        send_email(subject, create_html_email(today_str, questions, topic_desc, prev_test=prev_test))
        print(f"\n[OK] MPPSC Daily Quiz for {today_str} sent and recorded successfully!\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to send daily quiz: {e}\n")
        send_error_alert("Daily Quiz Sender (daily_quiz_sender.py)", e)
        raise e

if __name__ == "__main__":
    main()