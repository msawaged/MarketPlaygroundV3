"""
Backup feeder inside the web service: keeps the brain learning even if the separate hourly job (v4-seed-live) is
broken. Once an hour, if no successful learning round was recorded in the last 75 minutes, it runs a smaller round
itself (60 practice beliefs, 3 at a time, plus today's news), and retrains at most every 6 hours so user requests stay
fast. All the usual spending caps in seeder.auto still apply. MP_WEB_FEEDER=0 turns it off.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

from . import db

log = logging.getLogger(__name__)


def _last(job: str) -> dict:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (f"health:{job}",))
    try:
        return json.loads(row["v"]) if row else {}
    except Exception:
        return {}


def should_feed(now: datetime) -> bool:
    h = _last("learning")
    if not h.get("at") or not h.get("ok"):
        return True
    return now - datetime.fromisoformat(h["at"]) > timedelta(minutes=75)


def should_train(now: datetime) -> bool:
    from . import nn
    hist = nn.history(1)
    return not hist or now - datetime.fromisoformat(hist[0]["created_at"]) > timedelta(hours=6)


def feed_once() -> dict:
    from . import seeder
    now = datetime.now(timezone.utc)
    if not should_feed(now):
        return {"skipped": "the hourly job is healthy"}
    out = seeder.auto_with_health(batch_override=int(os.getenv("MP_WEB_FEED_BATCH", "60")), concurrency=3,
                                  train=should_train(now))
    return {"fed": True, "news": (out.get("news") or {}).get("ok", 0), "backfill": (out.get("backfill") or {}).get("ok", 0)}


def start_background(interval: int = 3600) -> None:
    if os.getenv("MP_WEB_FEEDER", "1") == "0" or os.getenv("MP_SEED_ENABLED", "true").lower() not in ("1", "true", "yes"):
        return

    def loop():
        time.sleep(600)  # let the server settle (and give the regular job its chance first)
        while True:
            try:
                lease = db.query_one("SELECT v FROM kv_cache WHERE k = 'feeder_lease'")
                if not lease or time.time() - float(lease["v"]) > interval * 0.9:
                    db.execute("DELETE FROM kv_cache WHERE k = 'feeder_lease'")
                    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
                               ("feeder_lease", str(time.time()), datetime.now(timezone.utc).isoformat()))
                    log.info("feeder: %s", feed_once())
            except Exception as e:
                log.warning("feeder: %s", e)
            time.sleep(interval)

    threading.Thread(target=loop, name="feeder", daemon=True).start()
