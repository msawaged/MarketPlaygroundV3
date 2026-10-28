# backend/retrain_worker.py
# ✅ Retrain worker: triggers on (file signature change OR feedback/news deltas) AND cooldown_ok.
# Watches your actual training CSVs so model edits trigger retrains.

import os, sys, time, json, hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# ── Import shim (works as module and script) ───────────────────────────────────
try:
    from .train_all_models import train_all_models
    from .utils.logger import write_training_log
except ImportError:
    ROOT = Path(__file__).resolve().parents[1]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from backend.train_all_models import train_all_models
    from backend.utils.logger import write_training_log

# ── Paths / constants ─────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH   = LOG_DIR / "retrain_worker.log"
STATE_PATH = LOG_DIR / "last_retrain.json"
LOCK_PATH  = LOG_DIR / "retrain.lock"

# Files whose content changes should trigger retrain
TRAINING_FILES: List[Path] = [
    # feedback/news & outcomes
    BASE_DIR / "feedback_log.csv",
    BASE_DIR / "feedback.csv",
    BASE_DIR / "news_beliefs.csv",
    BASE_DIR / "strategy_outcomes.csv",
    BASE_DIR / "Training_Strategies.csv",
    BASE_DIR / "beliefs.csv",
    # ✅ training datasets actually used by trainers
    BASE_DIR / "training_data" / "clean_belief_tags.csv",
    BASE_DIR / "training_data" / "final_belief_asset_training.csv",
    BASE_DIR / "training_data" / "cleaned_strategies.csv",
]

# Optional metrics JSONs the trainers write (used if train_all_models returns None)
BELIEF_METRICS   = BASE_DIR / "belief_model_metrics.json"
ASSET_METRICS    = BASE_DIR / "asset_model_metrics.json"
FEEDBACK_METRICS = BASE_DIR / "feedback_model_metrics.json"
STRAT_METRICS    = BASE_DIR / "strategy_model_metrics.json"

# Tunables via env
FEEDBACK_THRESHOLD  = int(os.getenv("RETRAIN_FEEDBACK_THRESHOLD", 5))
NEWS_THRESHOLD      = int(os.getenv("RETRAIN_NEWS_THRESHOLD", 3))
COOLDOWN_SECONDS    = int(os.getenv("RETRAIN_COOLDOWN_SECONDS", 1800))  # 30 min
POLL_INTERVAL       = int(os.getenv("RETRAIN_POLL_INTERVAL", 60))       # 60s

# ── Logging ───────────────────────────────────────────────────────────────────
def log_to_file(message: str):
    ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{ts}] {message}"
    print(line)
    try:
        with LOG_PATH.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        write_training_log(message, source="retrain_worker")
    except Exception:
        pass

# ── File fingerprint & counts (fast) ──────────────────────────────────────────
def _file_fingerprint(p: Path) -> str:
    """
    Compute a lightweight fingerprint of a file for signature tracking.
    Uses path, size, mtime, plus first/last 1KB of content.
    """
    try:
        if not p.exists() or not p.is_file():
            return f"{p.name}:MISSING"
        st = p.stat()
        h = hashlib.sha256()
        h.update(str(p.resolve()).encode())          # file path
        h.update(str(st.st_size).encode())           # file size
        h.update(str(int(st.st_mtime)).encode())     # mtime (seconds)
        with p.open("rb") as f:
            head = f.read(1024)
            tail = b""
            if st.st_size > 2048:
                f.seek(-1024, 2)
                tail = f.read(1024)
        h.update(head)
        h.update(tail)
        return h.hexdigest()
    except Exception as e:
        return f"{p.name}:ERR:{e}"


def compute_data_signature(files: List[Path]) -> str:
    parts = [_file_fingerprint(p) for p in files]
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def count_csv_rows_fast(p: Path) -> int:
    try:
        if not p.exists(): return 0
        with p.open("r", errors="ignore") as f:
            n = sum(1 for _ in f)
        return max(0, n - 1)  # subtract header
    except Exception:
        return 0

def current_row_counts(files: List[Path]) -> Dict[str, int]:
    return {p.name: count_csv_rows_fast(p) for p in files if p.exists()}

# ── State & lock ──────────────────────────────────────────────────────────────
def load_state() -> Dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            pass
    return {"feedback_count": 0, "news_count": 0, "last_signature": None, "cooldown_until": 0}

