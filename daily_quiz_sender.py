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

import sys
import argparse

def generate_questions_for_pipeline(pipe_cfg):
    prompt = get_quiz_prompt_for_pipeline(pipe_cfg)
    exam_name = pipe_cfg.get("exam_name", "Competitive Exam")
    topic_desc = pipe_cfg.get("topics") or f"General {exam_name} Mix"
    student_name = pipe_cfg.get("student_name", "Candidate")
    print(f"   Generating questions with AI for {student_name} ({exam_name} - {topic_desc})...")
    
    raw_response = generate_ai_completion(
        prompt=prompt,
        response_json=True
    )
    cleaned_json = clean_ai_json_output(raw_response)
    questions = json.loads(cleaned_json)
    print(f"   Generated {len(questions)} questions successfully.")
    return questions

def build_quiz_pdf_bytes(date_str, topic_desc, questions, exam_name="MPPSC"):
    """Generates a clean PDF document containing Daily Quiz questions."""
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
        fontName='Helvetica-Oblique',
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
    q_text_style = ParagraphStyle(
        'QText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=HexColor('#1A202C'),
        spaceAfter=6
    )
    opt_style = ParagraphStyle(
        'OptText',
        parent=styles['Normal'],
        fontName='Helvetica',
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
        q_text = q.get('question', '')
        options = q.get('options', {})

        q_elements = [
            Paragraph(f"Q{q_num}. [{topic}]", q_header_style),
            Spacer(1, 3),
            Paragraph(q_text, q_text_style),
            Spacer(1, 4)
        ]

        opt_rows = []
        for opt_key in ['A', 'B', 'C', 'D']:
            opt_val = options.get(opt_key, '')
            opt_rows.append([Paragraph(f"<b>({opt_key})</b> {opt_val}", opt_style)])

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

            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 14px; margin-bottom: 20px; font-size: 14px; line-height: 1.5;">
                <strong>📎 Downloadable Quiz PDF Attached!</strong><br>
                Please open the attached <code>{filename}</code> document to view today's complete set of drill questions and options.
                <br><br>
                <strong>📌 Submission Instructions:</strong> Click <strong>Reply</strong> to this email, type your answers in any format (e.g. <code>1A 2C 3B...</code> or <code>CBBBBC...</code> or <code>&lt;Topic&gt; ABCD...</code>), and send!
                <br><small style="color: #4a5568;">⏰ Please submit before midnight for automated evaluation.</small>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_email(subject, html_content, pdf_bytes, filename, receiver_email):
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
            print("      Email sent successfully!")
            return
        except Exception as smtp_err:
            print(f"      [WARN] SMTP Attempt {attempt}/{max_retries} failed: {smtp_err}")
            if attempt == max_retries:
                raise smtp_err
            time.sleep(3)

def run_pipeline_daily_quiz(pipe_cfg):
    pipeline_id = pipe_cfg.get("pipeline_id", "mppsc_default")
    student_name = pipe_cfg.get("student_name", "Candidate")
    receiver_email = pipe_cfg.get("receiver_email")
    exam_name = pipe_cfg.get("exam_name", "MPPSC")
    topic_desc = pipe_cfg.get("topics") or f"General {exam_name} Mix"

    if not receiver_email:
        print(f"[SKIP] No receiver_email configured for pipeline: {pipeline_id}")
        return

    print(f"\n=======================================================")
    print(f"🚀 Running Daily Quiz Pipeline: [{pipeline_id}] for {student_name} ({exam_name})")
    print(f"=======================================================")

    today_str = datetime.now().strftime("%Y-%m-%d")
    test_id = f"{pipeline_id.upper()}_{today_str}"

    # 1. Generate questions for this specific pipeline
    questions = generate_questions_for_pipeline(pipe_cfg)

    # 2. Build PDF document
    clean_exam_name = exam_name.replace(" ", "_")
    pdf_filename = f"{clean_exam_name}_Daily_Drill_{today_str}.pdf"
    pdf_bytes = build_quiz_pdf_bytes(today_str, topic_desc, questions, exam_name=exam_name)

    # 3. Save to database with pipeline_id
    print("   Saving questions to database...")
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
    print(f"   Saved to daily_tests table as PENDING for pipeline [{pipeline_id}].")

    # 4. Dispatch Email
    subject = f"🎯 [{exam_name}] Daily Drill - {today_str}"
    html_body = create_html_email(today_str, questions, topic_desc, exam_name=exam_name, student_name=student_name)
    send_email(subject, html_body, pdf_bytes, pdf_filename, receiver_email)
    print(f"[OK] Daily Quiz for {student_name} ({exam_name}) sent and recorded successfully!")

def main():
    parser = argparse.ArgumentParser(description="Send Daily Quiz across student pipelines.")
    parser.add_argument("--pipeline", type=str, help="Specific pipeline_id to run (e.g. ctet_swati or mppsc_default)")
    args = parser.parse_args()

    try:
        validate_config(["SENDER_EMAIL", "APP_PASSWORD", "DATABASE_URL"])

        print("[1/4] Initializing PostgreSQL database tables & checking pending tests...")
        init_and_migrate_db()

        active_pipelines = get_pipeline_configs(only_enabled=True)
        if args.pipeline:
            active_pipelines = [p for p in active_pipelines if p.get("pipeline_id") == args.pipeline]

        if not active_pipelines:
            print("No active pipelines configured to run.")
            return

        for pipe_cfg in active_pipelines:
            mark_expired_tests_absent(pipe_cfg.get("pipeline_id", "mppsc_default"))
            run_pipeline_daily_quiz(pipe_cfg)

        print("\n🎉 [ALL COMPLETED] Daily Quiz execution finished for all active pipelines!\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to send daily quiz: {e}\n")
        send_error_alert("Daily Quiz Sender (daily_quiz_sender.py)", e)
        raise e

if __name__ == "__main__":
    main()