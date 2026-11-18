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
    assert abs((start["cash_balance"] - p["account"]["cash_balance"]) - 1050.0) < 1e-6   # commission-free, like real US brokers

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


def test_practice_options_open_value_close_and_expire(tmp_path, monkeypatch):
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    from backend.v4 import market, practice_options as po
    from datetime import date, timedelta
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "o.db"))
    monkeypatch.setattr(pt, "paper_engine", eng)
    spot = {"v": 100.0}
    today = {"d": date(2026, 6, 1)}
    monkeypatch.setattr(market, "latest_price", lambda t: spot["v"])
    monkeypatch.setattr(market, "asset_info", lambda t: {"symbol": t})
    monkeypatch.setattr(market, "features", lambda t: {"vol60": 0.3})
    monkeypatch.setattr(market, "today", lambda: today["d"])
    clk = {"is_open": True}
    monkeypatch.setattr(market, "clock", lambda: clk)
    exp = (date(2026, 6, 1) + timedelta(days=90)).isoformat()
    legs = [{"action": "Buy", "option_type": "Call", "strike_price": 100, "expiration": exp, "quantity": 1, "instrument": "option"},
            {"action": "Sell", "option_type": "Call", "strike_price": 110, "expiration": exp, "quantity": 1, "instrument": "option",
             "est_premium": 0.01}]  # a client-sent price is ignored
    cash0 = 100000.0
    r = po.open_trade("u9", "XYZ", "Bull Call Spread", legs, 2, "it'll rise")
    assert r["status"] == "success" and 100 < r["set_aside"] < 2000  # a 10-wide spread costs < $1,000 a contract
    assert r["market_closed"] is False and "closed" not in r["message"]
    pos = po.positions("u9")
    assert len(pos) == 1 and abs(pos[0]["pnl"]) < 1e-6
    spot["v"] = 115.0
    gain = po.positions("u9")[0]["pnl"]
    assert gain > 0
    c = po.close("u9", pos[0]["position_id"])
    assert abs(c["pnl"] - gain) < 1e-6
    with eng._get_db_connection() as conn:
        cash = float(conn.execute("SELECT cash_balance FROM users WHERE user_id = 'u9'").fetchone()["cash_balance"])
    assert abs(cash - (cash0 + gain)) < 0.05
    # a credit trade sets aside its worst case, and settles at expiration on its own
    put_credit = [{"action": "Sell", "option_type": "Put", "strike_price": 95, "expiration": exp, "quantity": 1, "instrument": "option"},
                  {"action": "Buy", "option_type": "Put", "strike_price": 90, "expiration": exp, "quantity": 1, "instrument": "option"}]
    clk["is_open"] = False  # weekend: options still open right away (unlike shares), and the message says so
    r2 = po.open_trade("u9", "XYZ", "Bull Put Spread", put_credit, 1)
    assert r2["market_closed"] is True and "doesn't wait for the open" in r2["message"]
    assert 300 < r2["set_aside"] <= 500  # worst case of a 5-wide spread, less the credit
    today["d"] = date(2026, 6, 1) + timedelta(days=91)
    spot["v"] = 120.0  # puts expire worthless: keep the credit
    monkeypatch.setattr(market, "session_close_on", lambda t, d: (d.isoformat(), 120.0))
    assert po.positions("u9") == []
    with eng._get_db_connection() as conn:
        cash2 = float(conn.execute("SELECT cash_balance FROM users WHERE user_id = 'u9'").fetchone()["cash_balance"])
    assert cash2 > cash  # the credit was kept
    with pytest.raises(po.PracticeError):
        po.open_trade("u9", "XYZ", "x", [{"action": "Buy", "option_type": "Call", "strike_price": -5, "expiration": exp}], 1)
    with pytest.raises(po.PracticeError):
        po.open_trade("u9", "XYZ", "x", legs, 100000)


