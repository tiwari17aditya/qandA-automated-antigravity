import re
import json
import time
import random
import traceback
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import urllib.request
import urllib.error
from google import genai

from config import (
    SENDER_EMAIL,
    APP_PASSWORD,
    RECEIVER_EMAIL,
    GEMINI_API_KEY,
    GROQ_API_KEY,
    LLM_PROVIDER,
    GEMINI_MODEL,
    GROQ_MODEL,
)

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

def clean_ai_json_output(raw_text: str) -> str:
    """
    Cleans raw AI completion by stripping DeepSeek reasoning <think> tags
    and markdown ```json ... ``` wrappers.
    """
    # 1. Remove <think>...</think> reasoning blocks (e.g. from DeepSeek R1)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_text, flags=re.DOTALL).strip()
    
    # 2. Extract JSON content inside markdown code blocks
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    return cleaned

def call_groq_api(api_key: str, model: str, prompt: str, response_json: bool = False) -> str:
    """
    Direct HTTP client for Groq OpenAI-compatible chat completion API.
    Zero external dependencies, fast and lightweight.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "MPPSC-Quiz-Bot/2.0",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
    }
    if response_json:
        payload["response_format"] = {"type": "json_object"}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=35) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        return res_data["choices"][0]["message"]["content"]

def generate_ai_completion(prompt: str, response_json: bool = False) -> str:
    """
    Unified multi-provider AI completion engine with automatic failover across:
    1. Google Gemini Pool: gemini-2.5-flash, gemini-2.0-flash, gemini-2.0-flash-lite, gemini-1.5-flash
    2. Groq Open-Source Pool: deepseek-r1-distill-llama-70b, qwen-2.5-32b, mistral-saba-24b, gemma2-9b-it
    """
    gemini_models = [GEMINI_MODEL, "gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
    groq_models = [GROQ_MODEL, "deepseek-r1-distill-llama-70b", "qwen-2.5-32b", "mistral-saba-24b", "gemma2-9b-it"]

    # Filter duplicates while preserving order
    gemini_pool = [m for i, m in enumerate(gemini_models) if m and m not in gemini_models[:i]]
    groq_pool = [m for i, m in enumerate(groq_models) if m and m not in groq_models[:i]]

    # Determine provider priority based on LLM_PROVIDER
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        provider_order = [("groq", groq_pool), ("gemini", gemini_pool)]
    else:
        provider_order = [("gemini", gemini_pool), ("groq", groq_pool)]

    last_error = None

    for provider, model_list in provider_order:
        if provider == "gemini":
            if not GEMINI_API_KEY:
                continue
            client = genai.Client(api_key=GEMINI_API_KEY)
            for model_name in model_list:
                for attempt in range(1, 3):
                    try:
                        print(f"      Attempting AI generation with Gemini ({model_name})...")
                        kwargs = {"model": model_name, "contents": prompt}
                        if response_json:
                            kwargs["config"] = {"response_mime_type": "application/json"}
                        res = client.models.generate_content(**kwargs)
                        if res and res.text:
                            return res.text
                    except Exception as e:
                        last_error = e
                        err_msg = str(e).lower()
                        print(f"[WARN] Gemini ({model_name}) error: {e}")
                        if attempt < 2 and any(t in err_msg for t in ["429", "503", "unavailable", "quota", "temporary"]):
                            time.sleep(2.0 + random.uniform(0.5, 1.5))

        elif provider == "groq":
            if not GROQ_API_KEY:
                continue
            for model_name in model_list:
                for attempt in range(1, 3):
                    try:
                        print(f"      Attempting AI generation with Groq Open-Source ({model_name})...")
                        raw_text = call_groq_api(GROQ_API_KEY, model_name, prompt, response_json=response_json)
                        if raw_text:
                            return raw_text
                    except Exception as e:
                        last_error = e
                        print(f"[WARN] Groq ({model_name}) error: {e}")
                        if attempt < 2:
                            time.sleep(2.0 + random.uniform(0.5, 1.5))

    if last_error:
        raise last_error
    raise RuntimeError("No AI API keys configured or all AI providers failed.")

def gemini_generate_with_retry(client, model, prompt, config=None, max_retries=3, base_delay=3.0):
    """
    Backwards-compatible wrapper delegating to generate_ai_completion.
    """
    is_json = bool(config and config.get("response_mime_type") == "application/json")
    text = generate_ai_completion(prompt=prompt, response_json=is_json)
    
    class FakeResponse:
        def __init__(self, t):
            self.text = t
    return FakeResponse(text)


