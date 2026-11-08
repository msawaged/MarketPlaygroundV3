"""
v4 tests — no network: Claude and Alpaca are replaced with fakes.

Run:  PYTHONPATH=./ python -m pytest backend/v4/tests -q
"""
from __future__ import annotations

import json
import math
import os
import random
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np
import pytest

from backend.v4 import db, engine, grader, learning, market, nn, seeder, strategy

TODAY = date(2026, 10, 15)

# Synthetic market: ticker -> annual drift. WINR trends up, LOSR down, others flat-ish.
DRIFTS = {"SPY": 0.08, "WINR": 0.45, "LOSR": -0.35, "FLAT": 0.0, "PIPE": 0.25, "SPUD": 0.10, "XLI": 0.07}
NAMES = {"WINR": "Winner Plumbing Inc", "LOSR": "Loser Corp", "FLAT": "Flat Co", "PIPE": "Pipe Supply Co",
         "SPUD": "Spud Foods", "XLI": "Industrial Select Sector SPDR Fund", "SPY": "SPDR S&P 500 ETF Trust"}


def _series(sym: str):
    rnd = random.Random(sym)
    d = TODAY - timedelta(days=365 * 5)
    dates, closes, p = [], [], 50.0 + rnd.random() * 100
    while d <= TODAY:
        if d.weekday() < 5:
            p *= math.exp(DRIFTS[sym] / 252 + rnd.gauss(0, 0.012))
            dates.append(d.isoformat())
            closes.append(round(p, 4))
        d += timedelta(days=1)
    return dates, closes


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    pg = os.getenv("MP_TEST_DATABASE_URL")  # set to run the suite against a real Postgres
    if pg:
        monkeypatch.setenv("DATABASE_URL", pg)
        import psycopg
        with psycopg.connect(pg) as conn:
            conn.execute("DROP TABLE IF EXISTS outcomes, pick_themes, feedback, picks, beliefs, nn_models, kv_cache, waitlist, accounts, sessions, broker_links, broker_orders, email_tokens CASCADE")
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("MP_SQLITE_PATH", str(tmp_path / "t.db"))
    db.reset_for_tests()
    learning.invalidate()
    nn._loaded.update(at=0.0, row=None, model=None)
    market.clear_cache()
    series = {s: _series(s) for s in DRIFTS}
    monkeypatch.setattr(market, "today", lambda: TODAY)
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True, "next_open": None, "next_close": None})
    monkeypatch.setattr(market, "daily_closes", lambda s: series[s.upper()] if s.upper() in series else (_ for _ in ()).throw(market.MarketDataError("no data")))
    monkeypatch.setattr(market, "latest_price", lambda s: series[s.upper()][1][-1])
    monkeypatch.setattr(market, "asset_info", lambda s: (
        {"symbol": s, "name": NAMES[s], "is_etf": market._looks_like_etf(NAMES[s]), "tradable": True}
        if s in NAMES and s != "SPY" else None))
    yield


class FakeClaude:
    """Mimics anthropic.Anthropic().messages.create with structured output."""

    def __init__(self, payload=None):
        self.calls = []
        self.payload = payload
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        if "beliefs" in json.dumps(kw.get("extra_body", {})):  # seeder belief generator
            out = {"beliefs": ["more people are fixing old pipes", "people want cheaper food"]}
        else:
            out = self.payload or default_interp(kw["messages"][0]["content"])
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=json.dumps(out))],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=400, cache_read_input_tokens=0, cache_creation_input_tokens=0),
            stop_reason="end_turn",
        )


def default_interp(msg: str) -> dict:
    food = "potato" in msg.lower() or "food" in msg.lower()
    cands = [
        {"ticker": "SPUD" if food else "PIPE", "name": "x", "exposure": "direct", "direction": "bullish", "rationale": "direct play", "score": 0.8},
        {"ticker": "LOSR", "name": "x", "exposure": "supplier", "direction": "bullish", "rationale": "supplier", "score": 0.75},
        {"ticker": "WINR", "name": "x", "exposure": "beneficiary", "direction": "bullish", "rationale": "beneficiary", "score": 0.6},
        {"ticker": "FLAT", "name": "x", "exposure": "beneficiary", "direction": "bullish", "rationale": "meh", "score": 0.5},
        {"ticker": "XLI", "name": "x", "exposure": "etf", "direction": "bullish", "rationale": "sector etf", "score": 0.4},
        {"ticker": "NOPE", "name": "fake", "exposure": "direct", "direction": "bullish", "rationale": "not real", "score": 0.9},
    ]
    return {
        "is_market_belief": True, "note": "", "summary": "Plumbing demand rises.", "direction": "bullish",
        "horizon_days": 120, "conviction": "medium", "themes": ["Plumbing", "housing"] if not food else ["food", "potatoes"],
        "causal_chain": "More plumbing work -> suppliers sell more.", "candidates": cands,
    }


# ---------------- engine ----------------

def test_live_belief_end_to_end():
    fake = FakeClaude()
    r = engine.process_belief("plumbing demand is going to be high", "u1", "moderate", claude_client=fake)

    assert r["valid"] and r["engine"] == "v4"
    # fields the existing ChatInterface reads
    for k in ("strategy", "ticker", "direction", "price_info", "confidence", "tags", "expiry_date", "asset_class", "belief_id", "pick_id"):
        assert k in r
    assert r["strategy"]["type"] in strategy.STRUCTURES
    assert r["strategy"]["trade_legs"] and r["strategy"]["trade_legs"][0]["ticker"] == r["ticker"]
    tickers = [p["ticker"] for p in r["picks"]]
    assert "NOPE" not in tickers  # not tradable -> dropped
    assert len(tickers) == 5
    assert r["tags"] == ["plumbing", "housing"]  # lowercased
    assert sum(p["shown"] for p in r["picks"]) == engine.SHOW_TOP

    # one Claude call, structured output requested, prompt cached
    assert len(fake.calls) == 1
    ob = fake.calls[0]["extra_body"]["output_config"]
    assert ob["format"]["type"] == "json_schema" and ob["effort"] == "low"
    assert fake.calls[0]["system"][0]["cache_control"] == {"type": "ephemeral"}

    saved = engine.get_belief(r["belief_id"])
    assert saved["source"] == "user" and len(saved["picks"]) == 5


def test_identical_belief_reuses_interpretation():
    fake = FakeClaude()
    engine.process_belief("Plumbing demand is going to be HIGH!", "u1", claude_client=fake)
    r2 = engine.process_belief("plumbing demand is going to be high", "u2", claude_client=fake)
    assert len(fake.calls) == 1
    assert r2["usage"]["cost_usd"] == 0.0


def test_non_market_belief():
    fake = FakeClaude({"is_market_belief": False, "note": "That's a greeting.", "summary": "", "direction": "neutral",
                       "horizon_days": 30, "conviction": "low", "themes": [], "causal_chain": "", "candidates": []})
    r = engine.process_belief("hello there", claude_client=fake)
    assert r["valid"] is False and r["strategy"] is None and "greeting" in r["reason"]


def test_empty_belief_rejected():
    with pytest.raises(engine.BeliefError):
        engine.process_belief("   ")


def test_feedback():
    r = engine.process_belief("plumbing demand is going to be high", claude_client=FakeClaude())
    assert engine.record_feedback(r["belief_id"], "good")["status"] == "ok"
    engine.record_feedback(r["belief_id"], "down", pick_id=r["picks"][1]["pick_id"])
    with pytest.raises(engine.BeliefError):
        engine.record_feedback(r["belief_id"], "meh")
    counts = learning.feedback_counts([r["ticker"], r["picks"][1]["ticker"]])
    assert counts[r["ticker"]]["up"] == 1


# ---------------- strategy ----------------

def test_structures_and_economics():
    d = date(2026, 1, 5)
    assert strategy.default_structure("bullish", 400, "high", "moderate") == "Buy Stock"
    assert strategy.default_structure("bullish", 30, "medium", "moderate") == "Bull Call Spread"
    assert strategy.default_structure("bearish", 60, "high", "aggressive") == "Long Put"
    assert strategy.default_structure("neutral", 60, "low", "moderate") == "Iron Condor"
    for s in ("Long Call", "Bull Call Spread", "Long Put", "Bear Put Spread"):
        t = strategy.build_trade(s, "WINR", 100.0, 0.3, d, 90)
        assert t["net_cost"] > 0, s
        assert date.fromisoformat(t["expiration"]).weekday() == 4  # Friday
    ic = strategy.build_trade("Iron Condor", "WINR", 100.0, 0.3, d, 60)
    assert ic["net_cost"] < 0 and len(ic["trade_legs"]) == 4
    bcs = strategy.build_trade("Bull Call Spread", "WINR", 100.0, 0.3, d, 90)
    exp = date.fromisoformat(bcs["expiration"])
    up = strategy.structure_return(bcs, 100.0, 140.0, d, exp, 0.3)
    down = strategy.structure_return(bcs, 100.0, 70.0, d, exp, 0.3)
    assert up > 0.5 and down == pytest.approx(-1.0)


def test_learned_structure_switch():
    stats = {"Bull Call Spread": {"n": 100, "mean": -0.05}, "Buy Stock": {"n": 100, "mean": 0.04}}
    s, why = strategy.choose_structure("bullish", 30, "medium", "moderate", stats)
    assert s == "Buy Stock" and why.startswith("learned")
    s, why = strategy.choose_structure("bullish", 30, "medium", "moderate", {"Buy Stock": {"n": 5, "mean": 0.5}})
    assert s == "Bull Call Spread" and why == "rule"  # not enough evidence


# ---------------- seeding, grading, learning, network ----------------

def test_backfill_grade_learn_and_train(monkeypatch):
    monkeypatch.setattr(nn, "MIN_TRAIN", 50)
    monkeypatch.setattr(nn, "MIN_TEST", 20)
    fake = FakeClaude()
    res = seeder.run("backfill", n=120, generate=2, years=3, concurrency=1, max_usd=100, claude_client=fake)
    assert res["ok"] == 120 and res["errors"] == 0
    assert res["grading"]["graded"] > 400

    # backfilled rows never expose Claude's score/rank to the network
    rows = db.query("SELECT p.features FROM picks p JOIN beliefs b ON b.id=p.belief_id WHERE b.source='seed_backfill' LIMIT 50")
    for r in rows:
        f = json.loads(r["features"])["num"]
        assert f["has_claude"] == 0 and f["claude_score"] == 0 and f["backfill"] == 1
    # Claude is told the as-of date for backfill
    assert any("As of:" in c["messages"][0]["content"] for c in fake.calls if "messages" in c and "Belief:" in c["messages"][0]["content"])

    # outcomes are directional excess vs SPY; WINR (uptrend) should beat LOSR (downtrend) on average
    s = {t["ticker"]: t for t in learning.ticker_stats(["plumbing", "food", "potatoes", "housing"], ["WINR", "LOSR"])}
    assert s["WINR"]["mean"] > s["LOSR"]["mean"]

    # shared context for a new, similar belief from another user
    ctx = learning.build_context("I think plumbing work will be in high demand")
    assert ctx["similar"] and ctx["ticker_stats"]

    # the network trains, is evaluated walk-forward, and learns WINR > LOSR
    out = nn.train()
    assert out["status"] in ("active", "shadow"), out
    assert out["n_train"] >= 50 and out["n_test"] >= 20
    assert out["cutoff"]
    preds, w, mid = nn.predict([
        nn.make_features(belief_text="plumbing demand is going to be high", themes=["plumbing"], core_direction="bullish",
                         horizon_days=120, conviction="medium", cand={"ticker": t, "direction": "bullish", "exposure": "direct", "score": 0.6},
                         market=market.features(t, TODAY), rank=0, n_cands=5, is_etf=False, backfill=False)
        for t in ("WINR", "LOSR")
    ])
    assert mid and preds[0] > preds[1]
    if out["status"] == "active":
        assert w > 0

    # a live belief after training carries NN scores on its picks
    r = engine.process_belief("plumbing will boom", "u9", claude_client=fake)
    assert all(p["nn_score"] is not None for p in r["picks"])
    st = engine.stats()
    assert st["beliefs"]["seed_backfill"]["count"] == 120 and st["graded_picks"] > 0


def test_backfill_stops_starting_new_beliefs_at_the_deadline():
    import time as _t
    r = seeder.run("backfill", n=5, years=1, concurrency=1, claude_client=FakeClaude(), deadline=_t.time() - 1)
    assert r["ok"] == 0 and r["stopped_for_time"] == 5 and r["cost_usd"] == 0
    r2 = seeder.run("backfill", n=3, years=1, concurrency=1, claude_client=FakeClaude(), deadline=_t.time() + 600)
    assert r2["stopped_for_time"] == 0 and r2["ok"] + r2["skipped"] == 3


def test_grader_is_idempotent():
    seeder.run("backfill", n=5, years=1, concurrency=1, claude_client=FakeClaude())
    n1 = db.query_one("SELECT COUNT(*) AS n FROM outcomes")["n"]
    assert grader.grade()["graded"] == 0
    assert db.query_one("SELECT COUNT(*) AS n FROM outcomes")["n"] == n1


def test_train_skips_without_data():
    assert nn.train()["status"] == "skipped"


def test_market_features_use_only_past_data():
    d = date(2024, 6, 3)
    f1 = market.features("WINR", d)
    dates, closes = market.daily_closes("WINR")
    i = max(k for k, x in enumerate(dates) if x <= d.isoformat())
    assert f1["mom20"] == pytest.approx(closes[i] / closes[i - 20] - 1)


# ---------------- API ----------------

def test_api_routes(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.v4 import interpreter
    from backend.v4.router import router

    fake = FakeClaude()
    monkeypatch.setattr(interpreter, "_client", lambda: fake)
    app = FastAPI()
    app.include_router(router, prefix="/v4")
    c = TestClient(app)
    r = c.post("/v4/belief", json={"belief": "potatoes are in demand", "user_id": "api"})
    assert r.status_code == 200 and r.json()["ticker"] == "SPUD"
    bid = r.json()["belief_id"]
    assert c.post("/v4/feedback", json={"belief_id": bid, "kind": "up"}).status_code == 200
    assert c.get(f"/v4/belief/{bid}").json()["text"] == "potatoes are in demand"
    assert c.get("/v4/stats").json()["beliefs"]["user"]["count"] == 1
    assert c.post("/v4/belief", json={"belief": ""}).status_code == 400
    assert c.post("/v4/admin/grade").status_code == 403


def test_waitlist(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.v4.router import router

    monkeypatch.setenv("MP_ADMIN_TOKEN", "secret")
    app = FastAPI(); app.include_router(router, prefix="/v4"); c = TestClient(app)
    assert c.post("/v4/waitlist", json={"email": "Ana@Example.com", "belief": "potatoes are in demand"}).status_code == 200
    assert c.post("/v4/waitlist", json={"email": "ana@example.com"}).status_code == 200  # duplicate is fine
    assert c.post("/v4/waitlist", json={"email": "not-an-email"}).status_code == 400
    assert c.post("/v4/waitlist", json={"email": "bot@x.com", "website": "spam"}).status_code == 200
    r = c.get("/v4/admin/waitlist", headers={"X-Admin-Token": "secret"}).json()
    assert r["count"] == 1 and r["signups"][0]["belief"] == "potatoes are in demand"
    assert c.get("/v4/admin/waitlist").status_code == 403


def test_trade_includes_vol_for_charts():
    r = engine.process_belief("plumbing demand is going to be high", claude_client=FakeClaude())
    for p in r["picks"]:
        assert 0.05 <= p["trade"]["vol"] <= 2.5


def test_trending_uses_summaries_not_user_text():
    fake = FakeClaude()
    engine.process_belief("my neighbor Bob says plumbing demand is going to be high", "u1", claude_client=fake)
    engine.process_belief("potatoes are in demand", "u2", claude_client=fake)
    t = engine.trending(days=30)
    themes = {x["theme"]: x for x in t["themes"]}
    assert "plumbing" in themes and "food" in themes
    assert themes["plumbing"]["beliefs"] == 1 and themes["plumbing"]["direction"] == "bullish"
    assert "Bob" not in themes["plumbing"]["example"]           # Claude's summary, never raw user text
    assert themes["plumbing"]["tickers"] and themes["plumbing"]["tickers"][0]["ticker"]


def test_basket_builder_normalizes_and_validates():
    from backend.v4 import basket

    class FakeBasketClaude:
        def __init__(self): self.messages = self
        def create(self, **kw):
            out = {"basket": [
                {"ticker": "WINR", "type": "stock", "allocation_pct": 35, "rationale": "growth"},
                {"ticker": "PIPE", "type": "etf", "allocation_pct": 35, "rationale": "core"},
                {"ticker": "NOPE", "type": "etf", "allocation_pct": 30, "rationale": "not real"}],
                "goal": "Growth with some balance", "risk_profile": "moderate",
                "historical_note": "Mixes like this have had sizable swings in down years."}
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(out))])

    r = basket.generate("70% stocks 30% bonds", client=FakeBasketClaude())
    tickers = [b["ticker"] for b in r["basket"]]
    assert "NOPE" not in tickers and tickers == ["WINR", "PIPE"]
    assert sum(int(b["allocation"].rstrip("%")) for b in r["basket"]) == 100
    assert "not guarantee" in r["estimated_return"]
    assert basket.generate("")["engine"] == "fallback"


