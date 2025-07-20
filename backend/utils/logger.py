# backend/utils/logger.py
# ✅ Unified logging utility: logs to local files + Supabase DB

import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# ✅ Load environment variables from .env file
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def write_training_log(message: str, source: str = "unknown"):
    """
    Logs training activity to:
    1. backend/logs/last_training_log.txt      — latest log snapshot
    2. backend/logs/retrain_worker.log         — full history log
    3. backend/logs/last_training_log.json     — JSON used by API
    4. Supabase (training_logs table)          — cloud storage
    """
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"\n🕒 {timestamp} — {source}\n{message}\n"

    # ✅ Make sure logs directory exists
    log_dir = os.path.join("backend", "logs")
    os.makedirs(log_dir, exist_ok=True)

    # ✅ 1. Save as latest plaintext snapshot
    last_txt_path = os.path.join(log_dir, "last_training_log.txt")
    with open(last_txt_path, "w") as f:
        f.write(full_message)

    # ✅ 2. Append to rolling text log
    rolling_log_path = os.path.join(log_dir, "retrain_worker.log")
    with open(rolling_log_path, "a") as f:
        f.write(full_message)

    # ✅ 3. Save JSON version for API access
    json_log_path = os.path.join(log_dir, "last_training_log.json")
    with open(json_log_path, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "source": source,
            "message": message
        }, f)

    # ✅ 4. Push to Supabase training_logs table
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            response = requests.post(
                f"{SUPABASE_URL}/rest/v1/training_logs",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                },
                json={
                    "created_at": timestamp,
                    "source": source,
                    "message": message
                }
            )
            response.raise_for_status()
            print("✅ Supabase log saved")  # ✅ Confirm success in console
        except Exception as e:
            print(f"[⚠️ Supabase logging failed] {e}")

    # ✅ Also print to console for Render logs
    print(full_message.strip())