def test_shares_are_fractional_so_the_amount_matches_the_card(tmp_path, monkeypatch):
    """$1,000 of a $5,000 stock buys 0.2 shares ($1,000), not 1 share ($5,000); $1,000 of a $185 stock is ~$1,000, not $925."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": True})
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "fr.db"))
    prices = {"BIG": Decimal("5000"), "MID": Decimal("185")}
    monkeypatch.setattr(eng, "_get_real_market_price", lambda t: prices[t])
    cash0 = eng.get_portfolio("u5")["account"]["cash_balance"]
    for t in prices:
        r = eng.execute_paper_trade("u5", {"ticker": t, "type": "Buy Stock", "asset_class": "equity",
                                           "trade_legs": [{"action": "Buy", "ticker": t}], "investment_amount": 1000}, "x")
        assert r["status"] == "success", r
    pos = {p["ticker"]: p for p in eng.get_portfolio("u5")["positions"]}
    assert abs(pos["BIG"]["quantity"] - 0.2) < 1e-9
    assert abs(pos["MID"]["quantity"] - 5.4054) < 1e-9
    spent = cash0 - eng.get_portfolio("u5")["account"]["cash_balance"]
    assert 1999 < spent <= 2000
    prices["BIG"] = Decimal("5500")
    c = eng.close_position("u5", pos["BIG"]["position_id"])
    assert c["status"] == "success" and abs(c["realized_pnl"] - 100.0) < 1e-6   # 0.2 x $500
    r = eng.execute_paper_trade("u5", {"ticker": "BIG", "type": "Buy Stock", "asset_class": "equity",
                                       "trade_legs": [{"action": "Buy", "ticker": "BIG"}], "investment_amount": 0.1}, "x")
    assert r["status"] == "error" and "too small" in r["message"]  # 10 cents of a $5,000 stock rounds to 0 shares


def test_no_made_up_price_when_every_feed_is_down(tmp_path, monkeypatch):
    """It used to fill at an invented $100 when the price feed failed. Now the trade is refused instead."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    from backend.v4 import market
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": True})
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "np.db"))
    def down(*a, **k):
        raise RuntimeError("feed down")
    monkeypatch.setattr(market, "latest_price", down)
    monkeypatch.setattr(pt.yf, "Ticker", down)
    r = eng.execute_paper_trade("u6", {"ticker": "ZZZ", "type": "Buy Stock", "asset_class": "equity",
                                       "trade_legs": [{"action": "Buy", "ticker": "ZZZ"}], "investment_amount": 1000}, "x")
    assert r["status"] == "error" and "live price" in r["message"]
    assert eng.get_portfolio("u6")["positions"] == []
    # with the card's feed up, the fill uses that same price
    monkeypatch.setattr(market, "latest_price", lambda t: 40.0)
    r = eng.execute_paper_trade("u6", {"ticker": "ZZZ", "type": "Buy Stock", "asset_class": "equity",
                                       "trade_legs": [{"action": "Buy", "ticker": "ZZZ"}], "investment_amount": 1000}, "x")
    assert r["status"] == "success" and abs(eng.get_portfolio("u6")["positions"][0]["avg_price"] - 40.0) < 1e-9