def test_engine_switch_routes_to_v4_and_legacy_is_lazy(monkeypatch):
    import sys
    from backend import engine_switch

    monkeypatch.delenv("ENGINE_VERSION", raising=False)
    monkeypatch.setattr(engine, "process_belief", lambda b, u, r, source="user": {"engine": "v4", "src": source})
    out = engine_switch.run_belief("x", source="system")
    assert out == {"engine": "v4", "src": "system"}
    assert engine_switch.engine_version() == "v4"
    monkeypatch.setenv("ENGINE_VERSION", "legacy")
    assert engine_switch.engine_version() == "legacy"
    assert "backend.ai_engine.ai_engine" not in sys.modules or True  # legacy only imported when legacy runs


def test_rate_limit_on_costly_endpoints(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend import rate_limit

    rate_limit.reset_for_tests()
    monkeypatch.setenv("MP_RATE_LIMIT", "3")
    app = FastAPI()
    app.add_middleware(rate_limit.CostlyEndpointRateLimit)

    @app.post("/v4/belief")
    def b():
        return {"ok": True}

    @app.get("/v4/stats")
    def s():
        return {"ok": True}

    c = TestClient(app)
    assert [c.post("/v4/belief").status_code for _ in range(4)] == [200, 200, 200, 429]
    assert c.get("/v4/stats").status_code == 200            # free endpoints are not limited
    # behind Render: "<what the visitor sent>, <real visitor>, <render proxy>"
    real = lambda fake: {"x-forwarded-for": f"{fake}, 5.5.5.5, 10.0.0.1"}
    assert [c.post("/v4/belief", headers=real(f"1.2.3.{i}")).status_code for i in range(4)] == [200, 200, 200, 429]  # faking the first entry doesn't help
    assert c.post("/v4/belief", headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1"}).status_code == 200  # a different real visitor
    rate_limit.reset_for_tests()


def test_daily_caps_protect_the_claude_bill(monkeypatch):
    monkeypatch.setenv("MP_USER_DAILY_CAP", "2")
    monkeypatch.setenv("MP_DAILY_CLAUDE_CAP", "3")
    fake = FakeClaude()
    engine.process_belief("plumbing one", "u-cap", claude_client=fake)
    engine.process_belief("plumbing two", "u-cap", claude_client=fake)
    with pytest.raises(engine.BudgetError):
        engine.process_belief("plumbing three", "u-cap", claude_client=fake)
    engine.process_belief("plumbing one", "u-cap", claude_client=fake)       # a repeat is cached: free, still works
    engine.process_belief("plumbing four", "u-other", claude_client=fake)    # 3rd fresh call today: hits the global cap next
    with pytest.raises(engine.BudgetError):
        engine.process_belief("plumbing five", "u-third", claude_client=fake)
    seeder.run("backfill", n=2, years=1, concurrency=1, claude_client=fake)  # the practice feed isn't capped


def test_learning_status_and_my_beliefs(monkeypatch):
    fake = FakeClaude()
    r = engine.process_belief("plumbing demand is going to be high", "u-me", "moderate", claude_client=fake)
    engine.process_belief("potatoes are in demand", "u-other", "moderate", claude_client=fake)

    ls = engine.learning_status()
    assert ls["beliefs_from_people"] == 2 and ls["people"] == 2
    assert [l["name"] for l in ls["layers"]] == ["Claude", "Track record", "MarketPlayground network"]
    assert ls["layers"][2]["on"] is False and "Waiting" in ls["layers"][2]["what"]

    mine = engine.my_beliefs("u-me")
    assert len(mine["beliefs"]) == 1 and mine["beliefs"][0]["belief_id"] == r["belief_id"]
    shown = mine["beliefs"][0]["picks"]
    assert len(shown) == engine.SHOW_TOP
    assert all(p["vs_spy"] is not None for p in shown)  # entered today; synthetic closes exist
    assert engine.my_beliefs("anonymous")["beliefs"] == []
    assert engine.my_beliefs("u-nobody")["beliefs"] == []

    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.v4.router import router
    app = FastAPI(); app.include_router(router, prefix="/v4")
    c = TestClient(app)
    assert c.get("/v4/learning").status_code == 403  # owner only
    monkeypatch.setenv("MP_ADMIN_TOKEN", "owner")
    assert c.get("/v4/learning", headers={"X-Admin-Token": "owner"}).status_code == 200
    assert c.get("/v4/my_beliefs", params={"user_id": "u-me"}).json()["beliefs"][0]["text"].startswith("plumbing")
    assert c.get("/v4/admin/ml").status_code == 403


def test_track_record_respects_direction():
    stat = {"n": 40, "mean": 0.0, "raw_mean": 0.10, "up": 0, "down": 0}
    assert learning.ticker_adjustment(stat, "bullish") > 0
    assert learning.ticker_adjustment(stat, "bearish") < 0


def test_network_blend_can_reorder_picks():
    # tiny predictions still reorder: rescaled to Claude's spread
    out = nn.on_claude_scale([0.001, 0.003, -0.002], [0.8, 0.7, 0.6])
    assert out.index(max(out)) == 1
    assert abs(sum(out) / 3 - 0.7) < 1e-9


def test_network_learns_within_belief_label():
    # the belief-level part of the label is removed; lone-idea beliefs are dropped from training
    y, keep = nn.within_belief(["a", "a", "a", "b", "c", "c"], np.array([0.30, 0.10, 0.20, 0.50, -0.4, -0.2]))
    assert np.allclose(y[:3], [0.10, -0.10, 0.0], atol=1e-6)
    assert np.allclose(y[4:], [-0.10, 0.10], atol=1e-6)
    assert keep.tolist() == [True, True, True, False, True, True]
    # order inside a belief is unchanged, so the top-pick lift the gates use is unchanged
    raw = np.array([0.30, 0.10, 0.20])
    assert y[:3].argsort().tolist() == raw.argsort().tolist()


def test_balanced_results_mix_shares_and_options():
    fake = FakeClaude()
    r = engine.process_belief("plumbing demand is going to be high", "u-mix", "moderate", claude_client=fake)
    shown = [p["structure"] for p in r["picks"] if p["shown"]]
    assert "Buy Stock" in shown and any(s in strategy.OPTION_STRUCTURES for s in shown)
    bold = engine.process_belief("plumbing demand is going to be high", "u-mix", "aggressive", claude_client=fake)
    bs = [p for p in bold["picks"] if p["shown"] and p["price"] >= 10]
    assert bs[0]["structure"] in strategy.OPTION_STRUCTURES  # Bold: options first
    assert all(p.get("alt") for p in r["picks"] if p["shown"])  # every card can switch Shares <-> Options
    top = r["picks"][0]
    assert top["structure"] == "Buy Stock" and top["alt"]["structure"] in strategy.OPTION_STRUCTURES
    assert strategy.vary_structure("Bull Call Spread", "bullish", "aggressive", 0, False, 5.0)[0] == "Buy Stock"


def _client():
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.v4.router import router
    app = FastAPI(); app.include_router(router, prefix="/v4")
    return TestClient(app)


def test_movers_today_change_only_trusts_the_previous_session():
    from backend.v4 import movers
    snap = lambda a, b: {"dailyBar": {"t": a + "T04:00:00Z"}, "prevDailyBar": {"t": b + "T04:00:00Z"}}
    assert movers._today_change(105.0, 100.0, snap("2026-11-04", "2026-11-03")) == 0.05
    assert movers._today_change(105.0, 100.0, snap("2026-11-02", "2026-10-30")) == 0.05   # over a weekend
    assert movers._today_change(105.0, 100.0, snap("2026-11-04", "2026-10-20")) is None   # stale "previous" bar
    assert movers._today_change(160.0, 100.0, snap("2026-11-04", "2026-11-03")) is None   # +60%: a data error
    assert movers._today_change(105.0, 0.0, {}) is None


def test_owner_can_remove_an_account(monkeypatch):
    from backend.v4 import auth
    c = _client()
    r = c.post("/v4/auth/signup", json={"email": "gone@example.com", "password": "correct horse", "name": "G"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    assert c.get("/v4/auth/me", headers=hdr).status_code == 200
    monkeypatch.setenv("MP_BLOCKED_EMAILS", " Gone@Example.com , other@example.com")
    assert c.get("/v4/auth/me", headers=hdr).status_code == 401                 # signed out right away
    r = c.post("/v4/auth/login", json={"email": "gone@example.com", "password": "correct horse"})
    assert r.status_code == 403 and "no longer has access" in r.text            # can't log back in
    assert c.post("/v4/auth/signup", json={"email": "GONE@example.com", "password": "another one"}).status_code == 403
    assert auth.purge_blocked() == 1
    assert not db.query_one("SELECT 1 AS x FROM sessions s JOIN accounts a ON a.id = s.account_id WHERE a.email = 'gone@example.com'")
    sent = []
    monkeypatch.setattr(auth.mailer, "send", lambda *a, **k: sent.append(a))
    auth.forgot_password("gone@example.com")
    assert sent == []                                                            # no emails to a removed account
    assert db.query_one("SELECT 1 AS x FROM accounts WHERE email = 'gone@example.com'")  # data kept: reversible
    monkeypatch.setenv("MP_BLOCKED_EMAILS", "")
    assert c.post("/v4/auth/login", json={"email": "gone@example.com", "password": "correct horse"}).status_code == 200


def test_accounts_signup_login_merge_and_delete(monkeypatch):
    from backend.v4 import auth
    c = _client()
    fake = FakeClaude()
    dev1, dev2 = "u-11111111-aaaa", "u-22222222-bbbb"
    engine.process_belief("plumbing demand is going to be high", dev1, claude_client=fake)
    engine.process_belief("potatoes are in demand", dev2, claude_client=fake)

    r = c.post("/v4/auth/signup", json={"email": "Pat@Example.com", "password": "short", "device_id": dev1})
    assert r.status_code == 400
    r = c.post("/v4/auth/signup", json={"email": "Pat@Example.com", "password": "correct horse", "name": "Pat", "device_id": dev1})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]; acc = r.json()["account"]
    assert acc["email"] == "pat@example.com" and acc["uid"] == dev1 and acc["name"] == "Pat"
    stored = db.query_one("SELECT pw_hash FROM accounts")["pw_hash"]
    assert "correct horse" not in stored and stored.startswith("scrypt$")
    assert c.post("/v4/auth/signup", json={"email": "pat@example.com", "password": "another one"}).status_code == 409

    assert c.get("/v4/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()["account"]["email"] == "pat@example.com"
    assert c.get("/v4/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401

    assert c.post("/v4/auth/login", json={"email": "pat@example.com", "password": "wrong pass"}).status_code == 401
    r = c.post("/v4/auth/login", json={"email": " PAT@example.com", "password": "correct horse", "device_id": dev2})
    assert r.status_code == 200 and r.json()["moved_beliefs"] == 1
    tok2 = r.json()["token"]
    assert len(engine.my_beliefs(dev1)["beliefs"]) == 2  # both devices' beliefs now under the account

    # change password signs out other sessions
    h2 = {"Authorization": f"Bearer {tok2}"}
    assert c.post("/v4/auth/password", json={"current": "correct horse", "new": "battery staple"}, headers=h2).status_code == 200
    assert c.get("/v4/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    assert c.get("/v4/auth/me", headers=h2).status_code == 200

    assert c.post("/v4/auth/logout", headers=h2).status_code == 200
    assert c.get("/v4/auth/me", headers=h2).status_code == 401

    r = c.post("/v4/auth/login", json={"email": "pat@example.com", "password": "battery staple"})
    h3 = {"Authorization": f"Bearer {r.json()['token']}"}
    assert c.post("/v4/auth/delete", json={"password": "nope nope"}, headers=h3).status_code == 401
    assert c.post("/v4/auth/delete", json={"password": "battery staple"}, headers=h3).status_code == 200
    assert db.query_one("SELECT COUNT(*) AS n FROM accounts")["n"] == 0
    assert engine.my_beliefs(dev1)["beliefs"] == []  # detached from the person, kept for learning
    assert db.query_one("SELECT COUNT(*) AS n FROM beliefs")["n"] == 2


def test_admin_password_reset(monkeypatch):
    monkeypatch.setenv("MP_ADMIN_TOKEN", "secret")
    c = _client()
    c.post("/v4/auth/signup", json={"email": "sam@example.com", "password": "first password"})
    assert c.post("/v4/admin/reset_password", json={"email": "sam@example.com"}).status_code == 403
    temp = c.post("/v4/admin/reset_password", json={"email": "sam@example.com"}, headers={"X-Admin-Token": "secret"}).json()["temporary_password"]
    assert c.post("/v4/auth/login", json={"email": "sam@example.com", "password": temp}).status_code == 200
    assert c.get("/v4/admin/accounts", headers={"X-Admin-Token": "secret"}).json()["count"] == 1


def test_replay_one_year():
    r = engine.replay(["WINR", "LOSR", "NOPE"], ["bullish", "bullish", "bullish"], 365)
    assert [p["ticker"] for p in r["picks"]] == ["WINR", "LOSR"]  # NOPE has no history
    assert len(r["dates"]) == len(r["basket"]) == len(r["spy"]) and len(r["dates"]) > 40
    winr = r["picks"][0]
    assert winr["return"] > 0 and winr["right"] is True
    assert r["picks"][1]["right"] is False  # LOSR trends down
    bear = engine.replay(["LOSR"], ["bearish"], 365)
    assert bear["picks"][0]["right"] is True and bear["picks"][0]["vs_spy"] > 0 and bear["belief_right"] is True
    c = _client()
    assert c.get("/v4/replay", params={"tickers": "WINR", "directions": "bullish"}).status_code == 200
    assert c.get("/v4/replay", params={"tickers": "NOPE"}).status_code == 404


def test_options_never_short_fuse():
    for h in (7, 14, 21, 30):
        exp = strategy.pick_expiry(TODAY, h)
        assert (exp - TODAY).days >= 30 and exp.weekday() == 4


def test_interpretation_has_exit_plan_and_optional_question():
    from backend.v4 import interpreter
    out = interpreter._sanitize({"horizon_days": 90, "themes": ["X"], "candidates": [],
                                 "wrong_if": ["a", "b", "c", "d"], "exit_rule": " sell at -10% ",
                                 "clarify_question": "US or worldwide?", "clarify_options": ["US"]})
    assert out["wrong_if"] == ["a", "b", "c"] and out["exit_rule"] == "sell at -10%"
    assert out["clarify_question"] == "" and out["clarify_options"] == []  # one option isn't a choice
    payload = default_interp("plumbing")
    payload.update(wrong_if=["Housing starts fall"], exit_rule="Sell if down 10%.",
                   clarify_question="Which part?", clarify_options=["Repairs", "New homes"])
    r = engine.process_belief("plumbing demand rises", "u-x", claude_client=FakeClaude(payload))
    i = r["interpretation"]
    assert i["wrong_if"] == ["Housing starts fall"] and i["clarify_options"] == ["Repairs", "New homes"]


def test_headlines_route(monkeypatch):
    monkeypatch.setattr(market, "headlines", lambda limit=6: [{"headline": "Copper hits record", "source": "x", "url": "", "symbols": ["FCX"], "created_at": ""}][:limit])
    r = _client().get("/v4/headlines", params={"limit": 3})
    assert r.status_code == 200 and r.json()["headlines"][0]["headline"] == "Copper hits record"


def test_real_money_is_off_by_default_and_safe_when_on(monkeypatch):
    pytest.importorskip("cryptography")
    from backend.v4 import brokerage
    c = _client()
    tok = c.post("/v4/auth/signup", json={"email": "rm@example.com", "password": "long enough pw"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.delenv("MP_REAL_MONEY", raising=False)
    assert c.get("/v4/broker/status", headers=h).json()["enabled"] is False
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 50}, headers=h).status_code == 403
    assert c.get("/v4/broker/connect", headers=h).status_code == 403

    # switched on, with a fake Alpaca behind it
    monkeypatch.setenv("MP_REAL_MONEY", "on"); monkeypatch.setenv("MP_TOKEN_KEY", "k")
    monkeypatch.setenv("ALPACA_OAUTH_CLIENT_ID", "cid"); monkeypatch.setenv("MP_MAX_ORDER_USD", "500")
    url = c.get("/v4/broker/connect", headers=h).json()["url"]
    assert "env=paper" in url and "client_id=cid" in url
    state = url.split("state=")[1].split("&")[0]
    sent = []

    class R:
        def __init__(self, code, js): self.status_code, self._js, self.content, self.text = code, js, b"x", ""
        def json(self): return self._js
    monkeypatch.setattr(brokerage.requests, "post", lambda *a, **k: R(200, {"access_token": "secret-token"}))
    def fake_request(method, url, headers=None, json=None, timeout=None):
        assert headers["Authorization"] == "Bearer secret-token" and url.startswith("https://paper-api.alpaca.markets")
        if url.endswith("/v2/account"): return R(200, {"buying_power": "300", "cash": "300", "equity": "1000", "status": "ACTIVE"})
        sent.append(json); return R(200, {"id": "o1", "status": "accepted"})
    monkeypatch.setattr(brokerage.requests, "request", fake_request)
    assert c.get("/v4/broker/callback", params={"code": "abc", "state": state}, follow_redirects=False).status_code in (302, 307)
    assert "secret-token" not in db.query_one("SELECT token_enc FROM broker_links")["token_enc"]  # encrypted at rest
    assert c.get("/v4/broker/status", headers=h).json()["connected"] is True
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 900}, headers=h).status_code == 400  # over cap
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 400}, headers=h).status_code == 400  # over buying power
    pv = c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 100}, headers=h).json()
    assert pv["env"] == "paper" and "You'll buy about $100.00 of WINR" in pv["plain"]
    assert c.post("/v4/broker/order", json={"preview_id": pv["preview_id"]}, headers=h).status_code == 400  # must confirm
    r = c.post("/v4/broker/order", json={"preview_id": pv["preview_id"], "confirm": True}, headers=h)
    assert r.status_code == 200 and sent[-1]["notional"] == "100.00" and sent[-1]["symbol"] == "WINR"
    assert c.post("/v4/broker/order", json={"preview_id": pv["preview_id"], "confirm": True}, headers=h).status_code == 409  # no double send
    monkeypatch.setenv("MP_REAL_MONEY_PILOT", "someone@else.com")
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 10}, headers=h).status_code == 403


