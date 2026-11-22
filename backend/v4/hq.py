"""
Agent HQ (2026-11-13): every agent at one table, one meeting thread with Murad.

- Roster: docs/hq/agents.json. Status: docs/hq/status/<key>.json, written by each agent at the end of its run.
  Read from GitHub (fresh, cached 2 min) so status-only commits don't need a deploy; falls back to the deployed copy.
- Messages: table hq_messages. Only the owner (brokerage.is_owner) can read the page or post. Agents read their
  messages with read-only SQL and answer in their status file ("replies").
"""
from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from . import db

ROOT = Path(__file__).resolve().parents[2] / "docs" / "hq"
RAW = "https://raw.githubusercontent.com/msawaged/MarketPlaygroundV3/v4-polish/docs/hq/"
_cache: dict = {}
TTL = 120


class HQError(Exception):
    pass


def _fetch(name: str) -> Optional[str]:
    hit = _cache.get(name)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    txt = None
    try:
        with urllib.request.urlopen(RAW + name, timeout=6) as r:
            txt = r.read().decode("utf-8")
    except Exception:
        p = ROOT / name
        txt = p.read_text("utf-8") if p.exists() else None
    _cache[name] = (time.time(), txt)
    return txt


def _json(name: str, default):
    try:
        t = _fetch(name)
        return json.loads(t) if t else default
    except Exception:
        return default


def _cron_field(f: str, lo: int, hi: int) -> Optional[set]:
    """One cron field -> the set of values it allows (None = '*', any). Supports a, a-b, */n, a-b/n and lists."""
    if f == "*":
        return None
    out: set = set()
    for part in f.split(","):
        rng, _, step = part.partition("/")
        if rng == "*":
            a, b = lo, hi
        elif "-" in rng:
            a, b = (int(x) for x in rng.split("-", 1))
        else:
            a = int(rng)
            b = hi if step else a
        out.update(range(a, b + 1, int(step) if step else 1))
    return out


def next_run(cron: Optional[str], now: Optional[datetime] = None) -> Optional[str]:
    """When a scheduled agent next starts (UTC ISO), from its 5-field cron with an optional 'CRON_TZ=<zone> ' prefix,
    the same string its scheduled task uses (docs/hq/agents.json "cron"). None if there's no schedule or it can't be read.
    Shown on the HQ page so Murad knows when a message he sends will be read."""
    if not cron:
        return None
    try:
        from zoneinfo import ZoneInfo
        tz = timezone.utc
        c = cron.strip()
        if c.startswith("CRON_TZ="):
            z, c = c[len("CRON_TZ="):].split(None, 1)
            tz = ZoneInfo(z)
        mi, ho, dom, mon, dow = c.split()
        mins, hours = _cron_field(mi, 0, 59), _cron_field(ho, 0, 23)
        doms, mons, dows = _cron_field(dom, 1, 31), _cron_field(mon, 1, 12), _cron_field(dow, 0, 7)
        if dows is not None and 7 in dows:
            dows = dows | {0}
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        local = now.astimezone(tz)
        for d in range(0, 367):
            day = (local + timedelta(days=d)).date()
            if mons is not None and day.month not in mons:
                continue
            dom_ok = doms is None or day.day in doms
            dow_ok = dows is None or ((day.weekday() + 1) % 7) in dows
            # standard cron: when both day fields are restricted, either one matching is enough
            if not ((dom_ok or dow_ok) if (doms is not None and dows is not None) else (dom_ok and dow_ok)):
                continue
            for h in sorted(hours if hours is not None else range(24)):
                for m in sorted(mins if mins is not None else range(60)):
                    t = datetime(day.year, day.month, day.day, h, m, tzinfo=tz).astimezone(timezone.utc)
                    if t > now:
                        return t.isoformat().replace("+00:00", "Z")
    except Exception:
        return None
    return None


def roster() -> list[dict]:
    agents = _json("agents.json", [])
    out = []
    for a in agents:
        st = _json(f"status/{a['key']}.json", None) or {}
        out.append({**a, "status": st, "next_run": next_run(a.get("cron"))})
    return out


def post(body: str, to: str = "all") -> dict:
    body = (body or "").strip()
    if not body:
        raise HQError("Write a message first.")
    keys = {a["key"] for a in _json("agents.json", [])} | {"all"}
    to = to if to in keys else "all"
    row = db.query_one("SELECT MAX(id) AS m FROM hq_messages")
    new_id = int((row or {}).get("m") or 0) + 1   # one writer (the owner), so max+1 is safe and portable
    db.execute("INSERT INTO hq_messages (id, author, to_agent, body, created_at) VALUES (?,?,?,?,?)",
               (new_id, "murad", to, body[:4000], datetime.now(timezone.utc).isoformat()))
    return {"ok": True, "id": new_id, "to": to}


def board() -> dict:
    agents = roster()
    msgs = db.query("SELECT id, author, to_agent, body, created_at FROM hq_messages ORDER BY id DESC LIMIT 200")
    thread = [{"kind": "murad", "id": m["id"], "to": m["to_agent"], "body": m["body"], "at": m["created_at"]} for m in msgs]
    for a in agents:
        st = a["status"]
        for r in (st.get("replies") or [])[-10:]:
            thread.append({"kind": "agent", "agent": a["key"], "name": a["name"], "re": r.get("re"),
                           "body": str(r.get("body", ""))[:2000], "at": r.get("at") or st.get("updated_at")})
        if st.get("last_run"):
            thread.append({"kind": "status", "agent": a["key"], "name": a["name"], "body": st["last_run"],
                           "at": st.get("updated_at")})
    thread.sort(key=lambda x: x.get("at") or "")
    for a in agents:  # which of Murad's messages each agent hasn't read yet
        upto = int((a["status"] or {}).get("read_up_to") or 0)
        a["unread"] = sum(1 for m in msgs if m["id"] > upto and m["to_agent"] in ("all", a["key"]))
    needs = [{"agent": a["key"], "name": a["name"], "need": n, "at": a["status"].get("updated_at")}
             for a in agents for n in (a["status"].get("needs_from_murad") or [])]
    return {"agents": agents, "thread": thread[-150:], "needs": needs}
