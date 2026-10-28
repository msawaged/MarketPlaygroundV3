"""Practice portfolio: open a position, see it with its id, sell it, cash comes back."""
from decimal import Decimal

import pytest

pytest.importorskip("yfinance")  # part of requirements.txt; skipped in the light test env


def test_paper_open_and_close(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    from backend.paper_trading import PaperTradingEngine
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