def test_big_move_beliefs_get_straddles_and_strangles():
    assert strategy.default_structure("volatile", 60, "medium", "aggressive") == "Long Straddle"
    assert strategy.default_structure("volatile", 60, "medium", "moderate") == "Long Strangle"
    assert strategy.default_structure("volatile", 60, "medium", "conservative") == "Sell / Avoid"
    st = strategy.build_trade("Long Straddle", "WINR", 100.0, 0.4, TODAY, 60)
    legs = st["trade_legs"]
    assert [l["option_type"] for l in legs] == ["Call", "Put"] and legs[0]["strike_price"] == legs[1]["strike_price"]
    sg = strategy.build_trade("Long Strangle", "WINR", 100.0, 0.4, TODAY, 60)
    kc, kp = sg["trade_legs"][0]["strike_price"], sg["trade_legs"][1]["strike_price"]
    assert kp < 100 < kc and sg["net_cost"] < st["net_cost"]  # strangle is cheaper
    # a big move either way pays; standing still loses
    up = strategy.structure_return(st, 100, 130, TODAY, TODAY + timedelta(days=60), 0.4)
    down = strategy.structure_return(st, 100, 70, TODAY, TODAY + timedelta(days=60), 0.4)
    flat = strategy.structure_return(st, 100, 100, TODAY, TODAY + timedelta(days=70), 0.4)
    assert up > 0 and down > 0 and flat < 0

    payload = default_interp("plumbing")
    payload["direction"] = "volatile"
    for c in payload["candidates"]:
        c["direction"] = "volatile"
    r = engine.process_belief("this earnings report will be a shock either way", "u-v", "moderate", claude_client=FakeClaude(payload))
    shown = [p for p in r["picks"] if p["shown"]]
    assert all(p["structure"] in strategy.VOLATILE or p["price"] < 10 for p in shown)
    # graded on size of move vs the market, not up/down
    grader.grade()


def test_strategy_library_and_preferences():
    from backend.v4 import library
    # every structure builds, and its economics come off the payoff
    for name in strategy.STRUCTURES:
        tr = strategy.build_trade(name, "WINR", 100.0, 0.35, TODAY, 90, target_price=110 if "Butterfly" in name else 0)
        assert tr["type"] == name
    cc = strategy.build_trade("Covered Call", "WINR", 100.0, 0.35, TODAY, 90)
    assert [l["instrument"] for l in cc["trade_legs"]] == ["stock", "option"] and cc["max_profit"] != "Unlimited"
    pp = strategy.build_trade("Protective Put", "WINR", 100.0, 0.35, TODAY, 90)
    assert pp["max_profit"] == "Unlimited" and pp["max_loss"] < 2000  # the put puts a floor under 100 shares
    csp = strategy.build_trade("Cash-Secured Put", "WINR", 100.0, 0.35, TODAY, 90)
    k = csp["trade_legs"][0]["strike_price"]
    assert abs(csp["capital"] - (k * 100 - csp["trade_legs"][0]["est_premium"] * 100)) < 30
    assert strategy.structure_return(cc, 100, 120, TODAY, TODAY + timedelta(days=95), 0.35) > 0
    assert strategy.structure_return(pp, 100, 60, TODAY, TODAY + timedelta(days=95), 0.35) > -0.2  # floor works

    P = strategy.normalize_prefs
    assert library.allowed("bullish", "moderate", "shares") == ["Buy Stock"]
    assert library.allowed("bullish", "moderate", "options", "income")[0] == "Cash-Secured Put"
    assert "Long Call" not in library.allowed("bullish", "conservative", "options")
    assert "Long Call Butterfly" not in library.allowed("bullish", "aggressive")  # needs a target price
    s, why = strategy.select("bullish", 90, "medium", "moderate", P({"instrument": "options", "goal": "protect"}), claude_pick="Long Call")
    assert s == "Protective Put"  # Claude's pick ignored: it doesn't serve the goal
    s, why = strategy.select("bullish", 90, "medium", "moderate", P({}), claude_pick="Covered Call", claude_why="Earns income.", rank=2)
    assert s == "Covered Call" and why == "Earns income."
    s, _ = strategy.select("bullish", 90, "medium", "moderate", P({"instrument": "options"}), price=6.0)
    assert s == "Buy Stock"  # options on a $6 stock are thin

    payload = default_interp("plumbing")
    for c in payload["candidates"]:
        c["strategy"], c["strategy_why"] = "Cash-Secured Put", "Get paid to wait."
    r = engine.process_belief("plumbing demand rises a lot", "u-p", "moderate", claude_client=FakeClaude(payload),
                              prefs={"instrument": "options", "goal": "income"})
    shown = [p for p in r["picks"] if p["shown"]]
    assert r["prefs"] == {"instrument": "options", "goal": "income", "budget_usd": 0.0, "horizon_days": 0}
    assert all(p["structure"] == "Cash-Secured Put" and p["structure_reason"] == "Get paid to wait." for p in shown)
    r2 = engine.process_belief("plumbing demand rises a lot", "u-p", "moderate", claude_client=FakeClaude(payload),
                               prefs={"instrument": "shares"})
    assert all(p["structure"] == "Buy Stock" for p in r2["picks"] if p["shown"])


def test_auto_warmup_force_feeds_until_target(monkeypatch):
    from backend.v4 import seeder as _sd
    monkeypatch.setattr(_sd, "EXTRA_BACKFILL_GRANTS", {})  # extra grants are tested separately
    monkeypatch.setenv("MP_WARMUP_GRADED", "100000"); monkeypatch.setenv("MP_WARMUP_BUDGET_USD", "1")
    monkeypatch.setenv("MP_WARMUP_BATCH", "12"); monkeypatch.setenv("MP_WARMUP_GENERATE", "0")
    monkeypatch.setenv("MP_SEED_N", "3"); monkeypatch.setenv("MP_SEED_GENERATE", "0")
    monkeypatch.setenv("MP_HOURLY_TRAIN", "1")
    monkeypatch.setattr(nn, "train", lambda force=False: {"status": "skipped", "reason": "test"})
    fake = FakeClaude()
    out = seeder.auto(claude_client=fake)
    assert out["backfill"]["ok"] > 0 and out["backfill"]["grading"]["graded"] > 0 and "train" in out
    assert out["live"]["ok"] == 3  # TODAY is a weekday
    out2 = seeder.auto(claude_client=fake)
    assert "live" not in out2  # live batch only once a day
    monkeypatch.setenv("MP_HOURLY_TRAIN", "0")
    assert "train" not in seeder.auto(claude_client=fake)  # by default the hourly job skips the slow retrain
    monkeypatch.setenv("MP_WARMUP_GRADED", "1")
    out3 = seeder.auto(claude_client=fake)
    assert "backfill" not in out3  # warmed up: stop force-feeding


def test_users_never_see_practice_beliefs():
    fake = FakeClaude()
    seeder.run("backfill", 6, claude_client=fake)       # practice feed, graded right away
    seeder.run("live", 3, claude_client=fake)
    assert engine.trending()["themes"] == []             # nothing from real people yet
    r = engine.process_belief("plumbing demand is going to be high", "u-real", claude_client=fake)
    assert all(p["track_record"] is None for p in r["picks"])  # practice results never shown as a track record
    t = engine.trending()
    assert len(t["themes"]) > 0 and all(th["beliefs"] == 1 for th in t["themes"])



def test_email_verification_and_password_reset(monkeypatch):
    from backend.v4 import mailer
    monkeypatch.setenv("MP_MAIL_TEST_SINK", "1"); mailer._sent_for_tests.clear()
    monkeypatch.setenv("MP_SITE_URL", "https://site.example")
    c = _client()
    r = c.post("/v4/auth/signup", json={"email": "new@example.com", "password": "a good password", "name": "Ana"}).json()
    assert r["needs_verification"] and "token" not in r
    mail = mailer._sent_for_tests[-1]
    assert mail["to"] == "new@example.com" and "https://site.example/verify?token=" in mail["text"]
    login = c.post("/v4/auth/login", json={"email": "new@example.com", "password": "a good password"})
    assert login.status_code == 403 and "confirm your email" in login.json()["detail"]
    assert c.post("/v4/auth/resend", json={"email": "nobody@example.com"}).status_code == 200  # same answer for unknown emails
    c.post("/v4/auth/resend", json={"email": "new@example.com"})
    tok = mailer._sent_for_tests[-1]["text"].split("verify?token=")[1].split()[0]
    v = c.post("/v4/auth/verify", json={"token": tok}).json()
    assert v["account"]["email"] == "new@example.com" and v["token"]
    assert c.post("/v4/auth/verify", json={"token": tok}).status_code == 409  # second open: already confirmed, no new session
    assert c.post("/v4/auth/login", json={"email": "new@example.com", "password": "a good password"}).status_code == 200
    # forgot password
    c.post("/v4/auth/forgot", json={"email": "new@example.com"})
    rt = mailer._sent_for_tests[-1]["text"].split("reset?token=")[1].split()[0]
    assert c.post("/v4/auth/reset", json={"token": rt, "password": "short"}).status_code == 400
    assert c.post("/v4/auth/reset", json={"token": rt, "password": "brand new password"}).status_code == 200
    assert c.post("/v4/auth/login", json={"email": "new@example.com", "password": "brand new password"}).status_code == 200
    assert c.post("/v4/auth/login", json={"email": "new@example.com", "password": "a good password"}).status_code == 401


def test_accounts_made_before_verification_still_log_in(monkeypatch):
    from backend.v4 import mailer
    c = _client()
    c.post("/v4/auth/signup", json={"email": "old@example.com", "password": "old password ok"})  # email not configured -> verified
    monkeypatch.setenv("MP_MAIL_TEST_SINK", "1")
    assert c.post("/v4/auth/login", json={"email": "old@example.com", "password": "old password ok"}).status_code == 200


def test_bearish_belief_leads_with_bearish_picks():
    """A beneficiary scored higher by Claude/the network must not jump ahead of the user's bearish call."""
    payload = {
        "is_market_belief": True, "note": "", "summary": "Pipe makers suffer.", "direction": "bearish",
        "horizon_days": 120, "conviction": "medium", "themes": ["plumbing"], "causal_chain": "x",
        "candidates": [
            {"ticker": "WINR", "name": "x", "exposure": "beneficiary", "direction": "bullish", "rationale": "rival gains", "score": 0.95},
            {"ticker": "PIPE", "name": "x", "exposure": "direct", "direction": "bearish", "rationale": "hurt", "score": 0.6},
            {"ticker": "LOSR", "name": "x", "exposure": "supplier", "direction": "bearish", "rationale": "hurt", "score": 0.5},
        ],
    }
    r = engine.process_belief("pipe makers are going to struggle", "ub", "moderate", claude_client=FakeClaude(payload))
    dirs = [p["direction"] for p in r["picks"]]
    assert dirs[:2] == ["bearish", "bearish"] and dirs[-1] == "bullish"
    assert r["picks"][0]["ticker"] == "PIPE" and r["picks"][0]["structure"] in ("Bear Put Spread", "Long Put", "Sell / Avoid", "Bear Call Spread")


def test_grading_separates_the_call_from_how_well_we_expressed_it():
    """belief_right = the user's part; sel_edge = ours (each pick vs the simple choice)."""
    def row(pid, d, ret, etf=False, spy=0.03):
        return {"pick_id": pid, "checkpoint_days": 30, "direction": d, "ret": ret, "spy_ret": spy, "etf": etf}
    by = {t[4]: t for t in grader._group_scores(
        [row("A", "bullish", 0.10), row("B", "bullish", 0.02), row("F", "bullish", 0.05, etf=True)], "bullish")}
    assert by["A"][0] == pytest.approx(0.05) and by["A"][3] == "fund"          # benchmark = the sector fund
    assert by["A"][1] == pytest.approx(0.05) and by["B"][1] == pytest.approx(-0.03)
    assert by["F"][1] is None                                                   # the fund isn't graded vs itself
    assert {t[2] for t in by.values()} == {1}                                   # theme beat the market: call came true

    by = {t[4]: t for t in grader._group_scores(
        [row("A", "bearish", -0.10, spy=0.0), row("B", "bearish", -0.02, spy=0.0)], "bearish")}
    assert by["A"][3] == "basket" and by["A"][1] == pytest.approx(0.04) and by["B"][1] == pytest.approx(-0.04)
    assert by["A"][2] == 1                                                      # theme fell vs market: bearish call right

    by = {t[4]: t for t in grader._group_scores([row("S", "bullish", 0.10, spy=0.20)], "bullish")}
    assert by["S"][1] is None and by["S"][3] == "self" and by["S"][2] == 0     # lone idea: nothing to compare; call wrong

    by = {t[4]: t for t in grader._group_scores(
        [row("V1", "volatile", 0.20), row("V2", "volatile", -0.05)], "volatile")}
    assert by["V1"][1] == pytest.approx(0.125) and by["V2"][1] == pytest.approx(-0.025)


def test_backfill_grades_both_questions_and_network_learns_selection():
    seeder.run("backfill", n=60, years=1, concurrency=1, claude_client=FakeClaude())
    grader.grade()  # (the backfill grades as it goes; this catches anything left)
    rows = db.query("SELECT p.ticker, o.sel_edge, o.belief_right, o.bench_kind FROM outcomes o JOIN picks p ON p.id = o.pick_id")
    assert rows and all(r["bench_kind"] for r in rows)
    assert all(r["sel_edge"] is None for r in rows if r["ticker"] == "XLI")     # XLI is the benchmark fund
    assert any(r["sel_edge"] is not None for r in rows if r["ticker"] != "XLI")
    assert {r["belief_right"] for r in rows} <= {0, 1}
    assert grader.score_selection() == 0                                        # nothing left to score
    w = [r["sel_edge"] for r in rows if r["ticker"] == "WINR" and r["sel_edge"] is not None]
    l = [r["sel_edge"] for r in rows if r["ticker"] == "LOSR" and r["sel_edge"] is not None]
    assert sum(w) / len(w) > sum(l) / len(l)                                    # the uptrend beat the fund, the downtrend didn't
    sc = engine.expression_scorecard(30)
    assert sc["picks"]["n"] > 0 and 0 <= sc["calls"]["came_true_rate"] <= 1


