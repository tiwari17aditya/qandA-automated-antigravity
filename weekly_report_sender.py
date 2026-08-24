import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import smtplib
import time
import argparse
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

from config import (
    SENDER_EMAIL,
    APP_PASSWORD,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    get_pipeline_configs,
    validate_config,
)
from db import get_db_connection, init_and_migrate_db, mark_expired_tests_absent
from alert_utils import send_error_alert, generate_ai_completion

def generate_ai_study_recommendation(summary_data, weak_topics, daily_scores_str="", exam_name="MPPSC", student_name="Candidate", lang="english"):
    """
    Generates a personalized study strategy tailored to the student's exam
    based on accuracy, consistency, and weak topics using AI completion.
    """
    weak_str = ", ".join([f"{t['topic']} ({t['accuracy']:.0f}%)" for t in weak_topics]) if weak_topics else "None (High Performance!)"
    lang_instruction = "IMPORTANT: Write the recommendation response in clear Devanagari Hindi (हिन्दी)." if lang.lower() == "hindi" else "Write the response in English."

    prompt = f"""
    You are an expert mentor for {exam_name}.
    Review {student_name}'s weekly drill performance:
    - Tests Attempted: {summary_data['tests_completed']} / {summary_data['tests_assigned']} ({summary_data['att_rate']:.0f}% Attendance)
    - Tests Absent: {summary_data['tests_absent']}
    - Overall Weekly Score: {summary_data['total_score']} / {summary_data['total_possible']} ({summary_data['overall_pct']:.1f}%)
    - Best Scoring Day: {summary_data.get('best_day', 'N/A')}
    - Daily Score Progression: {daily_scores_str or 'N/A'}
    - Weak Topics Identified (<70% accuracy): {weak_str}

    {lang_instruction}

    Provide a concise, motivating, and actionable study action plan for {student_name} in 3 short sections:
    1. 🎯 Weekly Performance Verdict (2-3 sentences assessing drill consistency and score trend)
    2. 🚨 High-Priority Revision Areas (Targeting identified weak topics with specific {exam_name} preparation tips)
    3. 💡 Strategic Advice for Next Week's Drills (2 actionable daily drill habits)

    Keep tone encouraging, rigorous, and direct. Format with clean HTML bullet points.
    """
    
    response_text = generate_ai_completion(prompt=prompt, response_json=False)
    return response_text.strip()

