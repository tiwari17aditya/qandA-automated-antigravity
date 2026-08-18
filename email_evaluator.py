import json
import re
import imaplib
import email
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import (
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    DATABASE_URL,
    validate_config,
)
from db import get_db_connection, init_and_migrate_db, mark_expired_tests_absent
from alert_utils import send_error_alert

def extract_answers_from_text(text, total_expected=15):
    numbered_matches = re.findall(r'(?:Q|Question)?\s*(\d{1,2})[\s.:)\-]*([A-Da-d])', text)
    if len(numbered_matches) >= total_expected:
        sorted_ans = sorted(numbered_matches, key=lambda x: int(x[0]))
        return [ans[1].upper() for ans in sorted_ans[:total_expected]]
    
    clean_chars = re.findall(r'[A-Da-d]', text.split('On ')[0].split('wrote:')[0])
    if len(clean_chars) >= total_expected:
        return [c.upper() for c in clean_chars[:total_expected]]
        
    return None

def send_feedback_email(date_str, score, total, pct, breakdown_html, weak_analysis_html):
    subject = f"📊 Evaluation Report - MPPSC Drill ({date_str})"
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 650px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <h2 style="color: #2b6cb0; margin-top: 0;">🎯 Performance Report: {date_str}</h2>
            <div style="font-size: 20px; font-weight: bold; background: #edf2f7; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                Score: {score} / {total} ({pct:.1f}%)
            </div>
            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">📈 Cumulative Topic Mastery</h3>
            {weak_analysis_html}
            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-top: 25px;">📝 Detailed Question Analysis</h3>
            {breakdown_html}
        </div>
    </body>
    </html>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