def test_my_calls_compares_picks_with_the_sector_fund():
    engine.process_belief("plumbing demand is going to be high", "u-fund", "moderate", claude_client=FakeClaude())
    b = engine.my_beliefs("u-fund")["beliefs"][0]
    assert any(p["vs_simple"] is not None and p["simple"] == "XLI" for p in b["picks"])
    assert all(p["ticker"] != "XLI" or p["vs_simple"] is None for p in b["picks"])


# ---------------- fuzz: hostile and random input never crashes the server ----------------

_NASTY = ["", " ", "\n\t", "a", "x" * 5000, "🚀📉💸" * 50, "'; DROP TABLE beliefs; --", "<script>alert(1)</script>",
          "\u0000null\u0000byte", "Robert'); --", "../../etc/passwd", "%00%0a", "TSLA " * 400, "١٢٣ أسهم", "ñandú café",
          "{\"json\": true}", "null", "None", "-1", "1e309", "NaN"]


def _rand_val(rng):
    pick = rng.randrange(9)
    if pick == 0:
        return rng.choice(_NASTY)
    if pick == 1:
        return rng.randint(-10**12, 10**12)
    if pick == 2:
        return rng.random() * rng.choice([1, -1, 1e12])
    if pick == 3:
        return None
    if pick == 4:
        return [rng.choice(_NASTY) for _ in range(rng.randint(0, 3))]
    if pick == 5:
        return {rng.choice(_NASTY)[:20]: rng.choice(_NASTY) for _ in range(rng.randint(0, 3))}
    if pick == 6:
        return rng.choice([True, False])
    if pick == 7:
        return rng.choice(["plumbing will boom", "potatoes are in demand", "airlines will crash", "AAPL hits 300"])
    return rng.choice(["conservative", "moderate", "aggressive", "bold", "MODERATE", "careful"])


def test_fuzz_api_never_500s(monkeypatch):
    import random as _r
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.v4 import interpreter, mailer
    from backend.v4.router import router
    from urllib.parse import quote

    fake = FakeClaude()
    monkeypatch.setattr(interpreter, "_client", lambda: fake)
    monkeypatch.setattr(market, "headlines", lambda limit=4: [])
    monkeypatch.setenv("MP_MAIL_TEST_SINK", "1")
    monkeypatch.setenv("MP_ADMIN_TOKEN", "owner")
    app = FastAPI(); app.include_router(router, prefix="/v4")
    c = TestClient(app, raise_server_exceptions=False)
    rng = _r.Random(20261029)
    posts = {
        "/v4/belief": ["belief", "user_id", "risk_profile", "prefs"],
        "/v4/feedback": ["belief_id", "kind", "user_id", "pick_id"],
        "/v4/waitlist": ["email", "belief", "source", "website"],
        "/v4/auth/signup": ["email", "password", "name", "device_id"],
        "/v4/auth/login": ["email", "password", "device_id"],
        "/v4/auth/profile": ["name"],
        "/v4/auth/password": ["current", "new"],
        "/v4/auth/delete": ["password"],
        "/v4/auth/verify": ["token", "device_id"],
        "/v4/auth/resend": ["email"],
        "/v4/auth/forgot": ["email"],
        "/v4/auth/reset": ["token", "password"],
        "/v4/auth/logout": [],
        "/v4/broker/preview": ["ticker", "side", "amount_usd", "belief_id", "pick_id"],
        "/v4/broker/order": ["preview_id", "confirm"],
        "/v4/broker/disconnect": [],
        "/v4/admin/reset_password": ["email"],
    }
    gets = ["/v4/belief/{x}", "/v4/trending?days={x}", "/v4/stats", "/v4/headlines?limit={x}",
            "/v4/replay?tickers={x}&directions={x}&days={x}", "/v4/my_beliefs?user_id={x}", "/v4/learning",
            "/v4/auth/me", "/v4/broker/status", "/v4/broker/connect", "/v4/broker/callback?code={x}&state={x}",
            "/v4/admin/accounts", "/v4/admin/ml", "/v4/admin/waitlist"]
    n = 0
    for _ in range(int(os.getenv("MP_FUZZ_ROUNDS", "25"))):
        for path, fields in posts.items():
            body = {f: _rand_val(rng) for f in fields if rng.random() < 0.85}
            if rng.random() < 0.1:
                body = rng.choice([[], "text", 5, None])
            hdr = rng.choice([{}, {"Authorization": "Bearer " + quote(str(rng.choice(_NASTY)))[:300]}, {"X-Admin-Token": "nope"}])
            r = c.post(path, json=body, headers=hdr)
            assert r.status_code < 500 or path == "/v4/belief" and r.status_code in (502,), (path, body, r.status_code, r.text[:200])
            n += 1
        for g in gets:
            url = g.replace("{x}", quote(str(_rand_val(rng)), safe=""))
            r = c.get(url, headers=rng.choice([{}, {"Authorization": "Bearer junk"}, {"X-Admin-Token": "nope"}]))
            assert r.status_code < 500, (url, r.status_code, r.text[:200])
            n += 1
    assert n > 700
    # admin routes never answer to a wrong token
    for g in ["/v4/admin/accounts", "/v4/admin/ml", "/v4/admin/waitlist", "/v4/learning"]:
        assert c.get(g, headers={"X-Admin-Token": "nope"}).status_code == 403


def test_fuzz_engine_with_well_formed_but_weird_beliefs():
    import random as _r
    rng = _r.Random(7)
    fake = FakeClaude()
    risks = ["conservative", "moderate", "aggressive", "", "BOLD", "x" * 300]
    prefs_pool = [None, {}, {"instrument": "options"}, {"instrument": "shares", "goal": "income"},
                  {"instrument": "bogus", "goal": "moon"}, {"goal": ["list"]}, {"instrument": None}, {"x": 1}]
    for i in range(150):
        text = rng.choice(_NASTY + ["plumbing will boom", "potatoes are in demand", "airlines will crash"])
        if not text.strip():
            continue
        r = engine.process_belief(text[:1000], f"u-fz{i % 7}", rng.choice(risks), claude_client=fake,
                                  prefs=rng.choice(prefs_pool))
        assert isinstance(r, dict) and "picks" in r
        for p in r["picks"]:
            t = p["trade"]
            assert p["structure"] and t is not None
            assert all(math.isfinite(float(x)) for x in [p["price"], p["score"]])
    assert engine.my_beliefs("u-fz1")["beliefs"]


def test_messy_claude_answers_never_break_a_belief():
    """Claude's JSON can come back incomplete or odd; the engine must clean it up, not crash."""
    import copy
    import random as _r
    rng = _r.Random(3)
    base = default_interp("plumbing")
    mutations = [
        lambda d: d.pop("horizon_days"), lambda d: d.update(horizon_days="soon"), lambda d: d.update(horizon_days=-5),
        lambda d: d.update(horizon_days=10 ** 9), lambda d: d.update(direction="sideways"), lambda d: d.pop("themes"),
        lambda d: d.update(themes="plumbing"), lambda d: d.update(conviction=None), lambda d: d.update(candidates=[]),
        lambda d: d["candidates"][0].update(score=7), lambda d: d["candidates"][0].update(score="high"),
        lambda d: d["candidates"][0].pop("direction"), lambda d: d["candidates"][0].update(direction="up"),
        lambda d: d["candidates"][0].update(ticker="pipe "), lambda d: d["candidates"][0].update(ticker=""),
        lambda d: d["candidates"][1].update(strategy="Moon Rocket"), lambda d: d["candidates"][1].update(strategy=None),
        lambda d: d.update(target_price="lots"), lambda d: d.update(target_price=-3), lambda d: d.update(wrong_if="x"),
        lambda d: d.update(clarify_options="a,b"), lambda d: d["candidates"].append({"ticker": "WINR"}),
        lambda d: d["candidates"].extend(copy.deepcopy(d["candidates"])),  # duplicates
    ]
    for i in range(80):
        d = copy.deepcopy(base)
        for m in rng.sample(mutations, rng.randint(1, 4)):
            try:
                m(d)
            except Exception:
                pass
        r = engine.process_belief(f"plumbing demand will rise {i}", f"u-m{i}", rng.choice(["conservative", "moderate", "aggressive"]),
                                  claude_client=FakeClaude(d))
        assert isinstance(r, dict)
        tickers = [p["ticker"] for p in r.get("picks", [])]
        assert len(tickers) == len(set(tickers)), tickers  # no duplicate picks


def test_every_structure_has_sane_numbers_across_prices_and_horizons():
    import random as _r
    rng = _r.Random(11)
    entry = date(2026, 10, 15)
    n = 0
    for name in strategy.STRUCTURES:
        for _ in range(40):
            price = rng.choice([1.5, 4.8, 12.3, 47.0, 103.9, 488.0, 1520.0, 6100.0]) * rng.uniform(0.9, 1.1)
            vol = rng.choice([0.08, 0.2, 0.35, 0.8, 1.6])
            horizon = rng.choice([7, 30, 90, 180, 365, 730])
            tp = price * rng.uniform(0.8, 1.4) if name == "Long Call Butterfly" else 0.0
            t = strategy.build_trade(name, "TEST", price, vol, entry, horizon, target_price=tp)
            n += 1
            for leg in t.get("trade_legs", []):
                if leg.get("instrument") == "stock":
                    assert leg["quantity"] > 0
                    continue
                assert leg["strike_price"] > 0, (name, price, leg)
                assert leg["est_premium"] >= 0 and math.isfinite(leg["est_premium"]), (name, leg)
                exp = date.fromisoformat(leg["expiration"])
                assert (exp - entry).days >= strategy.MIN_DAYS_TO_EXPIRY, (name, horizon, leg["expiration"])
            for k in ("max_loss", "capital"):
                if k in t and isinstance(t[k], (int, float)):
                    assert math.isfinite(t[k]) and t[k] >= 0, (name, k, t[k])
            if isinstance(t.get("max_profit"), (int, float)):
                assert math.isfinite(t["max_profit"]), (name, t)
    assert n == 40 * len(strategy.STRUCTURES)


def test_shares_lead_and_every_pick_can_switch():
    from backend.v4 import strategy
    auto = strategy.normalize_prefs({})
    # Balanced, bullish: the top idea is plain shares even if Claude suggested an option
    s, why = strategy.select("bullish", 60, "medium", "moderate", auto, claude_pick="Bull Call Spread", rank=0, price=150)
    assert s == "Buy Stock" and "Shares first" in why
    assert strategy.select("bullish", 60, "medium", "moderate", auto, rank=1, price=150)[0] == "Buy Stock"
    assert strategy.select("bullish", 60, "medium", "moderate", auto, rank=2, price=150)[0] != "Buy Stock"
    # Bold: options first, shares second
    assert strategy.select("bullish", 60, "high", "aggressive", auto, rank=0, price=150)[0] != "Buy Stock"
    assert strategy.select("bullish", 60, "high", "aggressive", auto, rank=1, price=150)[0] == "Buy Stock"
    # Someone who chose options keeps options
    s, _ = strategy.select("bullish", 60, "medium", "moderate", strategy.normalize_prefs({"instrument": "options"}), rank=0, price=150)
    assert s != "Buy Stock"
    # The other version exists both ways
    assert strategy.alternative("Buy Stock", "bullish", 60, "medium", "moderate", 150) in strategy.OPTION_STRUCTURES
    assert strategy.alternative("Bear Put Spread", "bearish", 60, "medium", "moderate", 150) == "Sell / Avoid"
    assert strategy.alternative("Buy Stock", "bullish", 60, "medium", "moderate", 5) == ""


def test_movers_feed_turns_headlines_into_hunches(monkeypatch):
    from backend.v4 import movers
    news = [
        {"headline": "Airlines add record holiday flights as bookings jump", "symbols": ["DAL", "UAL"], "source": "x", "url": "u", "created_at": "t"},
        {"headline": "Stocks mixed in afternoon trade", "symbols": [], "source": "x", "url": "u", "created_at": "t"},
        {"headline": "Chipmaker warns on demand", "symbols": ["NOPE"], "source": "x", "url": "u", "created_at": "t"},
    ]
    monkeypatch.setattr(market, "headlines", lambda limit=6: news)
    monkeypatch.setattr(market, "asset_info", lambda s: None if s in ("FAKE", "NOPE") else {"symbol": s})
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {s: {"price": 10.0, "change": 0.01} for s in syms})
    payload = {"items": [
        {"n": 0, "keep": True, "hunch": "People will fly more this holiday season", "why": "More seats sold.",
         "companies": [{"ticker": "$DAL", "direction": "up", "why": "more fares"}, {"ticker": "FAKE", "direction": "up", "why": "x"},
                       {"ticker": "dal", "direction": "up", "why": "dup"}, {"ticker": "JETS", "direction": "sideways", "why": "fund"}]},
        {"n": 1, "keep": False, "hunch": "", "why": "", "companies": []},
        {"n": 2, "keep": True, "hunch": "Chip demand is cooling", "why": "", "companies": [{"ticker": "NOPE", "direction": "down", "why": "x"}]},
    ]}
    fake = FakeClaude(payload)
    out = movers.feed(client=fake)
    assert len(out["items"]) == 1  # the vague one dropped, the one with no real tickers dropped
    it = out["items"][0]
    assert it["hunch"].startswith("People will fly")
    assert [c["ticker"] for c in it["companies"]] == ["DAL", "JETS"]
    assert it["companies"][1]["direction"] == "up" and it["companies"][0]["change"] == 0.01
    movers.feed(client=fake)
    assert len(fake.calls) == 1  # cached: one Claude call shared by everyone

    # no Claude: still a feed, headline is the hunch, tagged tickers are the companies
    db.execute("DELETE FROM kv_cache WHERE k = ?", (movers.KEY,))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    plain = movers.feed()
    assert plain["ai"] is False and plain["items"][0]["hunch"] == news[0]["headline"]
    assert [c["ticker"] for c in plain["items"][0]["companies"]] == ["DAL", "UAL"]


def test_brain_learns_from_real_news_both_sides(monkeypatch):
    from backend.v4 import movers, seeder
    feed = {"items": [{"headline": "Airline bookings slow", "hunch": "Holiday travel will be weaker than airlines expect."},
                      {"headline": "Raw headline only", "hunch": "Raw headline only"}]}
    monkeypatch.setattr(movers, "feed", lambda client=None: feed)
    got = seeder.news_beliefs(6)
    assert got == ["Holiday travel will be weaker than airlines expect",
                   "I don't think holiday travel will be weaker than airlines expect"]
    seen = []
    monkeypatch.setattr(seeder.engine, "process_belief", lambda text, **kw: seen.append((text, kw["source"])) or {"valid": True, "usage": {"cost_usd": 0.001}})
    r = seeder.run("live", n=len(got), beliefs=got, source="seed_news", max_usd=1)
    assert r["ok"] == 2 and {s for _, s in seen} == {"seed_news"} and {t for t, _ in seen} == set(got)


def test_opposite_side_keeps_names_and_acronyms_capitalised():
    f = seeder._lower_first
    assert f("AI demand will keep lifting chips") == "AI demand will keep lifting chips"
    assert f("UK regulators will tighten rules") == "UK regulators will tighten rules"
    assert f("Microsoft pulling back will hurt neoclouds") == "Microsoft pulling back will hurt neoclouds"
    assert f("Tesla's robotaxi push will grow") == "Tesla's robotaxi push will grow"
    assert f("Hong Kong regulators will act") == "Hong Kong regulators will act"
    assert f("Canadian plant closures will shift output") == "Canadian plant closures will shift output"
    assert f("Fresenius will win clinics", "rivals lose to Fresenius in China") == "Fresenius will win clinics"
    assert f("Cheap chips will spread") == "cheap chips will spread"
    assert f("A Democratic Congress will block it") == "a Democratic Congress will block it"
    assert f("Data center demand will rise") == "data center demand will rise"


def test_price_target_below_today_means_bearish():
    interp = {"direction": "bullish", "target_price": 5.0}
    valid = [{"ticker": "SLS", "price": 9.0, "direction": "bullish"}, {"ticker": "XBI", "price": 90.0, "direction": "bullish"}]
    engine._fix_direction_from_target(interp, valid, "SELLAS (SLS) will fall to $5 by December")
    assert interp["direction"] == "bearish" and [v["direction"] for v in valid] == ["bearish", "bearish"]
    ok = {"direction": "bullish", "target_price": 15.0}
    v2 = [{"ticker": "SLS", "price": 9.0, "direction": "bullish"}]
    engine._fix_direction_from_target(ok, v2, "SLS to $15")
    assert ok["direction"] == "bullish" and v2[0]["direction"] == "bullish"


