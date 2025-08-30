# backend/news_ingestor_loop.py
"""
News Ingestor Worker Loop
- Runs backend/news_ingestor.py on an env-driven interval.
- Backoff on failures, graceful shutdown on SIGTERM (Render-friendly).
- Stdout-only, timestamped logs (Render captures them).
"""

import os
import signal
import sys
import time
import subprocess
from datetime import datetime, timezone

RUNNING = True

def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _log(msg: str):
    print(f"[{_utc_now()}] [news_ingestor_loop] {msg}", flush=True)

def _handle_sigterm(signum, frame):
    global RUNNING
    _log("Received SIGTERM, shutting down after current cycle…")
    RUNNING = False

signal.signal(signal.SIGTERM, _handle_sigterm)

def run_once() -> int:
    _log("Starting ingestion cycle: python backend/news_ingestor.py --once")
    try:
        result = subprocess.run(
            [sys.executable, "backend/news_ingestor.py", "--once"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutes hard cap for a single run
        )
    except subprocess.TimeoutExpired:
        _log("ERROR: news_ingestor.py timed out.")
        return 124
    except Exception as e:
        _log(f"ERROR: unexpected exception launching news_ingestor.py: {e}")
        return 1

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        _log(f"STDERR from news_ingestor.py:\n{result.stderr}")

    return result.returncode

def main():
    poll_seconds = int(os.getenv("NEWS_POLL_SECONDS", "300"))
    max_backoff = min(max(2 * poll_seconds, 60), 3600)  # cap backoff 1h
    backoff = 5
    consecutive_failures = 0

    _log(f"Loop online. Poll interval={poll_seconds}s, max_backoff={max_backoff}s")

    while RUNNING:
        start = time.time()
        rc = run_once()
        elapsed = time.time() - start

        if rc == 0:
            consecutive_failures = 0
            backoff = 5
            sleep_for = max(poll_seconds - elapsed, 1)
            _log(f"Cycle OK (elapsed={elapsed:.2f}s). Sleeping {sleep_for:.0f}s.")
            end_sleep = time.time() + sleep_for
            while RUNNING and time.time() < end_sleep:
                time.sleep(min(1, end_sleep - time.time()))
        else:
            consecutive_failures += 1
            backoff = min(int(backoff * 2), max_backoff)
            _log(f"Cycle FAILED (rc={rc}). failures={consecutive_failures}. Backing off {backoff}s.")
            end_sleep = time.time() + backoff
            while RUNNING and time.time() < end_sleep:
                time.sleep(min(1, end_sleep - time.time()))

    _log("Exited loop cleanly.")

if __name__ == "__main__":
    main()

