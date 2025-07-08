# backend/routes/debug_router.py
# ✅ Debug Router: Central hub for inspecting backend AI loop health, outcomes, logs, and strategy leaderboards

import os
import json
import subprocess
import requests
import csv
from collections import Counter
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse

router = APIRouter()

# === 📁 File paths used by diagnostics and logs ===
LOGS_DIR = os.path.join("backend", "logs")
LAST_JSON_LOG = os.path.join(LOGS_DIR, "last_training_log.json")
LAST_TRAINING_LOG_TXT = os.path.join(LOGS_DIR, "last_training_log.txt")
RETRAIN_LOG_PATH = os.path.join(LOGS_DIR, "retrain_worker.log")
FEEDBACK_PATH = os.path.join("backend", "feedback_data.json")
STRATEGY_PATH = os.path.join("backend", "strategy_log.json")
OUTCOMES_PATH = os.path.join("backend", "strategy_outcomes.csv")

# === 🔐 Supabase credentials ===
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# === ✅ GET /debug/run_news_ingestor — manually runs ingestion loop ===
@router.get("/debug/run_news_ingestor")
def run_news_ingestor():
    """
    🧠 Triggers news_ingestor.py manually using subprocess.
    ⏱️ Timeout increased to 90s to avoid premature kill on Render.
    """
    try:
        result = subprocess.run(
            ["python", "backend/news_ingestor.py"],
            capture_output=True,
            text=True,
            timeout=90
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run script: {str(e)}")

# === ✅ GET /debug/ingested_news — pulls latest beliefs from Supabase ===
@router.get("/debug/ingested_news")
def get_ingested_news(limit: int = 10):
    """
    🔍 Pulls latest ingested news beliefs from Supabase `news_beliefs` table.
    Replaces old local file-based version for cloud compatibility.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase credentials not set in environment.")

    try:
        url = f"{SUPABASE_URL}/rest/v1/news_beliefs?order=timestamp.desc&limit={limit}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}"
        }
        r = requests.get(url, headers=headers)

        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text)

        return {"entries": r.json()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

# === 🧪 Core AI loop diagnostics ===

@router.get("/debug/retrain_log")
def get_latest_retrain_log():
    """🔁 Load structured JSON from last_training_log.json"""
    if not os.path.exists(LAST_JSON_LOG):
        raise HTTPException(status_code=404, detail="No retraining log found.")
    try:
        with open(LAST_JSON_LOG, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read retrain log: {str(e)}")

@router.get("/debug/last_training_status", response_class=PlainTextResponse)
def read_last_training_status():
    """📄 Return raw text version of last training run"""
    if os.path.exists(LAST_TRAINING_LOG_TXT):
        with open(LAST_TRAINING_LOG_TXT, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No last training log found.")

@router.get("/debug/retrain_worker_log", response_class=PlainTextResponse)
def read_retrain_worker_log():
    """📄 Returns full retrain_worker.log from backend/logs"""
    if os.path.exists(RETRAIN_LOG_PATH):
        with open(RETRAIN_LOG_PATH, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="No retrain log found.")

@router.get("/last_training_log", response_class=PlainTextResponse)
def view_last_training_log():
    """📄 Alias route for viewing last training log (plain text)"""
    if os.path.exists(LAST_TRAINING_LOG_TXT):
        with open(LAST_TRAINING_LOG_TXT, "r") as f:
            return f.read()
    raise HTTPException(status_code=404, detail="Training log not found.")

@router.get("/debug/feedback_count")
def get_feedback_count():
    """📈 Count feedback entries in feedback_data.json"""
    if not os.path.exists(FEEDBACK_PATH):
        raise HTTPException(status_code=404, detail="feedback_data.json not found.")
    try:
        with open(FEEDBACK_PATH, "r") as f:
            data = json.load(f)
        return {"feedback_count": len(data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read feedback data: {str(e)}")

@router.get("/debug/last_strategy_log")
def get_last_strategy_log():
    """📊 Returns count + last entry from strategy_log.json"""
    if not os.path.exists(STRATEGY_PATH):
        raise HTTPException(status_code=404, detail="strategy_log.json not found.")
    try:
        with open(STRATEGY_PATH, "r") as f:
            data = json.load(f)
        return {
            "total_strategies": len(data),
            "last_entry": data[-1] if data else {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read strategy log: {str(e)}")

@router.get("/logs/recent", response_class=PlainTextResponse)
def get_recent_logs(lines: int = 50):
    """📜 Tail N lines from retrain_worker.log"""
    if not os.path.exists(RETRAIN_LOG_PATH):
        raise HTTPException(status_code=404, detail="Log file not found.")
    try:
        with open(RETRAIN_LOG_PATH, "r") as f:
            content = f.readlines()
            return "".join(content[-lines:])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading log file: {str(e)}")

@router.get("/debug/ai_loop_status")
def get_ai_loop_status():
    """
    🔁 Summary of current AI pipeline status:
    - Last strategy
    - Feedback count
    - Last retrain
    """
    status = {}
    try:
        if os.path.exists(STRATEGY_PATH):
            with open(STRATEGY_PATH, "r") as f:
                data = json.load(f)
                status["last_strategy"] = data[-1] if data else {}
        else:
            status["last_strategy"] = "Not available"
    except Exception as e:
        status["last_strategy"] = f"Error: {str(e)}"

    try:
        if os.path.exists(FEEDBACK_PATH):
            with open(FEEDBACK_PATH, "r") as f:
                status["feedback_count"] = len(json.load(f))
        else:
            status["feedback_count"] = 0
    except Exception as e:
        status["feedback_count"] = f"Error: {str(e)}"

    try:
        if os.path.exists(LAST_JSON_LOG):
            with open(LAST_JSON_LOG, "r") as f:
                status["last_retrain"] = json.load(f)
        else:
            status["last_retrain"] = "Not available"
    except Exception as e:
        status["last_retrain"] = f"Error: {str(e)}"

    return status

# === ✅ /debug/strategy_leaderboard — top strategy types by count ===
@router.get("/debug/strategy_leaderboard")
def strategy_leaderboard(limit: int = 10):
    """
    📊 Returns most common strategy types from strategy_log.json (cleaned).
    Handles corrupted rows gracefully.
    """
    if not os.path.exists(STRATEGY_PATH):
        raise HTTPException(status_code=404, detail="strategy_log.json not found.")
    
    try:
        with open(STRATEGY_PATH, "r") as f:
            data = json.load(f)

        # ✅ Filter out invalid entries
        strategy_types = []
        for entry in data:
            if isinstance(entry, dict):
                strat = entry.get("strategy")
                if isinstance(strat, dict):
                    strat_type = strat.get("type")
                    if strat_type:
                        strategy_types.append(strat_type)

        # ✅ Return top N most common
        top = Counter(strategy_types).most_common(limit)
        return [{"strategy": s, "count": c} for s, c in top]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Leaderboard generation error: {str(e)}")

# === ✅ /debug/pnl_leaderboard — ranks by actual outcome PnL% ===
@router.get("/debug/pnl_leaderboard")
def pnl_leaderboard(limit: int = 10):
    """
    🏆 Returns top N strategies from strategy_outcomes.csv based on actual PnL%.
    Filters corrupted or malformed rows. Sorted by pnl_percent descending.
    """
    if not os.path.exists(OUTCOMES_PATH):
        raise HTTPException(status_code=404, detail="strategy_outcomes.csv not found.")
    
    try:
        rows = []
        with open(OUTCOMES_PATH, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # ✅ Ensure all required fields exist and are valid
                    belief = row.get("belief", "")
                    ticker = row.get("ticker", "")
                    strategy = row.get("strategy", "")
                    pnl = float(row.get("pnl_percent", ""))
                    if strategy and ticker:
                        rows.append({
                            "belief": belief.strip(),
                            "ticker": ticker.strip(),
                            "strategy": strategy.strip(),
                            "pnl_percent": pnl
                        })
                except:
                    continue  # Skip bad rows

        # ✅ Sort by PnL%, highest first
        sorted_rows = sorted(rows, key=lambda x: x["pnl_percent"], reverse=True)
        return sorted_rows[:limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PNL leaderboard error: {str(e)}")