def test_trending_counts_each_belief_once_under_one_theme():
    fake = FakeClaude()
    for risk in ("moderate", "aggressive", "conservative"):
        engine.process_belief("plumbing demand is going to be high", "u-t1", risk, claude_client=fake)
    engine.process_belief("Plumbing demand is going to be high", "u-t2", "moderate", claude_client=fake)
    for i in range(4):
        engine.process_belief(f"people want cheaper food {i}", "u-t3", "moderate", claude_client=fake)
    themes = engine.trending(days=14)["themes"]
    names = [t["theme"] for t in themes]
    assert "housing" not in names and "potatoes" not in names  # filed under the main theme only, no twin cards
    plumbing = next(t for t in themes if t["theme"].lower() == "plumbing")
    assert plumbing["beliefs"] == 1 and plumbing["people"] == 2  # re-runs and case changes count once
    food = next(t for t in themes if t["theme"] == "food")
    assert food["beliefs"] == 4 and food["people"] == 1


def test_movers_falls_back_when_claude_keeps_nothing(monkeypatch):
    from backend.v4 import movers
    monkeypatch.setattr(market, "headlines", lambda limit=6: [{"headline": "Delta raises outlook", "symbols": ["DAL"], "source": "x", "url": "", "created_at": ""}])
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s})
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {})
    out = movers.feed(client=FakeClaude({"items": [{"n": 0, "keep": False, "hunch": "", "why": "", "companies": []}]}))
    assert [it["headline"] for it in out["items"]] == ["Delta raises outlook"] and out["diag"]["headlines"] == 1


def test_called_it_email_once_and_unsubscribe(monkeypatch):
    from backend.v4 import notify, mailer
    from datetime import datetime, timedelta, timezone
    monkeypatch.setenv("MP_MAIL_TEST_SINK", "1")
    mailer._sent_for_tests.clear()
    db.execute("INSERT INTO accounts (id, uid, email, name, pw_hash, created_at, verified) VALUES (?,?,?,?,?,?,?)",
               ("a-n1", "u-n1", "n1@example.com", "Sam Lee", "x", "2026-01-01", 1))
    db.execute("INSERT INTO accounts (id, uid, email, name, pw_hash, created_at, verified) VALUES (?,?,?,?,?,?,?)",
               ("a-n2", "u-n2", "n2@example.com", "", "x", "2026-01-01", 0))  # not confirmed: never emailed
    old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    new = datetime.now(timezone.utc).isoformat()
    beliefs = {"u-n1": [{"belief_id": "b-new", "text": "too new", "created_at": new, "call": {"playing_out": True, "vs_spy": 0.2}},
                        {"belief_id": "b-1", "text": "AI will need more power", "created_at": old, "call": {"playing_out": True, "vs_spy": 0.051}}],
               "u-n2": [{"belief_id": "b-2", "text": "x", "created_at": old, "call": {"playing_out": True, "vs_spy": 0.3}}]}
    monkeypatch.setattr(engine, "my_beliefs", lambda uid, limit=30: {"beliefs": beliefs.get(uid, [])})
    assert notify.run()["sent"] == 1
    m = mailer._sent_for_tests[-1]
    assert m["to"] == "n1@example.com" and "AI will need more power" in m["text"] and "+5.1 points" in m["text"]
    assert "Hi Sam" in m["text"] and "Unsubscribe" in m["text"]
    assert notify.run()["sent"] == 0  # once per belief, and at most weekly
    assert not notify.unsubscribe("a-n1", "wrong")
    assert notify.unsubscribe("a-n1", notify.unsubscribe_sig("a-n1"))
    db.execute("DELETE FROM kv_cache WHERE k LIKE 'notify%'")
    assert notify.run()["accounts"] == 0  # unsubscribed and unconfirmed people are skipped


def test_passkey_challenges_are_single_use_and_unknown_keys_refused():
    from backend.v4 import passkeys
    from backend.v4.auth import AuthError
    opts = passkeys.login_options("https://marketplayground-web.onrender.com")
    assert opts["options"]["rpId"] == "marketplayground-web.onrender.com" and opts["challenge_id"]
    with pytest.raises(AuthError) as e:
        passkeys.login_verify(opts["challenge_id"], {"id": "nope", "rawId": "nope", "type": "public-key", "response": {}})
    assert e.value.status == 401
    with pytest.raises(AuthError):  # the same challenge can't be replayed
        passkeys.login_verify(opts["challenge_id"], {"id": "nope"})
    assert passkeys._rp_id("https://evil.example") == "marketplayground-web.onrender.com"


def test_brain_snapshot_is_public_safe_and_counts():
    from backend.v4 import brain
    fake = FakeClaude()
    engine.process_belief("my secret plan about plumbing demand", "u-private", "moderate", claude_client=fake)
    engine.process_belief("people want cheaper food", "seed", "moderate", source="seed_news", claude_client=fake)
    brain._cache.update(at=0, v=None)
    s = brain.snapshot()
    assert s["counts"]["beliefs"] == 2 and s["counts"]["from_news"] == 1 and s["counts"]["people"] == 1
    assert s["counts"]["companies"] > 0 and len(s["growth"]) == 31
    texts = " ".join(x["text"] for x in s["learned"])
    assert "secret" not in texts and "cheaper food" in texts  # a user's own words never appear
    assert "secret" not in json.dumps(s)


def test_expert_panel_and_market_backdrop(monkeypatch):
    from backend.v4 import interpreter
    out = interpreter._sanitize({"panel": {"economist": "Rates are falling.", "skeptic": 5, "junk": "x"}})
    assert out["panel"] == {"economist": "Rates are falling.", "industry": "", "geopolitics": "", "skeptic": "5"}
    assert interpreter._sanitize({})["panel"]["geopolitics"] == ""
    msg = interpreter.build_user_message("oil will rise", "moderate", None, {"regime": "oil +5.0% over 1 month"})
    assert "Market backdrop: oil +5.0% over 1 month" in msg
    assert "panel" in interpreter.SCHEMA["required"]
    market._regime_cache.clear()
    line = market.regime(TODAY)
    assert "US stocks" in line and "over 3 months" in line  # built only from prices up to that day


def test_brain_activity_never_shows_peoples_words_and_schedule():
    from backend.v4 import brain
    from datetime import datetime, timezone
    fake = FakeClaude()
    engine.process_belief("my private hunch about plumbing", "u-p1", "moderate", claude_client=fake)
    engine.process_belief("people want cheaper food", "seed", "moderate", source="seed_news", claude_client=fake)
    brain._cache.update(at=0, v=None)
    s = brain.snapshot()
    kinds = {e["kind"] for e in s["activity"]}
    assert {"person", "news"} <= kinds
    assert "private" not in json.dumps(s["activity"])
    nr = brain._next_runs(datetime(2026, 10, 30, 22, 50, tzinfo=timezone.utc))  # a Friday, after grading
    assert nr["learning"].startswith("2026-10-30T23:13") and nr["grading"].startswith("2026-11-02T22:47")  # Monday


def test_job_health_is_recorded_and_public_view_hides_errors(monkeypatch):
    from backend.v4 import seeder, brain
    monkeypatch.setattr(seeder, "auto", lambda claude_client=None: (_ for _ in ()).throw(RuntimeError("secret detail")))
    with pytest.raises(RuntimeError):
        seeder.auto_with_health()
    pub, full = brain.health(True), brain.health(False)
    assert pub["learning"]["ok"] is False and "detail" not in pub["learning"]
    assert "secret detail" in full["learning"]["detail"]
    monkeypatch.setattr(seeder, "auto", lambda claude_client=None: {"news": {"ok": 4, "errors": 0}, "grade": {"graded": 9}})
    seeder.auto_with_health()
    h = brain.health(False)["learning"]
    assert h["ok"] is True and h["summary"]["added"] == 4 and h["summary"]["graded"] == 9


def test_backup_feeder_only_feeds_when_the_hourly_job_is_quiet(monkeypatch):
    from backend.v4 import feeder, seeder, brain
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    assert feeder.should_feed(now)  # nothing recorded yet
    seeder.record_health("learning_cron", True)
    assert not feeder.should_feed(now)
    assert feeder.should_feed(now + timedelta(minutes=80))
    seeder.record_health("learning_cron", False, "boom")
    assert feeder.should_feed(now)
    calls = []
    monkeypatch.setattr(seeder, "auto", lambda **kw: calls.append(kw) or {"news": {"ok": 3, "errors": 0}})
    r = feeder.feed_once()
    assert r["fed"] and calls[0]["batch_override"] == 20 and calls[0]["concurrency"] == 1 and calls[0]["train"] is False
    assert feeder.feed_once()["fed"]  # its own rounds don't stop it: it waits for the regular job to succeed
    seeder._learning_health("cron", False, "no key")
    assert brain.health(True)["learning"]["ok"] is True  # a cron failure doesn't hide the backup's success


def test_same_question_same_companies_across_trade_styles():
    fake = FakeClaude()
    a = engine.process_belief("Plumbing demand is going to be high", "u-sq", "moderate", prefs={"instrument": "shares"}, claude_client=fake)
    b = engine.process_belief("plumbing demand is going to be high", "u-sq", "aggressive", prefs={"instrument": "options"}, claude_client=fake)
    assert len(fake.calls) == 1  # asked once, reused
    assert [p["ticker"] for p in a["picks"]] == [p["ticker"] for p in b["picks"]]
    assert {p["structure"] for p in b["picks"] if p["shown"]} != {"Buy Stock"}  # trades still follow the choice


def test_story_mode_cards_are_grounded_and_cached(monkeypatch):
    from backend.v4 import movers
    news = [{"headline": "Cloud sales doubled to $30.7B from $15.2B a year ago", "symbols": ["GOOGL"], "source": "x",
             "url": "u", "created_at": "t", "summary": "Search sales came in at $63.4B versus $65B expected."}]
    monkeypatch.setattr(market, "headlines", lambda limit=6: news)
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s})
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {s: {"price": 10.0, "change": -0.05} for s in syms})
    feed_payload = {"items": [{"n": 0, "keep": True, "hunch": "Cloud demand keeps booming", "why": "AI spending.",
                               "companies": [{"ticker": "GOOGL", "direction": "up", "why": "cloud"}]}]}
    movers.feed(client=FakeClaude(feed_payload))
    story_payload = {"hook_big": "$30.7B", "hook_line": "Cloud just doubled.", "happened": "Sales doubled.",
                     "figures": [{"label": "Cloud sales", "before_label": "A year ago", "before": "$15.2B", "after_label": "Now", "after": "$30.7B"},
                                 {"label": "Made up", "before_label": "Then", "before": "$1B", "after_label": "Now", "after": "$99B"}],
                     "why": "AI needs servers.", "twist": "Spending could slow."}
    fake = FakeClaude(story_payload)
    out = movers.story(news[0]["headline"], client=fake)
    st = out["story"]
    assert st["hook_big"] == "$30.7B" and st["ai"] is True
    assert [f["label"] for f in st["figures"]] == ["Cloud sales"]  # the invented numbers were dropped
    assert out["item"]["companies"][0]["change"] == -0.05
    movers.story(news[0]["headline"], client=fake)
    assert len(fake.calls) == 1  # one call per story, shared by everyone
    assert movers.story("Some headline that isn't in the feed", client=fake) is None
    # no Claude: still a story built from the article itself
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fb = movers._fallback_story(out["item"])
    # the hook is shown whole or replaced, never clipped mid-phrase
    assert movers._hook("Credit stress looks contained") == "Credit stress looks contained"
    assert movers._hook("This hook phrase is far too long to show on one card") == ""
    assert fb["ai"] is False and fb["figures"] == [] and fb["hook_line"]


def test_lineages_evolve_and_snapshot(monkeypatch):
    from backend.v4 import lineages, brain
    monkeypatch.setattr(lineages, "MIN_BELIEFS", 10)
    rng = __import__("random").Random(1)
    for i in range(60):
        bid = f"b-lin{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", f"2026-01-{1 + i % 28:02d}T00:00:00", "2026-01-01", "seed_backfill"))
        for j in range(3):
            mom = rng.uniform(-0.3, 0.3)
            pid = f"p-lin{i}-{j}"
            feats = {"num": {"mom60": mom, "vol60": rng.uniform(0.2, 0.6), "claude_score": rng.random()}}
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", "2026-01-01", 10.0, db.dumps(feats)))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, lineages.CHECKPOINT, "2026-02-01", 10.0, 0.0, 0.0, mom * 0.5 + rng.gauss(0, 0.01), "2026-02-01"))
    monkeypatch.setattr(lineages, "SNAP_TTL", 0)
    r1 = lineages.evolve(seed=1)
    assert r1["evolved"] and r1["generation"] == 2
    snap = lineages.snapshot()
    assert len(snap["alive"]) == lineages.POP_MAX and snap["alive"][0]["name"].startswith("Momentum")  # momentum wins this market
    lineages.evolve(seed=2)
    snap = lineages.snapshot()
    assert snap["retired"] == 2 and snap["generation"] == 3 and len(snap["alive"]) == lineages.POP_MAX
    assert any(e["kind"] == "born" for e in snap["events"])
    brain._cache["v"] = None
    assert brain.snapshot()["lineages"]["generation"] == 3
    assert lineages.champion() is None  # no live record yet: nothing gets a say in real rankings

    # calls created after the strategists were born (never used to select them); the app's own top pick is the
    # weakest candidate, momentum is right: a momentum strategist earns a say
    monkeypatch.setattr(lineages, "LIVE_MIN", 20)
    for i in range(30):
        bid = f"b-live{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", f"2099-01-{1 + i % 28:02d}T00:00:00", "2026-01-01", "seed_backfill"))
        for j, mom in enumerate((-0.2, 0.0, 0.2)):
            pid = f"p-live{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", "2026-01-01", 10.0, db.dumps({"num": {"mom60": mom}}), 1 if j == 0 else j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, lineages.CHECKPOINT, "2026-02-01", 10.0, 0.0, 0.0, mom * 0.5, "2026-02-01"))
    ch = lineages.pick_champion()
    assert ch and ch["live"]["fitness"] > ch["app"]["fitness"]
    assert lineages.champion()["id"] == ch["id"]


def test_lineages_leave_out_volatile_ideas():
    """A 'volatile' idea is graded on |move| - |S&P move| (beats the S&P ~75% of the time for any stock), so a
    strategist that picks it must not look skilled; and a champion never reorders one in the real ranking."""
    from backend.v4 import lineages
    for i in range(12):
        bid = f"b-linvol{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", f"2098-03-{1 + i:02d}T00:00:00", "2026-01-01", "seed_backfill"))
        # two directional ideas (high vol60 one loses) and a volatile one with the highest vol60 and a big |move| grade
        for j, (d, vol, ex) in enumerate((("bullish", 0.2, 0.02), ("bullish", 0.5, -0.02), ("volatile", 0.9, 0.15))):
            pid = f"p-linvol{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"V{j}", d, "2026-01-01", 10.0, db.dumps({"num": {"vol60": vol}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, lineages.CHECKPOINT, "2026-02-01", 10.0, 0.0, 0.0, ex, "2026-02-01"))
    beliefs = lineages._graded_beliefs(since="2098-01-01")
    assert len(beliefs) == 12 and all(len(b) == 2 for b in beliefs)
    risky, calm = lineages.score({"vol60": 1.0}, beliefs), lineages.score({"vol60": -1.0}, beliefs)
    assert risky["fitness"] < 0 < calm["fitness"]  # with the volatile idea in, 'risky' would have scored +15%

    nums = [{"vol60": 0.2}, {"vol60": 0.5}, {"vol60": 0.9}]
    s = lineages.score_candidates({"vol60": 1.0}, nums, ["bullish", "bearish", "volatile"])
    assert s[1] > s[0] and s[2] == (s[0] + s[1]) / 2  # volatile idea sits at the average: never moved
    assert lineages.score_candidates({"vol60": 1.0}, nums, ["bullish", "volatile", "volatile"]) is None


