"""Practice trades next to the same money in the S&P 500 over the same days."""
from backend.v4 import benchmark

DATES = ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13"]  # Mon..Fri
CLOSES = [600.0, 606.0, 612.0, 618.0, 630.0]


def test_spy_leg_starts_at_the_last_close_before_the_trade_new_york_time():
    # 2pm ET Tuesday: Tuesday hasn't closed yet, so Monday's close
    assert benchmark.level_before("2026-11-10T19:00:00+00:00", DATES, CLOSES) == ("2026-11-09", 600.0)
    # 4:30pm ET Tuesday: Tuesday's close
    assert benchmark.level_before("2026-11-10T21:30:00+00:00", DATES, CLOSES) == ("2026-11-10", 606.0)
    # a bare practice time is the server's UTC clock (01:00Z Wed = 8pm ET Tue)
    assert benchmark.level_before("2026-11-11 01:00:00", DATES, CLOSES) == ("2026-11-10", 606.0)
    # Saturday: Friday's close; before any history: nothing
    assert benchmark.level_before("2026-11-14T15:00:00+00:00", DATES, CLOSES) == ("2026-11-13", 630.0)
    assert benchmark.level_before("2026-11-01T15:00:00+00:00", DATES, CLOSES) is None


def test_same_money_in_the_sp500_adds_up_and_skips_what_it_cannot_measure():
    trades = [
        # $1,000 Tue 2pm -> Thu 5pm ET: S&P 600 -> 618 = +3.0% = +$30; the trade made +$50
        {"id": "a", "cost": 1000.0, "pnl": 50.0, "opened_at": "2026-11-10T19:00:00+00:00",
         "closed_at": "2026-11-12T22:00:00+00:00", "position_type": "long"},
        # $2,000 options set aside Tue 4:30pm ET, still open: 606 -> live 636.3 = +5.0% = +$100; the trade lost $40
        {"id": "b", "cost": 2000.0, "pnl": -40.0, "opened_at": "2026-11-10T21:30:00+00:00",
         "closed_at": None, "position_type": "options"},
        {"id": "s", "cost": 500.0, "pnl": 20.0, "opened_at": "2026-11-10T19:00:00+00:00",
         "closed_at": None, "position_type": "short"},                       # shorts don't fit a long benchmark
        {"id": "old", "cost": None, "pnl": None, "opened_at": None,
         "closed_at": "2026-11-12T22:00:00+00:00", "position_type": "long"},  # older sale, cost not recorded
    ]
    r = benchmark.compare(trades, DATES, CLOSES, live=636.3)
    assert set(r["rows"]) == {"a", "b"}
    assert r["rows"]["a"] == {"spy_ret": 3.0, "spy_gain": 30.0, "ahead": 20.0, "from": "2026-11-09", "to": "2026-11-12"}
    assert r["rows"]["b"]["spy_gain"] == 100.0 and r["rows"]["b"]["ahead"] == -140.0 and r["rows"]["b"]["to"] == "now"
    s = r["summary"]
    assert s["trades"] == 2 and s["money"] == 3000.0 and s["open"] == 1 and s["skipped_short"] == 1
    assert s["gain"] == 10.0 and s["spy_gain"] == 130.0 and s["ahead"] == -120.0 and s["beat"] == 1
    assert s["since"] == "2026-11-09"
    # no live price: open trades are left out rather than measured against a stale price
    r2 = benchmark.compare(trades, DATES, CLOSES, live=None)
    assert set(r2["rows"]) == {"a"} and r2["summary"]["open"] == 0


