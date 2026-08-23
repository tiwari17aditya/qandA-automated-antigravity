import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import io
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.colors import HexColor

from config import SENDER_EMAIL, APP_PASSWORD, RECEIVER_EMAIL, validate_config

def build_quiz_pdf_bytes(date_str, topic_desc, questions):
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
    elements.append(Paragraph(f"🎯 MPPSC Daily Prelims Drill - {date_str}", title_style))
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

        # Options Table
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

        # Card container
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

        # Render 4 options with color highlights
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

def send_test_daily_quiz():
    """Sends a sample Daily Quiz email with PDF attached."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    sample_questions = [
        {
            "q_num": 1,
            "topic": "Ancient History",
            "question": "Which Harappan site has provided evidence of a dockyard?",
            "options": {
                "A": "Kalibangan",
                "B": "Lothal",
                "C": "Mohenjo-daro",
                "D": "Surkotada"
            },
            "correct_option": "B",
            "explanation": "Lothal in Gujarat had a tidal dockyard, proving active maritime trade during the Indus Valley civilization."
        },
        {
            "q_num": 2,
            "topic": "MP Geography",
            "question": "The highest peak of Madhya Pradesh, Dhupgarh, is located in which mountain range?",
            "options": {
                "A": "Vindhya Range",
                "B": "Satpura Range",
                "C": "Kaimur Range",
                "D": "Maikal Range"
            },
            "correct_option": "B",
            "explanation": "Mount Dhupgarh (1,350 m) in Pachmarhi is the highest point of MP, situated in the Mahadeo Hills of the Satpura Range."
        }
    ]

    print("[TEST 1/3] Generating Daily Quiz PDF & sending test email...")
    pdf_bytes = build_quiz_pdf_bytes(today_str, "History & MP Geography", sample_questions)

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 2px solid #3182ce; padding-bottom: 10px; margin-bottom: 15px;">
                <h2 style="color: #2b6cb0; margin: 0;">🎯 [TEST] MPPSC Daily Prelims Drill</h2>
                <p style="color: #718096; margin: 5px 0 0 0;">Date: {today_str} &bull; 2 Questions &bull; Focus: History & MP Geography</p>
            </div>

            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 20px; font-size: 14px;">
                <strong>📎 Downloadable Quiz PDF Attached!</strong><br>
                Please open the attached <code>MPPSC_Daily_Drill_{today_str}.pdf</code> document to read today's drill questions.
                <br><br>
                <strong>📌 To Submit:</strong> Reply directly to this email with your answers (e.g. <code>1B 2B</code> or <code>BB</code>).
            </div>
            
            <p style="font-size: 12px; color: #718096; text-align: center; margin-top: 20px;">
                This is a non-recording test email for layout verification.
            </p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = f"🎯 [TEST] MPPSC Daily Prelims Drill - {today_str}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=f"MPPSC_Daily_Drill_{today_str}.pdf")
    msg.attach(pdf_attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print("         ✅ Test 1 (Daily Quiz PDF Email) sent successfully!")

def send_test_evaluation():
    """Sends a sample Evaluation report email with PDF attached (showing correct & incorrect highlighted options)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    breakdown_records = [
        {
            "q_num": 1,
            "topic": "Ancient History",
            "question": "Which Harappan site has provided evidence of a dockyard?",
            "options": {
                "A": "Kalibangan",
                "B": "Lothal",
                "C": "Mohenjo-daro",
                "D": "Surkotada"
            },
            "user_ans": "B",
            "correct_ans": "B",
            "is_correct": True,
            "explanation": "Lothal in Gujarat had a tidal dockyard, proving active maritime trade during the Indus Valley civilization."
        },
        {
            "q_num": 2,
            "topic": "MP Geography",
            "question": "The highest peak of Madhya Pradesh, Dhupgarh, is located in which mountain range?",
            "options": {
                "A": "Vindhya Range",
                "B": "Satpura Range",
                "C": "Kaimur Range",
                "D": "Maikal Range"
            },
            "user_ans": "A",
            "correct_ans": "B",
            "is_correct": False,
            "explanation": "Mount Dhupgarh (1,350 m) in Pachmarhi is the highest point of MP, situated in the Mahadeo Hills of the Satpura Range."
        }
    ]

    print("[TEST 2/3] Generating Evaluation Report PDF & sending test email...")
    pdf_bytes = build_eval_pdf_bytes(today_str, 1, 2, breakdown_records)

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <h2 style="color: #2b6cb0; margin-top: 0;">📊 [TEST] Performance Report: {today_str}</h2>
            
            <div style="font-size: 20px; font-weight: bold; background: #f0fff4; color: #22543d; padding: 15px; border-radius: 6px; border: 1px solid #9ae6b4; margin-bottom: 20px;">
                Score: 1 / 2 (50.0%)
            </div>

            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 12px; margin-bottom: 20px; font-size: 14px;">
                <strong>📎 Detailed Solution PDF Attached!</strong><br>
                Open the attached <code>MPPSC_Evaluation_Report_{today_str}.pdf</code> document to inspect all 4 options, your selection highlights, and detailed answer explanations.
            </div>

            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">📈 Topic Mastery Snapshot</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <tr style="background: #f7fafc;"><th style="text-align:left; padding:8px;">Topic</th><th style="padding:8px;">Accuracy</th><th style="padding:8px;">Status</th></tr>
                <tr style="border-bottom: 1px solid #edf2f7;"><td style="padding:8px;">Ancient History</td><td style="padding:8px; text-align:center;">1/1 (100%)</td><td style="padding:8px; text-align:center; color:#38a169; font-weight:bold;">🟢 Strong</td></tr>
                <tr style="border-bottom: 1px solid #edf2f7;"><td style="padding:8px;">MP Geography</td><td style="padding:8px; text-align:center;">0/1 (0%)</td><td style="padding:8px; text-align:center; color:#e53e3e; font-weight:bold;">🔴 Needs Focus</td></tr>
            </table>

            <p style="font-size: 12px; color: #718096; text-align: center; margin-top: 20px;">
                This is a non-recording test email for evaluation layout verification.
            </p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = f"📊 [TEST] Evaluation Report - MPPSC Drill ({today_str})"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    pdf_attachment.add_header("Content-Disposition", "attachment", filename=f"MPPSC_Evaluation_Report_{today_str}.pdf")
    msg.attach(pdf_attachment)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print("         ✅ Test 2 (Evaluation PDF Email) sent successfully!")

