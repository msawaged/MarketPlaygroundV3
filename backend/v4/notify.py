"""
"You called it" emails: when a call someone made at least a week ago is clearly playing out (its picks are ahead of
the S&P 500 in the direction they expected), email them once for that belief. At most one email per person per week,
only to confirmed accounts that haven't unsubscribed. Runs hourly inside the web service, which already has the
email settings.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import db, engine, mailer

log = logging.getLogger(__name__)
MIN_AGE_DAYS = 7
MIN_LEAD = 0.02          # ahead of the S&P 500 by at least 2 points
GAP_DAYS = 7             # at most one email per person per week


def _site() -> str:
    return (os.getenv("MP_SITE_URL") or "https://marketplayground-web.onrender.com").rstrip("/")


def _api() -> str:
    return (os.getenv("MP_API_URL") or "https://marketplayground-backend-18mm.onrender.com").rstrip("/")


def _key() -> bytes:
    return (os.getenv("MP_TOKEN_KEY") or os.getenv("MP_ADMIN_TOKEN") or "dev-only").encode()


def unsubscribe_sig(account_id: str) -> str:
    return hmac.new(_key(), f"unsub:{account_id}".encode(), hashlib.sha256).hexdigest()[:32]


def unsubscribe(account_id: str, sig: str) -> bool:
    if not account_id or not hmac.compare_digest(unsubscribe_sig(account_id), sig or ""):
        return False
    db.execute("UPDATE accounts SET notify_calls = 0 WHERE id = ?", (account_id,))
    return True


def _kv(k: str) -> Optional[str]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (k,))
    return row["v"] if row else None


def _kv_set(k: str, v: str) -> None:
    db.execute("DELETE FROM kv_cache WHERE k = ?", (k,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (k, v, datetime.now(timezone.utc).isoformat()))


def _pick_call(beliefs: list[dict]) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    for b in beliefs:
        c = b.get("call") or {}
        try:
            age = (now - datetime.fromisoformat(b["created_at"])).days
        except Exception:
            continue
        if age >= MIN_AGE_DAYS and c.get("playing_out") and (c.get("vs_spy") or 0) >= MIN_LEAD \
                and not _kv(f"notified:{b['belief_id']}"):
            return dict(b, age=age)
    return None


def _email(acc: dict, b: dict) -> tuple[str, str, str]:
    lead = round(b["call"]["vs_spy"] * 100, 1)
    text_belief = (b.get("text") or "").strip()[:140]
    first = (acc.get("name") or "").split(" ")[0]
    subject = "You called it 👀"
    days = b["age"]
    when = f"{days} days ago" if days < 60 else f"{round(days / 30)} months ago"
    unsub = f"{_api()}/v4/unsubscribe?a={acc['id']}&s={unsubscribe_sig(acc['id'])}"
    lead_line = (f"{'Hi ' + first + ', y' if first else 'Y'}ou said “{text_belief}” {when}. "
                 f"So far it's playing out: the companies behind it are {lead:+.1f} points ahead of the S&P 500 "
                 "in the direction you expected.")
    body = (f"{lead_line}\n\nSee how each pick is doing: {_site()}/my\n\n"
            "Practice money only. Past results don't predict future ones.\n"
            f"Don't want these? Unsubscribe: {unsub}\n")
    html_body = mailer.button_html(
        "You called it.", html.escape(lead_line), f"{_site()}/my", "See your calls",
        f"Practice money only. Past results don't predict future ones. "
        f"<a href=\"{html.escape(unsub)}\" style=\"color:#64748b\">Unsubscribe</a>")
    return subject, body, html_body


def run(max_emails: int = 50) -> dict:
    if not (mailer.configured() or os.getenv("MP_MAIL_TEST_SINK")):
        return {"sent": 0, "skipped": "email not configured"}
    accounts = db.query("SELECT id, uid, email, name FROM accounts WHERE verified = 1 AND COALESCE(notify_calls, 1) = 1")
    sent, now = 0, datetime.now(timezone.utc)
    for acc in accounts:
        if sent >= max_emails:
            break
        last = _kv(f"notify_last:{acc['id']}")
        if last and now - datetime.fromisoformat(last) < timedelta(days=GAP_DAYS):
            continue
        try:
            b = _pick_call(engine.my_beliefs(acc["uid"]).get("beliefs") or [])
            if not b:
                continue
            subject, text, html_body = _email(acc, b)
            mailer.send(acc["email"], subject, text, html_body)
        except Exception as e:  # one bad account never stops the rest
            log.warning("notify: %s: %s", acc["id"], e)
            continue
        _kv_set(f"notified:{b['belief_id']}", now.isoformat())
        _kv_set(f"notify_last:{acc['id']}", now.isoformat())
        sent += 1
    return {"sent": sent, "accounts": len(accounts)}


def start_background(interval: int = 3600) -> None:
    """Hourly loop in the web service. MP_NOTIFY_ENABLED=0 turns it off."""
    if os.getenv("MP_NOTIFY_ENABLED", "1") == "0":
        return

    def loop():
        time.sleep(120)  # let the server finish starting
        while True:
            try:
                # one runner at a time across workers: a short lease in kv_cache
                lease = _kv("notify_lease")
                if not lease or time.time() - float(lease) > interval * 0.9:
                    _kv_set("notify_lease", str(time.time()))
                    log.info("notify: %s", run())
            except Exception as e:
                log.warning("notify loop: %s", e)
            time.sleep(interval)

    threading.Thread(target=loop, name="notify", daemon=True).start()
