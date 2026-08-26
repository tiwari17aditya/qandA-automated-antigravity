import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import io
import json
import time
import smtplib
from datetime import datetime
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
    GEMINI_API_KEY,
    TOTAL_QUESTIONS,
    GEMINI_MODEL,
    TOPICS,
    QUESTIONS_PER_TOPIC,
    get_quiz_prompt,
    get_pipeline_configs,
    get_quiz_prompt_for_pipeline,
    validate_config,
)
from db import get_db_connection, init_and_migrate_db, mark_expired_tests_absent
from alert_utils import send_error_alert, generate_ai_completion, clean_ai_json_output

from logger_utils import get_pipeline_logger
import os
import sys
import argparse

def generate_questions_for_pipeline(pipe_cfg, logger=None):
    pipeline_id = pipe_cfg.get("pipeline_id", "mppsc_default")
    if logger is None:
        logger = get_pipeline_logger("daily_quiz", pipeline_id)
        
    prompt = get_quiz_prompt_for_pipeline(pipe_cfg)
    exam_name = pipe_cfg.get("exam_name", "Competitive Exam")
    topic_desc = pipe_cfg.get("topics") or f"General {exam_name} Mix"
    student_name = pipe_cfg.get("student_name", "Candidate")
    logger.info(f"Generating questions with AI for {student_name} ({exam_name} - {topic_desc})...")
    
    raw_response = generate_ai_completion(
        prompt=prompt,
        response_json=True
    )
    cleaned_json = clean_ai_json_output(raw_response)
    questions = json.loads(cleaned_json)
    if isinstance(questions, dict):
        for key in ["questions", "data", "quiz", "mcqs", "items"]:
            if key in questions and isinstance(questions[key], list):
                questions = questions[key]
                break
        else:
            for v in questions.values():
                if isinstance(v, list):
                    questions = v
                    break
    if not isinstance(questions, list):
        raise ValueError("AI response did not return a valid list of questions.")
        
    # Ensure fallback unified question/options keys for bilingual items if missing
    for q in questions:
        if "question" not in q:
            q_en = q.get("question_en", "")
            q_hi = q.get("question_hi", "")
            q["question"] = f"{q_en}\n({q_hi})" if q_en and q_hi else (q_en or q_hi)
        if "options" not in q:
            opts_en = q.get("options_en", {})
            opts_hi = q.get("options_hi", {})
            unified_opts = {}
            for k in ["A", "B", "C", "D"]:
                val_en = opts_en.get(k, "")
                val_hi = opts_hi.get(k, "")
                unified_opts[k] = f"{val_en} / {val_hi}" if val_en and val_hi else (val_en or val_hi)
            q["options"] = unified_opts

    logger.info(f"Generated {len(questions)} questions successfully.")
    return questions

from pdf_font_utils import register_unicode_fonts

def is_hindi_text(text):
    return any('\u0900' <= char <= '\u097f' for char in str(text))

