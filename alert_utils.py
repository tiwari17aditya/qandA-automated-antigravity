import time
import random
import smtplib
import traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import SENDER_EMAIL, APP_PASSWORD, RECEIVER_EMAIL

def send_error_alert(service_name, error, extra_info=""):
    """
    Sends an immediate high-priority alert email if any script or component fails.
    """
    try:
        if not SENDER_EMAIL or not APP_PASSWORD or not RECEIVER_EMAIL:
            print(f"[ALERT FALLBACK] Cannot send error email due to missing email credentials. Error in {service_name}: {error}")
            return

        subject = f"⚠️ [ALERT] MPPSC Automation Error in {service_name}"
        tb_str = traceback.format_exc()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background-color: #fff5f5; padding: 20px; color: #2d3748;">
            <div style="max-width: 650px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; border: 1px solid #feb2b2;">
                <h2 style="color: #e53e3e; margin-top: 0;">⚠️ Automation Error Alert</h2>
                <p>An error occurred during execution of <strong>{service_name}</strong> at <code>{timestamp}</code>.</p>
                
                <div style="background: #fed7d7; color: #9b2c2c; padding: 12px; border-radius: 6px; font-weight: bold; margin-bottom: 15px;">
                    {type(error).__name__}: {str(error)}
                </div>

                {f'<p><strong>Context:</strong> {extra_info}</p>' if extra_info else ''}

                <h3>🔍 Traceback Details:</h3>
                <pre style="background: #2d3748; color: #e2e8f0; padding: 15px; border-radius: 6px; overflow-x: auto; font-size: 12px;">{tb_str}</pre>
                
                <p style="color: #718096; font-size: 13px; margin-top: 20px;">
                    Please check your environment variables, database connection, or API quota.
                </p>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(SENDER_EMAIL, APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        print(f"[ALERT SENT] Error notification email sent successfully for {service_name}.")
    except Exception as alert_err:
        print(f"[CRITICAL] Failed to send error alert email: {alert_err}")

def gemini_generate_with_retry(client, model, prompt, config=None, max_retries=3, base_delay=2.0):
    """
    Executes Gemini API generation with exponential backoff and jitter to protect
    against rate limits (429, ResourceExhausted) on free-tier API keys.
    """
    for attempt in range(1, max_retries + 1):
        try:
            kwargs = {"model": model, "contents": prompt}
            if config:
                kwargs["config"] = config
            response = client.models.generate_content(**kwargs)
            return response
        except Exception as e:
            err_msg = str(e).lower()
            is_rate_limit = any(term in err_msg for term in ["429", "resource_exhausted", "quota", "rate limit", "too many requests"])
            
            if attempt < max_retries and is_rate_limit:
                sleep_time = base_delay * (2 ** (attempt - 1)) + random.uniform(0.5, 1.5)
                print(f"[WARN] Gemini rate limit encountered (attempt {attempt}/{max_retries}). Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)
            else:
                raise e
