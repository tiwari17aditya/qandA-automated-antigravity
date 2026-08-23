import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import io
import json
import re
import time
import imaplib
import email
import smtplib
from datetime import datetime
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.colors import HexColor

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
    Extracts candidate answers from unstructured email reply text across multiple formats.
    """
    total_expected = len(questions)
    
    cleaned_text = re.split(r'On\s+.*wrote:|\n\s*>\s*|\n--\s*\n|Sent from my', text, flags=re.IGNORECASE)[0].strip()
    if not cleaned_text:
        cleaned_text = text.strip()

    result_answers = [None] * total_expected

    # Method 1: Check if candidate grouped answers by topics
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

    # Method 2: Standard Numbered format across whole text (e.g. 1A 2B 3C)
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

def build_eval_pdf_bytes(date_str, score, total_q, breakdown_records):
    """Generates a clean PDF document containing detailed question evaluation with all 4 options highlighted."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'EvalTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=HexColor('#2B6CB0'),
        spaceAfter=4
    )
    pct = (score / total_q) * 100.0 if total_q > 0 else 0.0
    subtitle_style = ParagraphStyle(
        'EvalSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=HexColor('#2D3748'),
        spaceAfter=12
    )

    q_header_style = ParagraphStyle(
        'QHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=HexColor('#4A5568')
    )
    q_text_style = ParagraphStyle(
        'QText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=HexColor('#1A202C'),
        spaceAfter=6
    )
    opt_normal = ParagraphStyle(
        'OptNormal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=HexColor('#2D3748')
    )
    opt_user_correct = ParagraphStyle(
        'OptUserCorrect',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=HexColor('#22543D')
    )
    opt_user_wrong = ParagraphStyle(
        'OptUserWrong',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=HexColor('#742A2A')
    )
    opt_correct_needed = ParagraphStyle(
        'OptCorrectNeeded',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=HexColor('#22543D')
    )

    exp_style = ParagraphStyle(
        'ExpText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=HexColor('#4A5568')
    )

    elements = []

    # Title & Summary Banner
    elements.append(Paragraph(f"📊 Detailed Solution Report - {date_str}", title_style))
    elements.append(Paragraph(f"Final Score: {score} / {total_q} ({pct:.1f}%)", subtitle_style))
    elements.append(Spacer(1, 10))

    # Questions Breakdown
    for rec in breakdown_records:
        q_num = rec.get('q_num', 1)
        topic = rec.get('topic', 'General')
        q_text = rec.get('question', '')
        options = rec.get('options', {})
        user_ans = rec.get('user_ans')
        correct_ans = str(rec.get('correct_ans', '')).upper()
        is_correct = rec.get('is_correct', False)
        explanation = rec.get('explanation', '')

        if user_ans is not None:
            user_ans = str(user_ans).upper()

        if user_ans and is_correct:
            badge_text = "<font color='#22543D'><b>✅ CORRECT</b></font>"
            border_color = HexColor('#38A169')
            bg_card = HexColor('#F0FFF4')
        elif user_ans and not is_correct:
            badge_text = f"<font color='#742A2A'><b>❌ INCORRECT (Your Answer: {user_ans} | Correct: {correct_ans})</b></font>"
            border_color = HexColor('#E53E3E')
            bg_card = HexColor('#FFF5F5')
        else:
            badge_text = f"<font color='#4A5568'><b>⚪ UNATTEMPTED (Correct: {correct_ans})</b></font>"
            border_color = HexColor('#CBD5E0')
            bg_card = HexColor('#FAFAFA')

        card_elements = [
            Paragraph(f"Q{q_num}. [{topic}] &bull; {badge_text}", q_header_style),
            Spacer(1, 4),
            Paragraph(q_text, q_text_style),
            Spacer(1, 4)
        ]

        opt_table_rows = []
        for opt_key in ['A', 'B', 'C', 'D']:
            opt_val = options.get(opt_key, '')
            is_user_choice = (user_ans == opt_key)
            is_right_choice = (correct_ans == opt_key)

            if is_user_choice and is_right_choice:
                cell_bg = HexColor('#C6F6D5')
                txt = Paragraph(f"✅ <b>({opt_key}) {opt_val}</b> &mdash; <i>Your Choice (Correct)</i>", opt_user_correct)
            elif is_user_choice and not is_right_choice:
                cell_bg = HexColor('#FED7D7')
                txt = Paragraph(f"❌ <b>({opt_key}) {opt_val}</b> &mdash; <i>Your Choice (Incorrect)</i>", opt_user_wrong)
            elif not is_user_choice and is_right_choice:
                cell_bg = HexColor('#C6F6D5')
                txt = Paragraph(f"✔️ <b>({opt_key}) {opt_val}</b> &mdash; <i>Correct Answer</i>", opt_correct_needed)
            else:
                cell_bg = HexColor('#FFFFFF')
                txt = Paragraph(f"({opt_key}) {opt_val}", opt_normal)

            opt_table_rows.append(([txt], cell_bg))

        table_data = [[item[0][0]] for item in opt_table_rows]
        opt_table = Table(table_data, colWidths=[500])
        
        t_style = [
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, HexColor('#E2E8F0')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]
        for row_idx, item in enumerate(opt_table_rows):
            t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), item[1]))

        opt_table.setStyle(TableStyle(t_style))
        card_elements.append(opt_table)

        if explanation:
            card_elements.append(Spacer(1, 4))
            card_elements.append(Paragraph(f"💡 <b>Explanation:</b> <i>{explanation}</i>", exp_style))

        card_table = Table([[card_elements]], colWidths=[520])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), bg_card),
            ('BOX', (0, 0), (-1, -1), 1, border_color),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(card_table)
        elements.append(Spacer(1, 10))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def send_feedback_email(date_str, score, total, pct, weak_analysis_html, breakdown_records=None, is_absent=False):
    msg = MIMEMultipart()
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL

    if is_absent:
        subject = f"❌ Absent Notice - MPPSC Drill ({date_str})"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
            <div style="max-width: 650px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="border-bottom: 2px solid #e53e3e; padding-bottom: 10px; margin-bottom: 15px;">
                    <h2 style="color: #c53030; margin: 0;">❌ Absent Notice - MPPSC Drill ({date_str})</h2>
                </div>

                <div style="background-color: #fff5f5; border-left: 4px solid #e53e3e; padding: 14px; margin-bottom: 20px; font-size: 14px; color: #742a2a; line-height: 1.5;">
                    <strong>⚠️ You were marked ABSENT for the drill on {date_str}.</strong><br>
                    No response was received before the midnight cutoff.
                    <br><br>
                    <em>Note: Solution PDF report is not attached for unattempted drills.</em>
                </div>

                <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">📈 Cumulative Topic Mastery</h3>
                {weak_analysis_html}

                <div style="background-color: #edf2f7; padding: 12px; border-radius: 6px; font-size: 13px; color: #4a5568; margin-top: 20px;">
                    💡 <strong>Streak Tip:</strong> Reply to today's daily drill email before midnight to maintain your active study streak!
                </div>
            </div>
        </body>
        </html>
        """
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))
    else:
        subject = f"📊 Evaluation Report - MPPSC Drill ({date_str})"
        filename = f"MPPSC_Evaluation_Report_{date_str}.pdf"
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
            <div style="max-width: 650px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
                <h2 style="color: #2b6cb0; margin-top: 0;">🎯 Performance Report: {date_str}</h2>
                <div style="font-size: 20px; font-weight: bold; background: #edf2f7; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                    Score: {score} / {total} ({pct:.1f}%)
                </div>

                <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 20px; font-size: 14px;">
                    <strong>📎 Downloadable Detailed Solution PDF Attached!</strong><br>
                    Please open the attached <code>{filename}</code> document to inspect all 4 options, your selection highlights (Red/Green), and complete answer explanations.
                </div>

                <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">📈 Cumulative Topic Mastery</h3>
                {weak_analysis_html}
            </div>
        </body>
        </html>
        """
        msg["Subject"] = subject
        msg.attach(MIMEText(html, "html"))

        if breakdown_records:
            pdf_bytes = build_eval_pdf_bytes(date_str, score, total, breakdown_records)
            pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
            msg.attach(pdf_attachment)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            print(f"      Feedback email sent successfully for {date_str}!")
            return
        except Exception as smtp_err:
            print(f"      [WARN] Feedback SMTP Attempt {attempt}/{max_retries} failed: {smtp_err}")
            if attempt == max_retries:
                raise smtp_err
            time.sleep(3)