def test_portfolio_rows_get_their_sp500_comparison():
    pf = {
        "positions": [{"position_id": "p1", "quantity": 10, "avg_price": 100.0, "unrealized_pnl": 25.0,
                       "opened_at": "2026-11-10T19:00:00+00:00", "position_type": "long"}],
        "option_positions": [],
        "closed_trades": [{"kind": "options", "id": "o1", "cost": 500.0, "pnl": -500.0,
                           "opened_at": "2026-11-10T19:00:00+00:00", "closed_at": "2026-11-13T21:00:00+00:00"}],
    }
    benchmark.attach(pf, bars=lambda s: (DATES, CLOSES), live=lambda s: 612.0, at=lambda ny: None)
    assert pf["positions"][0]["vs_spy"]["spy_gain"] == 20.0          # $1,000 x (612/600 - 1)
    assert pf["closed_trades"][0]["vs_spy"]["spy_gain"] == 25.0      # $500 x (630/600 - 1)
    assert pf["benchmark"]["gain"] == -475.0 and pf["benchmark"]["spy_gain"] == 45.0
    empty = benchmark.attach({"positions": [], "option_positions": [], "closed_trades": []})
    assert empty["benchmark"] is None


def test_a_trade_opened_during_market_hours_starts_from_spy_at_that_moment_not_the_morning():
    """A 2pm trade isn't charged with the S&P's move from the previous close to 2pm. The old close-to-close rule did,
    so a brand-new trade showed 'behind the S&P' before it could move."""
    from datetime import datetime, timedelta, timezone
    # Tue Nov 10 bars: 9:30 open 601, 14:00 bar opens at 604.8 (SPY up 0.8% since Monday's 600 close)
    bars = [(datetime(2026, 11, 10, 14, 30, tzinfo=timezone.utc), 601.0),   # 9:30 ET
            (datetime(2026, 11, 10, 19, 0, tzinfo=timezone.utc), 604.8),    # 2:00 ET
            (datetime(2026, 11, 10, 19, 55, tzinfo=timezone.utc), 606.0)]   # 2:55 ET
    at = benchmark._price_at_factory(fetch=lambda day: bars if day == "2026-11-10" else [])
    # 2:02pm ET: the 2:00 bar's open
    assert benchmark.level_at("2026-11-10T19:02:00+00:00", DATES, CLOSES, at) == ("2026-11-10", 604.8)
    # 9:30 sharp (a queued order's fill, with the winter offset): the session's first bar = SPY's open
    assert benchmark.level_at("2026-11-10T09:30:00-05:00", DATES, CLOSES, at) == ("2026-11-10", 601.0)
    # outside regular hours, or a day with no bars: the last close before it, as before
    assert benchmark.level_at("2026-11-10T21:30:00+00:00", DATES, CLOSES, at) == ("2026-11-10", 606.0)
    assert benchmark.level_at("2026-11-11T19:02:00+00:00", DATES, CLOSES, at) == ("2026-11-10", 606.0)
    # open since 2:02pm, SPY now 604.8: no S&P move charged; the old rule said +0.8% (+$8 on $1,000)
    t = [{"id": "n", "cost": 1000.0, "pnl": 0.0, "opened_at": "2026-11-10T19:02:00+00:00", "closed_at": None,
          "position_type": "long"}]
    assert benchmark.compare(t, DATES, CLOSES, live=604.8, at=at)["rows"]["n"]["spy_gain"] == 0.0
    assert benchmark.compare(t, DATES, CLOSES, live=604.8)["rows"]["n"]["spy_gain"] == 8.0
    # opened 2:02pm, closed 2:57pm the same day: SPY 604.8 -> 606.0 = +$1.98 on $1,000
    t2 = [dict(t[0], id="d", closed_at="2026-11-10T19:57:00+00:00")]
    assert benchmark.compare(t2, DATES, CLOSES, live=None, at=at)["rows"]["d"]["spy_gain"] == 1.98
    # a fetch that fails falls back to the close rule, never an error
    boom = benchmark._price_at_factory(fetch=lambda day: (_ for _ in ()).throw(RuntimeError("down")))
    assert benchmark.level_at("2026-11-10T19:02:00+00:00", DATES, CLOSES, boom) == ("2026-11-09", 600.0)
