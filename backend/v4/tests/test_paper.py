"""Practice portfolio: open a position, see it with its id, sell it, cash comes back."""
from decimal import Decimal

import pytest

pytest.importorskip("yfinance")  # part of requirements.txt; skipped in the light test env


def test_paper_open_and_close(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    from backend.paper_trading import PaperTradingEngine
    import backend.paper_trading as pt
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": True})
    eng = PaperTradingEngine(db_path=str(tmp_path / "p.db"))
    prices = {"WSO": Decimal("100")}
    monkeypatch.setattr(eng, "_get_real_market_price", lambda t: prices[t])
    r = eng.execute_paper_trade("u1", {"ticker": "WSO", "type": "Buy Stock", "asset_class": "equity",
                                       "trade_legs": [{"action": "Buy", "ticker": "WSO"}], "investment_amount": 1000}, "pipes")
    assert r["status"] == "success"
    pos = eng.get_portfolio("u1")["positions"]
    assert len(pos) == 1 and pos[0]["position_id"] and pos[0]["quantity"] == 10
    prices["WSO"] = Decimal("110")
    c = eng.close_position("u1", pos[0]["position_id"])
    assert c["status"] == "success" and abs(c["realized_pnl"] - 100.0) < 1e-6
    after = eng.get_portfolio("u1")
    assert after["positions"] == [] and after["account"]["cash_balance"] > 100000 - 20


def test_orders_placed_while_closed_fill_at_the_next_open(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "q.db"))
    prices = {"WSO": Decimal("100")}
    monkeypatch.setattr(eng, "_get_real_market_price", lambda t: prices[t])
    state = {"open": False, "fill": None}
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": state["open"], "next_open": "2026-10-29T09:30:00-04:00"})
    monkeypatch.setattr(pt, "_open_after", lambda t, after: state["fill"])
    start = eng.get_portfolio("u2")["account"]

    # after hours: queued, buying power held, no position yet
    r = eng.execute_paper_trade("u2", {"ticker": "WSO", "type": "Buy Stock", "asset_class": "equity",
                                       "trade_legs": [{"action": "Buy", "ticker": "WSO"}], "investment_amount": 1000}, "pipes")
    assert r["status"] == "queued" and "opening price" in r["message"]
    p = eng.get_portfolio("u2")
    assert p["positions"] == [] and len(p["queued_orders"]) == 1 and p["market"]["is_open"] is False
    assert p["account"]["buying_power"] < start["buying_power"] and p["account"]["cash_balance"] == start["cash_balance"]

    # the market opens 5% higher: it fills at the open, not at last night's price
    state.update(open=True, fill=("2026-10-29", 105.0))
    p = eng.get_portfolio("u2")
    assert p["queued_orders"] == [] and len(p["positions"]) == 1
    assert abs(p["positions"][0]["avg_price"] - 105.0) < 1e-6 and p["positions"][0]["quantity"] == 10
    assert abs((start["cash_balance"] - p["account"]["cash_balance"]) - 1050.0) < 10.0   # plus the practice commission

    # selling after hours queues too, and fills at the following open
    state.update(open=False, fill=None)
    c = eng.close_position("u2", p["positions"][0]["position_id"])
    assert c["status"] == "queued"
    assert len(eng.get_portfolio("u2")["positions"]) == 1
    state.update(open=True, fill=("2026-10-30", 110.0))
    p = eng.get_portfolio("u2")
    assert p["positions"] == [] and p["queued_orders"] == []
    assert p["account"]["cash_balance"] > start["cash_balance"] + 30   # bought 105, sold 110 x10 (+$50), minus fees


def test_cancel_queued_returns_buying_power(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "c.db"))
    monkeypatch.setattr(eng, "_get_real_market_price", lambda t: Decimal("50"))
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": False, "next_open": None})
    monkeypatch.setattr(pt, "_open_after", lambda t, after: None)
    bp0 = eng.get_portfolio("u3")["account"]["buying_power"]
    eng.execute_paper_trade("u3", {"ticker": "ABC", "type": "Buy Stock", "asset_class": "equity",
                                   "trade_legs": [{"action": "Buy", "ticker": "ABC"}], "investment_amount": 500}, "x")
    oid = eng.get_portfolio("u3")["queued_orders"][0]["order_id"]
    assert eng.cancel_queued("u3", oid)["status"] == "cancelled"
    p = eng.get_portfolio("u3")
    assert p["queued_orders"] == [] and abs(p["account"]["buying_power"] - bp0) < 1e-6
    assert eng.cancel_queued("u3", oid)["status"] == "error"