def main():
    try:
        validate_config(["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "DATABASE_URL"])

        print("[1/3] Initializing DB & checking schema...")
        init_and_migrate_db()

        # Check and notify any absent expired tests
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check newly expired pending tests
        cursor.execute("""
            SELECT test_date, total_questions 
            FROM daily_tests 
            WHERE test_date < CURRENT_DATE 
              AND evaluated = FALSE 
              AND (status = 'PENDING' OR status IS NULL);
        """)
        pending_absents = cursor.fetchall()
        
        absents = mark_expired_tests_absent()
        if absents > 0:
            print(f"      Marked {absents} previous unreplied test(s) as ABSENT.")
            
            # Send absent emails for newly marked absent tests
            cursor.execute("SELECT topic, attempted, correct FROM topic_stats ORDER BY (correct::float / NULLIF(attempted, 0)) ASC")
            all_stats = cursor.fetchall()
            
            weak_analysis_html = "<table style='width: 100%; border-collapse: collapse; font-size: 14px;'><tr style='background: #f7fafc;'><th style='text-align:left; padding:8px;'>Topic</th><th style='padding:8px;'>Accuracy</th><th style='padding:8px;'>Status</th></tr>"
            for top, att, cor in all_stats:
                t_pct = (cor / att) * 100 if att > 0 else 0
                tag_color = "#e53e3e" if t_pct < 60 else "#d69e2e" if t_pct < 80 else "#38a169"
                tag_text = "🔴 Needs Focus" if t_pct < 60 else "🟡 Moderate" if t_pct < 80 else "🟢 Strong"
                weak_analysis_html += f"<tr style='border-bottom: 1px solid #edf2f7;'><td style='padding:8px;'>{top}</td><td style='padding:8px; text-align:center;'>{cor}/{att} ({t_pct:.0f}%)</td><td style='padding:8px; text-align:center; color: {tag_color}; font-weight:bold;'>{tag_text}</td></tr>"
            weak_analysis_html += "</table>"

            for abs_date, abs_total in pending_absents:
                abs_date_str = str(abs_date)
                send_feedback_email(abs_date_str, 0, abs_total or 15, 0.0, weak_analysis_html, is_absent=True)

        # Connect to Gmail IMAP for replies
        print("[2/3] Checking Gmail IMAP for MPPSC drill replies...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(SENDER_EMAIL, APP_PASSWORD)
        
        for f in ["\"[Gmail]/All Mail\"", "inbox"]:
            res, _ = mail.select(f)
            if res == "OK":
                break

        status, messages = mail.search(None, '(SUBJECT "MPPSC")')
        if status != "OK" or not messages[0]:
            print("      No MPPSC drill emails found in mailbox.")
            cursor.close()
            conn.close()
            mail.close()
            mail.logout()
            return

        email_ids = messages[0].split()
        recent_ids = list(reversed(email_ids))[:20]

        processed_count = 0
        for num in recent_ids:
            res, h_data = mail.fetch(num, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
            if not h_data or not h_data[0] or not isinstance(h_data[0], tuple):
                continue
            h_msg = email.message_from_bytes(h_data[0][1])
            raw_subject = h_msg.get("Subject", "")
            subject = decode_email_subject(raw_subject)

            if subject.startswith("📊") or subject.startswith("❌") or "alert" in subject.lower():
                continue

            date_match = re.search(r'\d{4}-\d{2}-\d{2}', subject)
            if not date_match:
                continue
            target_date = date_match.group(0)

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

            if is_evaluated and current_status == 'EVALUATED':
                continue

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
                else:
                    is_correct = False

                breakdown_records.append({
                    "q_num": i + 1,
                    "topic": topic,
                    "question": q.get("question", ""),
                    "options": q.get("options", {}),
                    "user_ans": user_ans,
                    "correct_ans": correct_ans,
                    "is_correct": is_correct,
                    "explanation": q.get("explanation", "")
                })

            pct = (score / len(questions)) * 100.0 if questions else 0.0

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

            cursor.execute("SELECT topic, attempted, correct FROM topic_stats ORDER BY (correct::float / NULLIF(attempted, 0)) ASC")
            all_stats = cursor.fetchall()
            
            weak_analysis_html = "<table style='width: 100%; border-collapse: collapse; font-size: 14px;'><tr style='background: #f7fafc;'><th style='text-align:left; padding:8px;'>Topic</th><th style='padding:8px;'>Accuracy</th><th style='padding:8px;'>Status</th></tr>"
            for top, att, cor in all_stats:
                t_pct = (cor / att) * 100 if att > 0 else 0
                tag_color = "#e53e3e" if t_pct < 60 else "#d69e2e" if t_pct < 80 else "#38a169"
                tag_text = "🔴 Needs Focus" if t_pct < 60 else "🟡 Moderate" if t_pct < 80 else "🟢 Strong"
                weak_analysis_html += f"<tr style='border-bottom: 1px solid #edf2f7;'><td style='padding:8px;'>{top}</td><td style='padding:8px; text-align:center;'>{cor}/{att} ({t_pct:.0f}%)</td><td style='padding:8px; text-align:center; color: {tag_color}; font-weight:bold;'>{tag_text}</td></tr>"
            weak_analysis_html += "</table>"

            send_feedback_email(target_date, score, len(questions), pct, weak_analysis_html, breakdown_records=breakdown_records, is_absent=False)
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