def main():
    try:
        if not validate_config(["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "DATABASE_URL"]):
            return

        print("[1/3] Initializing DB & checking expired tests...")
        init_and_migrate_db()
        absents = mark_expired_tests_absent()
        if absents > 0:
            print(f"      Marked {absents} past unsubmitted test(s) as ABSENT.")

        conn = get_db_connection()
        cursor = conn.cursor()

        # Read unread MPPSC emails from Inbox
        print("[2/3] Checking Gmail inbox for unread MPPSC drill replies...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(SENDER_EMAIL, APP_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, '(UNSEEN SUBJECT "MPPSC")')
        if status != "OK" or not messages[0]:
            print("      No unread MPPSC drill replies found in inbox.")
            cursor.close()
            conn.close()
            mail.close()
            mail.logout()
            return

        processed_count = 0
        for num in messages[0].split():
            res, msg_data = mail.fetch(num, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            subject = msg.get("Subject", "")

            date_match = re.search(r'\d{4}-\d{2}-\d{2}', subject)
            if not date_match: continue
            target_date = date_match.group(0)

            # Check if DB has this test AND it's not yet evaluated
            cursor.execute("""
                SELECT questions_json, total_questions 
                FROM daily_tests 
                WHERE test_date = %s AND (evaluated = FALSE OR status = 'PENDING')
            """, (target_date,))
            row = cursor.fetchone()
            if not row: continue
            
            questions = row[0]
            total_questions = row[1] or len(questions)
            
            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            user_answers = extract_answers_from_text(body, len(questions))
            if not user_answers: continue

            print(f"[3/3] Evaluating answers for quiz date: {target_date}...")
            score = 0
            breakdown_html = ""
            breakdown_records = []
            topic_updates = {}

            for i, q in enumerate(questions):
                user_ans = user_answers[i]
                correct_ans = q["correct_option"].upper()
                topic = q.get("topic", "General")

                if topic not in topic_updates:
                    topic_updates[topic] = {"att": 0, "cor": 0}
                topic_updates[topic]["att"] += 1

                is_correct = (user_ans == correct_ans)
                if is_correct:
                    score += 1
                    topic_updates[topic]["cor"] += 1
                    status_badge = "<span style='color: green;'>✅ Correct</span>"
                else:
                    status_badge = f"<span style='color: red;'>❌ Incorrect</span> (Your answer: <strong>{user_ans}</strong>, Correct: <strong>{correct_ans}</strong>)"

                breakdown_records.append({
                    "q_num": i + 1,
                    "topic": topic,
                    "question": q["question"],
                    "user_ans": user_ans,
                    "correct_ans": correct_ans,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", "")
                })

                breakdown_html += f"""
                <div style="border-bottom: 1px solid #edf2f7; padding: 10px 0;">
                    <div><strong>Q{i+1}. [{topic}]</strong> {status_badge}</div>
                    <div style="font-size: 13px; color: #4a5568; margin-top: 4px;">{q['question']}</div>
                    <div style="font-size: 13px; color: #2b6cb0; margin-top: 4px;">💡 <em>{q.get('explanation', '')}</em></div>
                </div>
                """

            pct = (score / len(questions)) * 100.0 if questions else 0.0

            # Update topic_stats in DB using Upsert
            for topic, data in topic_updates.items():
                cursor.execute("""
                    INSERT INTO topic_stats (topic, attempted, correct, accuracy, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (topic) DO UPDATE SET 
                        attempted = topic_stats.attempted + EXCLUDED.attempted,
                        correct = topic_stats.correct + EXCLUDED.correct,
                        accuracy = ((topic_stats.correct + EXCLUDED.correct)::float / (topic_stats.attempted + EXCLUDED.attempted)::float) * 100.0,
                        updated_at = CURRENT_TIMESTAMP;
                """, (topic, data["att"], data["cor"], (data["cor"] / data["att"]) * 100.0 if data["att"] > 0 else 0.0))

            # Mark test as EVALUATED in daily_tests with complete records
            cursor.execute("""
                UPDATE daily_tests 
                SET evaluated = TRUE, 
                    status = 'EVALUATED', 
                    score = %s,
                    percentage = %s,
                    user_answers_json = %s,
                    breakdown_json = %s,
                    evaluated_at = CURRENT_TIMESTAMP
                WHERE test_date = %s
            """, (score, pct, json.dumps(user_answers), json.dumps(breakdown_records), target_date))
            conn.commit()

            # Fetch all-time analytics from DB for the email report
            cursor.execute("SELECT topic, attempted, correct FROM topic_stats ORDER BY (correct::float / NULLIF(attempted, 0)) ASC")
            all_stats = cursor.fetchall()
            
            weak_analysis_html = "<table style='width: 100%; border-collapse: collapse; font-size: 14px;'><tr style='background: #f7fafc;'><th style='text-align:left; padding:8px;'>Topic</th><th style='padding:8px;'>Accuracy</th><th style='padding:8px;'>Status</th></tr>"
            for top, att, cor in all_stats:
                t_pct = (cor / att) * 100 if att > 0 else 0
                tag_color = "#e53e3e" if t_pct < 60 else "#d69e2e" if t_pct < 80 else "#38a169"
                tag_text = "🔴 Needs Focus" if t_pct < 60 else "🟡 Moderate" if t_pct < 80 else "🟢 Strong"
                weak_analysis_html += f"<tr style='border-bottom: 1px solid #edf2f7;'><td style='padding:8px;'>{top}</td><td style='padding:8px; text-align:center;'>{cor}/{att} ({t_pct:.0f}%)</td><td style='padding:8px; text-align:center; color: {tag_color}; font-weight:bold;'>{tag_text}</td></tr>"
            weak_analysis_html += "</table>"

            send_feedback_email(target_date, score, len(questions), pct, breakdown_html, weak_analysis_html)
            mail.store(num, '+FLAGS', '\\Seen')
            print(f"      [OK] Evaluated & feedback email sent for {target_date} (Score: {score}/{len(questions)} - {pct:.1f}%)")
            processed_count += 1

        cursor.close()
        conn.close()
        mail.close()
        mail.logout()

        if processed_count > 0:
            print(f"\n[OK] Successfully processed {processed_count} reply email(s)!\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to evaluate emails: {e}\n")
        send_error_alert("Email Evaluator (email_evaluator.py)", e)
        raise e

if __name__ == "__main__":
    main()