def build_quiz_pdf_bytes(date_str, topic_desc, questions, exam_name="MPPSC"):
    """Generates a clean PDF document containing Daily Quiz questions with proper multi-language font rendering."""
    font_reg, font_bold = register_unicode_fonts()
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
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=HexColor('#2B6CB0'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=HexColor('#4A5568'),
        spaceAfter=12
    )
    instruction_style = ParagraphStyle(
        'InstructionText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=HexColor('#2C5282')
    )
    q_header_style = ParagraphStyle(
        'QHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=HexColor('#2B6CB0')
    )
    q_text_eng = ParagraphStyle(
        'QTextEng',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=HexColor('#1A202C'),
        spaceAfter=4
    )
    q_text_dev = ParagraphStyle(
        'QTextDev',
        parent=styles['Normal'],
        fontName=font_bold,
        fontSize=10.5,
        leading=14,
        textColor=HexColor('#2D3748'),
        spaceAfter=6
    )
    opt_eng = ParagraphStyle(
        'OptEng',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=HexColor('#2D3748')
    )
    opt_dev = ParagraphStyle(
        'OptDev',
        parent=styles['Normal'],
        fontName=font_reg,
        fontSize=9.5,
        leading=13,
        textColor=HexColor('#2D3748')
    )

    elements = []

    # Title & Header
    elements.append(Paragraph(f"🎯 {exam_name} Daily Drill - {date_str}", title_style))
    elements.append(Paragraph(f"Focus: {topic_desc} &bull; Total Questions: {len(questions)}", subtitle_style))
    
    # Submission Tip Banner
    banner_data = [[
        Paragraph("📌 <b>Submission Format:</b> Reply directly to the quiz email with your answers (e.g. <code>1A 2C 3B...</code> or <code>ABCD...</code>) before midnight for evaluation.", instruction_style)
    ]]
    banner_table = Table(banner_data, colWidths=[520])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#EBF8FF')),
        ('BOX', (0, 0), (-1, -1), 1, HexColor('#3182CE')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 15))

    # Questions Loop
    for q in questions:
        q_num = q.get('q_num', 1)
        topic = q.get('topic', 'General')
        
        q_en = q.get('question_en', '')
        q_hi = q.get('question_hi', '')
        q_text = q.get('question', '')
        
        options_en = q.get('options_en', {})
        options_hi = q.get('options_hi', {})
        options = q.get('options', {})

        q_elements = [
            Paragraph(f"Q{q_num}. [{topic}]", q_header_style),
            Spacer(1, 3),
        ]

        if q_en and q_hi:
            q_elements.append(Paragraph(q_en, q_text_eng))
            q_elements.append(Paragraph(q_hi, q_text_dev))
        else:
            if is_hindi_text(q_text):
                q_elements.append(Paragraph(q_text, q_text_dev))
            else:
                q_elements.append(Paragraph(q_text, q_text_eng))

        q_elements.append(Spacer(1, 4))

        opt_rows = []
        for opt_key in ['A', 'B', 'C', 'D']:
            val_en = options_en.get(opt_key, '')
            val_hi = options_hi.get(opt_key, '')
            opt_val = options.get(opt_key, '')

            if val_en and val_hi:
                opt_paragraph = Paragraph(f'<b>({opt_key})</b> {val_en}<br/>&nbsp;&nbsp;&nbsp;&nbsp;<font name="{font_reg}"><i>{val_hi}</i></font>', opt_eng)
            elif is_hindi_text(opt_val):
                opt_paragraph = Paragraph(f'<font name="Helvetica-Bold"><b>({opt_key})</b></font> {opt_val}', opt_dev)
            else:
                opt_paragraph = Paragraph(f'<b>({opt_key})</b> {opt_val}', opt_eng)
            opt_rows.append([opt_paragraph])

        opt_table = Table(opt_rows, colWidths=[500])
        opt_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#FAFAFA')),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor('#E2E8F0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, HexColor('#EDF2F7')),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        q_elements.append(opt_table)

        card_table = Table([[q_elements]], colWidths=[520])
        card_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor('#FFFFFF')),
            ('BOX', (0, 0), (-1, -1), 1, HexColor('#CBD5E0')),
            ('PADDING', (0, 0), (-1, -1), 10),
        ]))
        elements.append(card_table)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

def create_html_email(date_str, questions, topic_desc, exam_name="MPPSC", student_name="Candidate"):
    clean_exam_name = exam_name.replace(" ", "_")
    filename = f"{clean_exam_name}_Daily_Drill_{date_str}.pdf"
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 2px solid #3182ce; padding-bottom: 10px; margin-bottom: 20px;">
                <h2 style="color: #2b6cb0; margin: 0;">🎯 {exam_name} Daily Drill - Hello {student_name}!</h2>
                <p style="color: #718096; margin: 5px 0 0 0;">Date: {date_str} &bull; {len(questions)} Questions &bull; Focus: {topic_desc}</p>
            </div>

            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 14px; margin-bottom: 20px; font-size: 14px; line-height: 1.6;">
                <strong>📎 Downloadable Quiz PDF Attached!</strong><br>
                Please open the attached <code>{filename}</code> document to view today's complete set of drill questions and options.
                <br><br>
                <strong>📌 Supported Reply Formats (Uppercase or Lowercase A/a/B/b):</strong>
                <ul style="margin: 6px 0; padding-left: 20px; color: #2d3748;">
                    <li><b>Format 1 (Continuous Stream):</b> <code>ABCDBADCB...</code> or <code>abcdbadcb...</code> (use <code>.</code> or <code>_</code> for unattempted)</li>
                    <li><b>Format 2 (Numbered Format):</b> <code>1A 2C 3A 4B...</code> or <code>1.a 2.c 3.b...</code></li>
                    <li><b>Format 3 (Topic-Separated Blocks):</b> <code>abcd | bcda | cadb</code> (use <code>|</code>, <code>/</code>, or <code>,</code> between topics)</li>
                </ul>
                <small style="color: #4a5568;">⏰ Please submit before midnight for automated evaluation & detailed solution PDF.</small>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(subject, html_content, pdf_bytes, filename, receiver_email, logger=None):
    if logger:
        logger.info(f"Sending quiz email to {receiver_email}...")
    else:
        print(f"   Sending quiz email to {receiver_email}...")

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email

    msg.attach(MIMEText(html_content, "html"))

    if pdf_bytes:
        pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(pdf_attachment)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
            if logger:
                logger.info("Email sent successfully!")
            else:
                print("      Email sent successfully!")
            return
        except Exception as smtp_err:
            if logger:
                logger.warning(f"SMTP Attempt {attempt}/{max_retries} failed: {smtp_err}")
            else:
                print(f"      [WARN] SMTP Attempt {attempt}/{max_retries} failed: {smtp_err}")
            if attempt == max_retries:
                raise smtp_err
            time.sleep(3)

