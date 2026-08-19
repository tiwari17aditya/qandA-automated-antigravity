import json
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from google import genai

from config import (
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    validate_config,
)
from db import get_db_connection, init_and_migrate_db, mark_expired_tests_absent
from alert_utils import send_error_alert, generate_ai_completion

def generate_ai_study_recommendation(summary_data, weak_topics):
    """
    Generates a personalized MPPSC Prelims study strategy
    based on the student's weekly accuracy and weak topics using AI fallback chain.
    """
    weak_str = ", ".join([f"{t['topic']} ({t['accuracy']:.0f}%)" for t in weak_topics]) if weak_topics else "None (Keep maintaining high performance!)"
    
    prompt = f"""
    You are an expert MPPSC State Services mentor.
    Review the student's weekly prelims drill performance:
    - Tests Attempted: {summary_data['tests_completed']} / {summary_data['tests_assigned']}
    - Tests Absent: {summary_data['tests_absent']}
    - Overall Weekly Score: {summary_data['total_score']} / {summary_data['total_possible']} ({summary_data['overall_pct']:.1f}%)
    - Weak Topics Identified: {weak_str}

    Provide a concise, motivating, and actionable study action plan for the coming week in 3 short sections:
    1. 🎯 Weekly Performance Verdict (2-3 sentences)
    2. 🚨 High-Priority Revision Areas (Bullet points targeting weak units/topics)
    3. 💡 Strategic Advice for Next Week's Drills (2 actionable tips)

    Keep tone encouraging, rigorous, and direct. Format with clean HTML bullet points.
    """
    
    response_text = generate_ai_completion(prompt=prompt, response_json=False)
    return response_text.strip()

def build_weekly_html(start_date, end_date, summary_data, daily_rows, topic_rows, ai_advice_html):
    att_color = "#38a169" if summary_data['att_rate'] >= 80 else "#d69e2e" if summary_data['att_rate'] >= 60 else "#e53e3e"
    score_color = "#38a169" if summary_data['overall_pct'] >= 75 else "#d69e2e" if summary_data['overall_pct'] >= 50 else "#e53e3e"

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
            <td style="padding: 8px;">{t_date}</td>
            <td style="padding: 8px;">{topic_desc or 'General Mix'}</td>
            <td style="padding: 8px; text-align: center;">{status_badge}</td>
            <td style="padding: 8px; text-align: center; font-weight: 600;">{score_display}</td>
        </tr>
        """

    topic_table_rows = ""
    for topic, att, cor, acc in topic_rows:
        tag_color = "#e53e3e" if acc < 60 else "#d69e2e" if acc < 80 else "#38a169"
        tag_text = "🔴 Needs Focus" if acc < 60 else "🟡 Moderate" if acc < 80 else "🟢 Strong"
        topic_table_rows += f"""
        <tr style="border-bottom: 1px solid #edf2f7;">
            <td style="padding: 8px;">{topic}</td>
            <td style="padding: 8px; text-align: center;">{cor}/{att} ({acc:.0f}%)</td>
            <td style="padding: 8px; text-align: center; color: {tag_color}; font-weight: bold;">{tag_text}</td>
        </tr>
        """

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f7fafc; padding: 20px; color: #2d3748;">
        <div style="max-width: 700px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0;">
            <div style="border-bottom: 2px solid #3182ce; padding-bottom: 12px; margin-bottom: 20px;">
                <h2 style="color: #2b6cb0; margin: 0;">📈 MPPSC Weekly Progress Report</h2>
                <p style="color: #718096; margin: 5px 0 0 0;">Week Range: {start_date} to {end_date}</p>
            </div>

            <!-- KPI Cards -->
            <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                <div style="flex: 1; background: #ebf8ff; border: 1px solid #bee3f8; padding: 12px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #2b6cb0; font-weight: bold; text-transform: uppercase;">Attendance</div>
                    <div style="font-size: 22px; font-weight: bold; color: {att_color}; margin-top: 4px;">{summary_data['att_rate']:.0f}%</div>
                    <div style="font-size: 11px; color: #718096;">{summary_data['tests_completed']}/{summary_data['tests_assigned']} Drills Done</div>
                </div>
                <div style="flex: 1; background: #f7fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #4a5568; font-weight: bold; text-transform: uppercase;">Overall Accuracy</div>
                    <div style="font-size: 22px; font-weight: bold; color: {score_color}; margin-top: 4px;">{summary_data['overall_pct']:.1f}%</div>
                    <div style="font-size: 11px; color: #718096;">{summary_data['total_score']}/{summary_data['total_possible']} Total Score</div>
                </div>
                <div style="flex: 1; background: #fff5f5; border: 1px solid #fed7d7; padding: 12px; border-radius: 6px; text-align: center;">
                    <div style="font-size: 11px; color: #c53030; font-weight: bold; text-transform: uppercase;">Missed Drills</div>
                    <div style="font-size: 22px; font-weight: bold; color: #e53e3e; margin-top: 4px;">{summary_data['tests_absent']}</div>
                    <div style="font-size: 11px; color: #718096;">Marked Absent</div>
                </div>
            </div>

            <!-- AI Strategy Section -->
            <div style="background: #faf5ff; border: 1px solid #e9d8fd; border-radius: 6px; padding: 15px; margin-bottom: 25px;">
                <h3 style="color: #6b46c1; margin-top: 0; margin-bottom: 10px;">🤖 AI Mentor Study Review & Strategy</h3>
                <div style="font-size: 14px; line-height: 1.6; color: #2d3748;">
                    {ai_advice_html}
                </div>
            </div>

            <!-- Daily Activity Table -->
            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 10px;">📅 Day-by-Day Activity</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 25px;">
                <tr style="background: #f7fafc; text-align: left;">
                    <th style="padding: 8px;">Date</th>
                    <th style="padding: 8px;">Topics</th>
                    <th style="padding: 8px; text-align: center;">Status</th>
                    <th style="padding: 8px; text-align: center;">Score</th>
                </tr>
                {daily_table_rows}
            </table>

            <!-- Topic Stats Table -->
            <h3 style="color: #2d3748; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; margin-bottom: 10px;">📊 Cumulative Topic Mastery</h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <tr style="background: #f7fafc; text-align: left;">
                    <th style="padding: 8px;">Topic</th>
                    <th style="padding: 8px; text-align: center;">Accuracy</th>
                    <th style="padding: 8px; text-align: center;">Mastery Level</th>
                </tr>
                {topic_table_rows if topic_table_rows else '<tr><td colspan="3" style="padding:8px; text-align:center; color:#718096;">No topic data recorded yet.</td></tr>'}
            </table>
        </div>
    </body>
    </html>
    """
    return html