def test_sold_positions_leave_a_closed_trade_record(tmp_path, monkeypatch):
    """A sale (now, or queued for the open) and a closed / expired options trade show up in Closed trades with what
    they cost, what came back and the gain, and those numbers match the cash that moved."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    from backend.routes import paper_trading_router as rt
    from backend.v4 import market, practice_options as po
    from datetime import date, timedelta
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "ct.db"))
    monkeypatch.setattr(pt, "paper_engine", eng)
    monkeypatch.setattr(rt, "paper_engine", eng)
    prices = {"WSO": Decimal("100"), "ABC": Decimal("50")}
    monkeypatch.setattr(eng, "_get_real_market_price", lambda t: prices[t])
    state = {"open": True, "fill": None}
    monkeypatch.setattr(pt, "_clock", lambda: {"is_open": state["open"], "next_open": None})
    monkeypatch.setattr(pt, "_open_after", lambda t, after: state["fill"])
    buy = lambda t, amt: eng.execute_paper_trade("u", {"ticker": t, "type": "Buy Stock", "asset_class": "equity",
                                                       "trade_legs": [{"action": "Buy", "ticker": t}],
                                                       "investment_amount": amt}, f"{t} goes up")
    assert eng.closed_trades("u") == []
    buy("WSO", 1000)
    buy("ABC", 500)
    pos = {p["ticker"]: p for p in eng.get_portfolio("u")["positions"]}
    prices["WSO"] = Decimal("112")
    eng.close_position("u", pos["WSO"]["position_id"])
    state["open"] = False  # after hours: queued, no record until it fills
    eng.close_position("u", pos["ABC"]["position_id"])
    assert [r["ticker"] for r in eng.closed_trades("u")] == ["WSO"]
    state.update(open=True, fill=("2026-10-30", 45.0))
    eng.get_portfolio("u")
    rows = {r["ticker"]: r for r in eng.closed_trades("u")}
    w, a = rows["WSO"], rows["ABC"]
    assert w["quantity"] == 10 and w["avg_price"] == 100 and w["exit_price"] == 112
    assert w["cost"] == 1000 and w["proceeds"] == 1120 and w["pnl"] == 120 and w["pnl_pct"] == 12
    assert w["belief"] == "WSO goes up" and w["opened_at"]
    assert a["exit_price"] == 45 and a["pnl"] == -50 and a["closed_at"].startswith("2026-10-30")
    cash = eng.get_portfolio("u")["account"]["cash_balance"]
    assert abs(cash - (100000 + w["pnl"] + a["pnl"])) < 0.01

    # options: one closed by hand, one settled at expiration
    spot = {"v": 100.0}
    today = {"d": date.today()}
    monkeypatch.setattr(market, "latest_price", lambda t: spot["v"])
    monkeypatch.setattr(market, "asset_info", lambda t: {"symbol": t})
    monkeypatch.setattr(market, "features", lambda t: {"vol60": 0.3})
    monkeypatch.setattr(market, "today", lambda: today["d"])
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    exp = (date.today() + timedelta(days=60)).isoformat()
    call = [{"action": "Buy", "option_type": "Call", "strike_price": 100, "expiration": exp, "quantity": 1, "instrument": "option"}]
    o1 = po.open_trade("u", "XYZ", "Long Call", call, 2, "XYZ pops")
    o2 = po.open_trade("u", "XYZ", "Long Call", call, 1)
    spot["v"] = 108.0
    c = po.close("u", o1["position_id"])
    today["d"] = date.today() + timedelta(days=61)
    spot["v"] = 90.0  # expires worthless: the whole cost is lost
    monkeypatch.setattr(market, "session_close_on", lambda t, d: (d.isoformat(), 90.0))
    assert po.positions("u") == []
    opts = {r["id"]: r for r in po.closed("u")}
    assert abs(opts[o1["position_id"]]["pnl"] - c["pnl"]) < 0.01 and opts[o1["position_id"]]["expired"] is False
    assert opts[o1["position_id"]]["contracts"] == 2 and opts[o1["position_id"]]["belief"] == "XYZ pops"
    e = opts[o2["position_id"]]
    assert e["expired"] is True and e["proceeds"] == 0 and abs(e["pnl"] + o2["set_aside"]) < 0.01
    assert e["closed_at"].startswith(exp)

    # the portfolio carries both kinds, newest first, and the record adds up to the account
    with eng._get_db_connection() as conn:
        cash = float(conn.execute("SELECT cash_balance FROM users WHERE user_id = 'u'").fetchone()["cash_balance"])
    allrows = rt._closed_trades("u")
    assert {r["kind"] for r in allrows} == {"shares", "options"} and len(allrows) == 4
    assert abs(cash - (100000 + sum(r["pnl"] for r in allrows))) < 0.05
    keys = [rt._when_key(r["closed_at"]) for r in allrows]
    assert keys == sorted(keys, reverse=True)

    # a sale made before this record existed still shows, with its cost unknown (not a made-up gain)
    with eng._get_db_connection() as conn:
        conn.execute("""INSERT INTO transactions (transaction_id, user_id, order_id, ticker, transaction_type, quantity,
                        price, amount, commission, net_amount, executed_at) VALUES ('t-old','u','o-old','OLD','SELL',
                        3, 20, 60, 0, 60, '2026-11-01T15:00:00+00:00')""")
    old = [r for r in eng.closed_trades("u") if r["ticker"] == "OLD"][0]
    assert old["pnl"] is None and old["cost"] is None and old["proceeds"] == 60


def test_closed_trade_times_carry_their_offset(tmp_path, monkeypatch):
    """Closing times go to the phone with a UTC offset (a bare server time read as local time put a 7:30pm ET close
    on the next day), older bare rows are read right, and only a 4pm-or-later settle on expiration day says Expired."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import json as _json
    import backend.paper_trading as pt
    from backend.routes import paper_trading_router as rt
    from backend.v4 import practice_options as po
    from datetime import datetime
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "tz.db"))
    monkeypatch.setattr(pt, "paper_engine", eng)
    monkeypatch.setattr(rt, "paper_engine", eng)
    eng._initialize_user("u")
    legs = _json.dumps([{"action": "Buy", "option_type": "Put", "strike_price": 39, "expiration": "2027-02-19",
                         "quantity": 1, "instrument": "option"}])
    rows = [("evening", "2026-11-16T23:30:00.123456"),       # older bare row: server UTC = 6:30pm ET Nov 16
            ("expiry", "2027-02-19T16:00:00"),               # older bare expiry settle (meant New York)
            ("morning", "2027-02-19T15:00:00.5+00:00"),      # closed by hand at 10am ET on expiration day
            ("new", po._now_utc())]
    with eng._get_db_connection() as conn:
        po.init(conn)
        for pid, shut in rows:
            conn.execute("""INSERT INTO option_positions (position_id, user_id, ticker, structure, legs, contracts,
                            entry_value, set_aside, vol, belief, status, opened_at, closed_at, close_value)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                         (pid, "u", "CMG", "Long Put", legs, 1, 2.0, 2.0, 0.3, "", "closed", "2026-11-16T20:00:00", shut, 2.0))
    got = {r["id"]: r for r in po.closed("u")}
    for r in got.values():
        assert datetime.fromisoformat(r["closed_at"]).tzinfo is not None
        assert datetime.fromisoformat(r["opened_at"]).tzinfo is not None
    assert datetime.fromisoformat(got["evening"]["closed_at"]).astimezone(po.market.NY).date().isoformat() == "2026-11-16"
    assert got["expiry"]["expired"] is True
    assert datetime.fromisoformat(got["expiry"]["closed_at"]).astimezone(po.market.NY).hour == 16
    assert got["morning"]["expired"] is False and got["evening"]["expired"] is False and got["new"]["expired"] is False
    assert po._expiry_close(datetime(2027, 2, 19).date()).utcoffset() is not None
    for r in rt._closed_trades("u"):
        assert r["closed_at"].endswith("+00:00")


def test_expired_options_settle_at_the_expiration_day_close_not_a_later_price(tmp_path, monkeypatch):
    """A Close Call YES ($100/$105 call spread) that was right at Friday's close must settle on Friday's close, even
    if the stock has fallen by the time the user next opens the app. Until that close is in, the trade waits
    ('settling') and can't be closed by hand at a later price."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    from backend.v4 import market, practice_options as po
    from datetime import date, datetime, timedelta
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "x.db"))
    monkeypatch.setattr(pt, "paper_engine", eng)
    spot = {"v": 102.0}
    today = {"d": date(2026, 11, 16)}
    now = {"t": datetime(2026, 11, 16, 11, 0, tzinfo=market.NY)}
    monkeypatch.setattr(market, "latest_price", lambda t: spot["v"])
    monkeypatch.setattr(market, "asset_info", lambda t: {"symbol": t})
    monkeypatch.setattr(market, "features", lambda t: {"vol60": 0.3})
    monkeypatch.setattr(market, "today", lambda: today["d"])
    monkeypatch.setattr(market, "now_ny", lambda: now["t"])
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    closes = {}
    monkeypatch.setattr(market, "session_close_on", lambda t, d: closes.get(d))
    exp = date(2026, 11, 20)
    legs = [{"action": "Buy", "option_type": "Call", "strike_price": 100, "expiration": exp.isoformat(), "quantity": 1, "instrument": "option"},
            {"action": "Sell", "option_type": "Call", "strike_price": 105, "expiration": exp.isoformat(), "quantity": 1, "instrument": "option"}]
    o = po.open_trade("u", "XYZ", "Close Call: YES", legs, 2)
    cost = o["set_aside"]
    def cash():
        with eng._get_db_connection() as conn:
            return float(conn.execute("SELECT cash_balance FROM users WHERE user_id = 'u'").fetchone()["cash_balance"])
    cash0 = cash()

    # expiration day, 3pm: still open, can be closed by hand
    today["d"], now["t"] = exp, datetime(2026, 11, 20, 15, 0, tzinfo=market.NY)
    p = po.positions("u")
    assert len(p) == 1 and p[0]["settling"] is False
    # 4:30pm: expired, waits for the official close, can't be closed at an after-hours price
    now["t"] = datetime(2026, 11, 20, 16, 30, tzinfo=market.NY)
    p = po.positions("u")
    assert len(p) == 1 and p[0]["settling"] is True
    with pytest.raises(po.PracticeError):
        po.close("u", o["position_id"])
    # next week the stock is at $95 (spread worth $0), but Friday closed at $106: full $500 a contract
    today["d"], now["t"] = date(2026, 11, 24), datetime(2026, 11, 24, 10, 0, tzinfo=market.NY)
    spot["v"] = 95.0
    assert len(po.positions("u")) == 1  # the close isn't in yet: no settle at today's $95
    closes[exp] = ("2026-11-20", 106.0)
    assert po.positions("u") == []
    c = po.closed("u")[0]
    assert c["expired"] is True and abs(c["proceeds"] - 1000.0) < 0.01
    assert abs(c["pnl"] - (1000.0 - cost)) < 0.01
    assert abs(cash() - (cash0 + 1000.0)) < 0.01