def save_state(feedback_count: int, news_count: int, signature: str):
    state = {
        "feedback_count": feedback_count,
        "news_count": news_count,
        "last_signature": signature,
        "cooldown_until": time.time() + COOLDOWN_SECONDS,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    STATE_PATH.write_text(json.dumps(state, indent=2))

class RetrainLocked(RuntimeError): pass

def acquire_lock(ttl_seconds=1800):
    now = time.time()
    if LOCK_PATH.exists():
        try:
            lock = json.loads(LOCK_PATH.read_text())
            if now < lock.get("expires_at", 0):
                raise RetrainLocked("Another training process is running")
        except Exception:
            pass  # stale lock → ignore
    LOCK_PATH.write_text(json.dumps({"expires_at": now + ttl_seconds}))

def release_lock():
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass

# ── Metrics fallback (never null) ─────────────────────────────────────────────
def _read_metrics(p: Path) -> Dict:
    try:
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return {}

def collect_all_metrics() -> Dict:
    counts = current_row_counts(TRAINING_FILES)
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "belief":   _read_metrics(BELIEF_METRICS),
        "asset":    _read_metrics(ASSET_METRICS),
        "feedback": _read_metrics(FEEDBACK_METRICS),
        "strategy": _read_metrics(STRAT_METRICS),
        "dataset": {"row_counts": counts},
    }

# ── Main loop ─────────────────────────────────────────────────────────────────
def run_retraining_loop(interval: int = POLL_INTERVAL):
    log_to_file("🧠 Retrain worker started (signature OR deltas; with cooldown).")

    while True:
        try:
            state = load_state()
            last_sig = state.get("last_signature")
            cooldown_until = state.get("cooldown_until", 0)

            sig = compute_data_signature(TRAINING_FILES)
            counts = current_row_counts(TRAINING_FILES)

            # choose the active feedback/news files we track for deltas
            current_feedback = counts.get("feedback_log.csv", 0) or counts.get("feedback.csv", 0)
            current_news = counts.get("news_beliefs.csv", 0)

            delta_feedback = current_feedback - state.get("feedback_count", 0)
            delta_news = current_news - state.get("news_count", 0)

            signature_changed = (sig != last_sig)
            has_meaningful_delta = (delta_feedback >= FEEDBACK_THRESHOLD) or (delta_news >= NEWS_THRESHOLD)
            cooldown_expired = (time.time() >= cooldown_until)

            log_to_file(f"🧾 Feedback: {current_feedback} (Δ {delta_feedback}) | News: {current_news} (Δ {delta_news})")
            log_to_file(f"🔎 Gate → sig_changed={signature_changed} delta_ok={has_meaningful_delta} cooldown_ok={cooldown_expired}")

            # ✅ New logic: retrain when (signature_changed OR deltas met) AND cooldown_ok
            if not ((signature_changed or has_meaningful_delta) and cooldown_expired):
                reasons = []
                if not signature_changed and not has_meaningful_delta:
                    reasons.append("no changes (sig & deltas)")
                if not cooldown_expired:
                    reasons.append(f"cooldown ({int(cooldown_until - time.time())}s left)")
                log_to_file("⏸️ Skipping retrain: " + ", ".join(reasons) if reasons else "⏸️ Skipping retrain")
                log_to_file(f"⏳ Sleeping for {interval} seconds...")
                time.sleep(interval)
                continue

            # acquire lock and run training
            try:
                acquire_lock(ttl_seconds=max(COOLDOWN_SECONDS, 900))
            except RetrainLocked as e:
                log_to_file(f"🔒 Skip: {e}")
                log_to_file(f"⏳ Sleeping for {interval} seconds...")
                time.sleep(interval)
                continue

            log_to_file("🔁 [START] Model retraining initiated...")

            returned = None
            try:
                returned = train_all_models()
            except TypeError:
                train_all_models()

            metrics = returned if isinstance(returned, dict) else collect_all_metrics()

            # persist state (advance counts + signature + cooldown)
            save_state(current_feedback, current_news, sig)

            # log metrics (never null)
            pretty = json.dumps(metrics, indent=2)
            log_to_file("📊 [REPORT] Model metrics:\n" + (pretty[:4000] + ("… (truncated)" if len(pretty) > 4000 else "")))
            (LOG_DIR / f"metrics_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json").write_text(pretty)
            log_to_file("✅ Retraining complete and state saved")

        except KeyboardInterrupt:
            log_to_file("🛑 Interrupted (Ctrl-C). Exiting.")
            release_lock()
            sys.exit(0)
        except Exception as e:
            log_to_file(f"❌ Uncaught error: {e}")
        finally:
            release_lock()
            log_to_file(f"⏳ Sleeping for {interval} seconds...")
            time.sleep(interval)

if __name__ == "__main__":
    run_retraining_loop()