def build_weekly_html(start_date, end_date, summary_data, daily_rows, topic_rows, ai_advice_html, exam_name="MPPSC", student_name="Candidate"):
    att_color = "#38a169" if summary_data['att_rate'] >= 80 else "#d69e2e" if summary_data['att_rate'] >= 60 else "#e53e3e"
    score_color = "#38a169" if summary_data['overall_pct'] >= 75 else "#d69e2e" if summary_data['overall_pct'] >= 50 else "#e53e3e"

    streak_cards_html = ""
    for row in daily_rows:
        t_date, topic_desc, status, score, total_q, pct = row
        try:
            d_obj = datetime.strptime(str(t_date), "%Y-%m-%d")
            day_name = d_obj.strftime("%a")
            date_short = d_obj.strftime("%d %b")
        except Exception:
            day_name = "Day"
            date_short = str(t_date)

        if status == 'EVALUATED':
            bg_color = "#f0fff4"; border_color = "#9ae6b4"; text_color = "#22543d"; badge_icon = f"✅ {score}/{total_q}"; sub_text = f"{pct:.0f}%"
        elif status == 'ABSENT':
            bg_color = "#fff5f5"; border_color = "#feb2b2"; text_color = "#9b2c2c"; badge_icon = "❌ Absent"; sub_text = "0%"
        else:
            bg_color = "#fffaf0"; border_color = "#fbd38d"; text_color = "#7b341e"; badge_icon = "⏳ Pending"; sub_text = "-"

        streak_cards_html += f"""
        <div style="flex: 1; min-width: 75px; background: {bg_color}; border: 1px solid {border_color}; padding: 8px 4px; border-radius: 6px; text-align: center;">
            <div style="font-size: 11px; font-weight: bold; color: #4a5568;">{day_name}</div>
            <div style="font-size: 10px; color: #718096; margin-bottom: 4px;">{date_short}</div>
            <div style="font-size: 12px; font-weight: bold; color: {text_color};">{badge_icon}</div>
            <div style="font-size: 10px; color: {text_color};">{sub_text}</div>
        </div>
        """

    daily_table_rows = ""
    for row in daily_rows:
        t_date, topic_desc, status, score, total_q, pct = row
        status_badge = (
            "<span style='color: #38a169; font-weight: bold;'>✅ Completed</span>" if status == 'EVALUATED'
            else "<span style='color: #e53e3e; font-weight: bold;'>❌ Absent</span>" if status == 'ABSENT'
            else "<span style='color: #d69e2e; font-weight: bold;'>⏳ Pending</span>"
        )
        score_display = f"{score}/{total_q} ({pct:.0f}%)" if status == 'EVALUATED' else "0" if status == 'ABSENT' else "-"
        daily_table_rows += f"""
        <tr style="border-bottom: 1px solid #edf2f7;">
            <td style="padding: 10px; font-size: 13px;">{t_date}</td>
            <td style="padding: 10px; font-size: 13px;">{topic_desc or 'General Mix'}</td>
            <td style="padding: 10px; text-align: center;">{status_badge}</td>
            <td style="padding: 10px; text-align: center; font-weight: bold;">{score_display}</td>
        </tr>
        """

    topic_table_rows = ""
    if topic_rows:
        for t_name, att, cor, acc in topic_rows:
            tag_color = "#e53e3e" if acc < 60 else "#d69e2e" if acc < 80 else "#38a169"
            tag_text = "🔴 Needs Focus" if acc < 60 else "🟡 Moderate" if acc < 80 else "🟢 Strong"
            topic_table_rows += f"""
            <tr style="border-bottom: 1px solid #edf2f7;">
                <td style="padding: 8px 10px; font-size: 13px;">{t_name}</td>
                <td style="padding: 8px 10px; text-align: center; font-size: 13px;">{cor}/{att} ({acc:.0f}%)</td>
                <td style="padding: 8px 10px; text-align: center; font-weight: bold; color: {tag_color}; font-size: 12px;">{tag_text}</td>
            </tr>
            """
    else:
        topic_table_rows = "<tr><td colspan='3' style='padding: 10px; text-align: center; color: #718096;'>No topic statistics recorded yet.</td></tr>"

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 700px; margin: 0 auto; background: #ffffff; padding: 30px; border-radius: 10px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 3px solid #2b6cb0; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #2b6cb0; margin: 0;">📊 {exam_name} Weekly Study Report</h2>
                <p style="color: #718096; margin: 5px 0 0 0; font-size: 14px;">
                    Candidate: <strong>{student_name}</strong> &bull; Period: {start_date.strftime('%d %b %Y')} &ndash; {end_date.strftime('%d %b %Y')}
                </p>
            </div>

            <div style="display: flex; gap: 15px; margin-bottom: 25px;">
                <div style="flex: 1; background: #f7fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: #718096; text-transform: uppercase;">Attendance Rate</div>
                    <div style="font-size: 22px; font-weight: bold; color: {att_color}; margin-top: 4px;">{summary_data['att_rate']:.0f}%</div>
                    <div style="font-size: 11px; color: #4a5568;">{summary_data['tests_completed']}/{summary_data['tests_assigned']} Drills</div>
                </div>
                <div style="flex: 1; background: #f7fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: #718096; text-transform: uppercase;">Overall Accuracy</div>
                    <div style="font-size: 22px; font-weight: bold; color: {score_color}; margin-top: 4px;">{summary_data['overall_pct']:.1f}%</div>
                    <div style="font-size: 11px; color: #4a5568;">{summary_data['total_score']}/{summary_data['total_possible']} Total Score</div>
                </div>
                <div style="flex: 1; background: #f7fafc; border: 1px solid #e2e8f0; padding: 15px; border-radius: 8px; text-align: center;">
                    <div style="font-size: 12px; color: #718096; text-transform: uppercase;">Unattempted</div>
                    <div style="font-size: 22px; font-weight: bold; color: #e53e3e; margin-top: 4px;">{summary_data['tests_absent']}</div>
                    <div style="font-size: 11px; color: #4a5568;">Missed Drills</div>
                </div>
            </div>

            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-top: 25px;">📅 Daily Drill Breakdown</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px;">
                <thead>
                    <tr style="background: #edf2f7; text-align: left; font-size: 12px; color: #4a5568;">
                        <th style="padding: 8px 10px;">Date</th>
                        <th style="padding: 8px 10px;">Topic Focus</th>
                        <th style="padding: 8px 10px; text-align: center;">Status</th>
                        <th style="padding: 8px 10px; text-align: center;">Score</th>
                    </tr>
                </thead>
                <tbody>{daily_table_rows}</tbody>
            </table>

            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px;">📈 Cumulative Topic Mastery</h3>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px;">
                <thead>
                    <tr style="background: #edf2f7; text-align: left; font-size: 12px; color: #4a5568;">
                        <th style="padding: 8px 10px;">Topic</th>
                        <th style="padding: 8px 10px; text-align: center;">Accuracy</th>
                        <th style="padding: 8px 10px; text-align: center;">Mastery Status</th>
                    </tr>
                </thead>
                <tbody>{topic_table_rows}</tbody>
            </table>

            <div style="background-color: #ebf8ff; border-left: 4px solid #3182ce; padding: 18px; border-radius: 6px; margin-top: 20px; line-height: 1.6;">
                <h3 style="color: #2b6cb0; margin-top: 0; margin-bottom: 10px;">🤖 AI Mentor Personal Strategy</h3>
                <div style="font-size: 14px; color: #2d3748;">{ai_advice_html}</div>
            </div>

            <div style="text-align: center; margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #a0aec0;">
                Automated {exam_name} Preparation System &bull; Keep practicing daily!
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_weekly_email(subject, html_content, receiver_email=None):
    print(f"   Sending weekly report email to {receiver_email}...")
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = receiver_email
    msg.attach(MIMEText(html_content, "html"))

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
                server.starttls()
                server.login(SENDER_EMAIL, APP_PASSWORD)
                server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
            print("      Weekly Report email sent successfully!")
            return
        except Exception as smtp_err:
            print(f"      [WARN] SMTP Attempt {attempt}/{max_retries} failed: {smtp_err}")
            if attempt == max_retries:
                raise smtp_err
            time.sleep(3)

