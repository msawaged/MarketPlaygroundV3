"""
Push notifications ("Market's open"): a short alert each trading day at about 9:35 am Eastern with the top news story
and the companies it moves, opening that story in Story mode.

Web Push with VAPID. The server makes its own key pair on first use and keeps it in kv_cache (nothing to configure).
Subscriptions live in push_subs; dead ones (404/410 from the push service) are removed. One daily send, guarded by a
kv lease so only one worker sends.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from . import db

log = logging.getLogger(__name__)
CONTACT = os.getenv("MP_PUSH_CONTACT", "mailto:hello.marketplayground@gmail.com")
SEND_AT_ET = (9, 35)


def init(conn=None) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS push_subs (
        endpoint TEXT PRIMARY KEY,
        sub TEXT NOT NULL,
        account_id TEXT,
        device_id TEXT,
        created_at TEXT NOT NULL,
        last_ok TEXT,
        fails INTEGER NOT NULL DEFAULT 0
    )""")


def _kv(k: str) -> Optional[str]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (k,))
    return row["v"] if row else None


def _kv_set(k: str, v: str) -> None:
    db.execute("DELETE FROM kv_cache WHERE k = ?", (k,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (k, v, datetime.now(timezone.utc).isoformat()))


def _vapid():
    """(Vapid instance, public key for the browser). Created once and stored."""
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01
    pem = _kv("vapid_private_pem")
    if not pem:
        v = Vapid01()
        v.generate_keys()
        pem = v.private_pem().decode()
        _kv_set("vapid_private_pem", pem)
    v = Vapid01.from_pem(pem.encode())
    raw = v.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    return v, base64.urlsafe_b64encode(raw).decode().rstrip("=")


def public_key() -> str:
    return _vapid()[1]


def _clean_sub(sub: Any) -> Optional[dict]:
    if not isinstance(sub, dict):
        return None
    ep = str(sub.get("endpoint") or "")
    keys = sub.get("keys") or {}
    if not ep.startswith("https://") or len(ep) > 1000 or not keys.get("p256dh") or not keys.get("auth"):
        return None
    return {"endpoint": ep, "keys": {"p256dh": str(keys["p256dh"])[:200], "auth": str(keys["auth"])[:100]}}


def subscribe(sub: Any, account_id: Optional[str] = None, device_id: Optional[str] = None) -> dict:
    init()
    s = _clean_sub(sub)
    if not s:
        raise ValueError("That doesn't look like a browser push subscription.")
    db.execute("DELETE FROM push_subs WHERE endpoint = ?", (s["endpoint"],))
    db.execute("INSERT INTO push_subs (endpoint, sub, account_id, device_id, created_at) VALUES (?,?,?,?,?)",
               (s["endpoint"], json.dumps(s), account_id, (device_id or "")[:80], datetime.now(timezone.utc).isoformat()))
    return {"ok": True}


def unsubscribe(endpoint: str) -> dict:
    init()
    db.execute("DELETE FROM push_subs WHERE endpoint = ?", (str(endpoint or ""),))
    return {"ok": True}


def is_subscribed(endpoint: str) -> bool:
    init()
    return bool(db.query_one("SELECT 1 AS x FROM push_subs WHERE endpoint = ?", (str(endpoint or ""),)))


def send_one(sub: dict, payload: dict, sender=None) -> bool:
    """True if delivered. Removes subscriptions the push service says are gone."""
    if sender is None:
        from pywebpush import webpush as sender
    v, _ = _vapid()
    try:
        sender(subscription_info=sub, data=json.dumps(payload), vapid_private_key=v, vapid_claims={"sub": CONTACT}, ttl=3600)
        db.execute("UPDATE push_subs SET last_ok = ?, fails = 0 WHERE endpoint = ?", (datetime.now(timezone.utc).isoformat(), sub["endpoint"]))
        return True
    except Exception as e:  # pywebpush.WebPushException carries the response
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (404, 410):
            db.execute("DELETE FROM push_subs WHERE endpoint = ?", (sub["endpoint"],))
        else:
            db.execute("UPDATE push_subs SET fails = fails + 1 WHERE endpoint = ?", (sub["endpoint"],))
            db.execute("DELETE FROM push_subs WHERE endpoint = ? AND fails >= 5", (sub["endpoint"],))
        log.warning("push: send failed (%s): %s", code, str(e)[:160])
        return False


def send_test(endpoint: str, sender=None) -> dict:
    init()
    row = db.query_one("SELECT sub FROM push_subs WHERE endpoint = ?", (str(endpoint or ""),))
    if not row:
        raise ValueError("Turn on alerts first.")
    last = _kv(f"push_test:{endpoint[-40:]}")
    if last and time.time() - float(last) < 60:
        raise ValueError("Give it a minute between tests.")
    _kv_set(f"push_test:{endpoint[-40:]}", str(time.time()))
    ok = send_one(json.loads(row["sub"]), {"title": "MarketPlayground alerts are on ✅",
                                           "body": "You'll get the Market's open story around 9:35 am Eastern on trading days.",
                                           "url": "/story"}, sender)
    return {"ok": ok}


def market_open_payload(feed: dict) -> Optional[dict]:
    items = (feed or {}).get("items") or []
    if not items:
        return None
    it = items[0]
    tick = ", ".join(c["ticker"] for c in it.get("companies", [])[:3])
    head = it["headline"] if len(it["headline"]) <= 90 else it["headline"][:87].rsplit(" ", 1)[0] + "…"
    from urllib.parse import quote
    return {"title": "Market's open 🔔", "body": f"{head}" + (f" · Moves: {tick}" if tick else "") + " · Believe it or doubt it?",
            "url": f"/story?h={quote(it['headline'])}"}


def send_market_open(sender=None, feed: Optional[dict] = None) -> dict:
    init()
    if feed is None:
        from . import movers
        feed = movers.feed()
    payload = market_open_payload(feed)
    if not payload:
        return {"sent": 0, "reason": "no story"}
    sent = 0
    for row in db.query("SELECT sub FROM push_subs"):
        if send_one(json.loads(row["sub"]), payload, sender):
            sent += 1
    return {"sent": sent, "title": payload["body"][:80]}


def _due(now_utc: datetime) -> bool:
    from zoneinfo import ZoneInfo
    et = now_utc.astimezone(ZoneInfo("America/New_York"))
    return et.weekday() < 5 and (et.hour, et.minute) >= SEND_AT_ET and et.hour < 11


def start_background(interval: int = 120) -> None:
    """Checks every 2 minutes; sends once per trading day after 9:35 am ET (skips market holidays)."""
    if os.getenv("MP_PUSH_ENABLED", "1") == "0":
        return

    def loop():
        time.sleep(60)
        while True:
            try:
                now = datetime.now(timezone.utc)
                from zoneinfo import ZoneInfo
                day = now.astimezone(ZoneInfo("America/New_York")).date().isoformat()
                if _due(now) and _kv("push_market_open_date") != day:
                    from . import market
                    if (market.clock() or {}).get("is_open"):
                        _kv_set("push_market_open_date", day)  # claim first: one send per day across workers
                        log.info("push: market open %s", send_market_open())
                    else:
                        _kv_set("push_market_open_date", day)  # holiday: nothing to send today
                if _kv("push_market_open_date") == day or not _due(now):  # updates never collide with the morning alert window
                    r = send_pending_update()
                    if r.get("sent"):
                        log.info("push: update %s", r)
            except Exception as e:
                log.warning("push loop: %s", e)
            time.sleep(interval)

    threading.Thread(target=loop, name="push", daemon=True).start()


# ---------------------------------------------------------------------------------------------------------------
# Product updates: each new item is pushed once to everyone, at most one a day, during daytime Eastern.
# Add new items at the TOP; the id must be unique and never reused.
UPDATES = [
    {"id": "2026-11-02-muline", "title": "New: MuLine 📈",
     "body": "Our own trend line is on every pick now: uptrend or downtrend at a glance, built to spot turns early without crying wolf.",
     "url": "/chat"},
    {"id": "2026-11-01-smarter-pick", "title": "The brain got smarter 🧠",
     "body": "Our new #1 pick beats the S&P 500 more often than the old way, on 1,700+ calls it had never seen. See the live scorecard.",
     "url": "/live"},
    {"id": "2026-10-31-story-mode", "title": "New: Story mode 🎬",
     "body": "Any market story in 30 seconds: what happened, why it matters, the twist, and the stocks it moves.",
     "url": "/story"},
]


def send_pending_update(sender=None, now_utc: Optional[datetime] = None) -> dict:
    init()
    from zoneinfo import ZoneInfo
    now_utc = now_utc or datetime.now(timezone.utc)
    et = now_utc.astimezone(ZoneInfo("America/New_York"))
    if not (11 <= et.hour < 19):
        return {"sent": 0, "reason": "outside daytime"}
    if _kv("push_update_day") == et.date().isoformat():
        return {"sent": 0, "reason": "already sent one today"}
    item = next((u for u in UPDATES if not _kv(f"push_update_sent:{u['id']}")), None)
    if not item:
        return {"sent": 0, "reason": "nothing new"}
    _kv_set(f"push_update_sent:{item['id']}", now_utc.isoformat())
    _kv_set("push_update_day", et.date().isoformat())
    sent = sum(1 for row in db.query("SELECT sub FROM push_subs")
               if send_one(json.loads(row["sub"]), {k: item[k] for k in ("title", "body", "url")}, sender))
    return {"sent": sent, "id": item["id"]}


def send_to_account(account_id: str, payload: dict, sender=None) -> int:
    """Personal alerts (e.g. "You called it") to every device the person turned alerts on for."""
    init()
    return sum(1 for row in db.query("SELECT sub FROM push_subs WHERE account_id = ?", (account_id,))
               if send_one(json.loads(row["sub"]), payload, sender))