def test_close_call_answers_show_what_their_practice_trade_did(tmp_path, monkeypatch):
    """A Close Call YES ($100/$105 call spread) is 'right' when the stock closes above $100, but a close at $101
    pays only $100 a contract, less than it cost: the answer list must show the trade lost, and the Close Call
    total must add up to the Portfolio's closed list."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    from backend.v4 import market, practice_options as po, yesno
    from datetime import date, datetime
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "cc.db"))
    monkeypatch.setattr(pt, "paper_engine", eng)
    today = {"d": date(2026, 11, 16)}
    now = {"t": datetime(2026, 11, 16, 11, 0, tzinfo=market.NY)}
    monkeypatch.setattr(market, "latest_price", lambda t: 102.0)
    monkeypatch.setattr(market, "asset_info", lambda t: {"symbol": t})
    monkeypatch.setattr(market, "features", lambda t: {"vol60": 0.3})
    monkeypatch.setattr(market, "today", lambda: today["d"])
    monkeypatch.setattr(market, "now_ny", lambda: now["t"])
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    closes = {}
    monkeypatch.setattr(market, "session_close_on", lambda t, d: closes.get(d))
    exp = date(2026, 11, 20)
    leg = lambda a, k: {"action": a, "option_type": "Call", "strike_price": k, "expiration": exp.isoformat(),
                        "quantity": 1, "instrument": "option"}
    a = po.open_trade("u", "XYZ", "Close Call: YES", [leg("Buy", 100), leg("Sell", 105)], 1)
    b = po.open_trade("u", "XYZ", "Close Call: YES", [leg("Buy", 100), leg("Sell", 105)], 1)
    assert a["set_aside"] > 100  # costs more than the $100 a $101 close pays

    views = [{"position_id": a["position_id"], "result": "open"}, {"position_id": b["position_id"], "result": "open"},
             {"position_id": None, "result": "open"}]
    yesno._attach_trades("u", views)
    assert views[0]["trade"] == {"cost": a["set_aside"], "status": "open", "pnl": None, "expired": False}
    assert "trade" not in views[2]
    assert yesno.trades_total(views) == {"settled": 0, "pnl": 0, "won": 0, "open": 2}
    assert yesno.trades_total([{"result": "open"}]) is None
    assert po.outcomes("someone-else", [a["position_id"]]) == {}

    # b closed by hand before expiry; a expires with Friday's close at $101 (right on the question)
    po.close("u", b["position_id"])
    today["d"], now["t"] = date(2026, 11, 23), datetime(2026, 11, 23, 10, 0, tzinfo=market.NY)
    closes[exp] = ("2026-11-20", 101.0)
    views = [{"position_id": a["position_id"], "result": "right"}, {"position_id": b["position_id"], "result": "right"}]
    yesno._attach_trades("u", views)   # settles a at Friday's close, the same step the Portfolio runs
    ta, tb = views[0]["trade"], views[1]["trade"]
    assert ta["status"] == "closed" and ta["expired"] is True
    assert abs(ta["pnl"] - (100.0 - a["set_aside"])) < 0.01 and ta["pnl"] < 0
    assert tb["status"] == "closed" and tb["expired"] is False
    tot = yesno.trades_total(views)
    assert tot["settled"] == 2 and tot["open"] == 0
    assert abs(tot["pnl"] - sum(c["pnl"] for c in po.closed("u"))) < 0.02


def test_practice_trade_from_a_card_opens_at_the_cards_per_strike_price(tmp_path, monkeypatch):
    """An idea card prices each strike at its own listed IV (strategy.price_at_strike_vols). Opening it as a practice
    trade used the AVERAGE of the legs' IVs, so a skewed spread opened at a different debit than the card showed.
    It now reads each strike's vol the card's way, stores it on the leg (marks keep it), and matches the card."""
    monkeypatch.setenv("MP_DATA_DIR", str(tmp_path))
    import backend.paper_trading as pt
    from backend.v4 import market, practice_options as po, strategy
    from datetime import date
    eng = pt.PaperTradingEngine(db_path=str(tmp_path / "o.db"))
    monkeypatch.setattr(pt, "paper_engine", eng)
    as_of = date(2026, 11, 18)
    monkeypatch.setattr(market, "latest_price", lambda t: 350.0)
    monkeypatch.setattr(market, "asset_info", lambda t: {"symbol": t})
    monkeypatch.setattr(market, "features", lambda t: {"vol60": 0.3})
    monkeypatch.setattr(market, "today", lambda: as_of)
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    card = strategy.build_trade("Bull Call Spread", "AAPL", 350.0, 0.26, as_of, 30)
    lo, hi = sorted(float(l["strike_price"]) for l in card["trade_legs"] if l["instrument"] == "option")
    smile = {lo: 0.26, hi: 0.21}
    asked = []

    def iv_row(u, kind, k, e):
        asked.append(kind)
        return (e, k, smile[k])
    monkeypatch.setattr(market, "option_iv_row", iv_row)
    monkeypatch.setattr(market, "option_iv", lambda u, kind, k, e: smile[k])
    card = strategy.price_at_strike_vols(card, 350.0, as_of, lambda kind, k, e: (e, k, smile[k]))
    assert card["vol_source"] == "implied_strike"
    q = po.quote("AAPL", card["trade_legs"])
    assert q["vol_source"] == "strike" and set(asked) == {"call"}
    assert q["unit_value"] == pytest.approx(card["net_cost"] * 100, abs=0.01)  # the card's debit, to the cent
    avg = po.unit_value([{k: v for k, v in l.items() if k != "vol"} for l in q["legs"]], 350.0, (0.26 + 0.21) / 2)
    assert abs(avg - card["net_cost"] * 100) > 5  # the old average-vol entry was visibly off
    r = po.open_trade("u1", "AAPL", "Bull Call Spread", card["trade_legs"], 1)
    assert r["status"] == "success" and "own implied volatility" in r["message"]
    pos = po.positions("u1")[0]
    assert abs(pos["pnl"]) < 1e-6  # marked at the same per-strike vols, so no instant gain or loss
    # a client can't set its own vols, and a missing strike falls back to the average (as before)
    monkeypatch.setattr(market, "option_iv_row", lambda u, kind, k, e: None if k == hi else (e, k, smile[k]))
    q2 = po.quote("AAPL", [dict(l, vol=0.9) for l in card["trade_legs"]])
    assert q2["vol_source"] == "market" and not any(l.get("vol") for l in q2["legs"])