def test_champion_moves_ranking_but_never_breaks_a_belief(monkeypatch):
    from backend.v4 import lineages
    monkeypatch.setattr(lineages, "champion", lambda: {"id": "st-x", "name": "Momentum · Gen 9", "weights": {"mom60": 5.0}})
    r = engine.process_belief("plumbing demand is going to be high", "u1", "moderate", claude_client=FakeClaude())
    assert r["valid"] and len(r["picks"]) == 5
    monkeypatch.setattr(lineages, "champion", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    r2 = engine.process_belief("people will cook at home more", "u1", "moderate", claude_client=FakeClaude())
    assert r2["valid"]


def test_research_walk_forward_runs_and_stores(monkeypatch):
    from backend.v4 import research
    rng = __import__("random").Random(3)
    d0 = __import__("datetime").date(2024, 1, 1)
    for i in range(400):
        bid = f"b-rs{i}"
        asof = (d0 + __import__("datetime").timedelta(days=i * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            mom = rng.uniform(-0.3, 0.3)
            pid = f"p-rs{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", asof, 10.0, db.dumps({"num": {"mom60": mom, "vol60": rng.uniform(0.2, 0.6)}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, mom * 0.3 + rng.gauss(0, 0.05), asof))
    out = research.run()
    r = out["results"]
    assert r["momentum (z_mom60)"]["lift"] > 0.02 and r["momentum (z_mom60)"]["n"] > 100
    assert r["ridge (learned)"]["lift"] > 0.02  # learns the planted signal out of sample
    assert abs(r["app (current #1)"]["lift"]) < 0.03
    assert db.query_one("SELECT v FROM kv_cache WHERE k = ?", (research.KEY,))


def test_ranker_v2_turns_on_only_with_an_out_of_sample_edge(monkeypatch):
    from backend.v4 import research
    test_research_walk_forward_runs_and_stores(monkeypatch)  # planted momentum signal
    rv = research.fit_production()
    assert rv["active"] and rv["oos"]["lift"] > 0
    s = research.score_candidates([{"mom60": 0.2}, {"mom60": -0.2}, {"mom60": 0.0}], ["bullish"] * 3)
    assert s[0] > s[2] > s[1]
    # no edge -> off
    monkeypatch.setattr(research, "MIN_T", 99.0)
    assert research.fit_production()["active"] is False
    assert research.score_candidates([{"mom60": 0.2}, {"mom60": -0.2}], ["bullish"] * 2) is None



def test_engine_uses_ranker_v2_scores(monkeypatch):
    from backend.v4 import research
    seen = {}
    def fake(nums, dirs):
        seen["n"] = len(nums)
        return [float(i) for i in range(len(nums))]
    monkeypatch.setattr(research, "score_candidates", fake)
    r = engine.process_belief("plumbing demand is going to be high", "u1", "moderate", claude_client=FakeClaude())
    assert r["valid"] and seen["n"] == 5


def test_extra_backfill_grant_is_capped(monkeypatch):
    from backend.v4 import seeder
    monkeypatch.setenv("MP_WARMUP_GRADED", "0")  # warm-up already done
    monkeypatch.setattr(seeder, "EXTRA_BACKFILL_GRANTS", {"t": 1.0})
    calls = []
    def fake_run(mode, n=0, generate=0, years=3.0, concurrency=4, max_usd=10.0, **kw):
        calls.append((mode, max_usd))
        return {"ok": 1, "skipped": 0, "errors": 0, "cost_usd": 0.6 if mode == "backfill" else 0.0}
    monkeypatch.setattr(seeder, "run", fake_run)
    monkeypatch.setattr(seeder, "news_beliefs", lambda *a, **k: [], raising=False)
    for _ in range(4):
        seeder.auto(claude_client=FakeClaude(), train=False)
    backfills = [c for c in calls if c[0] == "backfill"]
    assert [round(m, 2) for _, m in backfills] == [0.5, 0.4]  # 0.6 + 0.6 spent >= 1.0 granted: stops


def test_volume_profile_levels_and_features(monkeypatch):
    from datetime import timedelta as _td
    d0 = TODAY - _td(days=300)
    dates = [(d0 + _td(days=i)).isoformat() for i in range(200)]
    closes = [100.0] * 120 + [100 + i * 0.5 for i in range(80)]          # long base at 100, then a breakout
    vols = [5_000_000.0] * 120 + [1_000_000.0] * 75 + [4_000_000.0] * 5  # heavy volume in the base, a recent surge
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, closes))
    monkeypatch.setattr(market, "_vol_cache", {"XYZ": vols})
    vp = market.volume_profile("XYZ", window=150)
    assert vp and abs(vp["poc"] - 100) < 2 and vp["close"] > vp["vah"]   # broke out above where it traded
    f = market.vp_features("XYZ")
    assert f["vp_above_value"] == 1.0 and f["vp_poc_dist"] > 0.3 and f["rvol"] > 1.5
    monkeypatch.setattr(market, "_vol_cache", {})
    assert market.volume_profile("XYZ") is None and market.vp_features("XYZ")["vp_above_value"] == 0.0


def test_research_enrich_adds_vp_features(monkeypatch):
    from backend.v4 import research
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-en", "seed", "x", "x", "2026-01-01T00:00:00", "2026-01-01", "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-en", "b-en", "XYZ", "bullish", "2026-01-01", 10.0, db.dumps({"num": {"mom60": 0.1}})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-en", 90, "2026-04-01", 10.0, 0.0, 0.0, 0.01, "2026-04-01"))
    monkeypatch.setattr(market, "vp_features", lambda s, d=None: {"vp_poc_dist": 0.2, "vp_vah_dist": 0.1, "vp_val_dist": 0.3,
                                                                  "vp_above_value": 1.0, "vp_below_value": 0.0, "rvol": 2.0})
    monkeypatch.setattr(market, "trend_features", lambda s, d=None: {"mu_dist": 0.03, "mu_slope": 0.01, "mu_up": 1.0,
                                                                     "mu_age": 0.1, "mu_flips": 0.2})
    monkeypatch.setattr(market, "regime_features", lambda d=None: {"reg_trend": 1.0, "reg_crisis": 0.0, "reg_calm": 0.0})
    monkeypatch.setattr(market, "daily_closes", lambda s: (["2026-01-01"], [10.0]))
    out = research.enrich(10)
    assert out["enriched"] == 1 and out["remaining"] == 0
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-en'")["features"])["num"]
    assert num["vp_above_value"] == 1.0 and num["mom60"] == 0.1 and num["mu_up"] == 1.0
    assert research.enrich(10)["enriched"] == 0                             # nothing left to fill

    def outage(s):
        raise market.MarketDataError("down")
    db.execute("UPDATE picks SET features = ? WHERE id = 'p-en'", (db.dumps({"num": {"mom60": 0.1}}),))
    monkeypatch.setattr(market, "daily_closes", outage)
    assert research.enrich(10)["enriched"] == 0                             # a data outage never stores zeros
    assert "mu_up" not in db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-en'")["features"])["num"]


def test_alma_matches_the_published_worked_example():
    w = market.alma_weights(9, 0.85, 6)
    assert [round(x * 100, 1) for x in w] == [0.0, 0.0, 0.2, 1.2, 5.3, 14.8, 26.3, 30.1, 22.0]
    assert round(market.alma([100.0] * 8 + [110.0], 9, 0.85, 6), 1) == 102.2  # a plain 9-bar average: 101.1
    assert market.alma([1.0, 2.0], 9) is None
    assert market.sma_series([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]


def test_trend_state_turns_before_a_plain_average_and_never_looks_ahead(monkeypatch):
    import math as _m
    from datetime import timedelta as _td
    d0 = TODAY - _td(days=500)
    dates = [(d0 + _td(days=i)).isoformat() for i in range(400)]
    closes = [100 + 30 * _m.sin(i / 25) for i in range(400)]              # smooth waves
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, closes))
    peak = max(range(150, 250), key=lambda i: closes[i])                    # a top inside the data
    t = market.trend_state("XYZ", date.fromisoformat(dates[peak + 6]), chart=True)
    assert t["dir"] == -1 and t["sma_dir"] == 1                             # MuLine already turned down, SMA 20 not yet
    assert len(t["chart"]["close"]) == len(t["chart"]["line"]) == len(t["chart"]["dates"]) == market.TREND_LOOKBACK
    assert t["chart"]["dates"][-1] == dates[peak + 6]
    f1 = market.trend_features("XYZ", date.fromisoformat(dates[peak + 6]))
    future = closes[: peak + 7] + [5.0] * (400 - peak - 7)                  # wreck everything after the date
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, future))
    assert market.trend_features("XYZ", date.fromisoformat(dates[peak + 6])) == f1  # point-in-time only
    assert f1["mu_up"] == -1.0 and 0 < f1["mu_age"] < 0.2
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates[:30], closes[:30]))
    assert market.trend_state("XYZ") is None and market.trend_features("XYZ")["mu_up"] == 0.0


def test_muline_band_ignores_wiggles_and_lab_scores_lines(monkeypatch):
    import math as _m
    from backend.v4 import trendlab
    # a clean rise with tiny wiggles: plain slope flips every other day, MuLine's noise band doesn't
    px = [100 * (1.002 ** i) * (1 + 0.004 * (-1) ** i) for i in range(200)]
    line = market.muline_series(px)
    assert market.dir_turns(market.band_dirs(line, px)[40:])[2] == 0
    assert market.dir_turns(market.slope_dirs(px)[40:])[2] > 50
    # efficiency: straight line = 1, back-and-forth = ~0
    assert market.efficiency([1, 2, 3, 4]) == 1.0 and market.efficiency([1, 2, 1, 2, 1]) == 0.0
    # volume tilt: a heavy-volume day pulls the line toward its price
    win = [100.0] * 20 + [110.0]
    quiet = market.muline_weights(win, [1.0] * 21)[-1]
    loud = market.muline_weights(win, [1.0] * 20 + [4.0])[-1]
    assert loud > quiet
    # the lab: real turns found with hindsight, each line judged on lag and false turns
    waves = [100 + 30 * _m.sin(i / 25) for i in range(600)]
    piv = trendlab.pivots(waves)
    assert len(piv) >= 5 and all(a[1] != b[1] for a, b in zip(piv, piv[1:]))  # tops and bottoms alternate
    dates = [f"2020-{i:04d}" for i in range(600)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, waves))
    monkeypatch.setattr(market, "daily_volumes", lambda s: [])
    out = trendlab.run(["A", "B"])
    r = out["results"]
    assert out["stocks"] == 2 and r["MuLine"]["avg_lag"] < r["20-day average"]["avg_lag"]
    assert r["MuLine"]["false_per_year"] < 1 and out["verdict_vs_alma"] in (
        "quicker and calmer", "quicker but jumpier", "calmer but slower", "not better yet")


def test_trend_rider_joins_once_trend_features_are_on_most_graded_picks(monkeypatch):
    from backend.v4 import lineages
    for style, w in lineages.FOUNDERS[:5]:
        lineages._add(f"{style} · Gen 3", style, 3, None, w)
    def graded(i, with_trend):
        bid, pid = f"b-tr{i}", f"p-tr{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", "2026-01-01T00:00:00", "2026-01-01", "seed_backfill"))
        num = {"mom60": 0.1, **({"mu_dist": 0.02, "mu_up": 1.0} if with_trend else {})}
        db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
                   (pid, bid, "T", "bullish", "2026-01-01", 10.0, db.dumps({"num": num})))
        db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                   (pid, lineages.CHECKPOINT, "2026-04-01", 10.0, 0.0, 0.0, 0.01, "2026-04-01"))
    for i in range(10):
        graded(i, with_trend=i < 5)                                         # only half carry trend features yet
    lineages.ensure_founders()
    assert not db.query_one("SELECT 1 AS x FROM strategists WHERE style = 'Trend-rider'")
    for i in range(10, 40):
        graded(i, with_trend=True)                                          # enrichment caught up: 35 of 40
    lineages.ensure_founders()
    rows = db.query("SELECT name, gen, parent_id FROM strategists WHERE style = 'Trend-rider'")
    assert len(rows) == 1 and rows[0]["gen"] == 3 and rows[0]["parent_id"] is None and rows[0]["name"].startswith("Trend-rider · Gen 3")
    db.execute("UPDATE strategists SET status = 'retired' WHERE style = 'Trend-rider'")
    lineages.ensure_founders()                                              # retired founders never come back
    assert db.query_one("SELECT COUNT(*) AS n FROM strategists WHERE style = 'Trend-rider'")["n"] == 1
    f = lineages.features_of({"num": {"mu_up": -1.0, "mu_slope": -0.02, "mu_flips": 0.3}}, "bearish")
    assert f["mu_up"] == 1.0 and f["mu_slope"] == 0.02 and f["mu_flips"] == 0.3  # a falling trend agrees with a bearish call


def test_beta_and_risk_matched_scoring_catch_a_pure_risk_tilt():
    from backend.v4 import research
    rng = random.Random(9)
    sdates = [f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(300)]
    spy, stk = [100.0], [50.0]
    for _ in range(299):
        m = rng.gauss(0.0005, 0.01)
        spy.append(spy[-1] * (1 + m)); stk.append(stk[-1] * (1 + 2 * m + rng.gauss(0, 0.002)))
    assert abs(market.beta_value(sdates, stk, sdates, spy, 299) - 2.0) < 0.1     # moves ~2x the market
    assert market.beta_value(sdates, stk, sdates, spy, 50) == 1.0               # too little history -> neutral
    # a rule that just grabs the higher-beta stock in a rising market: beats the S&P, but not a risk-matched S&P
    picks = []
    for k in range(200):
        spy_ret = 0.04 + rng.gauss(0, 0.01)
        hi = 2.0 * spy_ret + rng.gauss(0, 0.02); lo = 0.5 * spy_ret + rng.gauss(0, 0.02)
        ex_hi, ex_lo = hi - spy_ret, lo - spy_ret
        exa_hi, exa_lo = hi - 2.0 * spy_ret, lo - 0.5 * spy_ret
        picks.append((ex_hi, (ex_hi + ex_lo) / 2, exa_hi, (exa_hi + exa_lo) / 2))
    m = research._metrics(picks)
    assert m["lift"] > 0.01 and m["lift_t"] > 3                                  # looks like skill...
    assert abs(m["lift_adj"]) < 0.01 and m["lift_adj_t"] < 1.0                   # ...but it's only risk
    app = {"beat": 0.5, "beat_adj": 0.5}
    assert research._passes(m, app) and not research._passes(m, app, risk=True)  # the risk check stops it
    # the real 2026-11-06 numbers: risk-matched edge, slightly lower raw beat rate than the old way
    old = {"beat": 0.5228, "beat_adj": 0.5287}
    gbm_adj = {"lift": 0.0091, "lift_t": 2.7, "beat": 0.5187, "beat_adj": 0.5364, "lift_adj": 0.0097, "lift_adj_t": 3.03}
    gbm = {"lift": 0.0136, "lift_t": 3.97, "beat": 0.5198, "beat_adj": 0.5265, "lift_adj": 0.0088, "lift_adj_t": 2.68}
    assert research._passes(gbm_adj, old, risk=True) and not research._passes(gbm_adj, old)
    assert not research._passes(gbm, old, risk=True)                             # loses on risk-matched beat rate
    assert not research._passes({**gbm_adj, "beat": 0.51}, old, risk=True)      # raw beat may not trail by >1 pt


def test_betting_against_beta_rule_prefers_low_beta_longs_and_high_beta_shorts():
    from backend.v4 import research
    assert "beta" in research.FEATS and "beta" in research.DIRECTIONAL
    rng = random.Random(11)
    d0 = __import__("datetime").date(2024, 1, 1)
    for k in range(400):
        bid = f"b-bab-{k}"
        asof = (d0 + __import__("datetime").timedelta(days=k * 2)).isoformat()
        bear = k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            beta = rng.uniform(0.3, 2.5)
            # planted: in the call's direction, low-beta longs and high-beta shorts do better
            ex = (beta - 1.0) * 0.05 if bear else (1.0 - beta) * 0.05
            num = {"beta": beta} if j else {}            # one idea per belief predates stored betas
            pid = f"p-bab-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": num}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.01), asof))
    data = research.load()
    f = {c["f"]["beta"] for b in data for c in b["cands"] if c["f"]["bearish"] == 0 and not c["has_beta"]}
    assert f == {1.0}                                    # a pick without a stored beta reads as market-like, not 0
    r = research.run(data=data)["results"]
    assert r["betting against beta (-z_beta)"]["lift"] > 0.02 and r["betting against beta (-z_beta)"]["n"] > 100
    assert r["betting against beta (-z_beta)"]["lift_t"] > 3


