"""
Take-profit and max-loss exits for real-money trades (2026-11-10, Murad chose the hybrid "C" design).

Where each exit lives:
  - Stocks (whole shares): BOTH exits live at Alpaca as a bracket order, placed with the buy. Nothing to watch here.
  - Options: Alpaca can't link exits to an option order, and option orders are day orders. So:
      * max loss: a STOP order at Alpaca, re-armed by this watcher at the start of every trading day
      * take profit: watched here; when the bid reaches the target we cancel the stop and sell with a limit at the bid

Restart safety (the web service restarts on every deploy):
  - everything is in the broker_exits table; the first tick after a restart catches up (a target hit while we were
    down sells immediately)
  - a DB lease means only one runner ticks, so the web service and a separate worker can't both sell
  - a heartbeat in kv_cache; watchdog() (run hourly by the seeder cron, and by the web service) alerts the owner when
    the watcher has been silent during market hours while exits are active

Runner: MP_EXITS_RUNNER=web (default, a thread in the web service) or worker (run `python -m backend.v4.exits` as its
own Render background worker; the web service then doesn't tick).
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import brokerage, db, market

log = logging.getLogger(__name__)

ACTIVE = ("waiting_fill", "armed", "tp_sent")
LEASE_SECONDS = 45
SELL_RETRY_SECONDS = 120
_OWNER = uuid.uuid4().hex[:12]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _kv(k: str) -> Optional[str]:
    row = db.query_one("SELECT v FROM kv_cache WHERE k = ?", (k,))
    return row["v"] if row else None


def _kv_set(k: str, v: str) -> None:
    db.execute("DELETE FROM kv_cache WHERE k = ?", (k,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (k, v, _now().isoformat()))


def _today() -> str:
    return market.today().isoformat()


def _update(eid: str, **kw) -> None:
    kw["updated_at"] = _now().isoformat()
    cols = ", ".join(f"{k} = ?" for k in kw)
    db.execute(f"UPDATE broker_exits SET {cols} WHERE id = ?", (*kw.values(), eid))


def _alert(account_id: str, title: str, body: str) -> None:
    try:
        from . import push
        push.send_to_account(account_id, {"title": title, "body": body, "url": "/account"})
    except Exception as e:  # alerts are best effort; never block an exit
        log.warning("exit alert failed: %s", e)


# ---------------------------------------------------------------------------------------------------------------
# Called by brokerage when an order with exits is sent
# ---------------------------------------------------------------------------------------------------------------
def on_placed(acc: dict, meta: dict, response: dict) -> None:
    ex = (meta or {}).get("exits")
    if not ex or not (ex.get("tp_pct") or ex.get("sl_pct")):
        return
    kind = meta.get("kind", "stock")
    now = _now().isoformat()
    db.execute("INSERT INTO broker_exits (id, account_id, env, symbol, kind, held_at, status, qty, source_order, entry, tp_pct, sl_pct, "
               "tp_price, sl_price, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (f"ex-{uuid.uuid4().hex[:16]}", acc["id"], brokerage.env(), meta.get("symbol") or meta.get("underlying"), kind,
                "alpaca" if kind == "stock" else "watched", "at_alpaca" if kind == "stock" else "waiting_fill",
                meta.get("qty"), response.get("id"), meta.get("est_price"), ex.get("tp_pct"), ex.get("sl_pct"),
                ex.get("tp_price"), ex.get("sl_price"), now, now))


def for_account(acc: dict) -> list[dict]:
    rows = db.query("SELECT * FROM broker_exits WHERE account_id = ? AND env = ? ORDER BY created_at DESC", (acc["id"], brokerage.env()))
    return [{k: r[k] for k in ("id", "symbol", "kind", "held_at", "status", "qty", "entry", "tp_pct", "sl_pct", "tp_price",
                               "sl_price", "note", "created_at")} for r in rows[:50]]


def cancel(acc: dict, eid: str) -> dict:
    """Stop watching an option exit and cancel its stop at Alpaca. (Stock brackets are cancelled in Alpaca's app.)"""
    r = db.query_one("SELECT * FROM broker_exits WHERE id = ? AND account_id = ?", (eid, acc["id"]))
    if not r:
        raise brokerage.BrokerError("That exit wasn't found.", 404)
    if r["status"] not in ACTIVE:
        return {"ok": True}
    for oid in (r["stop_order"], r["sell_order"]):
        if oid:
            _cancel_order(acc, oid)
    _update(eid, status="cancelled", note="You turned this exit off.")
    return {"ok": True}


# ---------------------------------------------------------------------------------------------------------------
# The watcher
# ---------------------------------------------------------------------------------------------------------------
def _order(acc: dict, oid: Optional[str]) -> dict:
    if not oid:
        return {}
    try:
        return brokerage._alpaca(acc, "GET", f"/v2/orders/{oid}")
    except brokerage.BrokerError:
        return {}


def _cancel_order(acc: dict, oid: str) -> None:
    try:
        brokerage._alpaca(acc, "DELETE", f"/v2/orders/{oid}")
    except brokerage.BrokerError:
        pass  # already filled or gone; the next tick reads its real status


def _held(acc: dict, symbol: str) -> float:
    p = brokerage._alpaca(acc, "GET", f"/v2/positions/{symbol}")
    return float(p.get("qty") or 0) if p else 0.0


def _open(o: dict) -> bool:
    return bool(o) and o.get("status") not in brokerage._FINAL


def _step(acc: dict, r: dict) -> None:
    eid, sym = r["id"], r["symbol"]
    if r["status"] == "waiting_fill":
        o = _order(acc, r["source_order"])
        filled = float(o.get("filled_qty") or 0)
        if filled > 0 and o.get("status") in brokerage._FINAL | {"partially_filled"} and float(o.get("filled_avg_price") or 0) > 0:
            if o.get("status") == "partially_filled":
                return  # wait until the buy finishes
            entry = float(o["filled_avg_price"])
            tp = round(entry * (1 + r["tp_pct"]), 2) if r["tp_pct"] else None
            sl = max(0.01, round(entry * (1 - r["sl_pct"]), 2)) if r["sl_pct"] else None
            _update(eid, status="armed", entry=entry, qty=filled, tp_price=tp, sl_price=sl)
            r = dict(r, status="armed", entry=entry, qty=filled, tp_price=tp, sl_price=sl)
        elif o and o.get("status") in brokerage._FINAL:
            _update(eid, status="cancelled", note="The buy didn't fill, so there's nothing to protect.")
            return
        else:
            return

    if r["status"] == "tp_sent":
        o = _order(acc, r["sell_order"])
        if o.get("status") == "filled":
            _update(eid, status="done", note=f"Take-profit sold at ${float(o.get('filled_avg_price') or 0):.2f}.")
            _alert(acc["id"], "Take-profit filled ✓", f"Sold {brokerage.option_label(sym)} at ${float(o.get('filled_avg_price') or 0):.2f}.")
            return
        sent = r["sell_sent_at"] or ""
        if _open(o) and sent and sent > (_now() - timedelta(seconds=SELL_RETRY_SECONDS)).isoformat():
            return  # give the limit order time to fill
        if _open(o):
            _cancel_order(acc, r["sell_order"])
            return  # next tick sees it cancelled
        _update(eid, status="armed", sell_order=None, note="The take-profit sale didn't fill; watching again.")
        r = dict(r, status="armed", sell_order=None)

    if r["status"] != "armed":
        return
    held = _held(acc, sym)
    if held <= 0:
        if r["stop_order"]:
            stop = _order(acc, r["stop_order"])
            if stop.get("status") == "filled":
                _update(eid, status="done", note=f"Max-loss stop sold at ${float(stop.get('filled_avg_price') or 0):.2f}.")
                _alert(acc["id"], "Max-loss stop filled", f"Sold {brokerage.option_label(sym)} at ${float(stop.get('filled_avg_price') or 0):.2f}. The loss was capped as planned.")
                return
            if _open(stop):
                _cancel_order(acc, r["stop_order"])
        _update(eid, status="done", note="You no longer hold it.")
        return
    qty = int(min(held, r["qty"] or held))
    stop = _order(acc, r["stop_order"])

    # 1) take profit first: the bid has reached the target
    q = market.option_quote(sym) if r["tp_price"] else None
    if r["tp_price"] and q and q["bid"] >= r["tp_price"]:
        if _open(stop):
            _cancel_order(acc, r["stop_order"])  # the stop holds the contracts; free them, sell next tick
            return
        try:
            res = brokerage._alpaca(acc, "POST", "/v2/orders", {
                "symbol": sym, "qty": str(qty), "side": "sell", "type": "limit", "limit_price": f"{q['bid']:.2f}",
                "time_in_force": "day", "client_order_id": f"mp-tp-{uuid.uuid4().hex[:12]}"})
        except brokerage.BrokerError as e:
            _update(eid, note=f"Take-profit sale was refused ({e}); retrying.")
            return
        _update(eid, status="tp_sent", sell_order=res.get("id"), sell_sent_at=_now().isoformat(), stop_order=None)
        _alert(acc["id"], "Take-profit hit 🎯", f"{brokerage.option_label(sym)} reached ${r['tp_price']:.2f}. Selling now at ${q['bid']:.2f}.")
        return

    # 2) max loss: keep a stop at Alpaca for today (option orders only last the day)
    if r["sl_price"]:
        if stop.get("status") == "filled":
            _update(eid, status="done", note=f"Max-loss stop sold at ${float(stop.get('filled_avg_price') or 0):.2f}.")
            _alert(acc["id"], "Max-loss stop filled", f"Sold {brokerage.option_label(sym)} at ${float(stop.get('filled_avg_price') or 0):.2f}. The loss was capped as planned.")
            return
        if _open(stop) and r["stop_day"] == _today():
            return
        if _open(stop):
            _cancel_order(acc, r["stop_order"])
            return
        try:
            res = brokerage._alpaca(acc, "POST", "/v2/orders", {
                "symbol": sym, "qty": str(qty), "side": "sell", "type": "stop", "stop_price": f"{r['sl_price']:.2f}",
                "time_in_force": "day", "client_order_id": f"mp-sl-{uuid.uuid4().hex[:12]}"})
            _update(eid, stop_order=res.get("id"), stop_day=_today(), note=None)
        except brokerage.BrokerError as e:
            _update(eid, note=f"Couldn't place today's max-loss stop ({e}); retrying.")


def _lease() -> bool:
    cur = _kv("exits:lease")
    if cur:
        owner, _, ts = cur.partition("|")
        if owner != _OWNER and time.time() - float(ts or 0) < LEASE_SECONDS:
            return False
    _kv_set("exits:lease", f"{_OWNER}|{time.time()}")
    return True


def tick() -> dict:
    """One pass over every active exit. Safe to call often; only the lease holder works."""
    if not brokerage.enabled() or not _lease():
        return {"ran": False}
    _kv_set("exits:beat", str(time.time()))
    if not market.is_open():
        return {"ran": True, "market_open": False}
    n = 0
    for r in db.query("SELECT * FROM broker_exits WHERE env = ? AND kind = 'option' AND status IN ('waiting_fill','armed','tp_sent')",
                      (brokerage.env(),)):
        acc = db.query_one("SELECT * FROM accounts WHERE id = ?", (r["account_id"],))
        if not acc:
            continue
        try:
            _step(acc, r)
            n += 1
        except Exception as e:
            log.warning("exit %s: %s", r["id"], e)
            _update(r["id"], note=f"Watcher error: {e}"[:300])
    return {"ran": True, "market_open": True, "checked": n}


def watchdog() -> Optional[str]:
    """Alert the account owners if exits are active, the market is open, and the watcher has been silent > 2 minutes.
    At most one alert an hour."""
    if not brokerage.enabled() or not market.is_open():
        return None
    rows = db.query("SELECT DISTINCT account_id FROM broker_exits WHERE kind = 'option' AND status IN ('waiting_fill','armed','tp_sent')")
    if not rows:
        return None
    beat = float(_kv("exits:beat") or 0)
    if time.time() - beat < 120:
        return None
    last = float(_kv("exits:watchdog_alert") or 0)
    if time.time() - last < 3600:
        return "quiet"
    _kv_set("exits:watchdog_alert", str(time.time()))
    mins = int((time.time() - beat) // 60) if beat else None
    for r in rows:
        _alert(r["account_id"], "Exit watcher is down ⚠️",
               f"Take-profits aren't being watched{f' (silent {mins} min)' if mins else ''}. Max-loss stops placed today are still at Alpaca.")
    return "alerted"


def run_forever() -> None:
    while True:
        try:
            tick()
        except Exception as e:
            log.warning("exits tick: %s", e)
        time.sleep(15 if market.is_open() else 60)


def start_background() -> None:
    """Web-service thread unless MP_EXITS_RUNNER=worker. The watchdog runs in the web service either way."""
    import threading

    def watch():
        time.sleep(180)
        while True:
            try:
                watchdog()
            except Exception as e:
                log.warning("exits watchdog: %s", e)
            time.sleep(300)

    threading.Thread(target=watch, daemon=True, name="exits-watchdog").start()
    if os.getenv("MP_EXITS_RUNNER", "web").lower() != "worker":
        threading.Thread(target=run_forever, daemon=True, name="exits").start()


if __name__ == "__main__":  # Render background worker: PYTHONPATH=./ python -m backend.v4.exits
    logging.basicConfig(level=logging.INFO)
    run_forever()
