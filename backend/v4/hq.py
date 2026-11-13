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
from datetime import datetime, timezone
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


def roster() -> list[dict]:
    agents = _json("agents.json", [])
    out = []
    for a in agents:
        st = _json(f"status/{a['key']}.json", None) or {}
        out.append({**a, "status": st})
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
    needs = [{"agent": a["key"], "name": a["name"], "need": n} for a in agents for n in (a["status"].get("needs_from_murad") or [])]
    return {"agents": agents, "thread": thread[-150:], "needs": needs}
