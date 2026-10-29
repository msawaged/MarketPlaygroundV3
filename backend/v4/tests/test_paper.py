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
