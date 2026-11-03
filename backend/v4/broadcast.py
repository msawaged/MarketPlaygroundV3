"""
One-time product emails to existing users, approved by the owner. Each broadcast has a key; every person gets it at
most once (kv_cache), only verified accounts that haven't unsubscribed, always with an unsubscribe link.
"""
from __future__ import annotations

import html
import logging
import threading
import time
from datetime import datetime, timezone

from . import db, mailer, notify

log = logging.getLogger(__name__)

# Owner approved on 2026-11-01 ("yes send the emails").
BROADCASTS = [{
    "key": "2026-11-01-whats-new",
    "subject": "What's new in MarketPlayground: a smarter brain + morning alerts",
    "title": "The brain got smarter.",
    "points": [
        "Smarter #1 pick: on 1,549 past calls it had never seen, it beat the S&P 500 56% of the time (the old way: 51%).",
        "Story mode: any market story in 30 seconds, with what happened, why it matters, the twist, and the stocks it moves.",
        "Market's open alerts: the day's top story and the stocks it moves, around 9:35 am Eastern on trading days.",
    ],
    "button": "Turn on alerts",
    "path": "/account",
    "tip": "On iPhone, first tap Share, then Add to Home Screen, and open MarketPlayground from your home screen.",
}]


def _kv(k):
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (k,))
    return row["v"] if row else None


def _kv_set(k, v):
    db.execute("DELETE FROM kv_cache WHERE k = ?", (k,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (k, v, datetime.now(timezone.utc).isoformat()))


def send(b: dict) -> dict:
    site, api = notify._site(), notify._api()
    sent = skipped = 0
    from . import auth
    for acc in db.query("SELECT id, email, name FROM accounts WHERE verified = 1 AND COALESCE(notify_calls, 1) = 1"):
        if auth.is_blocked(acc["email"]):
            continue
        mark = f"broadcast:{b['key']}:{acc['id']}"
        if _kv(mark):
            skipped += 1
            continue
        first = (acc.get("name") or "").split(" ")[0]
        unsub = f"{api}/v4/unsubscribe?a={acc['id']}&s={notify.unsubscribe_sig(acc['id'])}"
        url = f"{site}{b['path']}"
        hi = f"Hi {first}," if first else "Hi,"
        text = (f"{hi}\n\nA few things are new in MarketPlayground:\n\n" + "\n".join(f"- {p}" for p in b["points"])
                + f"\n\n{b['button']}: {url}\n{b['tip']}\n\nPractice money only. Not investment advice.\nUnsubscribe: {unsub}\n")
        lead = html.escape(hi) + "<br><br>" + "<br><br>".join("• " + html.escape(p) for p in b["points"])
        foot = (f"{html.escape(b['tip'])}<br><br>Practice money only. Not investment advice. "
                f"<a href=\"{html.escape(unsub)}\" style=\"color:#64748b\">Unsubscribe</a>")
        try:
            mailer.send(acc["email"], b["subject"], text, mailer.button_html(b["title"], lead, url, b["button"], foot))
        except Exception as e:
            log.warning("broadcast %s: %s", acc["id"], e)
            continue
        _kv_set(mark, datetime.now(timezone.utc).isoformat())
        sent += 1
        time.sleep(1)  # gentle on the mail server
    out = {"key": b["key"], "sent": sent, "already": skipped}
    _kv_set(f"broadcast_result:{b['key']}", str(out))
    return out


def run_pending() -> list:
    """Safe to run on every start: each person is marked when their email goes out, so nobody gets one twice and
    anyone missed (mail server hiccup, restart) is picked up next time."""
    return [send(b) for b in BROADCASTS]


def start_background() -> None:
    def go():
        time.sleep(100)
        try:
            log.info("broadcast: %s", run_pending())
        except Exception as e:
            log.warning("broadcast: %s", e)
    threading.Thread(target=go, name="broadcast", daemon=True).start()