@pytest.mark.parametrize("seed", [4, 11, 42])
def test_random_trade_sequences_keep_the_books_balanced(tmp_path, monkeypatch, seed):
    """300 random buys, sells, queued orders, cancels and fills across market open/close.
    The money must always add up: cash == start - what was paid + what came back, and buying
    power == cash - money held for orders still waiting for the open."""
    import random
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "f.db"))
    rng = random.Random(seed)
    prices = {t: Decimal(str(rng.randint(5, 400))) for t in ("AAA", "BBB", "CCC", "DDD")}
    state = {"open": True, "day": 0}
    monkeypatch.setattr(eng, "_get_real_market_price", lambda t: prices[t])
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": state["open"], "next_open": None})
    # a queued order fills at the "next open" price once the market has opened again
    monkeypatch.setattr(pt, "_open_after", lambda t, after: (f"2026-11-{state['day'] % 28 + 1:02d}", float(prices[t])) if state["open"] else None)
    uid = "fuzz"
    start = eng.get_portfolio(uid)["account"]["cash_balance"]

    def check():
        p = eng.get_portfolio(uid)
        a = p["account"]
        with eng._get_db_connection() as conn:
            paid = conn.execute("SELECT COALESCE(SUM(net_amount),0) FROM transactions WHERE user_id=? AND transaction_type IN ('BUY')", (uid,)).fetchone()[0]
            got = conn.execute("SELECT COALESCE(SUM(net_amount),0) FROM transactions WHERE user_id=? AND transaction_type IN ('SELL')", (uid,)).fetchone()[0]
            holds = 0.0
            for o in conn.execute("SELECT * FROM orders WHERE user_id=? AND status='pending' AND order_type!='close'", (uid,)).fetchall():
                holds += o["quantity"] * o["price"] + (o["commission"] or 0)
            n_pos = conn.execute("SELECT COUNT(*) FROM positions WHERE user_id=?", (uid,)).fetchone()[0]
        assert abs(a["cash_balance"] - (start - paid + got)) < 0.05, (a, paid, got)
        assert abs(a["buying_power"] - (a["cash_balance"] - holds)) < 0.05, (a, holds)
        assert a["buying_power"] >= -0.01 and a["cash_balance"] >= -0.01
        mv = sum(x["market_value"] for x in p["positions"])
        assert abs(a["total_value"] - (a["cash_balance"] + mv)) < 0.05
        assert len(p["positions"]) == n_pos
        return p

    ops = {"buy": 0, "sell": 0, "cancel": 0, "queued": 0, "rejected": 0}
    for step in range(300):
        r = rng.random()
        if r < 0.1:
            state["open"] = not state["open"]; state["day"] += 1
        elif r < 0.2:
            t = rng.choice(list(prices)); prices[t] = max(Decimal("1"), prices[t] * Decimal(str(round(rng.uniform(0.8, 1.25), 3))))
        elif r < 0.6:
            t = rng.choice(list(prices))
            res = eng.execute_paper_trade(uid, {"ticker": t, "type": "Buy Stock", "asset_class": "equity",
                                                "trade_legs": [{"action": "Buy", "ticker": t}],
                                                "investment_amount": rng.choice([1, 50, 500, 2500, 20000, 90000])}, "b")
            ops["queued" if res["status"] == "queued" else "buy" if res["status"] == "success" else "rejected"] += 1
        elif r < 0.85:
            pos = eng.get_portfolio(uid)["positions"]
            if pos:
                res = eng.close_position(uid, rng.choice(pos)["position_id"])
                assert res["status"] in ("success", "queued"), res
                ops["sell"] += 1
        else:
            q = eng.get_portfolio(uid)["queued_orders"]
            if q:
                assert eng.cancel_queued(uid, rng.choice(q)["order_id"])["status"] == "cancelled"
                ops["cancel"] += 1
        check()
    state["open"] = True
    final = check()
    assert final["queued_orders"] == [] or all(o["side"] for o in final["queued_orders"])
    assert ops["buy"] > 20 and ops["queued"] > 5 and ops["sell"] > 10, ops
