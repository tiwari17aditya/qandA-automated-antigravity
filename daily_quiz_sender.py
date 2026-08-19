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
from db import get_db_connection, init_and_migrate_db, mark_expired_tests_absent
from alert_utils import send_error_alert, gemini_generate_with_retry

def generate_questions():
    prompt = get_quiz_prompt()
    topic_desc = TOPICS if TOPICS else "General MPPSC Mix"
    print(f"[2/4] Generating questions with Gemini ({GEMINI_MODEL}) for: {topic_desc}...")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    response = gemini_generate_with_retry(
        client=client,
        model=GEMINI_MODEL,
        prompt=prompt,
        config={"response_mime_type": "application/json"}
    )
    questions = json.loads(response.text)
    print(f"      Generated {len(questions)} questions successfully.")
    return questions

def create_html_email(date_str, questions, topic_desc):
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 650px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 2px solid #3182ce; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="color: #2b6cb0; margin: 0;">🎯 MPPSC Daily Prelims Drill</h2>
                <p style="color: #718096; margin: 5px 0 0 0;">Date: {date_str} &bull; {len(questions)} Questions &bull; Focus: {topic_desc}</p>
            </div>
            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 20px; font-size: 14px;">
                <strong>📌 How to Submit:</strong> Click <strong>Reply</strong> to this email, type your answers (e.g. <code>1A 2C 3B...</code> or <code>ACDBACDB...</code>), and send!
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
        send_email(subject, create_html_email(today_str, questions, topic_desc))
        print(f"\n[OK] MPPSC Daily Quiz for {today_str} sent and recorded successfully!\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to send daily quiz: {e}\n")
        send_error_alert("Daily Quiz Sender (daily_quiz_sender.py)", e)
        raise e

if __name__ == "__main__":
    main()