def run_pipeline_weekly_report(pipe_cfg, cursor, conn):
    pipeline_id = pipe_cfg.get("pipeline_id", "mppsc_default")
    student_name = pipe_cfg.get("student_name", "Candidate")
    receiver_email = pipe_cfg.get("receiver_email")
    exam_name = pipe_cfg.get("exam_name", "MPPSC")
    lang = pipe_cfg.get("language", "english")

    if not receiver_email:
        print(f"[SKIP] No receiver_email configured for pipeline: {pipeline_id}")
        return

    print(f"\n=======================================================")
    print(f"📊 Generating Weekly Report for [{pipeline_id}] ({student_name} - {exam_name})")
    print(f"=======================================================")

    today = datetime.now().date()
    end_date = today
    start_date = today - timedelta(days=6)

    cursor.execute("""
        SELECT test_date, topics, status, score, total_questions, percentage
        FROM daily_tests
        WHERE test_date >= %s AND test_date <= %s AND pipeline_id = %s
        ORDER BY test_date ASC;
    """, (start_date, end_date, pipeline_id))
    daily_rows = cursor.fetchall()

    tests_assigned = 7
    tests_completed = sum(1 for r in daily_rows if r[2] == 'EVALUATED')
    tests_absent = sum(1 for r in daily_rows if r[2] == 'ABSENT')
    total_score = sum(r[3] for r in daily_rows if r[2] == 'EVALUATED')
    total_possible = sum(r[4] for r in daily_rows if r[2] == 'EVALUATED')
    overall_pct = (total_score / total_possible) * 100.0 if total_possible > 0 else 0.0
    att_rate = (tests_completed / tests_assigned) * 100.0 if tests_assigned > 0 else 0.0

    best_day = "N/A"
    max_pct = -1.0
    daily_scores_list = []
    for r in daily_rows:
        t_date, topic_desc, status, score, total_q, pct = r
        if status == 'EVALUATED':
            daily_scores_list.append(f"{t_date}: {score}/{total_q} ({pct:.0f}%)")
            if pct > max_pct:
                max_pct = pct
                best_day = f"{t_date} ({score}/{total_q} - {pct:.0f}%)"
        elif status == 'ABSENT':
            daily_scores_list.append(f"{t_date}: Absent (0/{total_q})")
        else:
            daily_scores_list.append(f"{t_date}: Pending")

    daily_scores_str = ", ".join(daily_scores_list)

    summary_data = {
        "tests_assigned": tests_assigned,
        "tests_completed": tests_completed,
        "tests_absent": tests_absent,
        "total_score": total_score,
        "total_possible": total_possible,
        "overall_pct": overall_pct,
        "att_rate": att_rate,
        "best_day": best_day,
        "daily_scores_str": daily_scores_str,
    }

    cursor.execute("SELECT topic, attempted, correct, accuracy FROM topic_stats WHERE pipeline_id = %s ORDER BY accuracy ASC;", (pipeline_id,))
    topic_rows = cursor.fetchall()
    weak_topics = [{"topic": r[0], "accuracy": r[3]} for r in topic_rows if r[3] < 70]

    print("   Generating AI study recommendation...")
    ai_advice = generate_ai_study_recommendation(summary_data, weak_topics, daily_scores_str=daily_scores_str, exam_name=exam_name, student_name=student_name, lang=lang)

    week_id = f"{pipeline_id.upper()}_WEEK_{start_date.strftime('%Y_%m_%d')}_TO_{end_date.strftime('%Y_%m_%d')}"
    cursor.execute("""
        INSERT INTO weekly_reports (
            week_id, pipeline_id, start_date, end_date, tests_assigned, tests_completed,
            tests_absent, total_score, total_possible, overall_percentage,
            summary_json, ai_recommendations
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (week_id) DO UPDATE SET
            tests_completed = EXCLUDED.tests_completed,
            tests_absent = EXCLUDED.tests_absent,
            total_score = EXCLUDED.total_score,
            overall_percentage = EXCLUDED.overall_percentage,
            summary_json = EXCLUDED.summary_json,
            ai_recommendations = EXCLUDED.ai_recommendations;
    """, (
        week_id, pipeline_id, start_date, end_date, tests_assigned, tests_completed,
        tests_absent, total_score, total_possible, overall_pct,
        json.dumps(summary_data), ai_advice
    ))
    conn.commit()

    html_report = build_weekly_html(start_date, end_date, summary_data, daily_rows, topic_rows, ai_advice, exam_name=exam_name, student_name=student_name)
    subject = f"📊 [{exam_name}] Weekly Study Report ({start_date.strftime('%d %b')} - {end_date.strftime('%d %b')})"
    send_weekly_email(subject, html_report, receiver_email=receiver_email)
    print(f"[OK] Weekly Report for {student_name} ({exam_name}) sent successfully!\n")

def main():
    parser = argparse.ArgumentParser(description="Send Weekly Study Reports across student pipelines.")
    parser.add_argument("--pipeline", type=str, help="Specific pipeline_id to run")
    args = parser.parse_args()

    try:
        validate_config(["SENDER_EMAIL", "APP_PASSWORD", "DATABASE_URL"])
        print("[1/3] Initializing DB & checking pending tests...")
        init_and_migrate_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        active_pipelines = get_pipeline_configs(only_enabled=True)
        if args.pipeline:
            active_pipelines = [p for p in active_pipelines if p.get("pipeline_id") == args.pipeline]

        for pipe_cfg in active_pipelines:
            mark_expired_tests_absent(pipe_cfg.get("pipeline_id", "mppsc_default"))
            run_pipeline_weekly_report(pipe_cfg, cursor, conn)
        cursor.close()
        conn.close()
        print("\n🎉 [ALL COMPLETED] Weekly Reports execution finished!\n")
    except Exception as e:
        print(f"\n[ERROR] Failed to generate weekly report: {e}\n")
        send_error_alert("Weekly Report Sender (weekly_report_sender.py)", e)
        raise e

if __name__ == "__main__":
    main()