def send_weekly_email(subject, html_content):
    print(f"[3/4] Sending Weekly Report email to {RECEIVER_EMAIL}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=25) as server:
        server.login(SENDER_EMAIL, APP_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
    print("      Email sent successfully!")

def main():
    try:
        validate_config(["SENDER_EMAIL", "APP_PASSWORD", "RECEIVER_EMAIL", "GEMINI_API_KEY", "DATABASE_URL"])

        print("[1/4] Gathering past 7 days performance metrics from database...")
        init_and_migrate_db()
        mark_expired_tests_absent()

        conn = get_db_connection()
        cursor = conn.cursor()

        today = datetime.now().date()
        start_date = today - timedelta(days=7)
        end_date = today

        # Fetch daily tests from past 7 days
        cursor.execute("""
            SELECT test_date, topics, status, score, total_questions, percentage
            FROM daily_tests
            WHERE test_date >= %s AND test_date <= %s
            ORDER BY test_date ASC;
        """, (start_date, end_date))
        daily_rows = cursor.fetchall()

        if not daily_rows:
            print("      No tests found in the past 7 days. Nothing to report.")
            cursor.close()
            conn.close()
            return

        tests_assigned = len(daily_rows)
        tests_completed = sum(1 for r in daily_rows if r[2] == 'EVALUATED')
        tests_absent = sum(1 for r in daily_rows if r[2] == 'ABSENT')
        total_score = sum(r[3] for r in daily_rows if r[2] == 'EVALUATED')
        total_possible = sum(r[4] for r in daily_rows if r[2] == 'EVALUATED')
        overall_pct = (total_score / total_possible) * 100.0 if total_possible > 0 else 0.0
        att_rate = (tests_completed / tests_assigned) * 100.0 if tests_assigned > 0 else 0.0

        summary_data = {
            "tests_assigned": tests_assigned,
            "tests_completed": tests_completed,
            "tests_absent": tests_absent,
            "total_score": total_score,
            "total_possible": total_possible,
            "overall_pct": overall_pct,
            "att_rate": att_rate
        }

        # Fetch topic stats
        cursor.execute("SELECT topic, attempted, correct, accuracy FROM topic_stats ORDER BY accuracy ASC;")
        topic_rows = cursor.fetchall()
        weak_topics = [{"topic": r[0], "accuracy": r[3]} for r in topic_rows if r[3] < 70]

        # Generate AI Study Strategy
        print("[2/4] Generating AI study review with Gemini...")
        ai_advice = generate_ai_study_recommendation(summary_data, weak_topics)

        # Save to weekly_reports table
        week_id = f"WEEK_{start_date.strftime('%Y_%m_%d')}_TO_{end_date.strftime('%Y_%m_%d')}"
        cursor.execute("""
            INSERT INTO weekly_reports (
                week_id, start_date, end_date, tests_assigned, tests_completed,
                tests_absent, total_score, total_possible, overall_percentage,
                summary_json, ai_recommendations
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (week_id) DO UPDATE SET
                tests_completed = EXCLUDED.tests_completed,
                tests_absent = EXCLUDED.tests_absent,
                total_score = EXCLUDED.total_score,
                overall_percentage = EXCLUDED.overall_percentage,
                summary_json = EXCLUDED.summary_json,
                ai_recommendations = EXCLUDED.ai_recommendations;
        """, (
            week_id, start_date, end_date, tests_assigned, tests_completed,
            tests_absent, total_score, total_possible, overall_pct,
            json.dumps(summary_data), ai_advice
        ))
        conn.commit()
        cursor.close()
        conn.close()

        # Send Email
        html_report = build_weekly_html(start_date, end_date, summary_data, daily_rows, topic_rows, ai_advice)
        subject = f"📊 MPPSC Weekly Study Report ({start_date.strftime('%d %b')} - {end_date.strftime('%d %b')})"
        send_weekly_email(subject, html_report)
        print(f"\n[4/4] [OK] Sunday Weekly Report sent successfully!\n")

    except Exception as e:
        print(f"\n[ERROR] Failed to generate weekly report: {e}\n")
        send_error_alert("Weekly Report Sender (weekly_report_sender.py)", e)
        raise e

if __name__ == "__main__":
    main()