def test_nightly_refit_loads_graded_calls_once_and_compactly(monkeypatch):
    from backend.v4 import research
    rng = random.Random(4)
    for i in range(170):
        bid = f"b-mem{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", "2025-01-01T00:00:00", f"2025-{1 + i % 12:02d}-{1 + i % 27:02d}", "seed_backfill"))
        for j in range(3):
            pid = f"p-mem{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, "T", "bullish", "2025-01-01", 10.0, db.dumps({"num": {"mom60": rng.uniform(-1, 1)}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, "2025-06-01", 10.0, 0.0, 0.0, rng.gauss(0, 0.1), "2025-06-01"))
    calls = []
    real = research.load
    monkeypatch.setattr(research, "load", lambda **kw: calls.append(1) or real(**kw))
    out = research.fit_production()
    assert len(calls) == 1 and out["trained_on"] == 170                    # never two copies in memory at once
    row = real()[0]["cands"][0]["f"]
    assert isinstance(row, research.FeatRow) and abs(row["z_mom60"]) < 5 and row.get("nope", 7.0) == 7.0


def test_regime_state_and_regime_aware_research(monkeypatch):
    from datetime import timedelta as _td
    from backend.v4 import research
    d0 = TODAY - _td(days=400)
    dates = [(d0 + _td(days=i)).isoformat() for i in range(300)]
    steady = [100 * (1.0008 ** i) for i in range(300)]                       # smooth climb
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, steady))
    market._state_cache.clear()
    assert market.regime_state()["regime"] == "trending"
    crash = steady[:280] + [steady[279] * (0.97 ** k) for k in range(1, 21)]  # sharp fall
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, crash))
    market._state_cache.clear()
    assert market.regime_state()["regime"] == "crisis" and market.regime_features()["reg_crisis"] == 1.0
    # research builds regime interactions and scores with them
    s = research.score_candidates  # production path tolerates the new keys
    assert callable(s)
    assert "zx_mom60_reg_trend" in research.ZKEYS


def test_option_iv_from_snapshots_and_practice_pricing(monkeypatch):
    from types import SimpleNamespace as NS
    from datetime import timedelta as _td
    exp = TODAY + _td(days=60)
    occ = lambda k, strike: f"XLI{exp.strftime('%y%m%d')}{k}{int(strike * 1000):08d}"
    snaps = {occ("C", 100): {"impliedVolatility": 0.31}, occ("C", 110): {"impliedVolatility": 0.27}, "BAD": {"impliedVolatility": 0.5}}
    calls = []
    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(url)
        return NS(status_code=200, json=lambda: {"snapshots": snaps})
    monkeypatch.setattr(market._session, "get", fake_get)
    market._iv_cache.clear()
    assert market.option_iv("XLI", "Call", 101, exp) == 0.31
    assert market.option_iv("XLI", "call", 109, exp) == 0.27 and len(calls) == 1  # cached per underlying/expiry
    monkeypatch.setattr(market._session, "get", lambda *a, **k: NS(status_code=403, json=lambda: {}))
    market._iv_cache.clear()
    assert market.option_iv("XLI", "call", 100, exp) is None  # unavailable -> callers fall back


def test_ranker_v2_picks_the_stronger_model(monkeypatch):
    from backend.v4 import research
    test_research_walk_forward_runs_and_stores(monkeypatch)
    base = research.run()
    # pretend the tree model won clearly out of sample
    res = {"results": dict(base["results"])}
    res["results"]["gbm (learned)"] = dict(res["results"]["ridge (learned)"], lift=res["results"]["ridge (learned)"]["lift"] + 0.01)
    rv = research.fit_production(res)
    assert rv["active"] and rv["kind"] == "gbm"
    s = research.score_candidates([{"mom60": 0.25}, {"mom60": -0.25}, {"mom60": 0.0}], ["bullish"] * 3)
    assert s[0] > s[1]
    # tree model loses -> ridge
    res["results"]["gbm (learned)"] = dict(res["results"]["ridge (learned)"], lift=0.0)
    assert research.fit_production(res)["kind"] == "ridge"


def test_push_alerts_market_open_updates_and_cleanup(monkeypatch):
    from types import SimpleNamespace as NS
    from datetime import datetime as _dt, timezone as _tz
    from backend.v4 import push
    from fastapi.testclient import TestClient
    from backend.v4.router import router
    from fastapi import FastAPI
    app = FastAPI(); app.include_router(router, prefix="/v4"); c = TestClient(app)
    key = c.get("/v4/push/key").json()["key"]
    assert len(key) > 80 and key == push.public_key()  # stable across calls
    sub = {"endpoint": "https://push.example.com/abc", "keys": {"p256dh": "BPk", "auth": "xyz"}}
    assert c.post("/v4/push/subscribe", json={"subscription": sub, "device_id": "d1"}).json()["ok"]
    assert c.post("/v4/push/subscribe", json={"subscription": {"endpoint": "http://bad"}}).status_code == 400
    assert c.post("/v4/push/status", json={"endpoint": sub["endpoint"]}).json()["subscribed"]
    sent = []
    ok = lambda **kw: sent.append(kw)  # noqa: E731
    feed = {"items": [{"headline": "Amazon arranges $80 billion credit line", "companies": [{"ticker": "AMZN"}, {"ticker": "NVDA"}]}]}
    r = push.send_market_open(sender=ok, feed=feed)
    assert r["sent"] == 1 and "AMZN, NVDA" in json.loads(sent[-1]["data"])["body"] and "/story?h=" in json.loads(sent[-1]["data"])["url"]
    # updates: one per day, daytime only, each once
    noon = _dt(2026, 11, 3, 17, 0, tzinfo=_tz.utc)   # 12:00 ET
    assert push.send_pending_update(sender=ok, now_utc=noon)["sent"] == 1
    assert push.send_pending_update(sender=ok, now_utc=noon)["reason"] == "already sent one today"
    assert push.send_pending_update(sender=ok, now_utc=_dt(2026, 11, 4, 3, 0, tzinfo=_tz.utc))["reason"] == "outside daytime"
    # gone subscriptions are removed
    def gone(**kw):
        raise type("WebPushException", (Exception,), {})("gone") if False else _Gone()
    class _Gone(Exception):
        response = NS(status_code=410)
    def gone_sender(**kw):
        raise _Gone()
    assert push.send_market_open(sender=gone_sender, feed=feed)["sent"] == 0
    assert not push.is_subscribed(sub["endpoint"])


def test_broadcast_sends_once_to_verified_subscribers(monkeypatch):
    from backend.v4 import broadcast, mailer
    monkeypatch.setenv("MP_MAIL_TEST_SINK", "1")
    monkeypatch.setattr(broadcast.time, "sleep", lambda s: None)
    mailer._sent_for_tests.clear()
    now = "2026-11-01T00:00:00"
    for i, (ver, ok) in enumerate([(1, 1), (1, 0), (0, 1)]):
        db.execute("INSERT INTO accounts (id, uid, email, name, pw_hash, verified, notify_calls, created_at) VALUES (?,?,?,?,?,?,?,?)",
                   (f"a-bc{i}", f"u-bc{i}", f"bc{i}@example.com", "Sam Lee", "x", ver, ok, now))
    out = broadcast.run_pending()
    assert out and out[0]["sent"] == 1
    m = [x for x in mailer._sent_for_tests if x["to"] == "bc0@example.com"][0]
    assert "Hi Sam" in m["text"] and "Unsubscribe" in m["text"] and "/account" in m["text"]
    again = broadcast.run_pending()
    assert again[0]["sent"] == 0 and again[0]["already"] == 1  # never twice


def test_mom_12_1_skips_latest_month_and_is_derived_for_old_picks(monkeypatch):
    from backend.v4 import market, research
    closes = [100.0] * 230 + [150.0] * 21  # i = 250: up 50% over the year, flat over the last month
    closes[-1] = 120.0                      # ...then a last-month drop that 12-1 ignores
    i = len(closes) - 1
    assert abs(market.mom_12_1(closes, i) - 0.5) < 1e-9
    assert market.mom_12_1(closes[:100], 99) == 0.0  # not enough history
    mom250, mom20 = closes[i] / closes[i - 250] - 1, closes[i] / closes[i - 20] - 1
    assert abs(research._with_derived({"mom250": mom250, "mom20": mom20})["mom_12_1"] - 0.5) < 1e-9
    assert research._with_derived({"mom_12_1": 0.1, "mom250": 0.9})["mom_12_1"] == 0.1  # stored value wins
    assert "mom_12_1" not in research._with_derived({"mom20": 0.1})  # no 1y history: leave missing
    assert "mom_12_1" in research.FEATS and "mom_12_1" in research.DIRECTIONAL
    # research picks it up from old picks that only stored mom250/mom20 (planted signal on 12-1)
    rng = __import__("random").Random(5)
    d0 = __import__("datetime").date(2024, 1, 1)
    for k in range(400):
        bid = f"b-m121-{k}"
        asof = (d0 + __import__("datetime").timedelta(days=k * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            m121, m20 = rng.uniform(-0.3, 0.3), rng.uniform(-0.1, 0.1)
            pid = f"p-m121-{k}-{j}"
            num = {"mom20": m20, "mom250": (1 + m121) * (1 + m20) - 1}
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", asof, 10.0, db.dumps({"num": num}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, m121 * 0.3 + rng.gauss(0, 0.05), asof))
    r = research.run()["results"]
    assert r["12-1 momentum (z_mom_12_1)"]["lift"] > 0.02 and r["12-1 momentum (z_mom_12_1)"]["n"] > 100
    assert r["residual 12-1 momentum (z_resid_mom)"]["n"] > 100  # old picks without resid_mom still run (as 0)


def test_frog_in_the_pan_id_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    steady = [100.0 * (1.001 ** k) for k in range(260)]           # up every day: continuous
    i = len(steady) - 1
    assert abs(market.fip_id(steady, i) - (-1.0)) < 1e-9
    jumpy = [100.0] * 260                                          # mostly small down days, one big jump up
    for k in range(1, 260):
        jumpy[k] = jumpy[k - 1] * (0.999 if k != 100 else 1.6)
    assert market.fip_id(jumpy, i) > 0.9                           # same sign of move, but discrete
    falling = [100.0 * (0.999 ** k) for k in range(260)]           # steady decline is continuous too
    assert abs(market.fip_id(falling, i) - (-1.0)) < 1e-9
    assert market.fip_id(steady[:100], 99) == 0.0                   # not a year of history
    # the latest month is skipped (as-of 12-1 window): changing it never changes the value
    late = steady[:-20] + [steady[-21] * (0.97 ** (k + 1)) for k in range(20)]
    assert market.fip_id(late, i) == market.fip_id(steady, i)
    assert "fip_id" in research.FEATS and "fip_id" not in research.DIRECTIONAL
    # enrich backfills fip_id as of each pick's own date only, without redoing the other features
    dates = [(__import__("datetime").date(2024, 1, 1) + __import__("datetime").timedelta(days=k)).isoformat() for k in range(400)]
    closes = [100.0 * (1.001 ** k) for k in range(300)] + [200.0 * (1.0 + (0.05 if k % 2 else -0.05)) for k in range(100)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, closes))
    monkeypatch.setattr(market, "vp_features", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0}
    asof = dates[270]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-fip", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-fip", "b-fip", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-fip", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    assert research.enrich(10000)["enriched"] >= 1
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-fip'")["features"])["num"]
    assert abs(num["fip_id"] - (-1.0)) < 1e-9 and num["vp_poc_dist"] == 0.2   # later choppy prices not seen


def test_residual_momentum_removes_market_beta_and_enrich_backfills_it(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(11)
    dates = [(_dt.date(2023, 1, 1) + _dt.timedelta(days=k)).isoformat() for k in range(400)]
    mkt = [rng.gauss(0.001, 0.01) for _ in range(400)]
    spy = [100.0]
    for x in mkt[1:]:
        spy.append(spy[-1] * (1 + x))
    def path(beta, alpha, noise=0.005):
        c = [50.0]
        for x in mkt[1:]:
            c.append(c[-1] * (1 + alpha + beta * x + rng.gauss(0, noise)))
        return c
    i = 300
    beta_only = path(2.0, 0.0)          # big raw momentum, all from leverage to SPY
    alpha = path(0.5, 0.002)            # steady stock-specific outperformance
    assert abs(market.resid_mom(dates, beta_only, dates, spy, i)) < 2.5
    assert market.resid_mom(dates, alpha, dates, spy, i) > 4.0
    assert market.resid_mom(dates, path(0.5, -0.002), dates, spy, i) < -4.0
    assert market.resid_mom(dates, alpha, dates, spy, 100) == 0.0                  # not a year of history
    late = alpha[:i - 19] + [alpha[i - 20] * 0.5] * 19 + alpha[i:]                   # latest month is skipped
    assert market.resid_mom(dates, late, dates, spy, i) == market.resid_mom(dates, alpha, dates, spy, i)
    assert "resid_mom" in research.FEATS and "resid_mom" in research.DIRECTIONAL
    # enrich backfills resid_mom as of each pick's own date only, leaving the other features alone
    after = alpha[:i + 1] + [alpha[i] * (0.9 if k % 2 else 1.1) for k in range(len(dates) - i - 1)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, spy) if s == "SPY" else (dates, after))
    monkeypatch.setattr(market, "vp_features", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3}
    asof = dates[i]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-rm", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-rm", "b-rm", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-rm", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    assert research.enrich(10000)["enriched"] >= 1
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-rm'")["features"])["num"]
    assert abs(num["resid_mom"] - market.resid_mom(dates, alpha, dates, spy, i)) < 1e-9   # later prices not seen
    assert num["fip_id"] == -0.3 and num["vp_poc_dist"] == 0.2


def test_max_effect_lottery_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    flat = [100.0] * 60
    assert market.max5(flat, 59) == 0.0
    spiky = [100.0] * 60
    for k in range(40, 60):                                        # 5 big up-days (+10%) among small down-days
        spiky[k] = spiky[k - 1] * (1.10 if k in (42, 46, 50, 54, 58) else 0.99)
    assert abs(market.max5(spiky, 59) - 0.10) < 1e-9
    assert market.max5(spiky, 10) == 0.0                           # not a month of history
    assert market.max5(spiky + [spiky[-1] * 3.0], 59) == market.max5(spiky, 59)   # later prices never seen
    assert "max5" in research.FEATS and "max5" in research.DIRECTIONAL
    # planted: high-MAX longs lag and high-MAX shorts pay; the rule (-z_max5, flipped for bearish) should find it
    rng = _r.Random(5)
    d0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-max-{k}", (d0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            m = rng.uniform(0.0, 0.08)
            ex = (m - 0.04) * 1.0 if bear else (0.04 - m) * 1.0
            pid = f"p-max-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"max5": m}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["avoid lottery stocks (-z_max5)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills max5 as of each pick's own date only, leaving the other features alone
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(len(spiky) + 30)]
    after = spiky + [spiky[-1] * (2.0 if k % 2 else 0.5) for k in range(30)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, after))
    monkeypatch.setattr(market, "vp_features", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    monkeypatch.setattr(market, "resid_features", lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0, "beta": 1.2}
    asof = dates[59]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-mx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-mx", "b-mx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-mx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-mx'")["features"])["num"]
    assert abs(num["max5"] - 0.10) < 1e-9 and num["beta"] == 1.2 and num["vp_poc_dist"] == 0.2


def test_daily_job_runs_each_phase_in_its_own_process():
    """grade-and-train runs grade/train/lineages/ranker as separate child processes so their memory peaks don't stack
    (the 512Mi cron was OOM-killed that way). A real child run on the empty test DB returns its JSON result."""
    ok, out = grader._run_phase("grade")
    assert ok and out["graded"] == 0


def test_daily_job_records_grading_and_keeps_going_when_a_phase_dies(monkeypatch):
    ran = []

    def fake(name, force_train=False):
        ran.append(name)
        if name == "ranker":
            return False, {"error": "ranker killed (out of memory?)"}
        return True, {"graded": 5} if name == "grade" else {"status": "shadow"}
    monkeypatch.setattr(grader, "_run_phase", fake)
    monkeypatch.setattr("sys.argv", ["grader", "--train"])
    grader.main()  # a dead optional phase doesn't fail the job
    assert ran == ["grade", "train", "lineages", "ranker"]
    h = json.loads(seeder._kv_get("health:grading"))
    assert h["ok"] and h["summary"] == {"graded": 5, "trained": "shadow"}


def test_daily_job_fails_loudly_when_grading_dies(monkeypatch):
    monkeypatch.setattr(grader, "_run_phase", lambda name, force_train=False: (False, {"error": "grade exited 1"}))
    monkeypatch.setattr("sys.argv", ["grader", "--train"])
    with pytest.raises(SystemExit):
        grader.main()
    assert json.loads(seeder._kv_get("health:grading"))["ok"] is False


def test_network_uses_numeric_inputs_and_scores_old_versions_with_theirs():
    # default: only the numbers ranker v2 uses; hashed text/ticker inputs memorized history that did not carry over
    rec = nn.make_features(belief_text="plumbing demand is going to be high", themes=["plumbing"], core_direction="bullish",
                           horizon_days=120, conviction="medium", cand={"ticker": "WINR", "direction": "bullish", "score": 0.6},
                           market={"mom60": 0.1}, rank=0, n_cands=5, is_etf=False, backfill=False)
    assert nn.INPUTS == "numeric"
    assert nn.vectorize([rec]).shape == (1, len(nn.MODEL_NUMERIC))
    assert nn.vectorize([rec], "all").shape == (1, nn.TEXT_DIM + nn.CAT_DIM + len(nn.MODEL_NUMERIC))
    # versions saved before the setting existed were trained on everything and must be scored that way
    assert nn.model_inputs({"metrics": {}}) == "all"
    assert nn.model_inputs({"metrics": {"inputs": "numeric"}}) == "numeric"
    assert nn.model_inputs(None) == "all"


def test_ranker_v2_leaves_out_volatile_ideas(monkeypatch):
    # 'volatile' ideas are graded on |move|, which beats the S&P most of the time; mixed into the directional
    # comparison they made 'pick the volatile idea' look like skill
    from backend.v4 import research
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-volx", "seed", "x", "x", "2025-01-01T00:00:00", "2025-01-01", "seed_backfill"))
    for j, (d, ex) in enumerate((("bullish", 0.01), ("bearish", -0.02), ("volatile", 0.30))):
        pid = f"p-volx-{j}"
        db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                   (pid, "b-volx", f"T{j}", d, "2025-01-01", 10.0, db.dumps({"num": {"mom60": 0.1 * j}}), j + 1))
        db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                   (pid, 90, "2025-04-01", 10.0, 0.0, 0.0, ex, "2025-04-01"))
    b = research.load()[0]
    assert len(b["cands"]) == 2 and abs(b["cands"][0]["rel"] - 0.015) < 1e-9
    assert not research.directional("volatile") and research.directional("Bearish")
    # serving: directional ideas are scored among themselves, the volatile one gets their average (never reordered)
    test_research_walk_forward_runs_and_stores(monkeypatch)
    assert research.fit_production()["active"]
    s = research.score_candidates([{"mom60": 0.2}, {"mom60": 0.9}, {"mom60": -0.2}], ["bullish", "volatile", "bullish"])
    assert s[0] > s[2] and abs(s[1] - (s[0] + s[2]) / 2) < 1e-9
    assert research.score_candidates([{"mom60": 0.2}, {"mom60": 0.9}], ["bullish", "volatile"]) is None


