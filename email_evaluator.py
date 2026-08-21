import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import re
import imaplib
import email
import smtplib
from datetime import datetime
from email.header import decode_header
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

def decode_email_subject(raw_subj):
    """Decodes MIME encoded subject headers (RFC 2047)."""
    if not raw_subj:
        return ""
    try:
        decoded_parts = decode_header(raw_subj)
        subj = ""
        for text, charset in decoded_parts:
            if isinstance(text, bytes):
                subj += text.decode(charset or "utf-8", errors="ignore")
            else:
                subj += str(text)
        return subj
    except Exception:
        return str(raw_subj)

def extract_answers_from_text(text, questions):
    """
    Extracts candidate answers from unstructured email reply text across multiple formats:
    1. Topic-grouped: "<Topic 1> ABCD... <Topic 2> ABCD..." or "Topic: a, b, c, d"
    2. Numbered/Keyed: "1A 2B 3C", "1. A\n2. B", "Q1: A, Q2: B", "1) a"
    3. Character stream: "CBBBBCDCCDDCDBCCACCACBCACBABCB"
    4. Delimited: "A, B, C, D, ..." or "A B C D ..."
    5. Partial submissions (skipping questions mapped properly).
    6. AI fallback: If regex fails or answers < 50% found, uses AI completion to extract JSON answers.
    """
    total_expected = len(questions)
    
    # 0. Clean quoted text and email trails
    cleaned_text = re.split(r'On\s+.*wrote:|\n\s*>\s*|\n--\s*\n|Sent from my', text, flags=re.IGNORECASE)[0].strip()
    if not cleaned_text:
        cleaned_text = text.strip()

    result_answers = [None] * total_expected

    # Method 1: Check if candidate grouped answers by topics
    # e.g., "<Indus Valley Civilization> CBBBB..." or "ICT: a, b, c, d"
    topic_blocks = re.findall(r'(?:<|\[|Topic:?|\b)([a-zA-Z0-9\s\-&,]+)(?:>|\]|:|\-)\s*([A-Da-d\s,.\d\(\)]+)', cleaned_text)
    if topic_blocks:
        topic_q_indices = {}
        for idx, q in enumerate(questions):
            t_name = q.get("topic", "").lower().strip()
            topic_q_indices.setdefault(t_name, []).append(idx)
        
        mapped_count = 0
        for block_topic, block_ans_str in topic_blocks:
            norm_bt = block_topic.lower().strip()
            best_match_key = None
            for tk in topic_q_indices:
                if tk in norm_bt or norm_bt in tk or any(w in norm_bt for w in tk.split() if len(w) > 3):
                    best_match_key = tk
                    break
            
            numbered_in_block = re.findall(r'(?:Q|Question)?\s*(\d{1,2})[\s.:)\-]*([A-Da-d])', block_ans_str)
            if numbered_in_block:
                for q_num_str, opt in numbered_in_block:
                    q_num = int(q_num_str)
                    if 1 <= q_num <= total_expected:
                        result_answers[q_num - 1] = opt.upper()
                        mapped_count += 1
            else:
                pure_chars = [c.upper() for c in re.findall(r'\b[A-Da-d]\b|[A-Da-d]', block_ans_str)]
                if best_match_key and pure_chars:
                    target_indices = topic_q_indices[best_match_key]
                    for i, char in enumerate(pure_chars):
                        if i < len(target_indices):
                            result_answers[target_indices[i]] = char
                            mapped_count += 1
        
        if mapped_count >= (total_expected // 2):
            return result_answers

    # Method 2: Standard Numbered format across whole text (e.g. 1A 2B 3C or 1. A 2. B or Q1: C)
    numbered_matches = re.findall(r'(?:Q|Question)?\s*(\d{1,2})[\s.:)\-]*([A-Da-d])', cleaned_text)
    if numbered_matches:
        num_found = 0
        for q_num_str, opt in numbered_matches:
            q_num = int(q_num_str)
            if 1 <= q_num <= total_expected:
                result_answers[q_num - 1] = opt.upper()
                num_found += 1
        if num_found >= 3:
            return result_answers

    # Method 3: Continuous character stream or space/comma separated letters
    lines = cleaned_text.splitlines()
    candidate_chars = []
    for line in lines:
        l_strip = line.strip()
        if re.search(r'\b(aditya|tiwari|thanks|regards|hello|hi|dear|sent|from)\b', l_strip, re.IGNORECASE):
            continue
        chars = re.findall(r'[A-Da-d]', l_strip)
        if len(chars) > 0 and (len(chars) / max(len(l_strip.replace(" ", "").replace(",", "").replace(".", "")), 1)) >= 0.7:
            candidate_chars.extend(chars)

    if len(candidate_chars) >= 3:
        for idx in range(min(len(candidate_chars), total_expected)):
            result_answers[idx] = candidate_chars[idx].upper()
        return result_answers

    # Method 4: AI Fallback Parser
    try:
        from alert_utils import generate_ai_completion, clean_ai_json_output
        ai_prompt = f"""
        Extract the candidate's answers from this email reply for {total_expected} questions.
        Email text:
        \"\"\"{cleaned_text}\"\"\"

        Return ONLY a JSON object mapping question number string to option letter (A, B, C, or D):
        {{"1": "A", "2": "C", ...}}
        """
        raw_ai = generate_ai_completion(prompt=ai_prompt, response_json=True)
        cleaned_json = clean_ai_json_output(raw_ai)
        parsed_dict = json.loads(cleaned_json)
        if isinstance(parsed_dict, dict):
            if "answers" in parsed_dict and isinstance(parsed_dict["answers"], dict):
                parsed_dict = parsed_dict["answers"]
            ai_found = 0
            for k, v in parsed_dict.items():
                try:
                    q_idx = int(k) - 1
                    if 0 <= q_idx < total_expected and str(v).upper() in ["A", "B", "C", "D"]:
                        result_answers[q_idx] = str(v).upper()
                        ai_found += 1
                except ValueError:
                    continue
            if ai_found > 0:
                return result_answers
    except Exception as parse_err:
        print(f"[WARN] AI answer parser fallback encountered error: {parse_err}")

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
    msg["X-Priority"] = "3"
    msg["Importance"] = "Normal"
    msg["Priority"] = "Normal"
    msg["Auto-Submitted"] = "auto-generated"
    msg["Precedence"] = "bulk"
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

def main():
    try:
        validate_config(["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "DATABASE_URL"])

        print("[1/3] Initializing DB & checking schema...")
        init_and_migrate_db()

        conn = get_db_connection()
        cursor = conn.cursor()

        # Connect to Gmail IMAP
        print("[2/3] Checking Gmail IMAP for MPPSC drill replies...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(SENDER_EMAIL, APP_PASSWORD)
        
        # Select "[Gmail]/All Mail" so replies in sent/threads/inbox are all captured, fallback to inbox
        for f in ["\"[Gmail]/All Mail\"", "inbox"]:
            res, _ = mail.select(f)
            if res == "OK":
                break

        # Search across all MPPSC emails
        status, messages = mail.search(None, '(SUBJECT "MPPSC")')
        if status != "OK" or not messages[0]:
            print("      No MPPSC drill emails found in mailbox.")
            cursor.close()
            conn.close()
            mail.close()
            mail.logout()
            return

        email_ids = messages[0].split()
        # Process recent 20 emails backwards
        recent_ids = list(reversed(email_ids))[:20]

        processed_count = 0
        for num in recent_ids:
            # Fast header peek
            res, h_data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if not h_data or not h_data[0] or not isinstance(h_data[0], tuple):
                continue
            h_msg = email.message_from_bytes(h_data[0][1])
            raw_subject = h_msg.get("Subject", "")
            subject = decode_email_subject(raw_subject)

            # Skip automated reports and alerts
            if subject.startswith("📊") or "alert" in subject.lower():
                continue

            date_match = re.search(r'\d{4}-\d{2}-\d{2}', subject)
            if not date_match:
                continue
            target_date = date_match.group(0)

            # Check if DB has this test AND (it is not evaluated OR was marked absent/pending)
            cursor.execute("""
                SELECT questions_json, total_questions, evaluated, status 
                FROM daily_tests 
                WHERE test_date = %s
            """, (target_date,))
            row = cursor.fetchone()
            if not row:
                continue
            
            questions = row[0]
            total_questions = row[1] or len(questions)
            is_evaluated = row[2]
            current_status = row[3]

            # If already evaluated and completed with status=EVALUATED, skip
            if is_evaluated and current_status == 'EVALUATED':
                continue

            # Fetch full email body for candidate reply
            res, b_data = mail.fetch(num, "(RFC822)")
            if not b_data or not b_data[0] or not isinstance(b_data[0], tuple):
                continue
            msg = email.message_from_bytes(b_data[0][1])

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            user_answers = extract_answers_from_text(body, questions)
            if not user_answers or all(a is None for a in user_answers):
                continue

            print(f"[3/3] Evaluating answers for quiz date: {target_date}...")
            score = 0
            breakdown_html = ""
            breakdown_records = []
            topic_updates = {}

            for i, q in enumerate(questions):
                user_ans = user_answers[i] if i < len(user_answers) else None
                correct_ans = str(q.get("correct_option", "")).upper()
                topic = q.get("topic", "General")

                if topic not in topic_updates:
                    topic_updates[topic] = {"att": 0, "cor": 0}

                if user_ans is not None:
                    topic_updates[topic]["att"] += 1
                    is_correct = (str(user_ans).upper() == correct_ans)
                    if is_correct:
                        score += 1
                        topic_updates[topic]["cor"] += 1
                        status_badge = "<span style='color: #276749; font-weight: bold;'>✅ Correct</span>"
                    else:
                        status_badge = f"<span style='color: #c53030; font-weight: bold;'>❌ Incorrect</span> (Your answer: <strong>{user_ans}</strong>, Correct: <strong>{correct_ans}</strong>)"
                else:
                    is_correct = False
                    status_badge = f"<span style='color: #718096; font-style: italic;'>⚪ Unattempted</span> (Correct: <strong>{correct_ans}</strong>)"

                breakdown_records.append({
                    "q_num": i + 1,
                    "topic": topic,
                    "question": q.get("question", ""),
                    "user_ans": user_ans,
                    "correct_ans": correct_ans,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", "")
                })

                breakdown_html += f"""
                <div style="border-bottom: 1px solid #edf2f7; padding: 10px 0;">
                    <div><strong>Q{i+1}. [{topic}]</strong> {status_badge}</div>
                    <div style="font-size: 13px; color: #4a5568; margin-top: 4px;">{q.get('question', '')}</div>
                    <div style="font-size: 13px; color: #2b6cb0; margin-top: 4px;">💡 <em>{q.get('explanation', '')}</em></div>
                </div>
                """

            pct = (score / len(questions)) * 100.0 if questions else 0.0

            # Update topic_stats in DB using Upsert
            for topic, data in topic_updates.items():
                if data["att"] > 0:
                    cursor.execute("""
                        INSERT INTO topic_stats (topic, attempted, correct, accuracy, updated_at)
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (topic) DO UPDATE SET 
                            attempted = topic_stats.attempted + EXCLUDED.attempted,
                            correct = topic_stats.correct + EXCLUDED.correct,
                            accuracy = ((topic_stats.correct + EXCLUDED.correct)::float / (topic_stats.attempted + EXCLUDED.attempted)::float) * 100.0,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (topic, data["att"], data["cor"], (data["cor"] / data["att"]) * 100.0))

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