def send_test_absent():
    """Sends a sample Absent notification email (no attachment provided)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    print("[TEST 3/3] Sending Absent Notice email (No attachment)...")

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 600px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 2px solid #e53e3e; padding-bottom: 10px; margin-bottom: 15px;">
                <h2 style="color: #c53030; margin: 0;">❌ Absent Notice - MPPSC Drill ({today_str})</h2>
            </div>

            <div style="background-color: #fff5f5; border-left: 4px solid #e53e3e; padding: 14px; margin-bottom: 20px; font-size: 14px; color: #742a2a;">
                <strong>⚠️ You were marked ABSENT for yesterday's drill ({today_str}).</strong><br>
                No response was received before the deadline. 
                <br><br>
                <em>Note: Solution PDF document is not attached for unattempted drills.</em>
            </div>

            <div style="background-color: #edf2f7; padding: 12px; border-radius: 6px; font-size: 13px; color: #4a5568;">
                💡 <strong>Streak Tip:</strong> Make sure to reply to today's daily drill email before midnight to keep your study streak active!
            </div>

            <p style="font-size: 12px; color: #718096; text-align: center; margin-top: 20px;">
                This is a non-recording test email for absent notification verification.
            </p>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["Subject"] = f"❌ [TEST] Absent Notice - MPPSC Drill ({today_str})"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print("         ✅ Test 3 (Absent Notice Email) sent successfully!")

def main():
    validate_config(["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL"])
    print(f"🚀 Dispatching 3 test email scenarios to {RECEIVER_EMAIL}...\n")
    send_test_daily_quiz()
    send_test_evaluation()
    send_test_absent()
    print("\n🎉 All 3 test emails sent successfully! Please check your Gmail inbox.\n")

if __name__ == "__main__":
    main()