def run_pipeline_daily_quiz(pipe_cfg, dry_run=False):
    pipeline_id = pipe_cfg.get("pipeline_id", "mppsc_default")
    student_name = pipe_cfg.get("student_name", "Candidate")
    receiver_email = pipe_cfg.get("receiver_email")
    exam_name = pipe_cfg.get("exam_name", "MPPSC")
    topic_desc = pipe_cfg.get("topics") or f"General {exam_name} Mix"

    logger = get_pipeline_logger("daily_quiz", pipeline_id)

    if not receiver_email:
        logger.warning(f"No receiver_email configured for pipeline: {pipeline_id}. Skipping.")
        return

    logger.info(f"Running Daily Quiz Pipeline for {student_name} ({exam_name}) [Dry-Run: {dry_run}]")

    today_str = datetime.now().strftime("%Y-%m-%d")
    test_id = f"{pipeline_id.upper()}_{today_str}"

    # 1. Generate questions for this specific pipeline
    questions = generate_questions_for_pipeline(pipe_cfg, logger=logger)

    # 2. Build PDF document
    clean_exam_name = exam_name.replace(" ", "_")
    pdf_filename = f"{clean_exam_name}_Daily_Drill_{today_str}.pdf"
    pdf_bytes = build_quiz_pdf_bytes(today_str, topic_desc, questions, exam_name=exam_name)

    if dry_run:
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(logs_dir, exist_ok=True)
        out_pdf_path = os.path.join(logs_dir, f"dryrun_{pipeline_id}_{pdf_filename}")
        with open(out_pdf_path, "wb") as f:
            f.write(pdf_bytes)
        logger.info(f"[DRY-RUN COMPLETE] Generated {len(questions)} questions & saved test PDF locally to: {out_pdf_path}. (Zero DB modifications, Zero emails sent)")
        return

    # 3. Save to database with pipeline_id
    logger.info("Saving questions to database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO daily_tests (test_id, pipeline_id, test_date, topics, questions_json, evaluated, status, total_questions)
        VALUES (%s, %s, %s, %s, %s, FALSE, 'PENDING', %s)
        ON CONFLICT (pipeline_id, test_date) DO UPDATE SET 
            topics = EXCLUDED.topics,
            questions_json = EXCLUDED.questions_json,
            total_questions = EXCLUDED.total_questions,
            status = 'PENDING';
    """, (test_id, pipeline_id, today_str, topic_desc, json.dumps(questions), len(questions)))
    conn.commit()
    cursor.close()
    conn.close()
    logger.info(f"Saved to daily_tests table as PENDING for pipeline [{pipeline_id}].")

    # 4. Dispatch Email
    drill_key = f"DRILL-{today_str.replace('-', '')}"
    subject = f"🎯 [{exam_name}] Daily Drill - {today_str} [{drill_key}]"
    html_body = create_html_email(today_str, questions, topic_desc, exam_name=exam_name, student_name=student_name)
    send_email(subject, html_body, pdf_bytes, pdf_filename, receiver_email, logger=logger)
    logger.info(f"Daily Quiz for {student_name} ({exam_name}) sent and recorded successfully!")

def main():
    parser = argparse.ArgumentParser(description="Send Daily Quiz across student pipelines.")
    parser.add_argument("--pipeline", type=str, help="Specific pipeline_id to run (e.g. ctet_swati or mppsc_default)")
    parser.add_argument("--dry-run", action="store_true", help="Safe dry-run testing mode (No DB updates, No emails sent)")
    args = parser.parse_args()

    global_logger = get_pipeline_logger("daily_quiz", "system")

    try:
        if not args.dry_run:
            validate_config(["SENDER_EMAIL", "APP_PASSWORD", "DATABASE_URL"])
            global_logger.info("Initializing PostgreSQL database tables & checking pending tests...")
            init_and_migrate_db()
        else:
            global_logger.info("[SAFE DRY-RUN MODE] Skipping live DB init & mandatory credential checks.")

        active_pipelines = get_pipeline_configs(only_enabled=True)
        if args.pipeline:
            active_pipelines = [p for p in active_pipelines if p.get("pipeline_id") == args.pipeline]

        if not active_pipelines:
            global_logger.warning("No active pipelines configured to run.")
            return

        for pipe_cfg in active_pipelines:
            pipe_id = pipe_cfg.get("pipeline_id", "mppsc_default")
            if not args.dry_run:
                mark_expired_tests_absent(pipe_id)
            run_pipeline_daily_quiz(pipe_cfg, dry_run=args.dry_run)

        global_logger.info("Daily Quiz execution finished for all target pipelines!")

    except Exception as e:
        global_logger.error(f"Failed to send daily quiz: {e}")
        if not args.dry_run:
            send_error_alert("Daily Quiz Sender (daily_quiz_sender.py)", e)
        raise e

if __name__ == "__main__":
    main()