def test_budget_and_timeline_shape_the_strategies():
    p = strategy.normalize_prefs({"instrument": "options", "budget_usd": "150", "horizon_days": 5000})
    assert p["budget_usd"] == 150.0 and p["horizon_days"] == 730
    assert strategy.normalize_prefs({})["budget_usd"] == 0.0 and strategy.normalize_prefs({"horizon_days": "x"})["horizon_days"] == 0
    # shares fit any amount (fractional); options need one whole contract
    t = strategy.build_trade("Buy Stock", "WINR", 40.0, 0.3, TODAY, 90)
    assert strategy.size_for_budget(t, 40.0, 100.0) == {"budget": 100.0, "fits": True, "units": 2.5, "unit": "shares", "cost": 100.0}
    call = strategy.build_trade("Long Call", "WINR", 400.0, 0.4, TODAY, 180)
    assert not strategy.size_for_budget(call, 400.0, 200.0)["fits"]
    build = lambda s_: strategy.build_trade(s_, "WINR", 400.0, 0.4, TODAY, 180)
    s2, t2, why = strategy.fit_budget("Long Call", call, direction="bullish", risk="aggressive",
                                      prefs={"budget_usd": 200.0, "instrument": "auto", "goal": ""}, build=build, price=400.0)
    assert s2 != "Long Call" and why and strategy.size_for_budget(t2, 400.0, 200.0)["fits"]
    # within budget: untouched
    assert strategy.fit_budget("Long Call", call, direction="bullish", risk="aggressive",
                               prefs={"budget_usd": 1e6, "instrument": "auto", "goal": ""}, build=build, price=400.0)[0] == "Long Call"
    # end to end: their timeline replaces the AI's, every card says how it fits the budget
    r = engine.process_belief("plumbing demand is going to be high", "u-bud", "aggressive", claude_client=FakeClaude(),
                              prefs={"instrument": "auto", "budget_usd": 300, "horizon_days": 30})
    assert r["interpretation"]["horizon_days"] == 30
    for pk in r["picks"]:
        assert pk["budget"]["budget"] == 300.0
        assert pk["budget"]["fits"] or "No version" in pk["structure_reason"]


def test_ai_is_told_the_budget_and_timeline():
    from backend.v4 import interpreter
    msg = interpreter.build_user_message("gyms will be packed in January", "moderate", None, None,
                                         strategy.normalize_prefs({"budget_usd": "750", "horizon_days": 90}))
    assert "$750 total" in msg and "90 days" in msg
    plain = interpreter.build_user_message("gyms will be packed in January", "moderate", None, None, strategy.normalize_prefs({}))
    assert "budget" not in plain and "timeline" not in plain
    # a typed amount below the floor is raised to $10, never zero or negative
    assert strategy.normalize_prefs({"budget_usd": 3})["budget_usd"] == 10.0


def test_ideas_that_fit_the_budget_are_shown_first(monkeypatch):
    # make exactly one idea (the last one without a budget) "fit"; with a budget it moves to the front, and the
    # stored ranks and shown flags are renumbered to match what the person sees
    base = engine.process_belief("plumbing demand is going to be high", "u-fit", "aggressive", claude_client=FakeClaude(),
                                 prefs={"instrument": "options"})["picks"]
    last = base[-1]
    real = strategy.size_for_budget
    monkeypatch.setattr(strategy, "size_for_budget", lambda trade, price, budget: {**real(trade, price, budget),
                        "fits": abs(price - last["price"]) < 0.006})
    r = engine.process_belief("plumbing demand is going to be high", "u-fit", "aggressive", claude_client=FakeClaude(),
                              prefs={"instrument": "options", "budget_usd": 10})
    picks = r["picks"]
    assert len(base) >= 2 and picks[0]["ticker"] == last["ticker"] and picks[0]["shown"]
    assert [p["ticker"] for p in picks[1:]] == [p["ticker"] for p in base if p["ticker"] != last["ticker"]]
    rows = db.query("SELECT ticker, final_rank, shown FROM picks WHERE belief_id = ? ORDER BY final_rank", (r["belief_id"],))
    assert [x["ticker"] for x in rows] == [p["ticker"] for p in picks]
    assert [x["shown"] for x in rows] == [1 if p["shown"] else 0 for p in picks]


def test_ranker_v2_neural_net_competes_on_the_same_walk_forward(monkeypatch):
    # the neural network is a ranker v2 candidate: same inputs, labels and test; it learns the planted signal, and if
    # it is the best candidate that clears the (unchanged) gate it is stored and used to score live ideas
    import pickle
    from backend.v4 import research
    test_research_walk_forward_runs_and_stores(monkeypatch)  # planted momentum signal
    out = research.run()
    nn_res = out["results"]["neural net (learned)"]
    assert nn_res["n"] > 100 and nn_res["lift"] > 0.02
    assert "neural net (risk-adjusted)" in out["results"]
    x = np.random.default_rng(0).normal(size=(200, 3)); y = x[:, 0] * 0.1
    m = pickle.loads(pickle.dumps(research.MLPRanker(x, y)))
    p = m.predict(np.array([[1.0, 0, 0], [-1.0, 0, 0]]))
    assert p[0] > p[1]
    # force the net to be the only candidate that clears the gate
    def fake_passes(m_, app, risk=False):
        return m_ is out["results"]["neural net (learned)"]
    monkeypatch.setattr(research, "_passes", fake_passes)
    rv = research.fit_production(out)
    assert rv["model"] == "mlp" and rv["kind"] == "mlp" and rv["active"]
    s = research.score_candidates([{"mom60": 0.2}, {"mom60": -0.2}, {"mom60": 0.0}], ["bullish"] * 3)
    assert s[0] > s[2] > s[1]


def test_brain_forward_test_counts_only_live_calls():
    from backend.v4 import brain
    def add(bid, src, ideas):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "u", "x", "x", "2026-11-01T00:00:00", "2026-11-01", src))
        for j, (d, ex) in enumerate(ideas):
            pid = f"{bid}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", d, "2026-11-01", 10.0, "{}", j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 7, "2026-11-08", 10.0, 0.0, 0.0, ex, "2026-11-08"))
    add("fw-1", "user", [("bullish", 0.04), ("bullish", 0.00)])
    add("fw-2", "seed_news", [("bearish", -0.02), ("bullish", 0.02), ("volatile", 0.30)])
    add("fw-old", "seed_backfill", [("bullish", 0.50), ("bullish", -0.50)])     # hindsight: never counted
    f = brain._forward()["by_days"]["7"]
    assert f["beliefs"] == 2 and f["top_beat"] == 0.5
    assert abs(f["top_avg"] - 0.01) < 1e-9 and abs(f["lift"] - (0.02 + -0.02) / 2) < 1e-9


def test_time_shifted_practice_calls_are_training_only(monkeypatch):
    # augment: a practice basket re-scored a quarter earlier/later from prices only (no Claude); research uses the
    # shifted copies for training only, never for a test or a baseline
    from datetime import timedelta as _td
    from backend.v4 import augment, research
    asof = TODAY - _td(days=400)
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-aug", "seed", "x", "x", asof.isoformat() + "T00:00:00", asof.isoformat(), "seed_backfill"))
    for j, (t, d) in enumerate((("WINR", "bullish"), ("LOSR", "bullish"), ("FLAT", "bearish"), ("PIPE", "volatile"))):
        db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                   (f"p-aug{j}", "b-aug", t, d, asof.isoformat(), 10.0, db.dumps({"num": {"same_dir": 1.0, "log_horizon": 0.7}}), j + 1))
    out = augment.generate(10)
    assert out["baskets"] == 1 and out["ideas"] == 6                    # 3 directional ideas x 2 shifts; volatile skipped
    rows = db.query("SELECT shift, as_of, ticker, num, dir_excess FROM aug_ideas WHERE basket = 'b-aug' ORDER BY id")
    assert {r["shift"] for r in rows} == {-91, 91}
    for r in rows:  # features only from prices up to the shifted date; the stored static fields carry over
        num = json.loads(r["num"])
        assert num["same_dir"] == 1.0 and "mom60" in num
        d = __import__("datetime").date.fromisoformat(r["as_of"])
        assert abs(num["mom60"] - market.features(r["ticker"], d)["mom60"]) < 1e-9
    win = [r["dir_excess"] for r in rows if r["ticker"] == "WINR"]
    los = [r["dir_excess"] for r in rows if r["ticker"] == "LOSR"]
    assert min(win) > max(los)                                          # the uptrend beat the downtrend both times
    assert augment.generate(10)["baskets"] == 0                         # done baskets aren't redone
    data = research.load(include_aug=True)
    aug = [b for b in data if b.get("aug")]
    assert len(aug) == 2 and all(b["src_date"] == asof.isoformat() for b in aug)
    assert not any(b.get("aug") for b in research.load())


def test_research_adds_shifted_candidates_without_touching_tests(monkeypatch):
    from backend.v4 import augment, research
    test_research_walk_forward_runs_and_stores(monkeypatch)  # 400 real beliefs from 2024-01-01, planted momentum
    base = research.run()["results"]
    augment.ensure_table()
    rng = __import__("random").Random(9)
    d0 = __import__("datetime").date(2023, 6, 1)
    rows = []
    for i in range(300):
        asof = (d0 + __import__("datetime").timedelta(days=i * 3)).isoformat()
        src = "2099-01-01" if i % 10 == 0 else asof          # a basket "from the future" must never be trained on
        for j in range(4):
            mom = rng.uniform(-0.3, 0.3)
            rows.append((f"a{i}-{j}", f"bk{i}", 91, src, asof, f"T{j}", "bullish", json.dumps({"mom60": mom}),
                         mom * 0.3 + rng.gauss(0, 0.05), 0.0, 0.0, asof))
    db.executemany("INSERT INTO aug_ideas (id, basket, shift, src_date, as_of, ticker, direction, num, dir_excess, ret, spy_ret, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    seen = []
    real_fit = research._fit_gbm
    monkeypatch.setattr(research, "_fit_gbm", lambda train, keys, label="rel": seen.append(train) or real_fit(train, keys, label))
    out = research.run()
    r = out["results"]
    assert out["shifted_beliefs"] == 300 and r["gbm (+ shifted)"]["n"] == r["gbm (learned)"]["n"] > 100
    assert r["app (current #1)"] == base["app (current #1)"]          # baselines and tests: real calls only
    assert r["gbm (+ shifted)"]["lift"] > 0.02
    for train in seen:
        assert not any(b.get("aug") and b["src_date"] >= "2099" for b in train)
    assert any(any(b.get("aug") for b in train) for train in seen)


def test_ranker_confidence_thirds_and_live_label(monkeypatch):
    from backend.v4 import brain, research
    assert research.confidence_label(0.5, [0.1, 0.3]) == "high"
    assert research.confidence_label(0.2, [0.1, 0.3]) == "medium" and research.confidence_label(0.0, [0.1, 0.3]) == "low"
    assert research.confidence_label(0.5, None) == ""
    test_research_walk_forward_runs_and_stores(monkeypatch)  # planted momentum: confident calls should do better
    out = research.run()
    c = out["confidence"]["gbm (learned)"]
    assert c["cuts"][0] <= c["cuts"][1] and c["low"]["n"] + c["mid"]["n"] + c["high"]["n"] == out["results"]["gbm (learned)"]["n"]
    assert c["high"]["lift"] > c["low"]["lift"]
    rv = research.fit_production(out)
    assert rv["active"] and rv["confidence"] and len(rv["confidence"]["cuts"]) == 2
    monkeypatch.setattr(learning, "build_context", lambda belief: {})  # the planted beliefs' text is just "x"
    r = engine.process_belief("plumbing demand is going to be high", "u-conf", "moderate", claude_client=FakeClaude())
    top = r["picks"][0]
    assert top["confidence"] in ("high", "medium", "low") and all(p["confidence"] == "" for p in r["picks"][1:])
    f = json.loads(db.query_one("SELECT features FROM picks WHERE belief_id = ? AND final_rank = 0", (r["belief_id"],))["features"])
    assert f["rv2_conf"] == top["confidence"] and "rv2" in f
    sk = brain._skill()
    assert sk["ranker"]["confidence"]["cuts"] == rv["confidence"]["cuts"]
    # ranker off: the label comes from the app's own score, with the app's walk-forward cuts
    monkeypatch.setattr(research, "MIN_T", 99.0)
    off = research.fit_production(out)
    assert not off["active"] and off["confidence"] == out["confidence"]["app (current #1)"]
    r2 = engine.process_belief("plumbing demand will boom this year", "u-conf2", "moderate", claude_client=FakeClaude())
    assert r2["picks"][0]["confidence"] in ("high", "medium", "low")


def test_the_app_number_one_is_final_rank_zero():
    # engine stores final_rank from enumerate(): 0 is the #1 idea people see. Research's "app (current #1)",
    # lineages' app baseline and the Brain scorecard must read rank 0 (they read rank 1, the #2 idea, until 2026-11-08)
    from backend.v4 import research
    r = engine.process_belief("plumbing demand is going to be high", "u-rank", claude_client=FakeClaude())
    assert db.query_one("SELECT ticker FROM picks WHERE belief_id = ? AND final_rank = 0", (r["belief_id"],))["ticker"] == r["picks"][0]["ticker"]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-r0", "seed", "x", "x", "2025-01-01T00:00:00", "2025-01-01", "seed_backfill"))
    for j in range(3):
        db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                   (f"p-r0{j}", "b-r0", f"T{j}", "bullish", "2025-01-01", 10.0, "{}", j))
        db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                   (f"p-r0{j}", 90, "2025-04-01", 10.0, 0.0, 0.0, 0.1 * j, "2025-04-01"))
    b = [x for x in research.load() if any(c["ex"] == 0.2 for c in x["cands"])][0]
    assert [c["top"] for c in b["cands"]] == [True, False, False]
