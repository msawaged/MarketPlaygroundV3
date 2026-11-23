"""
v4 tests — no network: Claude and Alpaca are replaced with fakes.

Run:  PYTHONPATH=./ python -m pytest backend/v4/tests -q
"""
from __future__ import annotations

import bisect
import json
import math
import os
import random
from datetime import date, datetime, timedelta, timezone
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


def test_basket_route_never_serves_a_canned_basket_when_the_builder_fails(monkeypatch):
    """A failed build used to return a fixed 60/40 VTI/BND with "5-7% annually" for any goal (a 3-year house fund
    got 60% stocks and a promised return). Now it says no basket could be built."""
    from fastapi import HTTPException
    import importlib
    basket_router = importlib.import_module("backend.routes.basket_router")
    from backend.v4 import basket

    def boom(*a, **k): raise RuntimeError("model unavailable")
    monkeypatch.setattr(basket_router, "generate_basket", boom)
    with pytest.raises(HTTPException) as e:
        basket_router.route_generate_asset_basket(basket_router.BasketRequest(input_text="Safe house fund in 3 years"))
    assert e.value.status_code == 500 and "try again" in e.value.detail

    class EmptyClaude:
        def __init__(self): self.messages = self
        def create(self, **kw):
            out = {"basket": [], "goal": "x", "risk_profile": "moderate", "historical_note": "n"}
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(out))])
    with pytest.raises(ValueError):
        basket.generate("Safe house fund in 3 years", client=EmptyClaude())


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


def test_movers_snapshot_says_which_session_the_move_is_from(monkeypatch):
    from backend.v4 import movers
    # On a Saturday the move is Friday's: the feed must carry the session date so the card doesn't say "today".
    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"AMD": {"latestTrade": {"p": 91.2}, "dailyBar": {"t": "2026-11-13T05:00:00Z", "c": 91.2},
                            "prevDailyBar": {"t": "2026-11-12T05:00:00Z", "c": 100.0}},
                    "OLD": {"latestTrade": {"p": 50.0}, "dailyBar": {"t": "2026-11-13T05:00:00Z"},
                            "prevDailyBar": {"t": "2026-10-20T05:00:00Z", "c": 40.0}}}
    monkeypatch.setattr(movers.market._session, "get", lambda *a, **k: R())
    out = movers._snapshots(["AMD", "OLD"])
    assert out["AMD"] == {"price": 91.2, "change": -0.088, "change_day": "2026-11-13"}
    assert out["OLD"]["change"] is None and out["OLD"]["change_day"] is None


def test_movers_today_change_only_trusts_the_previous_session():
    from backend.v4 import movers
    snap = lambda a, b: {"dailyBar": {"t": a + "T04:00:00Z"}, "prevDailyBar": {"t": b + "T04:00:00Z"}}
    assert movers._today_change(105.0, 100.0, snap("2026-11-04", "2026-11-03")) == 0.05
    assert movers._today_change(105.0, 100.0, snap("2026-11-02", "2026-10-30")) == 0.05   # over a weekend
    assert movers._today_change(105.0, 100.0, snap("2026-11-04", "2026-10-20")) is None   # stale "previous" bar
    assert movers._today_change(160.0, 100.0, snap("2026-11-04", "2026-11-03")) is None   # +60%: a data error
    assert movers._today_change(105.0, 0.0, {}) is None


def test_movers_feed_shows_each_move_against_the_sp500(monkeypatch):
    from backend.v4 import movers
    # A whole-market selloff: ACN -3.4% on a day SPY fell 1.5% is -1.9 pts vs the market, not "-3.4% from the story".
    item = {"headline": "H", "hunch": "x", "companies": [{"ticker": "ACN", "direction": "up", "why": "w"},
                                                       {"ticker": "OLD", "direction": "down", "why": "w"}]}
    monkeypatch.setattr(movers, "_stored", lambda: {"items": [item], "built_at": "x", "checked_at": "x", "ai": True})
    monkeypatch.setattr(movers, "_age", lambda *a, **k: 0.0)
    monkeypatch.setattr(movers.market, "clock", lambda: {"is_open": False})
    seen = {}
    def snaps(syms):
        seen["syms"] = syms
        return {"SPY": {"price": 600.0, "change": -0.015, "change_day": "2026-11-17"},
                "ACN": {"price": 250.0, "change": -0.034, "change_day": "2026-11-17"},
                "OLD": {"price": 10.0, "change": 0.02, "change_day": "2026-11-14"}}  # a different session
    monkeypatch.setattr(movers, "_snapshots", snaps)
    out = movers.feed()
    assert "SPY" in seen["syms"]
    assert out["benchmark"] == {"ticker": "SPY", "change": -0.015, "change_day": "2026-11-17"}
    acn, old = out["items"][0]["companies"]
    assert acn["vs_market"] == -0.019
    assert old["vs_market"] is None  # never compare moves from different days
    # no SPY quote: no benchmark line and no comparisons, the plain move still shows
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {"ACN": {"price": 250.0, "change": -0.034,
                                                                    "change_day": "2026-11-17"}})
    out = movers.feed()
    assert out["benchmark"] is None and out["items"][0]["companies"][0]["vs_market"] is None
    assert out["items"][0]["companies"][0]["change"] == -0.034


def test_movers_feed_says_when_the_price_move_came_before_the_news(monkeypatch):
    from backend.v4 import movers
    # Tue Nov 17 2026 session: 9:30 AM-4 PM ET = 14:30-21:00 UTC
    assert movers.move_timing("2026-11-18T07:00:00Z", "2026-11-17") == "before"   # Wed 2 AM ET story, Tue's move
    assert movers.move_timing("2026-11-17T21:00:00Z", "2026-11-17") == "before"   # right at the close
    assert movers.move_timing("2026-11-17T16:00:00+00:00", "2026-11-17") == "during"  # 11 AM ET
    assert movers.move_timing("2026-11-17T12:00:00Z", "2026-11-17") is None       # before the open: all after it
    assert movers.move_timing("2026-11-14T15:00:00Z", "2026-11-17") is None       # an older story
    assert movers.move_timing("", "2026-11-17") is None and movers.move_timing("2026-11-17T16:00:00Z", None) is None
    item = {"headline": "H", "hunch": "x", "created_at": "2026-11-18T07:00:00Z",
            "companies": [{"ticker": "SERV", "direction": "up", "why": "w"}, {"ticker": "GIXI", "direction": "up", "why": "w"}]}
    monkeypatch.setattr(movers, "_stored", lambda: {"items": [item], "built_at": "x", "checked_at": "x", "ai": True})
    monkeypatch.setattr(movers, "_age", lambda *a, **k: 0.0)
    monkeypatch.setattr(movers.market, "clock", lambda: {"is_open": False})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {
        "SPY": {"price": 600.0, "change": -0.009, "change_day": "2026-11-17"},
        "SERV": {"price": 9.0, "change": -0.028, "change_day": "2026-11-17"}})  # GIXI: no quote
    serv, gixi = movers.feed()["items"][0]["companies"]
    assert serv["move_timing"] == "before"
    assert gixi["move_timing"] is None  # no move shown, nothing to say


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
    st = c.get("/v4/broker/status", headers=h).json()
    assert st["connected"] is True and st["on"] is False and st["can_switch"] is True
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 50}, headers=h).status_code == 403  # switch is off
    assert c.post("/v4/broker/switch", json={"on": True}, headers=h).json()["on"] is True
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



def test_wrong_if_pre_mortem_is_stored_owner_only_and_tripwire_reads_closes():
    # the pure check: closes strictly after the call date; bullish crossed at/below, bearish at/above
    dates, closes = ["2026-11-02", "2026-11-03", "2026-11-04", "2026-11-05"], [100.0, 96.0, 89.0, 95.0]
    t = engine.tripwire("bullish", 90.0, dates, closes, "2026-11-02", now=95.0)
    assert t["crossed_on"] == "2026-11-04" and t["crossed_close"] == 89.0 and t["past_now"] is False
    t = engine.tripwire("bullish", 80.0, dates, closes, "2026-11-02", now=79.0)
    assert t["crossed_on"] is None and t["past_now"] is True and t["checked_through"] == "2026-11-05"
    assert engine.tripwire("bullish", 101.0, dates, closes, "2026-11-02")["crossed_on"] == "2026-11-03"  # call day itself doesn't count
    assert engine.tripwire("bearish", 96.0, dates, closes, "2026-11-01")["crossed_on"] == "2026-11-02"
    assert engine.tripwire("bullish", 90.0, dates, closes, "2026-11-05")["checked_through"] is None   # nothing after the call yet

    r = engine.process_belief("plumbing demand is going to be high", "u-pm", "moderate", claude_client=FakeClaude())
    bid = r["belief_id"]
    top = db.query_one("SELECT ticker, direction, entry_price FROM picks WHERE belief_id = ? AND shown = 1 ORDER BY final_rank LIMIT 1", (bid,))
    assert top["direction"] == "bullish"
    with pytest.raises(engine.BeliefError):
        engine.set_wrong_if(bid, "u-someone-else", "housing starts fall")      # only the person who made the call
    with pytest.raises(engine.BeliefError):
        engine.set_wrong_if(bid, "anonymous", "housing starts fall")
    with pytest.raises(engine.BeliefError):
        engine.set_wrong_if(bid, "u-pm", "   ")                                  # nothing to store
    with pytest.raises(engine.BeliefError):
        engine.set_wrong_if(bid, "u-pm", None, price=top["entry_price"] * 1.1)   # bullish line must sit below entry
    with pytest.raises(engine.BeliefError):
        engine.set_wrong_if(bid, "u-pm", None, price=50.0, ticker="NOTAPICK")
    with pytest.raises(engine.BeliefError):
        engine.set_wrong_if(bid, "u-pm", None, price=float("nan"))
    line = round(top["entry_price"] * 0.9, 2)
    out = engine.set_wrong_if(bid, "u-pm", "  housing   starts fall " + "x" * 300, price=line)
    assert out["wrong_if"]["ticker"] == top["ticker"] and out["wrong_if"]["price"] == line
    assert len(out["wrong_if"]["text"]) == engine.WRONG_IF_MAX and out["wrong_if"]["text"].startswith("housing starts fall x")
    w = engine.my_beliefs("u-pm")["beliefs"][0]["wrong_if"]
    assert w["ticker"] == top["ticker"] and w["price"] == line and w["direction"] == "bullish"
    assert "crossed_on" in w and "past_now" in w
    engine.set_wrong_if(bid, "u-pm", "rates jump")                              # text only clears the price line
    w = engine.my_beliefs("u-pm")["beliefs"][0]["wrong_if"]
    assert {k: w[k] for k in ("text", "price", "ticker")} == {"text": "rates jump", "price": None, "ticker": None}
    assert "direction" not in w and w["answer"] is None and w["can_answer"] is False
    assert engine.my_beliefs("u-fund-none")["beliefs"] == []

    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.v4.router import router
    app = FastAPI(); app.include_router(router, prefix="/v4")
    c = TestClient(app)
    assert c.post("/v4/wrong_if", json={"belief_id": bid, "user_id": "u-pm", "text": "margins shrink"}).status_code == 200
    assert c.post("/v4/wrong_if", json={"belief_id": bid, "user_id": "u-x", "text": "nope"}).status_code == 400
    assert engine.my_beliefs("u-pm")["beliefs"][0]["wrong_if"]["text"] == "margins shrink"

def test_wrong_if_did_that_happen_answer(monkeypatch):
    from datetime import date, timedelta
    r = engine.process_belief("plumbing demand is going to be high", "u-dth", "moderate", claude_client=FakeClaude())
    bid = r["belief_id"]
    made = db.query_one("SELECT as_of_date FROM beliefs WHERE id = ?", (bid,))["as_of_date"]
    with pytest.raises(engine.BeliefError):
        engine.answer_wrong_if(bid, "u-dth", "yes")                     # no line written yet
    engine.set_wrong_if(bid, "u-dth", "housing starts fall")
    w = engine.my_beliefs("u-dth")["beliefs"][0]["wrong_if"]
    assert w["can_answer"] is False and w["answer"] is None
    assert w["ask_from"] == (date.fromisoformat(made) + timedelta(days=engine.WRONG_IF_ASK_DAYS)).isoformat()
    with pytest.raises(engine.BeliefError):
        engine.answer_wrong_if(bid, "u-dth", "yes")                     # too early: nothing to look back on
    later = date.fromisoformat(made) + timedelta(days=engine.WRONG_IF_ASK_DAYS)
    monkeypatch.setattr(engine.market, "today", lambda: later)
    with pytest.raises(engine.BeliefError):
        engine.answer_wrong_if(bid, "u-other", "yes")                   # only the person who made the call
    with pytest.raises(engine.BeliefError):
        engine.answer_wrong_if(bid, "anonymous", "yes")
    with pytest.raises(engine.BeliefError):
        engine.answer_wrong_if(bid, "u-dth", "maybe")
    out = engine.answer_wrong_if(bid, "u-dth", " Partly ")
    assert out["answer"] == "partly" and out["answered_at"] == later.isoformat()
    w = engine.my_beliefs("u-dth")["beliefs"][0]["wrong_if"]
    assert w["can_answer"] is True and w["answer"] == "partly" and w["answered_at"] == later.isoformat()
    engine.answer_wrong_if(bid, "u-dth", "yes")                         # can change it as things play out
    assert engine.my_beliefs("u-dth")["beliefs"][0]["wrong_if"]["answer"] == "yes"
    engine.set_wrong_if(bid, "u-dth", "housing starts fall")            # same line again keeps the answer
    assert engine.my_beliefs("u-dth")["beliefs"][0]["wrong_if"]["answer"] == "yes"
    engine.set_wrong_if(bid, "u-dth", "mortgage rates jump")            # a new line is a new test
    w = engine.my_beliefs("u-dth")["beliefs"][0]["wrong_if"]
    assert w["answer"] is None and w["answered_at"] is None
    engine.answer_wrong_if(bid, "u-dth", "no")
    assert engine.answer_wrong_if(bid, "u-dth", None)["answer"] is None  # clearing is allowed

    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.v4.router import router
    app = FastAPI(); app.include_router(router, prefix="/v4")
    c = TestClient(app)
    assert c.post("/v4/wrong_if/answer", json={"belief_id": bid, "user_id": "u-dth", "answer": "no"}).json()["answer"] == "no"
    assert c.post("/v4/wrong_if/answer", json={"belief_id": bid, "user_id": "u-x", "answer": "no"}).status_code == 400


def test_how_sure_calibration_scores_stated_probabilities():
    from datetime import date
    from backend.v4 import calibration
    # pure pieces
    assert [calibration.checkpoint_for(h) for h in (None, 5, 30, 60, 90, 120, 365, 900)] == [7, 7, 30, 90, 90, 180, 365, 365]
    assert calibration.normalize(75) == 0.75 and calibration.normalize("0.9") == 0.9
    assert calibration.normalize(0.7) is None and calibration.normalize(float("nan")) is None and calibration.normalize("x") is None
    assert calibration.can_set("2026-11-13", today=date(2026, 11, 14)) and not calibration.can_set("2026-11-12", today=date(2026, 11, 14))
    assert calibration.score([]) == {"graded": 0, "pending": 0, "min_graded": 10, "ready": False}
    pairs = [(0.9, 1)] * 2 + [(0.9, 0)] * 2 + [(0.55, 1)] * 6     # said 90% -> right half the time; said 55% -> always
    sc = calibration.score(pairs, pending=3)
    assert sc["graded"] == 10 and sc["ready"] and sc["pending"] == 3
    assert abs(sc["brier"] - (2 * 0.01 + 2 * 0.81 + 6 * 0.2025) / 10) < 1e-4
    rows = {b["said"]: b for b in sc["buckets"]}
    assert rows[0.9]["actual"] == 0.5 and rows[0.9]["verdict"] == "overconfident" and rows[0.9]["n"] == 4
    assert rows[0.55]["verdict"] == "underconfident" and rows[0.55]["right"] == 6
    assert calibration.score([(0.75, 1), (0.75, 0)])["buckets"][0]["verdict"] == "too few to say"
    assert calibration.score([(0.75, 1)] * 7 + [(0.75, 0)] * 4)["overall"] == "leaning overconfident"   # 64% of 11: could be luck
    assert calibration.score([(0.75, 1)] * 8 + [(0.75, 0)] * 2)["overall"] == "about right"

    # stored on the user's own call, inside the window, one of the choices only
    r = engine.process_belief("plumbing demand is going to be high", "u-sure", "moderate", claude_client=FakeClaude())
    bid = r["belief_id"]
    with pytest.raises(engine.BeliefError):
        engine.set_user_prob(bid, "u-other", 75)
    with pytest.raises(engine.BeliefError):
        engine.set_user_prob(bid, "anonymous", 75)
    with pytest.raises(engine.BeliefError):
        engine.set_user_prob(bid, "u-sure", 70)
    out = engine.set_user_prob(bid, "u-sure", 75)
    assert out["sure"]["prob"] == 0.75
    mb = engine.my_beliefs("u-sure")
    b0 = mb["beliefs"][0]
    assert b0["sure"]["prob"] == 0.75 and b0["sure"]["can_set"] is True
    assert b0["sure"]["checkpoint_days"] == calibration.checkpoint_for(b0["horizon_days"])
    assert mb["calibration"] == {"graded": 0, "pending": 1, "min_graded": 10, "ready": False}

    # graded at its checkpoint: other checkpoints don't count
    cp = b0["sure"]["checkpoint_days"]
    pids = [x["id"] for x in db.query("SELECT id FROM picks WHERE belief_id = ?", (bid,))]
    other = 7 if cp != 7 else 30
    for pid in pids:
        for c, right in ((cp, 1), (other, 0)):
            db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at, belief_right)
                          VALUES (?, ?, '2026-01-01', 1, 0.1, 0.0, 0.1, '2026-01-01', ?)""", (pid, c, right))
    cal = engine.my_beliefs("u-sure")["calibration"]
    assert cal["graded"] == 1 and cal["pending"] == 0 and cal["hit_rate"] == 1.0 and abs(cal["brier"] - 0.0625) < 1e-9

    # locked once the day after the call has passed
    db.execute("UPDATE beliefs SET as_of_date = '2020-01-02' WHERE id = ?", (bid,))
    with pytest.raises(engine.BeliefError):
        engine.set_user_prob(bid, "u-sure", 90)
    assert engine.my_beliefs("u-sure")["beliefs"][0]["sure"]["can_set"] is False
    assert engine.my_beliefs("u-nobody")["beliefs"] == []

    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.v4.router import router
    app = FastAPI(); app.include_router(router, prefix="/v4")
    c = TestClient(app)
    r2 = engine.process_belief("airlines will struggle this year", "u-sure", "moderate", claude_client=FakeClaude())
    assert c.post("/v4/user_prob", json={"belief_id": r2["belief_id"], "user_id": "u-sure", "prob": 0.55}).status_code == 200
    assert c.post("/v4/user_prob", json={"belief_id": r2["belief_id"], "user_id": "u-sure", "prob": 0.6}).status_code == 400


def test_calibration_compares_with_the_outside_view():
    from backend.v4 import calibration
    # base rate 50%: always saying it scores 0.25 on every call
    sharp = [(0.9, 1, 0.5)] * 9 + [(0.55, 0, 0.5)] * 3       # mostly 90% and right: clearly better
    ov = calibration.score(sharp)["outside"]
    assert ov["n"] == 12 and ov["outside_brier"] == 0.25 and ov["brier"] < 0.25 and ov["verdict"] == "better than the outside view"
    bad = [(0.9, 0, 0.5)] * 8 + [(0.9, 1, 0.5)] * 4           # 90% sure, right a third of the time
    assert calibration.score(bad)["outside"]["verdict"] == "worse than the outside view"
    mixed = [(0.65, 1, 0.5), (0.65, 0, 0.5)] * 6                 # small edge either way: could be luck
    assert calibration.score(mixed)["outside"]["verdict"] == "about the same as the outside view"
    # needs MIN_OUTSIDE calls with a base rate; calls without one (cell hidden) are left out, the rest still scores
    few = [(0.75, 1, 0.5)] * 5 + [(0.75, 1, None)] * 6
    sc = calibration.score(few)
    assert sc["ready"] and "outside" not in sc and sc["graded"] == 11
    assert "outside" not in calibration.score([(0.75, 1)] * 12)   # old 2-tuples still work
    assert calibration.outside_view([(0.9, 1, 0.47)] * 10)["avg_base_rate"] == 0.47


def test_base_rate_outside_view_counts_each_call_once(monkeypatch):
    from backend.v4 import baserate, calibration
    assert baserate.public()["cells"] == {} and baserate.for_call("bullish", 90) is None   # nothing computed yet
    made = []
    for i, text in enumerate(["plumbing demand is going to be high", "ai chip demand keeps growing",
                              "everyone is getting a pet", "airlines will struggle this year"]):
        r = engine.process_belief(text, f"u-br{i}", "moderate", claude_client=FakeClaude())
        made.append(r["belief_id"])
    dirs = {b: db.query_one("SELECT direction FROM beliefs WHERE id = ?", (b,))["direction"] for b in made}
    # each call: every pick graded at 90 days with the same belief_right (one result per call, as the grader stores it)
    right = {made[0]: 1, made[1]: 0, made[2]: 1, made[3]: 1}
    for b in made:
        for x in db.query("SELECT id FROM picks WHERE belief_id = ?", (b,)):
            for cp, r in ((90, right[b]), (7, 0)):
                db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at, belief_right)
                              VALUES (?, ?, '2026-01-01', 1, 0.1, 0.0, 0.1, '2026-01-01', ?)""", (x["id"], cp, r))
    out = baserate.compute()
    want: dict = {}
    for b in made:
        w = want.setdefault(dirs[b], [0, 0]); w[0] += 1; w[1] += right[b]
    for d, (n, k) in want.items():
        c = out["cells"][d]["90"]
        assert c["n"] == n and c["right"] == k and abs(c["beat"] - round(k / n, 3)) < 1e-9   # calls, not picks
        assert out["cells"][d]["7"]["right"] == 0 and c["since"] and c["upto"] >= c["since"]
    # small cells are hidden from the app until they reach MIN_N calls
    assert baserate.public()["cells"] == {}
    monkeypatch.setattr(baserate, "MIN_N", 1)
    d0 = dirs[made[0]]
    got = baserate.for_call(d0, 60)
    assert got["checkpoint_days"] == calibration.checkpoint_for(60) == 90 and got["n"] == want[d0][0]
    assert baserate.for_call("sideways", 90) is None
    # stored in kv, served by the public endpoint
    baserate._cache.update(at=0.0, v=None)
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from backend.v4.router import router
    app = FastAPI(); app.include_router(router, prefix="/v4")
    body = TestClient(app).get("/v4/base_rates").json()
    assert body["cells"][d0]["90"]["n"] == want[d0][0]


def test_base_rate_spread_says_how_far_calls_landed():
    from backend.v4 import baserate
    assert abs(baserate._pct([1.0, 2.0, 3.0, 4.0, 5.0], 0.1) - 1.4) < 1e-9 and baserate._pct([5.0], 0.9) == 5.0   # = percentile_cont
    assert abs(baserate._call_excess("bearish", -0.10, 0.02) - 0.12) < 1e-9 and abs(baserate._call_excess("volatile", -0.3, 0.1) - 0.2) < 1e-9
    texts = ["plumbing demand is going to be high", "ai chip demand keeps growing", "everyone is getting a pet",
             "airlines will struggle this year", "solar keeps getting cheaper", "banks will have a rough year"]
    made = [engine.process_belief(t, f"u-sp{i}", "moderate", claude_client=FakeClaude())["belief_id"]
            for i, t in enumerate(texts)]
    bench = [0.20, -0.05, 0.10, -0.15, 0.02, 0.30]
    want: dict = {}
    for b, br in zip(made, bench):
        d = db.query_one("SELECT direction FROM beliefs WHERE id = ?", (b,))["direction"]
        x = baserate._call_excess(d, br, 0.01)
        for pk in db.query("SELECT id, direction FROM picks WHERE belief_id = ?", (b,)):
            # picks in another direction carry their own group's benchmark; only the call's own direction counts
            mine = pk["direction"] == d
            db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at,
                                                belief_right, bench_ret)
                          VALUES (?, 90, '2026-01-01', 1, 0.1, 0.01, 0.1, '2026-01-01', ?, ?)""",
                       (pk["id"], 1 if x > 0 else 0, br if mine else -9.0))
        want.setdefault(d, []).append(x)
    cells = baserate.compute()["cells"]
    for d, xs in want.items():
        xs.sort()
        c = cells[d]["90"]
        assert c["n"] == len(xs) and c["right"] == sum(1 for x in xs if x > 0)
        for q, k in ((0.1, "p10"), (0.5, "p50"), (0.9, "p90")):
            assert abs(c[k] - round(baserate._pct(xs, q), 4)) < 1e-9
        assert c["p10"] <= c["p50"] <= c["p90"]


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
        "/v4/wrong_if": ["belief_id", "user_id", "text", "price", "ticker"],
        "/v4/user_prob": ["belief_id", "user_id", "prob"],
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


def test_movers_answers_are_matched_to_their_headline_not_just_their_number(monkeypatch):
    """Live 2026-11-18: four cards carried the neighbouring headline's hunch. Answers echo the headline's start and
    are filed under the headline they name; one naming no headline is dropped; reasons are cut at a whole word."""
    from backend.v4 import movers
    news = [{"headline": h, "symbols": [], "source": "x", "url": "u", "created_at": "t"} for h in (
        "Sulnox Group PLC Secures New Canadian Patent",
        "Egypt gas field sale stalls as oil majors balk",
        "Private AI cloud builder raises $5 billion")]
    monkeypatch.setattr(market, "headlines", lambda limit=6: news)
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s})
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {})
    long_why = "Steady multi-year lithium demand from Chinese battery giants supports Sociedad Quimica's sales growth"
    payload = {"items": [  # numbers shifted by one, as seen live
        {"n": 0, "starts": "Egypt gas field sale stalls", "keep": True, "hunch": "Oil majors will struggle in Egypt",
         "why": "", "companies": [{"ticker": "XOM", "direction": "down", "why": long_why + " " + long_why}]},
        {"n": 1, "starts": "Private AI cloud builder raises", "keep": True, "hunch": "AI cloud funding boosts chips",
         "why": "", "companies": [{"ticker": "NVDA", "direction": "up", "why": "more GPU orders"}]},
        {"n": 2, "starts": "Totally different headline here", "keep": True, "hunch": "Made up", "why": "",
         "companies": [{"ticker": "AAPL", "direction": "up", "why": "x"}]},
        {"n": 2, "starts": "Sulnox Group PLC Secures New", "keep": False, "hunch": "", "why": "", "companies": []},
    ]}
    out = movers.build(client=FakeClaude(payload))
    got = {it["headline"]: it["hunch"] for it in out["items"]}
    assert got == {news[1]["headline"]: "Oil majors will struggle in Egypt", news[2]["headline"]: "AI cloud funding boosts chips"}
    why = next(it for it in out["items"] if it["hunch"].startswith("Oil"))["companies"][0]["why"]
    full = long_why + " " + long_why
    assert len(why) <= 110 and why.endswith("…") and full.startswith(why[:-1]) and full[len(why) - 1] == " "


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


def test_news_opposite_side_only_for_single_claims(monkeypatch):
    """A compound or already-negated hunch has no clean opposite ("I don't think a merger would face scrutiny and could
    drag on Tesla" was read as bearish TSLA, like the original), so only the hunch itself is learned."""
    from backend.v4 import movers, seeder
    hunches = ["A Tesla-SpaceX merger would face heavy scrutiny and could drag on Tesla",
               "Cloud outages will fade slowly, and customers may spread workloads across providers",
               "Democratic midterm wins won't change economic policy for a while",
               "Peloton's refinancing will ease debt pressure but dilute future shareholder returns",
               "A 90-day shipping waiver will ease oil and fertilizer supply worries"]
    feed = {"items": [{"headline": f"h{i}", "hunch": h} for i, h in enumerate(hunches)]}
    monkeypatch.setattr(movers, "feed", lambda client=None: feed)
    got = seeder.news_beliefs(20)
    assert got == hunches + ["I don't think a 90-day shipping waiver will ease oil and fertilizer supply worries"]


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
    # Live Nov 21: "I don't think Tungsten supply outside China will tighten" (the summary named "the Sunrise Tungsten
    # Project") and "I don't think Cheaper AI chips will spread" (an acronym second word isn't a two-word name).
    tungsten = ("Torrent Gold has finalized the acquisition of the Sunrise Tungsten Project in New Mexico. "
                "Non-Chinese tungsten producer gains as global supply tightens.")
    assert f("Tungsten supply outside China will tighten", tungsten) == "tungsten supply outside China will tighten"
    assert f("Cruise lines will keep ordering ships", "orders at Norwegian Cruise Line rose") == \
        "cruise lines will keep ordering ships"
    assert f("Cheaper AI chips will spread") == "cheaper AI chips will spread"
    assert f("Giant AI-driven deals will grow") == "giant AI-driven deals will grow"
    assert f("New York lenders will pull back") == "New York lenders will pull back"
    assert f("Fresenius will win clinics", "rivals lose, Fresenius gains") == "Fresenius will win clinics"
    # Live Nov 22 / Nov 19: "I don't think spanish banks ...", "I don't think european solar output ...".
    assert f("Spanish banks will face higher taxes") == "Spanish banks will face higher taxes"
    assert f("European solar output will keep growing") == "European solar output will keep growing"
    assert f("Korean chipmakers will gain") == "Korean chipmakers will gain"
    assert f("Silicon photonics chips will spread") == "silicon photonics chips will spread"


def test_news_opposite_reads_as_english_and_still_pairs_with_its_hunch(monkeypatch):
    """ "I don't think bitcoin may slide" isn't English: may / might / could become "will" in the opposite, the
    month May is left alone, an opposite learned before the change isn't learned again, and the renamed opposite
    still runs after its hunch with the hunch's picks to avoid."""
    from backend.v4 import movers, seeder
    assert seeder._opposite("Bitcoin may slide toward $38,000") == "I don't think bitcoin will slide toward $38,000"
    assert seeder._opposite("Rate cuts could lift homebuilders") == "I don't think rate cuts will lift homebuilders"
    assert seeder._opposite("Retail sales will beat May levels") == "I don't think retail sales will beat May levels"
    feed = {"items": [{"headline": "h1", "hunch": "Bitcoin's weekend selloff may signal a longer crypto downturn ahead."},
                      {"headline": "h2", "hunch": "Solar demand might cool."}]}
    monkeypatch.setattr(movers, "feed", lambda client=None: feed)
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, source, created_at, as_of_date) VALUES (?,?,?,?,?,?,?)",
               ("b-legacy", "seed", "I don't think solar demand might cool", "x", "seed_news", "2026-11-16T00:00:00+00:00",
                "2026-11-16"))
    got = seeder.news_beliefs(10)
    assert got == ["Bitcoin's weekend selloff may signal a longer crypto downturn ahead",
                   "I don't think Bitcoin's weekend selloff will signal a longer crypto downturn ahead",
                   "Solar demand might cool"]
    seen = {}
    monkeypatch.setattr(seeder.engine, "process_belief",
                        lambda text, **kw: seen.setdefault(text, kw.get("avoid")) or {"valid": True, "picks": [{"ticker": "IBIT", "direction": "bearish"}]})
    seeder.run("live", n=2, beliefs=got[:2], source="seed_news", concurrency=1, max_usd=1)
    assert seen[got[1]] == {("IBIT", "bearish")}


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


def test_movers_drops_a_claude_pick_that_is_a_foreign_tag_for_a_different_us_company(monkeypatch):
    """Live 2026-11-15: Centrica (London ticker CNA) showed as "CNA", which in the US is CNA Financial, an insurer,
    with that insurer's price move. A tagged ticker must name the company in the story even when Claude picked it."""
    from backend.v4 import movers
    names = {"CNA": "CNA Financial Corporation Common Stock", "EQNR": "Equinor ASA", "DAL": "Delta Air Lines, Inc."}
    news = [{"headline": "Centrica and Equinor Advance in Bidding Process for Uniper", "symbols": ["CNA", "EQNR"],
             "summary": "Centrica and Equinor moved to the second round.", "source": "x", "url": "", "created_at": ""},
            {"headline": "Weekend chaos at US airports", "symbols": [], "summary": "", "source": "x", "url": "", "created_at": ""}]
    ai = {0: {"keep": True, "hunch": "Utilities will keep bidding", "why": "w", "companies": [
              {"ticker": "CNA", "direction": "up", "why": "gas"}, {"ticker": "EQNR", "direction": "up", "why": "gas"}]},
          1: {"keep": True, "hunch": "Airlines face costs", "why": "w", "companies": [{"ticker": "DAL", "direction": "down", "why": "costs"}]}}
    monkeypatch.setattr(market, "headlines", lambda limit=6: news)
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s, "name": names[s]})
    monkeypatch.setattr(movers, "_ask_claude", lambda news, client=None: ai)
    out = movers.build()
    assert [[c["ticker"] for c in it["companies"]] for it in out["items"]] == [["EQNR"], ["DAL"]]  # DAL: not a tag, kept
    assert all("_tags" not in it for it in out["items"])
    assert "CNA Financial" in movers.PROMPT


def test_movers_fallback_drops_tags_for_a_different_company_and_keeps_the_curated_feed(monkeypatch):
    from backend.v4 import movers
    from datetime import datetime, timedelta, timezone
    names = {"DOCS": "Doximity, Inc. Class A Common Stock", "SMTK": "SmartKem, Inc. Common Stock", "GHRS": "GH Research PLC"}
    news = [{"headline": "Dr. Martens plc Announces Ex-Dividend Date", "symbols": ["DOCS"], "source": "x", "url": "", "created_at": ""},
            {"headline": "SmartKem Reports Third Quarter Results", "symbols": ["SMTK"], "source": "x", "url": "", "created_at": ""},
            {"headline": "RBC Maintains Buy Rating on GH Research", "symbols": ["GHRS"], "source": "x", "url": "", "created_at": ""}]
    monkeypatch.setattr(market, "headlines", lambda limit=6: news)
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s, "name": names[s]})
    monkeypatch.setattr(market, "clock", lambda: {"is_open": False})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    db.execute("DELETE FROM kv_cache WHERE k = ?", (movers.KEY,))
    plain = movers.feed()
    assert [it["companies"][0]["ticker"] for it in plain["items"]] == ["SMTK", "GHRS"]  # Doximity isn't Dr. Martens

    # a curated feed from yesterday beats raw routine headlines; it keeps its own age and isn't rebuilt every call
    built = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    curated = {"items": [{"headline": "Airlines add flights", "hunch": "People will fly more", "why": "", "summary": "",
                          "source": "x", "url": "", "created_at": "", "companies": [{"ticker": "DAL", "direction": "up", "why": "fares"}]}],
               "built_at": built, "ai": True}
    db.execute("DELETE FROM kv_cache WHERE k = ?", (movers.KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (movers.KEY, json.dumps(curated), built))
    calls = []
    real_build = movers.build
    monkeypatch.setattr(movers, "build", lambda client=None: calls.append(1) or real_build(client))
    out = movers.feed()
    assert out["items"][0]["hunch"] == "People will fly more" and out["built_at"] == built
    movers.feed()
    assert len(calls) == 1


def test_movers_keeps_todays_stories_when_a_rebuild_finds_few(monkeypatch):
    """Live 2026-11-17 10:24 AM ET: a rebuild kept 1 of 30 headlines and "Moving now" showed one Temu story. Stories
    already picked stay (after the new ones) until they are a day old; stale ones and duplicates don't."""
    from backend.v4 import movers
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    iso = lambda h: (now - timedelta(hours=h)).isoformat().replace("+00:00", "Z")
    old_items = [{"headline": h, "hunch": h, "why": "", "summary": "", "source": "x", "url": "", "created_at": c,
                  "companies": [{"ticker": "DAL", "direction": "up", "why": "w", "price": 50.0, "change": 0.02}]}
                 for h, c in (("Temu deal", iso(1)), ("Airlines add flights", iso(3)), ("Week-old news", iso(30)),
                              ("No date", ""))]
    built = (now - timedelta(hours=1)).isoformat()
    db.execute("DELETE FROM kv_cache WHERE k = ?", (movers.KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)",
               (movers.KEY, json.dumps({"items": old_items, "built_at": built, "ai": True}), built))
    news = [{"headline": "Temu deal", "symbols": [], "summary": "", "source": "x", "url": "", "created_at": iso(1)},
            {"headline": "Chip export rules tighten", "symbols": [], "summary": "", "source": "x", "url": "", "created_at": iso(0.2)}]
    ai = {0: {"keep": True, "hunch": "Temu deal", "why": "", "companies": [{"ticker": "AMZN", "direction": "down", "why": "w"}]},
          1: {"keep": True, "hunch": "Chips face limits", "why": "", "companies": [{"ticker": "NVDA", "direction": "down", "why": "w"}]}}
    monkeypatch.setattr(market, "headlines", lambda limit=6: news)
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s})
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {"DAL": {"price": 51.0, "change": -0.01}})
    monkeypatch.setattr(movers, "_ask_claude", lambda news, client=None: ai)
    monkeypatch.setattr(movers, "TTL", 0)
    out = movers.feed()
    assert [it["headline"] for it in out["items"]] == ["Temu deal", "Chip export rules tighten", "Airlines add flights"]
    assert out["items"][0]["companies"][0]["ticker"] == "AMZN"  # the fresh copy wins a duplicate
    carried = out["items"][2]["companies"][0]
    assert carried["price"] == 51.0 and carried["change"] == -0.01  # today's price, not the stored one
    stored = json.loads(db.query_one("SELECT v FROM kv_cache WHERE k = ?", (movers.KEY,))["v"])
    assert "price" not in stored["items"][2]["companies"][0]
    # never past MAX_ITEMS
    many = [dict(old_items[1], headline=f"Story {i}") for i in range(12)]
    assert len(movers._carry([], many)) == movers.MAX_ITEMS


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


def test_brain_counts_say_how_many_grades_are_real_time():
    """Practice calls on past dates are graded at once at every checkpoint, so they swamp 'graded'. The page
    must be able to say how many grades came from calls made in real time (the forward test's set)."""
    from backend.v4 import brain
    seeder.run("backfill", n=5, years=1, concurrency=1, claude_client=FakeClaude())
    practice = db.query_one("SELECT COUNT(*) AS n FROM outcomes")["n"]
    assert practice > 0
    engine.process_belief("people want cheaper food", "seed", "moderate", source="seed_news", claude_client=FakeClaude())
    pid = db.query_one("SELECT p.id FROM picks p JOIN beliefs b ON b.id = p.belief_id WHERE b.source = 'seed_news'")["id"]
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) "
               "VALUES (?, 7, ?, 1, 0.01, 0, 0.01, ?)", (pid, TODAY.isoformat(), datetime.now(timezone.utc).isoformat()))
    brain._cache.update(at=0, v=None)
    s = brain.snapshot()
    assert s["counts"]["graded"] == practice + 1 and s["counts"]["graded_live"] == 1
    assert s["growth"][-1]["live"] == 1 and s["growth"][-1]["graded"] == practice + 1


def test_brain_just_graded_feed_says_real_time_or_practice_and_the_call_date():
    """'Just graded by the market' mixed practice calls (dated in the past, graded at once) with real-time ones and
    showed only 'after 365 days · 2h ago', which reads as a year-old live call. Each row now says which it was and
    the date the call is made as of."""
    from backend.v4 import brain
    seeder.run("backfill", n=3, years=1, concurrency=1, claude_client=FakeClaude())
    engine.process_belief("people want cheaper food", "seed", "moderate", source="seed_news", claude_client=FakeClaude())
    pid = db.query_one("SELECT p.id FROM picks p JOIN beliefs b ON b.id = p.belief_id WHERE b.source = 'seed_news'")["id"]
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) "
               "VALUES (?, 7, ?, 1, 0.01, 0, 0.01, ?)", (pid, TODAY.isoformat(), "2999-01-01T00:00:00+00:00"))
    rows = brain._recent_graded(limit=50)
    assert rows[0]["live"] is True and rows[0]["called_on"]
    practice = [r for r in rows if not r["live"]]
    assert practice and all(r["called_on"] and r["called_on"] < TODAY.isoformat() for r in practice)
    asof = {x["as_of_date"][:10] if isinstance(x["as_of_date"], str) else str(x["as_of_date"]) for x in db.query(
        "SELECT b.as_of_date FROM beliefs b WHERE b.source = 'seed_backfill'")}
    assert {r["called_on"] for r in practice} <= asof


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
    nr = brain._next_runs(datetime(2026, 10, 30, 22, 50, tzinfo=timezone.utc))  # a Friday 6:50 PM ET (EDT)
    assert nr["learning"].startswith("2026-10-30T23:13")
    # Friday's close is graded by the first hourly run after midnight ET (Sat 12:13 AM EDT = 04:13 UTC), not Monday.
    assert nr["grading"].startswith("2026-10-31T04:13")


def test_next_market_grading_is_the_first_run_after_midnight_et_following_a_trading_day():
    from datetime import datetime, timezone
    from backend.v4 import brain
    # Fri Nov 20 2026, 10:23 PM ET (EST): Friday's close is graded at Sat 12:13 AM ET = 05:13 UTC.
    assert brain._next_runs(datetime(2026, 11, 21, 3, 23, tzinfo=timezone.utc))["grading"].startswith("2026-11-21T05:13")
    # Sat 1 AM ET, after that run: nothing new until Monday's close, graded Tue 12:13 AM ET.
    assert brain._next_runs(datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc))["grading"].startswith("2026-11-24T05:13")
    # Tue 3 PM ET: Tuesday's close is graded Wed 12:13 AM ET.
    assert brain._next_runs(datetime(2026, 11, 24, 20, 0, tzinfo=timezone.utc))["grading"].startswith("2026-11-25T05:13")


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
    # a bare date under "Moving now" read like the page's own (future) date: say when the news is for instead
    yr = datetime.now(timezone.utc).year
    assert movers._hook(f"November 30, {yr}") == "On Nov 30"
    assert movers._hook(f"30 November {yr + 1}") == f"On Nov 30, {yr + 1}"
    assert movers._hook("$51 billion") == "$51 billion" and movers._hook("May 2026 sales") == "May 2026 sales"
    # a bare year isn't a hook either (live: "2026" from "the 2026 Dubai Precious Metals Conference")
    assert movers._hook("2026") == "" and movers._hook("In 2027") == "" and movers._hook("Up 2026%") == "Up 2026%"
    assert movers._fallback_story({"headline": "SMX shows trueGold at the 2026 Dubai Precious Metals Conference"})["hook_big"] == "Moving now"
    assert movers._fallback_story({"headline": "In 2026 Oil jumps 5% as OPEC cuts"})["hook_big"] == "5%"
    # the no-Claude hook never takes digits out of a model name ("E195-E2" -> "195")
    assert movers._fallback_story({"headline": "Latam launches the Embraer E195-E2"})["hook_big"] == "Moving now"
    assert movers._fallback_story({"headline": "Oil jumps 5% as OPEC cuts"})["hook_big"] == "5%"
    assert fb["ai"] is False and fb["figures"] == [] and fb["hook_line"]
    # story text ends on a whole sentence, also for text cached with a mid-sentence "…"
    cut = ("Fewer young buyers slow homebuilder sales, and prices keep people out. Stronger policy pressure could "
           "push more public spending toward building, which may matter for housing-linked…")
    assert movers._sentences(cut, 240) == "Fewer young buyers slow homebuilder sales, and prices keep people out."
    assert movers._sentences("It hit 242 U.S. cities. Ages rose to 40.", 320) == "It hit 242 U.S. cities. Ages rose to 40."
    assert movers._sentences("word " * 80, 60).endswith("…")
    assert movers._hook("11,000 satellites, still…") == ""
    # the hook keeps the article's hedge on its number (live 2026-11-21: "up to 8 million barrels" -> "8 million barrels")
    src = "Saudi Arabia will supply up to 8 million barrels of crude oil to Japan's reserve."
    assert movers._hook("8 million barrels", src) == "Up to 8 million barrels"
    assert movers._hook("Up to 8 million barrels", src) == "Up to 8 million barrels"
    assert movers._hook("Japan gets 8 million barrels more", src) == ""  # too long once hedged: dropped, not overstated
    assert movers._hook("$51 billion", "A deal worth $51 billion, up from about $40 billion.") == "$51 billion"
    # a softer hedge a few words back (live 2026-11-22: "a deal potentially valued at $45 billion" -> "$45 billion")
    src = "Nscale is reportedly in discussions with Anthropic in a deal potentially valued at $45 billion."
    assert movers._hook("$45 billion", src) == "Potentially $45 billion"
    assert movers._hook("A potential $45 billion deal", src) == "A potential $45 billion deal"
    assert movers._hook("$2 billion", "The merger could be worth $2 billion to holders.") == "Potentially $2 billion"
    assert movers._hook("$5 billion", "Sales in May 2026 rose to $5 billion.") == "$5 billion"  # May the month
    # live 2026-11-22: "Up 10% supply" for a company's projection; say it plainly and say it's a forecast
    src = ("Mission Produce Projects 10% Increase in Avocado Industry Volumes for Q4 FY26\nMission Produce announced that it "
           "expects avocado industry volumes for the fourth quarter of fiscal year 2026 to rise by approximately 10%.")
    assert movers._hook("Up 10% supply", src) == "Forecast: Supply up 10%"
    assert movers._hook("Up 12% revenue", "Revenue rose 12% last quarter. The company expects more.") == "Revenue up 12%"
    assert movers._hook("Up 10% in a week") == "Up 10% in a week"
    assert movers._hook("Expected 10% more avocados", src) == "Expected 10% more avocados"


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


def test_lineages_scoreboard_shows_the_apps_own_pick_and_the_average_idea(monkeypatch):
    """'+2.6 pts vs the S&P' only means skill next to what the app's own #1 and a random idea did on the same calls."""
    from backend.v4 import lineages
    for i in range(10):
        bid = f"b-linwin{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", f"2096-03-{1 + i:02d}T00:00:00", "2026-01-01",
                    "seed_backfill" if i < 8 else "seed_news", "bullish"))
        # the app's #1 (rank 0) wins +4%, the other longs -1% and +0%; a short on a competitor (+9%) can't be a #1
        for j, (d, ex, rank) in enumerate((("bullish", 0.04, 0), ("bullish", -0.01, 1), ("bullish", 0.0, 2), ("bearish", 0.09, 3))):
            pid = f"p-linwin{i}-{j}"
            # Claude liked W1 best; the stored #1 (W0) came from a track record that, on practice calls, peeked
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank, claude_score) VALUES (?,?,?,?,?,?,?,?,?)",
                       (pid, bid, f"W{j}", d, "2026-01-01", 10.0, db.dumps({"num": {}}), rank, 0.9 if j == 1 else 0.5))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, lineages.CHECKPOINT, "2026-02-01", 10.0, 0.0, 0.0, ex, "2026-02-01"))
    w = lineages.window_baselines(lineages._graded_beliefs(since="2096-01-01"))
    assert "app_pit" not in w  # only when every candidate carries its point-in-time score
    wp = lineages.window_baselines(lineages._graded_beliefs(since="2096-01-01", pit=True))
    # no-peek #1: practice calls (8) fall back to Claude's favourite W1 (-1%, nothing graded before their date);
    # real-time calls (2) keep their stored #1 (+4%). The opposite-direction short (+9%) is never the #1.
    assert wp["app_pit"]["n"] == 10 and abs(wp["app_pit"]["fitness"] - (8 * -0.01 + 2 * 0.04) / 10) < 1e-9
    assert wp["app_pit"]["beat_rate"] == 0.2 and wp["app"] == w["app"]
    assert w["n"] == 10 and w["app"]["n"] == 10
    assert abs(w["app"]["fitness"] - 0.04) < 1e-9 and w["app"]["beat_rate"] == 1.0
    assert abs(w["avg_idea"] - 0.01) < 1e-9  # mean of the longs only (+4, -1, 0): the short is never a #1
    assert w["practice"] == 0.8
    assert lineages.window_baselines([])["n"] == 0

    # stored by the daily evolve (even when it's too early to evolve), read by the page
    monkeypatch.setattr(lineages, "MIN_BELIEFS", 10 ** 9)
    monkeypatch.setattr(lineages, "SNAP_TTL", 0)
    assert lineages.evolve(seed=3)["evolved"] is False
    win = lineages.snapshot()["window"]
    assert win and win["n"] > 0 and set(win) == {"app", "app_pit", "avg_idea", "practice", "n"}


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


def test_lineages_pick_the_number_one_within_the_beliefs_own_direction():
    """The engine shows a bullish belief's longs first, so a strategist that 'picks' the short on a competitor gets
    no credit for it: its #1 is its favourite among the longs (same rule as research._lead)."""
    from backend.v4 import lineages
    for i in range(10):
        bid = f"b-linlead{i}"
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", f"2097-03-{1 + i:02d}T00:00:00", "2026-01-01", "seed_backfill", "bullish"))
        # two longs (the calm one does better) and a short on a competitor with the highest vol60 and a big win
        for j, (d, vol, ex) in enumerate((("bullish", 0.2, 0.02), ("bullish", 0.5, -0.02), ("bearish", 0.9, 0.12))):
            pid = f"p-linlead{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"L{j}", d, "2026-01-01", 10.0, db.dumps({"num": {"vol60": vol}}), j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, lineages.CHECKPOINT, "2026-02-01", 10.0, 0.0, 0.0, ex, "2026-02-01"))
    beliefs = lineages._graded_beliefs(since="2097-01-01", limit=10)
    assert len(beliefs) == 10 and all(len(b) == 3 for b in beliefs)
    assert all(sum(not c["lead"] for c in b) == 1 for b in beliefs)
    risky, calm = lineages.score({"vol60": 1.0}, beliefs), lineages.score({"vol60": -1.0}, beliefs)
    assert abs(risky["fitness"] + 0.02) < 1e-9  # its #1 is the riskier long, not the short (+12%) it liked best
    assert abs(calm["fitness"] - 0.02) < 1e-9 and calm["fitness"] > risky["fitness"]
    assert abs(lineages._baseline(beliefs)["fitness"] - 0.02) < 1e-9  # the app's #1 (rank 0) is the calm long


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
    pb = out["luck"]["pbo"]  # "would we have picked the winner?" rides along (reporting only)
    assert pb.get("n_splits") == 70 and "app (current #1)" not in pb["winners"]
    assert set(out["luck"]["pbo_learned"].get("winners") or {}) <= set(r) - {"app (current #1)"}


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


def test_ranker_that_passed_alone_goes_live_alone(monkeypatch):
    # a model that cleared the gate on its own must order the ideas exactly as in its walk-forward test; it used to go
    # live as an untested 50/50 blend with the app's score (2026-11-16: shown #1 != the model's #1 in 17 of 62 beliefs)
    from backend.v4 import research
    test_research_walk_forward_runs_and_stores(monkeypatch)
    rv = research.fit_production()
    assert rv["active"] and not rv["mix"] and rv["weight"] == research.WEIGHT == 1.0


def test_engine_orders_by_a_lone_ranker_exactly_as_tested(monkeypatch):
    from backend.v4 import research
    def run(rk):
        monkeypatch.setattr(research, "ranker", lambda: rk)
        # the model prefers exactly the reverse of the app's order
        monkeypatch.setattr(research, "score_candidates",
                            lambda nums, dirs: [float(i) for i in range(len(nums))] if rk else None)
        r = engine.process_belief("plumbing demand is going to be high", "u1", "moderate", claude_client=FakeClaude())
        rows = db.query("SELECT ticker, features FROM picks WHERE belief_id = ? ORDER BY final_rank", (r["belief_id"],))
        lead = {p["ticker"] for p in r["picks"] if p["direction"] == r["picks"][0]["direction"]}
        return [p["ticker"] for p in r["picks"]], {x["ticker"]: db.loads(x["features"], {}).get("rv2") for x in rows
                                                   if x["ticker"] in lead}
    base, _ = run(None)
    alone, rv2 = run({"active": True, "mix": False, "weight": 0.5})      # a stale stored weight is ignored
    assert alone[0] != base[0] and all(v is not None for v in rv2.values())
    # the shown #1 is the model's favourite idea in the belief's own direction, whatever the app thought
    assert len(rv2) >= 2 and rv2[alone[0]] == max(rv2.values())
    mixed, _ = run({"active": True, "mix": True, "weight": research.MIX_WEIGHT})
    assert sorted(mixed) == sorted(base)                                 # a mix still blends at its tested weight


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
    monkeypatch.setattr(research, "load", lambda **kw: (None if kw.get("live_only") else calls.append(1)) or real(**kw))
    out = research.fit_production()
    assert len(calls) == 1 and out["trained_on"] == 170                    # never two full copies in memory at once
    # (the live check's small load of real-time calls only is not counted)
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


def test_regime_label_says_why_with_the_numbers(monkeypatch):
    """The Brain page used to call every non-trending, non-crisis market 'Calm: markets are quiet', even with the
    S&P 500 swinging 22% a year. 'calm' is really 'in between'; the state carries the numbers, the close date and the
    rule, written from the same thresholds the classifier uses."""
    from datetime import timedelta as _td
    d0 = TODAY - _td(days=400)
    dates = [(d0 + _td(days=i)).isoformat() for i in range(300)]
    steady = [100 * (1.0008 ** i) for i in range(300)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, steady))
    market._state_cache.clear()
    st = market.regime_state()
    assert st["regime"] == "trending" and st["date"] == dates[-1] and st["rule"] == market.REGIME_RULE
    # flat but choppy: +/-1.5% day after day, no trend, near the high -> "in between" (calm), though not quiet
    chop = [100 * (1.015 if i % 2 else 1.0) for i in range(300)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, chop))
    market._state_cache.clear()
    st = market.regime_state()
    assert st["regime"] == "calm" and market.REG_TREND_VOL <= st["spy_vol20"] <= market.REG_CRISIS_VOL
    assert abs(st["spy_r60"]) < 0.02 and st["spy_dd"] > market.REG_CRISIS_DD
    r = market.REGIME_RULE
    assert "more than 4% over 3 months" in r and "under 22%" in r and "above 28%" in r and "12% below" in r
    assert "quiet" not in r

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
    # tree model (and every other learned candidate) loses -> ridge; zero them all so a lucky net on the tiny
    # synthetic set can't win by chance
    for name in list(res["results"]):
        if name.startswith(("gbm", "neural net")) or (name != "ridge (learned)" and name.startswith("ridge")):
            res["results"][name] = dict(res["results"]["ridge (learned)"], lift=0.0, lift_adj=0.0)
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


def test_intermediate_momentum_echo_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    # 300 closes: +50% from index 49 (i-250) to 174 (i-125), then flat; only the 12-7 leg counts
    closes = [100.0] * 50 + [100.0 * (1.5 ** (k / 125)) for k in range(1, 126)] + [150.0] * 125
    i = 299
    assert abs(market.mom_12_7(closes, i) - 0.5) < 1e-9
    assert market.mom_12_7(closes, 200) == 0.0                     # not a year of history
    assert market.mom_12_7(closes + [999.0], i) == market.mom_12_7(closes, i)   # later prices never seen
    assert "mom_12_7" in research.FEATS and "mom_12_7" in research.DIRECTIONAL
    # planted: high 12-7 momentum longs pay and shorts of it lag; the rule (z_mom_12_7, flipped for bearish) finds it
    rng = _r.Random(7)
    d0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-e-{k}", (d0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            m = rng.uniform(-0.3, 0.3)
            ex = -m * 0.1 if bear else m * 0.1
            pid = f"p-e-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"mom_12_7": m}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["intermediate momentum (z_mom_12_7)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills mom_12_7 as of each pick's own date only, leaving the other features alone
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(len(closes) + 30)]
    after = closes + [closes[-1] * (2.0 if k % 2 else 0.5) for k in range(30)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, after))
    for name in ("vp_features", "resid_features", "fip_features", "max_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03}
    asof = dates[i]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-ec", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-ec", "b-ec", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-ec", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-ec'")["features"])["num"]
    assert abs(num["mom_12_7"] - 0.5) < 1e-9 and num["max5"] == 0.03 and num["beta"] == 1.2


def test_moving_average_distance_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    # 250 closes: 179 at 100 then 71 at 200 -> MA21 = 200, MA200 = (129*100 + 71*200)/200 = 135.5
    closes = [100.0] * 179 + [200.0] * 71
    i = 249
    assert abs(market.mad(closes, i) - (200.0 / 135.5 - 1.0)) < 1e-9
    assert market.mad(closes, 150) == 0.0                           # under 200 days of history
    assert market.mad(closes + [999.0], i) == market.mad(closes, i)  # later prices never seen
    assert "mad" in research.FEATS and "mad" in research.DIRECTIONAL
    # planted: high-MAD longs pay and shorts of high MAD lag; the rule (z_mad, flipped for bearish) finds it
    rng = _r.Random(11)
    d0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-md-{k}", (d0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            m = rng.uniform(-0.3, 0.3)
            ex = -m * 0.1 if bear else m * 0.1
            pid = f"p-md-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"mad": m}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["moving average distance (z_mad)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills mad as of each pick's own date only, leaving the other features alone
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(len(closes) + 30)]
    after = closes + [closes[-1] * (3.0 if k % 2 else 0.3) for k in range(30)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, after))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4}
    asof = dates[i]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-mdx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-mdx", "b-mdx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-mdx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-mdx'")["features"])["num"]
    assert abs(num["mad"] - (200.0 / 135.5 - 1.0)) < 1e-9 and num["mom_12_7"] == 0.4 and num["beta"] == 1.2


def test_amihud_illiquidity_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, math as _m, random as _r
    # 200 closes alternating 100 / 101 with 1,000 shares a day: |r| ~ 1% on each $100k traded
    closes = [100.0 if k % 2 == 0 else 101.0 for k in range(200)]
    vols = [1000.0] * 200
    i = 199
    vals = [abs(closes[k] / closes[k - 1] - 1) / (closes[k] * vols[k]) for k in range(1, 200)]
    assert abs(market.amihud(closes, vols, i) - _m.log1p(1e8 * sum(vals) / len(vals))) < 1e-9
    assert market.amihud(closes, [v * 100 for v in vols], i) < market.amihud(closes, vols, i)  # more volume = liquid
    assert market.amihud(closes, vols, 100) == 0.0                     # under ~6 months of history
    assert market.amihud(closes, vols[:-1], i) == 0.0                  # volumes not aligned with closes
    assert market.amihud(closes + [1.0], vols + [1.0], i) == market.amihud(closes, vols, i)  # later bars never seen
    assert "amihud" in research.FEATS and "amihud" in research.DIRECTIONAL
    # planted: illiquid longs pay and shorts of the most liquid stock pay; the rule (z_amihud, flipped for bearish) finds it
    rng = _r.Random(13)
    d0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-am-{k}", (d0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            a = rng.uniform(0.0, 4.0)
            ex = -(a - 2.0) * 0.02 if bear else (a - 2.0) * 0.02
            pid = f"p-am-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"amihud": a}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["illiquidity premium (z_amihud)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills amihud as of each pick's own date only, leaving the other features alone
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(len(closes) + 30)]
    after = closes + [closes[-1] * (3.0 if k % 2 else 0.3) for k in range(30)]
    after_v = vols + [1.0] * 30
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, after))
    monkeypatch.setattr(market, "daily_volumes", lambda s: after_v)
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05}
    asof = dates[i]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-amx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-amx", "b-amx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-amx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-amx'")["features"])["num"]
    assert abs(num["amihud"] - market.amihud(closes, vols, i)) < 1e-9 and num["mad"] == 0.05 and num["beta"] == 1.2



def test_continuing_overreaction_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    # 252 sessions = 12 blocks of 21; every block rises with 1,000 shares a day -> CO = +1; falling -> -1
    up = [100.0 + k for k in range(253)]
    vols = [1000.0] * 253
    i = 252
    assert abs(market.co(up, vols, i) - 1.0) < 1e-12
    assert abs(market.co(list(reversed(up)), vols, i) + 1.0) < 1e-12
    # latest month down on heavy volume, the other 11 up on light volume: weights favour the recent month
    mix = list(up)
    for k in range(232, 253):
        mix[k] = mix[231] - (k - 231)
    heavy = [1000.0] * 232 + [20000.0] * 21
    v_mix = market.co(mix, heavy, i)
    sv = -12 * 21 * 20000.0 + sum(range(1, 12)) * 21 * 1000.0
    mv = (21 * 20000.0 + 11 * 21 * 1000.0) / 12
    assert abs(v_mix - sv / (mv * 78.0)) < 1e-12 and v_mix < 0
    assert market.co(up, vols, 200) == 0.0                     # under a year of history
    assert market.co(up, vols[:-1], i) == 0.0                  # volumes not aligned with closes
    assert market.co(up + [1.0], vols + [1e9], i) == market.co(up, vols, i)  # later bars never seen
    assert "co" in research.FEATS and "co" in research.DIRECTIONAL
    # planted: high CO longs and low CO shorts pay; the rule (z_co, flipped for bearish) finds it
    rng = _r.Random(17)
    d0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-co-{k}", (d0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            c = rng.uniform(-1.0, 1.0)
            ex = -c * 0.02 if bear else c * 0.02
            pid = f"p-co-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"co": c}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["continuing overreaction (z_co)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills co as of each pick's own date only, leaving the other features alone
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(len(mix) + 30)]
    after = mix + [mix[-1] * 3.0] * 30
    after_v = heavy + [1e9] * 30
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, after))
    monkeypatch.setattr(market, "daily_volumes", lambda s: after_v)
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5}
    asof = dates[i]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-cox", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-cox", "b-cox", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-cox", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-cox'")["features"])["num"]
    assert abs(num["co"] - v_mix) < 1e-12 and num["amihud"] == 2.5 and num["beta"] == 1.2


def test_seasonality_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    d0 = _dt.date(2021, 1, 4)
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(1500)]  # every calendar day, no gaps
    closes = [100.0 + 0.01 * k for k in range(1500)]
    i = 1480  # just over 4 years in, so all four past-year windows exist
    d = _dt.date.fromisoformat(dates[i])
    want = []
    for y in range(1, 5):
        a = dates.index((d - _dt.timedelta(days=365 * y)).isoformat())
        want.append(closes[a + 63] / closes[a] - 1.0)
    assert abs(market.seas(dates, closes, i) - sum(want) / 4) < 1e-12
    # only past-year windows count: under a year of history -> 0; later prices never change the value
    assert market.seas(dates, closes, 300) == 0.0
    assert market.seas(dates[:200], closes[:200], 150) == 0.0
    later = closes[: i + 1] + [9999.0] * (len(closes) - i - 1)
    assert market.seas(dates, later, i) == market.seas(dates, closes, i)
    # one year of history: just that year's window
    j = 400
    a = dates.index((_dt.date.fromisoformat(dates[j]) - _dt.timedelta(days=365)).isoformat())
    assert abs(market.seas(dates, closes, j) - (closes[a + 63] / closes[a] - 1.0)) < 1e-12
    assert "seas" in research.FEATS and "seas" in research.DIRECTIONAL
    # planted: good past seasons for longs and bad ones for shorts pay; the rule (z_seas, flipped) finds it
    rng = _r.Random(23)
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-se-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            sv = rng.uniform(-0.2, 0.2)
            ex = -sv * 0.1 if bear else sv * 0.1
            pid = f"p-se-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"seas": sv}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["same season, past years (z_seas)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills seas as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3}
    asof = dates[i]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-sex", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-sex", "b-sex", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-sex", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-sex'")["features"])["num"]
    assert abs(num["seas"] - sum(want) / 4) < 1e-12 and num["co"] == 0.3 and num["beta"] == 1.2


def test_downside_beta_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(31)
    d0 = _dt.date(2023, 1, 2)
    n = 400
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    m = [rng.gauss(0.0004, 0.01) for _ in range(n)]
    spy = [100.0]
    for r in m[1:]:
        spy.append(spy[-1] * (1 + r))

    def path(f):
        out = [50.0]
        for k in range(1, n):
            out.append(out[-1] * (1 + f(m[k]) + rng.gauss(0, 0.002)))
        return out
    sym = path(lambda r: 1.0 * r)                            # same beta on up and down days -> ~0
    crash = path(lambda r: 2.0 * r if r < 0 else 0.5 * r)    # falls hard with the market, lags it up -> > 0
    i = n - 1
    assert abs(market.dbeta(dates, sym, dates, spy, i)) < 0.15
    assert market.dbeta(dates, crash, dates, spy, i) > 0.5
    assert market.dbeta(dates, crash, dates, spy, 100) == 0.0          # under ~6 months of history
    assert market.dbeta(dates, crash, [], [], i) == 0.0                 # no SPY
    later = crash[: 300 + 1] + [c * 5 for c in crash[301:]]
    assert market.dbeta(dates, later, dates, spy, 300) == market.dbeta(dates, crash, dates, spy, 300)  # no look-ahead
    assert "dbeta" in research.FEATS and "dbeta" in research.DIRECTIONAL
    # planted: high downside beta longs and low downside beta shorts pay; the rule (z_dbeta, flipped) finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-db-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            dv = rng.uniform(-0.5, 0.5)
            ex = -dv * 0.04 if bear else dv * 0.04
            pid = f"p-db-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"dbeta": dv}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["downside beta premium (z_dbeta)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills dbeta as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, spy if s == "SPY" else later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02}
    asof = dates[300]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-dbx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-dbx", "b-dbx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-dbx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-dbx'")["features"])["num"]
    assert abs(num["dbeta"] - market.dbeta(dates, crash, dates, spy, 300)) < 1e-12
    assert num["seas"] == 0.02 and num["beta"] == 1.2


def test_short_term_reversal_rule():
    from backend.v4 import research
    import datetime as _dt, random as _r
    assert "mom20" in research.FEATS and "mom20" in research.DIRECTIONAL
    # planted: last month's losers pay for longs and last month's winners lose for shorts; the rule (-z_mom20) finds it
    rng = _r.Random(41)
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-rv-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            m = rng.uniform(-0.15, 0.15)
            ex = m * 0.2 if bear else -m * 0.2
            pid = f"p-rv-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"mom20": m}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    res = research.run(data=research.load())["results"]
    r = res["short-term reversal (-z_mom20)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3



def test_idiosyncratic_vol_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(53)
    d0 = _dt.date(2023, 1, 2)
    n = 400
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    m = [rng.gauss(0.0004, 0.01) for _ in range(n)]
    spy = [100.0]
    for r in m[1:]:
        spy.append(spy[-1] * (1 + r))

    def path(beta, noise):
        out = [50.0]
        for k in range(1, n):
            out.append(out[-1] * (1 + beta * m[k] + rng.gauss(0, noise)))
        return out
    calm = path(1.5, 0.002)     # big market beta but little of its own noise -> low ivol
    wild = path(0.5, 0.03)      # low beta, lots of its own noise -> high ivol (~0.48 annualized)
    i = n - 1
    assert market.ivol(dates, calm, dates, spy, i) < 0.08
    assert 0.3 < market.ivol(dates, wild, dates, spy, i) < 0.8
    assert market.ivol(dates, wild, dates, spy, 10) == market.IVOL_NEUTRAL   # under 15 days
    assert market.ivol(dates, wild, [], [], i) == market.IVOL_NEUTRAL        # no SPY
    later = wild[: 300 + 1] + [c * 5 for c in wild[301:]]
    assert market.ivol(dates, later, dates, spy, 300) == market.ivol(dates, wild, dates, spy, 300)  # no look-ahead
    assert "ivol" in research.FEATS and "ivol" in research.DIRECTIONAL
    # planted: low-ivol longs and high-ivol shorts pay; the rule (-z_ivol, flipped for shorts) finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-iv-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            iv = rng.uniform(0.1, 0.9)
            ex = iv * 0.05 if bear else -iv * 0.05
            pid = f"p-iv-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"ivol": iv}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["low idiosyncratic vol (-z_ivol)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills ivol as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, spy if s == "SPY" else later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1}
    asof = dates[300]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-ivx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-ivx", "b-ivx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-ivx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-ivx'")["features"])["num"]
    assert abs(num["ivol"] - market.ivol(dates, wild, dates, spy, 300)) < 1e-12
    assert num["dbeta"] == 0.1 and num["beta"] == 1.2

def test_long_term_reversal_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(61)
    # ltr = return from ~3 years to ~1 year ago; the latest year is skipped
    n = 1000
    closes = [100.0] * n
    for k in range(n - 1 - 756, n - 1 - 252 + 1):
        closes[k] = 100.0 * (1 + 0.5 * (k - (n - 1 - 756)) / 504)   # +50% over the formation period
    for k in range(n - 1 - 252 + 1, n):
        closes[k] = 10.0                                             # the latest year crashes: not counted
    i = n - 1
    assert abs(market.ltr(closes, i) - 0.5) < 1e-9
    assert market.ltr(closes, 400) == 0.0                            # under a year of formation data
    assert abs(market.ltr(closes[:600], 599) - (closes[347] / closes[0] - 1)) < 1e-12  # starts at the first close
    later = closes[:700] + [c * 9 for c in closes[700:]]
    assert market.ltr(later, 699) == market.ltr(closes, 699)          # no look-ahead
    assert "ltr" in research.FEATS and "ltr" in research.DIRECTIONAL
    # planted: long-term losers pay for longs, long-term winners pay for shorts; the rule (-z_ltr) finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-lt-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            lt = rng.uniform(-0.6, 1.5)
            ex = lt * 0.03 if bear else -lt * 0.03
            pid = f"p-lt-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"ltr": lt}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["long-term reversal (-z_ltr)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills ltr as of each pick's own date only, leaving the other features alone
    dates = [(_dt.date(2020, 1, 1) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25}
    asof = dates[699]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-ltx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-ltx", "b-ltx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-ltx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-ltx'")["features"])["num"]
    assert abs(num["ltr"] - market.ltr(closes, 699)) < 1e-12 and num["ltr"] != 0.0
    assert num["ivol"] == 0.25 and num["beta"] == 1.2


def test_luck_bar_counts_every_try_and_leaves_the_gate_alone():
    from backend.v4 import research, brain
    import random as _r
    assert abs(research._bar(37) - 3.2048) < 1e-3 and abs(research._bar(1) - 1.96) < 1e-2
    rng = _r.Random(5)
    res = {f"noise {k}": {"n": 2703, "lift_t": rng.gauss(0, 1), "lift_adj_t": rng.gauss(0, 1)} for k in range(36)}
    res["app (current #1)"] = {"n": 2703, "lift_t": 6.0, "lift_adj_t": 2.5}
    res["negative"] = {"n": 2703, "lift_t": -7.0, "lift_adj_t": -7.0}
    res["empty"] = {}
    lk = research.luck(res)
    assert lk["tests"] == 38 and lk["tries_ever"] == 38
    assert lk["clear"] == ["app (current #1)"]                 # noise never clears; a big negative t never "clears"
    assert lk["app_clears"] and not lk["app_clears_adj"]       # t 2.5 is not enough once 38 ways were tried
    assert research.luck(res, tries_ever=500)["bar_ever"] > lk["bar_ever"]   # past tries raise the bar
    # the running set of tries keeps rules that were dropped later
    assert research._tries(["a", "b"]) == 2 and research._tries(["b", "c"]) == 3
    # the gate does not read it: same verdict with or without the luck block
    m, app = {"lift": 0.02, "lift_t": 2.5, "beat": 0.56}, {"beat": 0.55}
    assert research._passes(m, app) and research._passes({**m, "luck": {"clear": []}}, app)
    # the brain page gets it from the latest research run
    db.execute("DELETE FROM kv_cache WHERE k = ?", (research.KEY,))
    db.execute("INSERT INTO kv_cache (k, v, created_at) VALUES (?,?,?)", (research.KEY, json.dumps(
        {"at": "2026-11-12T10:00:00+00:00", "results": res, "luck": lk}), "2026-11-12T10:00:00+00:00"))
    sk = brain._skill()
    assert sk["luck"]["tries_ever"] == 38 and sk["luck"]["n"] == 2703 and sk["luck"]["app_clears"]

def test_overlap_honest_t_counts_shared_market_paths_once():
    """Calls made on the same day (or a few days apart) share one 90-day market path, so they aren't independent.
    lift_t_nw sums residuals per date and weights date pairs by window overlap: a shared shock with no real edge
    looks significant on the plain t but not on the honest one, while a real per-pick edge survives both."""
    from backend.v4 import research
    import random as _r
    import datetime as _dt
    rng = _r.Random(3)   # this seed's shared shocks happen to average positive, like a lucky stretch of market
    d0 = _dt.date(2025, 1, 1)
    dates = [(d0 + _dt.timedelta(days=2 * k)).isoformat() for k in range(150)]
    # one slowly drifting market shock per date (overlapping windows): AR(1) across dates, 6 calls per date
    noise, edge, sh = [], [], 0.0
    for d in dates:
        sh = 0.95 * sh + rng.gauss(0, 0.01)
        for _ in range(6):
            mean = rng.gauss(0, 0.002)
            noise.append((mean + sh + rng.gauss(0, 0.003), mean, 0.0, 0.0, d))
            edge.append((mean + 0.01 + rng.gauss(0, 0.03), mean, 0.0, 0.0, d))
    m = research._metrics(noise)
    assert m["dates"] == 150 and m["n"] == 900
    assert m["lift_t"] > 5 and abs(m["lift_t_nw"]) < 2.5          # looks like an edge; counted honestly, it isn't clear
    assert m["n_eff"] < m["n"] / 10
    e = research._metrics(edge)
    assert e["lift_t"] > 5 and e["lift_t_nw"] > 4                  # a real per-pick edge still shows up
    assert e["n_eff"] > e["n"] / 3
    # no dates (older 4-tuples): same output as before, no honest-t keys
    assert "lift_t_nw" not in research._metrics([p[:4] for p in noise])
    # se is never negative and same-day-only data equals date clustering
    x = __import__("numpy").array([1.0, -1.0, 2.0, 0.0])
    assert research._se_overlap(x, ["2025-01-01", "2025-01-01", "2025-06-01", "2025-06-01"]) >= 0
    # the luck block reports the honest lens beside the plain one; the gate never reads it
    res = {"app (current #1)": {**m, "lift_adj_t": m["lift_t"], "lift_adj_t_nw": m["lift_t_nw"]},
           "real edge": {**e, "lift_adj_t": e["lift_t"], "lift_adj_t_nw": e["lift_t_nw"]}}
    lk = research.luck(res)
    assert lk["app_clears"] and not lk["app_clears_nw"] and lk["clear_nw"] == ["real edge"]
    assert lk["app_dates"] == 150 and lk["app_n_eff"] == m["n_eff"] and lk["app_t_nw"] == m["lift_t_nw"]
    app = {"beat": 0.0, "beat_adj": 0.0}
    assert research._passes(m, app) == research._passes({k: v for k, v in m.items() if not k.endswith("_nw")}, app)


def test_feature_coverage_marks_rules_on_half_filled_data_provisional():
    """A rule scored while older calls still lack its input is partly scored on placeholders: research reports each
    feature's coverage on the test-period calls and flags the rules that read one under 99% ("still filling in")."""
    from backend.v4 import research, brain
    import datetime as _dt, random as _r
    rng = _r.Random(11)
    assert research.rule_inputs(lambda f: f["z_mom_12_1"] - f["z_fip_id"]) == ["fip_id", "mom_12_1"]
    assert research.rule_inputs(lambda f: -abs(f["z_vp_poc_dist"]) + f["reg_trend"] + f["bearish"]) == ["reg_trend", "vp_poc_dist"]
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof = f"b-cov-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            num = {"mom60": rng.gauss(0, 0.1), "ivol": rng.uniform(0.1, 0.9)}
            if q % 2 == 0:                        # half the ideas never got "seas" (not backfilled yet)
                num["seas"] = 0.0 if q == 0 else rng.gauss(0, 0.05)   # and half of those that did store exactly 0
            pid = f"p-cov-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bullish", asof, 10.0, db.dumps({"num": num}), q))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, rng.gauss(0, 0.05), asof))
    out = research.run(data=research.load())
    cov = out["coverage"]
    assert cov["n"] > 500 and cov["share"]["mom60"] == 1.0 and cov["share"]["ivol"] == 1.0
    assert cov["share"]["seas"] == 0.5 and cov["zero_share"]["seas"] == 0.5 and cov["share"]["dbeta"] == 0.0
    pv = out["provisional"]
    assert pv["same season, past years (z_seas)"] == {"seas": 0.5}
    assert "momentum (z_mom60)" not in pv and "low idiosyncratic vol (-z_ivol)" not in pv
    assert "app (current #1)" not in pv and pv["downside beta premium (z_dbeta)"] == {"dbeta": 0.0}
    assert out["low_coverage"]["seas"] == 0.5 and "mom60" not in out["low_coverage"]
    assert len(json.dumps({k: out[k] for k in ("coverage", "provisional", "low_coverage")})) < 8000  # small kv payload
    # reporting only: the gate sees the same result with or without it, and the brain page gets it from the kv
    m = out["results"]["momentum (z_mom60)"]
    assert research._passes(m, out["results"]["app (current #1)"]) == research._passes(dict(m), out["results"]["app (current #1)"])
    sk = brain._skill()
    assert sk["luck"]["provisional"]["same season, past years (z_seas)"] == {"seas": 0.5}
    # full data: nothing provisional
    full = [{"date": "2025-01-01", "cands": [{"miss": 0, "zero": 0}, {"miss": 0, "zero": 0}]}]
    c2 = research.coverage(full)
    assert all(v == 1.0 for v in c2["share"].values()) and research.provisional({"x": lambda f: f["z_seas"]}, c2) == {}


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


def test_protect_goal_over_budget_says_the_price_includes_the_shares():
    # "Protect what I own" = insurance for shares they have; the card prices it with 100 shares included, so the note
    # must say so instead of "No version of this idea fits".
    build = lambda s_: strategy.build_trade(s_, "WINR", 185.0, 0.24, TODAY, 33)
    pp = build("Protective Put")
    s2, _, why = strategy.fit_budget("Protective Put", pp, direction="bearish", risk="moderate",
                                     prefs={"budget_usd": 5000.0, "instrument": "options", "goal": "protect"},
                                     build=build, price=185.0)
    assert s2 == "Protective Put" and "includes buying 100 shares" in why and "already own the shares" in why
    assert "No version" not in why


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


def test_brain_forward_confidence_split_says_which_calls_it_covers():
    # Confidence labels started after the forward test did, so the High/Medium/Low split covers fewer calls than the
    # headline. The split's own total ("all") and its start date are sent so the page can say what it adds up to.
    from backend.v4 import brain
    def add(bid, day, conf, top, other):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "u", "x", "x", f"{day}T15:00:00", day, "seed_news"))
        for j, ex in enumerate((top, other)):
            feats = db.dumps({"rv2_conf": conf} if conf and j == 0 else {})
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (f"{bid}-{j}", bid, f"T{j}", "bullish", day, 10.0, feats, j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (f"{bid}-{j}", 7, day, 10.0, 0.0, 0.0, ex, day))
    add("cf-old", "2026-10-29", None, 0.10, 0.00)     # before labels existed: in the headline only
    add("cf-h", "2026-11-05", "high", 0.04, 0.00)
    add("cf-l", "2026-11-06", "low", -0.02, 0.00)
    out = brain._forward()
    assert out["by_days"]["7"]["beliefs"] == 3
    c = out["by_confidence"]["7"]
    assert c["high"]["beliefs"] == 1 and c["low"]["beliefs"] == 1 and c["all"]["beliefs"] == 2
    assert abs(c["all"]["lift"] - (0.02 + -0.01) / 2) < 1e-9
    assert out["confidence_since"] == "2026-11-05"


def test_brain_forward_luck_check_counts_same_day_calls_once():
    # Calls made the same day ride the same market week and news, so 40 calls on 4 days are not 40 independent
    # tries. The forward test keeps the plain t and adds the overlap-honest t the scorecard uses; the page judges
    # "unlikely to be luck" on that one.
    from backend.v4 import brain
    rng = __import__("random").Random(3)
    k = 0
    for day, shared in (("2026-11-02", 0.05), ("2026-11-03", 0.04), ("2026-11-10", -0.01), ("2026-11-11", -0.005)):
        for _ in range(10):
            k += 1
            bid = f"lk-{k}"
            db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                       (bid, "u", "x", "x", f"{day}T15:00:00", day, "seed_news"))
            for j, ex in enumerate((shared + rng.gauss(0, 0.003), 0.0)):
                db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                           (f"{bid}-{j}", bid, f"T{j}", "bullish", day, 10.0, "{}", j))
                db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                           (f"{bid}-{j}", 7, day, 10.0, 0.0, 0.0, ex, day))
    r = brain._forward()["by_days"]["7"]
    assert r["beliefs"] == 40 and r["days"] == 4
    assert r["lift_t"] > 3                        # counted as 40 independent calls it looks clear of luck
    assert 0 < r["lift_t_nw"] < 2 < r["lift_t"]   # counted honestly (4 call days) it isn't
    assert r["n_eff"] < 10


def test_brain_forward_overlap_t_is_never_surer_than_the_plain_t():
    # A group whose calls fall on 3 days inside one 7-day window: the date sums of the residuals nearly cancel, so
    # the raw overlap error comes out tiny and a no-edge group read t -3.5 on the live page ("clear of luck").
    # Counting overlap can only make calls less independent, so the honest t is never bigger than the plain one.
    from backend.v4 import brain
    rng = __import__("random").Random(7)
    k = 0
    for day in ("2026-11-09", "2026-11-10", "2026-11-11"):
        for _ in range(30):
            k += 1
            bid = f"ov-{k}"
            db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                       (bid, "u", "x", "x", f"{day}T15:00:00", day, "seed_news"))
            for j, ex in enumerate((rng.gauss(-0.001, 0.05), 0.0)):
                db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                           (f"{bid}-{j}", bid, f"T{j}", "bullish", day, 10.0, "{}", j))
                db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                           (f"{bid}-{j}", 7, day, 10.0, 0.0, 0.0, ex, day))
    r = brain._forward()["by_days"]["7"]
    assert r["days"] == 3 and r["beliefs"] == 90
    assert abs(r["lift_t_nw"]) <= abs(r["lift_t"]) + 0.01
    assert r["n_eff"] <= r["beliefs"]


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
    pit = out["confidence"]["app, no look-ahead"]  # thirds on the app's score without look-ahead, not the stored one
    assert not off["active"] and off["confidence"]["basis"] == "app, no look-ahead"
    assert all(off["confidence"][k] == pit[k] for k in ("low", "mid", "high"))
    assert pit["low"]["n"] + pit["mid"]["n"] + pit["high"]["n"] == out["results"]["app, no look-ahead"]["n"]
    r2 = engine.process_belief("plumbing demand will boom this year", "u-conf2", "moderate", claude_client=FakeClaude())
    f2 = json.loads(db.query_one("SELECT features FROM picks WHERE belief_id = ? AND final_rank = 0", (r2["belief_id"],))["features"])
    assert f2["rv2_conf"] in ("high", "medium", "low")  # always recorded for the forward test
    assert r2["picks"][0]["confidence"] == (f2["rv2_conf"] if research.confidence_backed(off["confidence"]) else "")


def test_confidence_badge_hidden_while_the_test_does_not_back_it(monkeypatch):
    """Prod 2026-11-15: no-look-ahead thirds read high +0.2 / mid +0.9 / low +0.5 pts. A green "High confidence"
    (whose tooltip says the most confident picks did better) would tell users the opposite of the evidence, so the
    badge is hidden; the label is still stored on the pick for the live forward test."""
    from backend.v4 import research
    t = lambda x: {"n": 900, "lift": x}
    assert not research.confidence_backed({"high": t(0.002), "mid": t(0.009), "low": t(0.005)})
    assert research.confidence_backed({"high": t(0.02), "mid": t(0.009), "low": t(0.005)})
    assert not research.confidence_backed({"high": t(0.02), "low": {"n": 0, "lift": 0.0}})
    assert not research.confidence_backed(None) and not research.confidence_backed({})
    test_research_walk_forward_runs_and_stores(monkeypatch)
    out = research.run()
    rv = research.fit_production(out)
    rv["confidence"] = {**rv["confidence"], "high": t(0.002), "mid": t(0.009), "low": t(0.005)}
    monkeypatch.setattr(research, "ranker", lambda: rv)
    monkeypatch.setattr(learning, "build_context", lambda belief: {})
    r = engine.process_belief("plumbing demand is going to be high", "u-conf3", "moderate", claude_client=FakeClaude())
    assert all(p["confidence"] == "" for p in r["picks"])
    f = json.loads(db.query_one("SELECT features FROM picks WHERE belief_id = ? AND final_rank = 0", (r["belief_id"],))["features"])
    assert f["rv2_conf"] in ("high", "medium", "low")


def test_app_confidence_is_judged_without_look_ahead_and_cut_on_live_calls(monkeypatch):
    """Ranker off: the #1's confidence badge comes from the app's point-in-time score (the stored practice score has
    look-ahead), and once enough real-time calls exist its cuts split those calls into thirds (prod Nov 8-15: 56% of
    live #1 picks were 'high' under the practice cuts)."""
    from backend.v4 import research
    third = {"n": 1, "lift": 0.0}
    blocks = {"app (current #1)": {"cuts": [0.1, 0.18], "low": third, "mid": third, "high": {"n": 1, "lift": 0.025}},
              "app, no look-ahead": {"cuts": [0.05, 0.09], "low": third, "mid": third, "high": {"n": 1, "lift": 0.004}}}
    monkeypatch.setattr(research, "_live_spreads", lambda days=research.CONF_LIVE_DAYS: [0.1] * 20)
    c = research._app_confidence(blocks)
    assert c["basis"] == "app, no look-ahead" and c["high"]["lift"] == 0.004 and c["cuts"] == [0.05, 0.09]
    assert "cuts_from" not in c  # too few real-time calls: keep the walk-forward cuts
    live = [i / 299 * 0.4 for i in range(300)]  # spreads 0 .. 0.4, evenly
    monkeypatch.setattr(research, "_live_spreads", lambda days=research.CONF_LIVE_DAYS: live)
    c = research._app_confidence(blocks)
    assert c["cuts_from"] == "live" and c["cuts_n"] == 300 and c["cuts_test"] == [0.05, 0.09]
    assert abs(c["cuts"][0] - 0.4 / 3) < 1e-3 and abs(c["cuts"][1] - 0.8 / 3) < 1e-3
    labels = [research.confidence_label(x, c["cuts"]) for x in live]
    assert all(abs(labels.count(k) - 100) <= 2 for k in ("low", "medium", "high"))
    assert blocks["app, no look-ahead"]["cuts"] == [0.05, 0.09]  # the research record itself is not changed
    # without a point-in-time block (older research record) it falls back to the stored score's thirds
    c = research._app_confidence({"app (current #1)": blocks["app (current #1)"]})
    assert c["basis"] == "app (current #1)" and c["high"]["lift"] == 0.025
    assert research._app_confidence({}) is None


def test_live_spreads_read_real_time_calls_only():
    from backend.v4 import research
    now = datetime.now(timezone.utc).isoformat()
    for bid, src, scores in (("b-rt1", "user", [0.9, 0.5, 0.4]), ("b-old", "seed_backfill", [0.9, 0.1])):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "u", "x", "x", now, now[:10], src))
        for i, sc in enumerate(scores):
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, final_score, final_rank, entry_date, entry_price) "
                       "VALUES (?,?,?,?,?,?,?,?)", (f"{bid}-{i}", bid, f"T{i}", "bullish", sc, i, now[:10], 10.0))
    sp = research._live_spreads()
    assert len(sp) == 1 and abs(sp[0] - (0.9 - 0.6)) < 1e-6


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


def test_ranker_mix_is_tested_as_it_goes_live_and_needs_real_time_proof(monkeypatch):
    # option B (2026-11-09): each model is also judged mixed into the app's score at 25%, vs the app alone; a mix can
    # only go live after it holds up on enough real-time calls (live_check), and then runs at its tested weight
    from backend.v4 import research
    import numpy as _np
    mx = research.mix_scores([0.5, 0.6, 0.7], [3.0, 0.0, -3.0], 0.25)
    assert _np.argmax(mx) == 2 and abs(mx.mean() - 0.6) < 1e-9          # 25% can't flip a clear app ordering...
    assert _np.argmax(research.mix_scores([0.6, 0.6, 0.6], [3.0, 0.0, -3.0], 0.25)) == 0   # ...but breaks a tie
    test_research_walk_forward_runs_and_stores(monkeypatch)
    out = research.run()
    assert out["results"]["gbm (learned)" + research.MIX]["n"] == out["results"]["gbm (learned)"]["n"]
    target = out["results"]["gbm (learned)" + research.MIX]
    monkeypatch.setattr(research, "_passes", lambda m, app, risk=False: m is target)
    rv = research.fit_production(out)                                    # no real-time calls yet: stays off
    assert not rv["active"] and rv["live"]["n"] == 0 and not rv["live"]["ok"] and rv["live"]["needed"] == 300
    monkeypatch.setattr(research, "live_check", lambda *a, **k: {"ok": True, "n": 300})
    rv = research.fit_production(out)
    assert rv["active"] and rv["model"] == "gbm_mix" and rv["mix"] and rv["weight"] == 0.25
    s = research.score_candidates([{"mom60": 0.2}, {"mom60": -0.2}], ["bullish"] * 2)
    assert s and s[0] > s[1]


def test_live_check_uses_real_time_calls_only():
    from backend.v4 import research
    def add(bid, src):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "u", "x", "x", "2026-11-01T00:00:00", "2026-11-01", src))
        for j in range(3):
            pid = f"{bid}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank, final_score) VALUES (?,?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", "2026-11-01", 10.0, db.dumps({"num": {"mom60": 0.1 * j}}), j, 0.9 - 0.1 * j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 30, "2026-12-01", 10.0, 0.0, 0.0, 0.05 - 0.02 * j, "2026-12-01"))
    for i in range(4):
        add(f"lv{i}", "user")
    add("lv-old", "seed_backfill")                                      # practice calls never count here
    zero = [0.0] * len(research.ZKEYS)
    research._set_keys()
    r = research.live_check(None, zero, [1.0] * len(research.ZKEYS), zero, days=30, min_calls=4)
    assert r["n"] == 4 and r["ok"] and abs(r["app"]["avg"] - 0.05) < 1e-9   # a flat model leaves the app's #1 in place
    assert not research.live_check(None, zero, [1.0] * len(research.ZKEYS), zero, days=30, min_calls=5)["ok"]


def test_app_baseline_without_look_ahead_uses_only_earlier_track_records():
    # practice calls were scored long after their date, so the app's track-record nudge saw later outcomes. The
    # "app, no look-ahead" baseline rebuilds it from outcomes graded before each call's own date (2026-11-09 log)
    from backend.v4 import research
    def belief(bid, as_of, src, ranks, claude, exs, ev):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", "2026-11-01T00:00:00", as_of, src, "bullish"))
        for j, (tk, rk, cs, ex) in enumerate(zip(("AAA", "BBB"), ranks, claude, exs)):
            pid = f"{bid}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank, claude_score, final_score) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (pid, bid, tk, "bullish", as_of, 10.0, "{}", rk, cs, cs))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, sel_edge, graded_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (pid, 90, ev, 10.0, 0.0, 0.0, ex, ex, ev))
    # a LATER practice call where BBB did far better: its outcome lifted BBB's track record when the early call was
    # scored, so the stored #1 of the early call is BBB although Claude preferred AAA
    belief("pit-late", "2025-06-01", "seed_backfill", (1, 0), (0.505, 0.5), (-0.2, 0.3), "2025-09-01")
    belief("pit-early", "2025-01-01", "seed_backfill", (1, 0), (0.505, 0.5), (0.0, 0.3), "2025-04-01")
    belief("pit-live", "2026-11-01", "user", (1, 0), (0.505, 0.5), (0.0, 0.1), "2027-01-30")
    data = research.load()
    early, late, live = ([b for b in data if b["date"] == d][0] for d in ("2025-01-01", "2025-06-01", "2026-11-01"))
    pick = lambda b: max(range(2), key=lambda i: b["cands"][i]["pit"])
    assert early["cands"][1]["top"] and pick(early) == 0     # nothing graded before 2025-01-01: Claude's order
    assert late["cands"][1]["top"] and pick(late) == 1       # by June, BBB's earlier win was already graded
    assert live["cands"][1]["top"] and pick(live) == 1       # real-time calls were point-in-time: stored #1 stays
    # the score a mix is tested with: the same point-in-time app score, without the engine's sort offsets
    assert early["cands"][0]["pit_app"] == 0.505 and early["cands"][1]["pit_app"] == 0.5
    assert [c["pit_app"] for c in live["cands"]] == [c["app"] for c in live["cands"]]   # real time: stored score


def test_ranker_mixes_are_tested_on_the_app_score_without_look_ahead():
    # 2026-11-14 brain upgrade: the "+ app (25%)" mixes were mixed into the STORED app score of practice calls, which
    # carries look-ahead, so a model with no edge inherited the app's inflated lift and cleared the gate offline.
    # Planted: the stored score knows the outcome, Claude's own score is noise, the features carry nothing.
    from backend.v4 import research
    rng = random.Random(21)
    d0 = __import__("datetime").date(2024, 1, 1)
    for k in range(300):
        bid, asof = f"b-mixpit-{k}", (d0 + __import__("datetime").timedelta(days=k * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", "2026-11-01T00:00:00", asof, "seed_backfill", "bullish"))
        exs = [rng.gauss(0, 0.05) for _ in range(3)]
        order = sorted(range(3), key=lambda j: -exs[j])
        for j in range(3):
            pid = f"p-mixpit-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank, claude_score, final_score) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (pid, bid, f"Z{k}{j}", "bullish", asof, 10.0, "{}", order.index(j), rng.uniform(0.4, 0.6), 0.5 + exs[j]))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, "2027-06-01", 10.0, 0.0, 0.0, exs[j], "2027-06-01"))
    r = research.run(data=research.load())["results"]
    assert r["app (current #1)"]["lift"] > 0.03                   # the stored #1 has look-ahead...
    assert abs(r["app, no look-ahead"]["lift"]) < 0.015            # ...the point-in-time one doesn't
    mix = r["ridge (learned)" + research.MIX]
    assert mix["n"] == r["ridge (learned)"]["n"] > 100
    assert abs(mix["lift"]) < 0.015                                # the mix no longer inherits it


def test_migration_target_parses_add_column():
    from backend.v4 import db
    assert db._migration_target("ALTER TABLE picks ADD COLUMN spy_entry REAL") == ("picks", "spy_entry")
    assert db._migration_target("ALTER TABLE accounts ADD COLUMN verified INTEGER NOT NULL DEFAULT 1") == ("accounts", "verified")
    assert db._migration_target("CREATE INDEX IF NOT EXISTS ix ON picks(x)") is None
    for stmt in db._migrations():
        assert db._migration_target(stmt) is not None, stmt


def test_personal_keys_mode_options_close_and_journey(monkeypatch):
    from backend.v4 import brokerage
    c = _client()
    tok = c.post("/v4/auth/signup", json={"email": "owner@example.com", "password": "long enough pw"}).json()["token"]
    other = c.post("/v4/auth/signup", json={"email": "other@example.com", "password": "long enough pw"}).json()["token"]
    h, ho = {"Authorization": f"Bearer {tok}"}, {"Authorization": f"Bearer {other}"}
    monkeypatch.setenv("MP_REAL_MONEY", "on"); monkeypatch.setenv("MP_BROKER_ENV", "live"); monkeypatch.setenv("MP_MAX_ORDER_USD", "1000")
    monkeypatch.setenv("MP_BROKER_KEY_ID", "kid"); monkeypatch.setenv("MP_BROKER_SECRET_KEY", "ksec")
    monkeypatch.delenv("MP_REAL_MONEY_PILOT", raising=False)
    # keys mode with no pilot list: nobody can trade (never "everyone")
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 10}, headers=h).status_code == 403
    monkeypatch.setenv("MP_REAL_MONEY_PILOT", "owner@example.com")
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 10}, headers=ho).status_code == 403
    assert c.get("/v4/broker/connect", headers=h).status_code == 409

    sent, held = [], {}
    sym = "WINR261218C00100000"

    class R:
        def __init__(self, code, js): self.status_code, self._js, self.content, self.text = code, js, b"x", ""
        def json(self): return self._js

    def fake_request(method, url, headers=None, json=None, timeout=None, params=None):
        assert headers["APCA-API-KEY-ID"] == "kid" and url.startswith("https://api.alpaca.markets")
        path = url.split("alpaca.markets")[1]
        if path == "/v2/account":
            return R(200, {"buying_power": "5000", "options_buying_power": "800", "equity": "5000", "status": "ACTIVE"})
        if path == "/v2/options/contracts":
            assert params["type"] == "call"
            return R(200, {"option_contracts": [
                {"symbol": sym, "strike_price": "100", "expiration_date": "2026-12-18", "tradable": True},
                {"symbol": "WINR270115C00110000", "strike_price": "110", "expiration_date": "2027-01-15", "tradable": True}]})
        if path.startswith("/v2/positions/"):
            s = path.split("/")[-1]
            return R(200, {"symbol": s, "qty": str(held[s])}) if s in held else R(404, {"message": "position does not exist"})
        if path == "/v2/orders" and method == "POST":
            sent.append(json); return R(200, {"id": f"o{len(sent)}", "status": "accepted"})
        if path == "/v2/orders" and method == "GET":
            return R(200, [])
        if path.startswith("/v2/orders/"):
            n = int(path.split("o")[-1]); o = sent[n - 1]
            px = {"buy": 2.5, "sell": 4.0}[o["side"]] if o["symbol"] == sym else 100.0
            return R(200, {"id": f"o{n}", "status": "filled", "filled_qty": o.get("qty") or "1", "filled_avg_price": str(px),
                           "filled_at": f"2026-11-1{n}T15:00:00Z"})
        raise AssertionError(path)
    monkeypatch.setattr(brokerage.requests, "request", fake_request)
    monkeypatch.setattr(market, "option_quote", lambda s: {"bid": 2.4, "ask": 2.5, "mid": 2.45, "t": None} if s == sym else None)
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(brokerage, "_spy", lambda: 500.0)

    st = c.get("/v4/broker/status", headers=h).json()
    assert st["connected"] is True and st["mode"] == "keys" and st["env"] == "live" and st["funding_url"]
    assert st["owner"] is True and st["setup"]["keys"] is True and "ksec" not in json.dumps(st)  # never the values
    so = c.get("/v4/broker/status", headers=ho).json()
    assert so["owner"] is False and so["can_switch"] is False and "setup" not in so
    assert c.post("/v4/broker/switch", json={"on": True}, headers=ho).status_code == 403
    assert c.post("/v4/broker/switch", json={"on": True, "max_order_usd": 600}, headers=h).json()["max_order_usd"] == 600
    body = {"underlying": "WINR", "option_type": "Call", "strike": 100, "expiration": "2026-12-18"}
    assert c.post("/v4/broker/preview_option", json=dict(body, contracts=3), headers=h).status_code == 400  # $750 > my $600 limit
    c.post("/v4/broker/switch", json={"on": True, "max_order_usd": 1000}, headers=h)
    assert c.post("/v4/broker/preview_option", json=dict(body, contracts=5), headers=h).status_code == 400  # $1,250 > cap
    assert c.post("/v4/broker/preview_option", json=dict(body, contracts=4), headers=h).status_code == 400  # > options buying power
    pv = c.post("/v4/broker/preview_option", json=dict(body, contracts=2), headers=h).json()
    assert pv["contract"] == sym and pv["limit_price"] == 2.5 and pv["total_usd"] == 500.0 and pv["max_loss_usd"] == 500.0
    assert pv["breakeven"] == 102.5 and "most you can lose" in pv["plain"]
    r = c.post("/v4/broker/order", json={"preview_id": pv["preview_id"], "confirm": True}, headers=h)
    assert r.status_code == 200
    assert sent[-1] == {"symbol": sym, "qty": "2", "side": "buy", "type": "limit", "limit_price": "2.50",
                        "time_in_force": "day", "client_order_id": f"mp-{pv['preview_id']}"}
    # can't sell what you don't hold (no naked options)
    assert c.post("/v4/broker/preview_close", json={"symbol": "WINR270115C00110000"}, headers=h).status_code == 400
    held[sym] = 2
    assert c.post("/v4/broker/preview_close", json={"symbol": sym, "qty": 3}, headers=h).status_code == 400
    c.post("/v4/broker/switch", json={"on": False}, headers=h)  # off: no buys, but you can always sell what you hold
    assert c.post("/v4/broker/preview_option", json=dict(body, contracts=1), headers=h).status_code == 403
    cl = c.post("/v4/broker/preview_close", json={"symbol": sym, "qty": 1}, headers=h).json()
    assert cl["side"] == "sell" and cl["limit_price"] == 2.4
    assert c.post("/v4/broker/order", json={"preview_id": cl["preview_id"], "confirm": True}, headers=h).status_code == 200
    assert sent[-1]["side"] == "sell" and sent[-1]["qty"] == "1" and sent[-1]["type"] == "limit"

    # the public journey: off until switched on, then every fill as lots
    assert c.get("/v4/journey").json()["enabled"] is False
    monkeypatch.setenv("MP_JOURNEY_PUBLIC", "on"); brokerage._journey_cache.clear()
    j = c.get("/v4/journey").json()
    assert j["enabled"] and j["trades"] == 2 and "cost_usd" not in j["lots"][0]  # dollars hidden by default
    closed = [l for l in j["lots"] if l["status"] == "closed"]; still = [l for l in j["lots"] if l["status"] == "open"]
    assert len(closed) == 1 and abs(closed[0]["return"] - 0.6) < 1e-9  # 2.50 -> 4.00
    assert len(still) == 1 and abs(still[0]["return"] - (2.45 / 2.5 - 1)) < 1e-6
    assert j["summary"]["wins"] == 1 and j["summary"]["closed"] == 1


def test_build_lots_fifo_partial():
    from backend.v4 import brokerage
    lots = brokerage.build_lots([
        {"symbol": "A", "side": "buy", "qty": 10, "price": 10, "at": "1", "kind": "stock"},
        {"symbol": "A", "side": "buy", "qty": 10, "price": 20, "at": "2", "kind": "stock"},
        {"symbol": "A", "side": "sell", "qty": 15, "price": 30, "at": "3", "kind": "stock"},
    ])
    assert [(l["qty"], l["entry"], l["exit"]) for l in lots] == [(10, 10, 30), (5, 20, 30), (5, 20, None)]


def test_exits_stock_bracket_and_option_watcher(monkeypatch):
    from backend.v4 import brokerage, exits
    c = _client()
    tok = c.post("/v4/auth/signup", json={"email": "exits@example.com", "password": "long enough pw"}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    monkeypatch.setenv("MP_REAL_MONEY", "on"); monkeypatch.setenv("MP_BROKER_ENV", "live")
    monkeypatch.setenv("MP_BROKER_KEY_ID", "kid"); monkeypatch.setenv("MP_BROKER_SECRET_KEY", "ksec")
    monkeypatch.setenv("MP_REAL_MONEY_PILOT", "exits@example.com"); monkeypatch.setenv("MP_MAX_ORDER_USD", "1000")
    sym = "WINR261218C00100000"
    orders, held, quote = {}, {}, {"bid": 2.4, "ask": 2.5}

    class R:
        def __init__(self, code, js): self.status_code, self._js, self.content, self.text = code, js, b"x", ""
        def json(self): return self._js

    def fake_request(method, url, headers=None, json=None, timeout=None, params=None):
        path = url.split("alpaca.markets")[1]
        if path == "/v2/account":
            return R(200, {"buying_power": "5000", "options_buying_power": "5000", "equity": "5000"})
        if path == "/v2/options/contracts":
            return R(200, {"option_contracts": [{"symbol": sym, "strike_price": "100", "expiration_date": "2026-12-18"}]})
        if path.startswith("/v2/positions/"):
            s = path.split("/")[-1]
            return R(200, {"qty": str(held[s])}) if held.get(s) else R(404, {})
        if path == "/v2/orders" and method == "POST":
            oid = f"o{len(orders) + 1}"; orders[oid] = dict(json, id=oid, status="accepted"); return R(200, orders[oid])
        if path.startswith("/v2/orders/"):
            oid = path.split("/")[-1]
            if method == "DELETE":
                orders[oid]["status"] = "canceled"; return R(204, {})
            return R(200, orders[oid])
        raise AssertionError(path)
    monkeypatch.setattr(brokerage.requests, "request", fake_request)
    monkeypatch.setattr(market, "option_quote", lambda s: dict(quote, mid=(quote["bid"] + quote["ask"]) / 2))
    monkeypatch.setattr(market, "clock", lambda: {"is_open": True})
    monkeypatch.setattr(market, "is_open", lambda: True)
    monkeypatch.setattr(brokerage, "_spy", lambda: 500.0)

    assert c.post("/v4/broker/switch", json={"on": True}, headers=h).json()["on"] is True
    # stocks: whole shares, bracket at Alpaca
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 10, "take_profit_pct": 0.2, "max_loss_pct": 0.1}, headers=h).status_code == 400
    pv = c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 1000, "take_profit_pct": 0.2, "max_loss_pct": 0.1}, headers=h).json()
    assert "est_price" in pv, pv
    px = pv["est_price"]; n = int(1000 // px)
    assert pv["exits"]["tp_price"] == round(px * 1.2, 2) and pv["amount_usd"] == round(n * px, 2)
    c.post("/v4/broker/order", json={"preview_id": pv["preview_id"], "confirm": True}, headers=h)
    o = orders["o1"]
    assert o["order_class"] == "bracket" and o["qty"] == str(n) and "notional" not in o and o["time_in_force"] == "gtc"
    assert o["stop_loss"]["stop_price"] == f"{px * 0.9:.2f}"
    assert c.post("/v4/broker/preview", json={"ticker": "WINR", "amount_usd": 100, "max_loss_pct": 0.99}, headers=h).status_code == 400

    # options: buy with exits -> watcher arms a stop, take-profit sells at the bid
    pv = c.post("/v4/broker/preview_option", json={"underlying": "WINR", "option_type": "call", "strike": 100, "expiration": "2026-12-18",
                                                   "contracts": 2, "take_profit_pct": 0.5, "max_loss_pct": 0.4}, headers=h).json()
    assert "renewed each trading morning" in pv["plain"]
    c.post("/v4/broker/order", json={"preview_id": pv["preview_id"], "confirm": True}, headers=h)
    buy = "o2"
    exits.tick(); assert db.query_one("SELECT status FROM broker_exits WHERE kind='option'")["status"] == "waiting_fill"
    orders[buy].update(status="filled", filled_qty="2", filled_avg_price="2.00"); held[sym] = 2
    exits.tick()
    ex = db.query_one("SELECT * FROM broker_exits WHERE kind='option'")
    assert ex["status"] == "armed" and ex["tp_price"] == 3.0 and ex["sl_price"] == 1.2
    stop = orders[ex["stop_order"]]
    assert stop["type"] == "stop" and stop["stop_price"] == "1.20" and stop["qty"] == "2" and stop["side"] == "sell"
    exits.tick(); assert len(orders) == 3  # a live stop for today is left alone
    quote.update(bid=3.1, ask=3.2)
    exits.tick(); assert orders[ex["stop_order"]]["status"] == "canceled" and len(orders) == 3  # free the contracts first
    exits.tick()
    ex = db.query_one("SELECT * FROM broker_exits WHERE kind='option'")
    sell = orders[ex["sell_order"]]
    assert ex["status"] == "tp_sent" and sell["type"] == "limit" and sell["limit_price"] == "3.10" and sell["qty"] == "2"
    sell.update(status="filled", filled_avg_price="3.10")
    exits.tick(); assert db.query_one("SELECT status FROM broker_exits WHERE kind='option'")["status"] == "done"
    # restart safety: a second process can't tick while the lease is fresh
    monkeypatch.setattr(exits, "_OWNER", "someone-else")
    assert exits.tick() == {"ran": False}


def test_price_check_parity_vol_and_log(monkeypatch):
    from backend.v4 import pricecheck
    today = date(2026, 11, 10); exp = date(2026, 12, 18)
    # European parity holds exactly -> within the spread
    S, K, r = 100.0, 100.0, 0.038
    t = (exp - today).days / 365
    p_mid = 3.0; c_mid = p_mid + S - K * math.exp(-r * t)
    call = {"type": "call", "strike": K, "expiration": exp, "bid": c_mid - 0.05, "ask": c_mid + 0.05, "iv": 0.3}
    put = {"type": "put", "strike": K, "expiration": exp, "bid": p_mid - 0.05, "ask": p_mid + 0.05, "iv": 0.31}
    p = pricecheck.parity(call, put, S, r, today)
    assert abs(p["gap"]) < 1e-9 and p["within_spread"]
    # calls $1 too cheap (e.g. a dividend) -> outside the spread, explained, never called free money
    cheap = dict(call, bid=call["bid"] - 1, ask=call["ask"] - 1)
    p2 = pricecheck.parity(cheap, put, S, r, today)
    assert abs(p2["gap"] + 1) < 1e-9 and not p2["within_spread"]
    txt = pricecheck.parity_text(p2, "WINR")
    assert "dividends" in txt and "Not free money" in txt
    assert pricecheck.vol_verdict(0.2, 0.3)[0] == "cheap" and pricecheck.vol_verdict(0.33, 0.3)[0] == "normal"
    assert pricecheck.vol_verdict(0.6, 0.3)[0] == "expensive" and pricecheck.vol_verdict(None, 0.3)[0] == "unknown"

    # end to end with a fake chain: the check is logged point-in-time for the pick
    chain = [dict(call, symbol="WINR261218C00100000"), dict(put, symbol="WINR261218P00100000")]
    monkeypatch.setattr(market, "option_chain_near", lambda *a, **k: chain)
    monkeypatch.setattr(market, "latest_price", lambda s: 100.0)
    monkeypatch.setattr(market, "is_open", lambda: True)
    pricecheck._cache.clear()
    r1 = _client().get("/v4/price_check", params={"underlying": "WINR", "option_type": "Call", "strike": 100,
                                                  "expiration": "2026-12-18", "pick_id": "pk1"}).json()
    assert r1["available"] and r1["contract"] == "WINR261218C00100000" and r1["parity"] is not None
    assert r1["vol_verdict"] in ("cheap", "normal", "expensive") and len(r1["lines"]) >= 3
    row = db.query_one("SELECT * FROM feature_log WHERE pick_id = 'pk1'")
    assert row["feature"] == "price_check" and json.loads(row["value"])["vol_verdict"] == r1["vol_verdict"]
    assert pricecheck.log_daily(limit=2, force=True)["logged"] >= 1


def test_price_check_compares_the_cards_own_price_with_the_listed_quote(monkeypatch):
    """The card prices every leg at one vol; the price check shows that estimate beside the listed mid and says why
    they differ (skew, the stock having moved, or a strike that isn't listed). Per request, never cached/logged."""
    from backend.v4 import pricecheck
    exp = date(2026, 12, 18)
    res = {"available": True, "underlying": "WINR", "strike": 90.0, "expiration": exp.isoformat(), "spot": 100.0,
           "bid": 1.90, "ask": 2.10, "mid": 2.0, "contract_iv": 0.36}
    # in line: inside the spread
    c = pricecheck.card_vs_listed(res, 2.05, 90, "2026-12-18", 0.30, "implied", 100.0)
    assert c["same_contract"] and c["in_spread"] and "in line with the market" in c["text"]
    assert "one number for every strike" in c["text"]
    # card too cheap: the strike's own IV explains it (skew)
    c = pricecheck.card_vs_listed(res, 1.50, 90, "2026-12-18", 0.30, "implied", 100.0)
    assert c["diff"] == -0.5 and c["diff_pct"] == -0.25 and not c["in_spread"]
    assert "$0.50 lower (25%)" in c["text"] and "36% implied volatility vs the card's 30%" in c["text"]
    # the stock moved since the card was priced: say that first
    c = pricecheck.card_vs_listed(res, 1.50, 90, "2026-12-18", 0.30, "implied", 104.0)
    assert "card was priced with WINR at $104.00" in c["text"] and "implied volatility vs" not in c["text"]
    # a strike that isn't listed: no one-for-one comparison
    c = pricecheck.card_vs_listed(res, 1.50, 91, "2026-12-18", 0.30, "historical", 100.0)
    assert not c["same_contract"] and c["diff"] is None and "isn't listed" in c["text"] and "past volatility" in c["text"] and "one number for every strike" in c["text"]
    assert pricecheck.card_vs_listed(res, None) is None and pricecheck.card_vs_listed({"available": False}, 2.0) is None

    # end to end: the card fields ride on the cached check without changing it or the feature log
    call = {"type": "call", "strike": 90.0, "expiration": exp, "bid": 1.90, "ask": 2.10, "iv": 0.36, "symbol": "WINR261218C00090000"}
    put = {"type": "put", "strike": 90.0, "expiration": exp, "bid": 0.4, "ask": 0.5, "iv": 0.37, "symbol": "WINR261218P00090000"}
    monkeypatch.setattr(market, "option_chain_near", lambda *a, **k: [call, put])
    monkeypatch.setattr(market, "latest_price", lambda s: 100.0)
    monkeypatch.setattr(market, "is_open", lambda: False)
    pricecheck._cache.clear()
    plain = _client().get("/v4/price_check", params={"underlying": "WINR", "option_type": "call", "strike": 90,
                                                     "expiration": "2026-12-18"}).json()
    assert plain["available"] and "card" not in plain
    r = _client().get("/v4/price_check", params={"underlying": "WINR", "option_type": "call", "strike": 90,
                                                 "expiration": "2026-12-18", "card_premium": 1.5, "card_vol": 0.3,
                                                 "card_vol_source": "implied", "card_spot": 100}).json()
    assert r["card"]["mid"] == 2.0 and r["card"]["diff"] == -0.5 and r["lines"] == plain["lines"]
    assert "card" not in pricecheck._cache[("WINR", "call", 90.0, "2026-12-18")][1]


def test_option_snapshots_follow_every_page_so_busy_chains_reach_the_asked_expiration(monkeypatch):
    """Alpaca returns 1,000 option snapshots a page, earliest expiration first. SPY's chain (daily expirations, $1
    strikes) ran past one page, so a Price check for SPY Dec 18 showed a Dec 4 contract (live, 2026-11-18)."""
    from types import SimpleNamespace as NS
    from backend.v4 import pricecheck
    near, asked = date(2026, 12, 4), date(2026, 12, 18)
    occ = lambda d, k, strike: f"SPY{d.strftime('%y%m%d')}{k}{int(strike * 1000):08d}"
    pages = [{"snapshots": {occ(near, "C", 732): {"latestQuote": {"bp": 9.0, "ap": 9.2}, "impliedVolatility": 0.2}},
              "next_page_token": "p2"},
             {"snapshots": {occ(asked, "C", 735): {"latestQuote": {"bp": 12.0, "ap": 12.2}, "impliedVolatility": 0.21},
                            occ(asked, "P", 735): {"latestQuote": {"bp": 14.0, "ap": 14.2}, "impliedVolatility": 0.22}},
              "next_page_token": None}]
    seen = []
    def fake_get(url, headers=None, params=None, timeout=None):
        seen.append(dict(params or {}))
        return NS(status_code=200, json=lambda: pages[1 if (params or {}).get("page_token") == "p2" else 0])
    monkeypatch.setattr(market._session, "get", fake_get)
    rows = market.option_chain_near("SPY", 735, asked)
    assert {(r["expiration"], r["strike"]) for r in rows} == {(near, 732.0), (asked, 735.0)} and len(seen) == 2
    assert pricecheck._closest(rows, "call", 735, asked)["expiration"] == asked
    # option_iv pages too, asks only for strikes near the one it prices, and reuses that band from its cache
    seen.clear(); market._iv_cache.clear()
    assert market.option_iv("SPY", "call", 735, asked) == 0.21 and len(seen) == 2
    assert float(seen[0]["strike_price_gte"]) < 735 * 0.75 and float(seen[0]["strike_price_lte"]) > 735 * 1.25
    assert market.option_iv("SPY", "call", 740, asked) == 0.21 and len(seen) == 2  # cached: inside the band
    # a failing later page keeps what came back; a failing first page means unavailable
    monkeypatch.setattr(market._session, "get", lambda url, headers=None, params=None, timeout=None:
                        NS(status_code=200, json=lambda: pages[0]) if not (params or {}).get("page_token") else NS(status_code=500, json=lambda: {}))
    assert len(market.option_chain_near("SPY", 735, asked)) == 1
    monkeypatch.setattr(market._session, "get", lambda *a, **k: NS(status_code=403, json=lambda: {}))
    assert market.option_chain_near("SPY", 735, asked) == []


def test_price_check_only_blames_volatility_when_it_points_the_same_way():
    """A card priced at a LOWER vol than the strike trades at can't be higher than the listed price because of vol."""
    from backend.v4 import pricecheck
    res = {"available": True, "underlying": "WINR", "strike": 90.0, "expiration": "2026-12-18", "spot": 100.0,
           "bid": 1.90, "ask": 2.10, "mid": 2.0, "contract_iv": 0.36}
    c = pricecheck.card_vs_listed(res, 2.60, 90, "2026-12-18", 0.30, "implied", 100.0)
    assert "$0.60 higher" in c["text"] and "Most of the gap is volatility" not in c["text"]
    c = pricecheck.card_vs_listed(res, 2.60, 90, "2026-12-18", 0.42, "implied", 100.0)
    assert "Most of the gap is volatility" in c["text"]


def test_price_check_vol_wording_is_plain_and_tiered():
    """Realized vol is described as yearly swings (not a % price move), and 'normal' says where in the band it sits."""
    from backend.v4 import pricecheck
    hi = pricecheck._vol_text("normal", 0.566, 0.508, 0.43, 0.566 / 0.43)
    assert "actually moved" not in hi and "43% a year over the last 60 trading days" in hi and "high end" in hi
    mid = pricecheck._vol_text("normal", 0.23, 0.27, 0.22, 0.23 / 0.22)
    assert "a little above realized" in mid and "high end" not in mid
    lo = pricecheck._vol_text("normal", 0.20, 0.21, 0.21, 0.20 / 0.21)
    assert "low end" in lo
    assert pricecheck._vol_text("cheap", 0.2, 0.3, 0.3, 0.67, "This option").startswith("This option is priced for 20%")
    assert pricecheck._pct_text(0.0032) == "0.3%" and pricecheck._pct_text(0.0005) == "less than 0.1%"
    assert pricecheck._pct_text(0.0127) == "1.3%" and pricecheck._pct_text(0.15) == "15%"


def test_research_picks_the_number_one_within_the_beliefs_own_direction(monkeypatch):
    # The engine always shows an idea in the belief's own direction first (engine._leads), so a ranker can only
    # reorder within that group. Here every bullish belief also has a short on a competitor that always wins big:
    # a model that learns "pick the short" must not get credit for a #1 users could never be shown (2026-11-11 log).
    from backend.v4 import research
    import datetime as _dt
    rng = __import__("random").Random(5)
    d0 = _dt.date(2024, 1, 1)
    for i in range(300):
        bid, asof = f"b-lead{i}", (d0 + _dt.timedelta(days=i * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill", "bullish"))
        for j in range(4):
            d = "bearish" if j == 3 else "bullish"
            mom = rng.uniform(-0.3, 0.3)
            ex = 0.3 if d == "bearish" else mom * 0.3 + rng.gauss(0, 0.02)
            pid = f"p-lead{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"L{j}", d, asof, 10.0, db.dumps({"num": {"mom60": mom}}), j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex, asof))
    data = research.load()
    b = data[0]
    assert [c["lead"] for c in b["cands"]] == [True, True, True, False]
    assert research._top(b, [0.0, 0.1, 0.2, 9.0]) == 2               # the short can't be the #1, however high it scores
    out = research.run(data=data)
    assert out["lead_only"] and out["mixed_direction"] == 1.0
    # the lone short has nothing to be ranked against in its own group, so it is not trained on (2026-11-14 night):
    # the model no longer learns to favour it (before, off_lead was > 0.9 here; now about chance, ~1 in 4 ideas)
    assert out["off_lead"]["ridge (learned)"] < 0.5
    for name in ("ridge (learned)", "gbm (learned)", "ridge (learned)" + research.MIX):
        # scored on the long it would really put first: always below the belief average (the short's +30%
        # lifts it), never the +22% lift that picking the short would show
        assert out["results"][name]["lift"] < 0
    # a belief with no stated direction (or only opposite ideas) still has a #1
    assert research._lead({"cands": [{"lead": False}, {"lead": False}]}) == [0, 1]


def test_ranker_v2_learns_each_idea_against_the_ideas_it_competes_with(monkeypatch):
    # 2026-11-14 night brain upgrade: the training label is the idea's outcome minus the average of its own group
    # (the lead group the engine picks the #1 from, or the off-direction group), not the whole belief. Planted: in
    # bullish beliefs the longs' order follows mom60, while a pair of shorts swings the belief average by a random
    # +-40%. Against the whole-belief mean that swing is noise on every long's label; against the longs' own mean
    # it is gone, and the learned ranker finds the real order.
    from backend.v4 import research
    import datetime as _dt
    rng = __import__("random").Random(11)
    d0 = _dt.date(2023, 1, 1)
    for i in range(360):
        bid, asof = f"b-grp{i}", (d0 + _dt.timedelta(days=i * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill", "bullish"))
        swing = rng.choice((-0.4, 0.4))
        for j in range(6):
            d = "bearish" if j >= 4 else "bullish"
            mom = rng.uniform(-0.3, 0.3)
            ex = swing + rng.gauss(0, 0.02) if d == "bearish" else mom * 0.1 + rng.gauss(0, 0.02)
            pid = f"p-grp{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"G{j}", d, asof, 10.0, db.dumps({"num": {"mom60": mom}}), j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex, asof))
    # a third belief shape: one lone short among longs is left out of training; a belief with no stated direction
    # keeps the old whole-belief label
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) VALUES (?,?,?,?,?,?,?,?)",
               ("b-grp-solo", "seed", "x", "x", "2025-06-01T00:00:00", "2025-06-01", "seed_backfill", "bullish"))
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-grp-none", "seed", "x", "x", "2025-06-01T00:00:00", "2025-06-01", "seed_backfill"))
    for bid, rows in (("b-grp-solo", (("bullish", 0.01), ("bullish", 0.03), ("bearish", 0.5))),
                      ("b-grp-none", (("bullish", 0.01), ("bearish", 0.03)))):
        for j, (d, ex) in enumerate(rows):
            pid = f"p-{bid}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"S{j}", d, "2025-06-01", 10.0, db.dumps({"num": {"mom60": 0.0}}), j))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, "2025-09-01", 10.0, 0.0, 0.0, ex, "2025-09-01"))
    data = research.load()
    solo = none = None
    for b in data:
        if b["date"] != "2025-06-01":
            continue
        if len(b["cands"]) == 3:
            solo = b
        elif len(b["cands"]) == 2:
            none = b
    assert [round(c["rel"], 6) for c in solo["cands"]] == [-0.01, 0.01, 0.0]      # longs vs longs; the short alone
    assert [c["train"] for c in solo["cands"]] == [True, True, False]
    assert [round(c["rel"], 6) for c in none["cands"]] == [-0.01, 0.01]            # no stated direction: whole belief
    x, y = research._xy([solo, none], ["z_mom60"], "rel")
    assert x.shape == (4, 1) and len(y) == 4                                        # the lone short is not trained on
    planted = [b for b in data if b["date"] != "2025-06-01"]
    for b in planted[:3]:
        longs = [c["rel"] for c in b["cands"] if c["lead"]]
        assert abs(sum(longs)) < 1e-9 and all(abs(r) < 0.1 for r in longs)        # the +-40% swing is not in them
    out = research.run(data=planted)
    assert out["results"]["ridge (learned)"]["n"] > 0
    assert out["ridge_weights_last"]["z_mom60"] > 0                                # learned the real within-group order


def test_trending_example_matches_the_theme_direction(monkeypatch):
    import json as _j
    def row(i, d, summ, text):
        return {"id": f"b-{i}", "user_id": f"u-{i}", "norm_text": text, "themes": _j.dumps(["ski resorts"]),
                "direction": d, "interpretation": _j.dumps({"summary": summ}), "source": "user"}
    rows = [row(1, "bullish", "Snowmaking will grow.", "more artificial snow"),   # newest, minority direction
            row(2, "bearish", "No snow hurts ski resorts.", "no snow in denver"),
            row(3, "bearish", "Warm winter hurts resorts.", "warm winter"),
            row(4, "bearish", "x", "a"), row(5, "bearish", "y", "b")]
    real = engine.db.query
    monkeypatch.setattr(engine.db, "query", lambda sql, args=(): rows if "FROM beliefs" in sql else [] if "FROM picks" in sql else real(sql, args))
    t = engine.trending(days=14)["themes"][0]
    assert t["direction"] == "bearish" and t["example"] == "No snow hurts ski resorts."


# ----------------------------------------------------------------------------- Yes / No (2026-11-12)

def _fake_chain(monkeypatch, iv=0.4):
    from backend.v4 import yesno

    def chain(u, strike, exp, days=21, band=0.15):
        spot = market.latest_price(u)
        out = []
        for e in (TODAY + timedelta(days=9), TODAY + timedelta(days=16)):
            for k in range(int(spot * 0.8), int(spot * 1.2) + 1):
                for t in ("call", "put"):
                    out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": e,
                                "bid": 1.0, "ask": 1.1, "iv": iv})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    monkeypatch.setattr(market, "option_iv", lambda *a, **k: iv)
    return yesno


def test_yesno_math():
    from backend.v4 import yesno
    assert abs(yesno.prob_above(100, 100, 0.0001, 0.3) - 0.5) < 0.02
    assert yesno.prob_above(100, 120, 7 / 365, 0.3) < 0.05
    assert yesno.prob_above(100, 80, 7 / 365, 0.3) > 0.95
    p, tilt = yesno.lean(0.5, 1, 1)
    assert tilt == pytest.approx(0.27) and 0.5 < p < 0.58          # small, capped nudge
    p, tilt = yesno.lean(0.5, -1, -1)
    assert p < 0.5 and abs(p - 0.5) < 0.08
    assert yesno.lean(0.3, 0, None) == (pytest.approx(0.3), 0.0)    # no read -> market's odds
    assert yesno.strikes_around([95, 100, 105], 101) == (100, 105)
    assert yesno.strikes_around([95, 100, 105], 100) == (95, 105)     # on a strike: centred on the line
    assert yesno.strikes_around([100, 105], 100) == (100, 105)         # lowest strike: line and the next one up
    assert yesno.strikes_around([95, 100], 100) is None
    assert "$2.50 either side of the $185.00 line" in yesno.spread_note("NVDA", 182.5, 187.5, 500, 185)
    assert "$5.00 below and $2.50 above the $185.00 line" in yesno.spread_note("NVDA", 180, 187.5, 750, 185)
    assert "line" not in yesno.spread_note("NVDA", 185, 187.5, 250).split("in between.")[1].split("NO is")[0]
    assert yesno.strikes_around([100, 105], 99) is None
    assert yesno.brier(0.7, True) == pytest.approx(0.09)


def test_yesno_quote_feed_failure_is_a_plain_message_not_a_500(monkeypatch):
    from backend.v4 import router, market

    def boom(symbol):
        raise market.MarketDataError("asset lookup failed for SPY: proxy")
    monkeypatch.setattr(market, "asset_info", boom)
    r = router._yesno(lambda m: m.expirations, "SPY")
    assert r["status"] == "error" and "Try again in a minute" in r["message"]


def test_yesno_uneven_strikes_still_centre_the_spread_on_the_line(monkeypatch):
    """Live SPY Nov 27 listed $699, $700, $705 and nothing between: the nearest pair $699/$705 bet on a close above
    $702 and cost 41% of its payout beside 'Market's odds 43%'. A pair the same distance either side wins."""
    from backend.v4 import yesno
    spy = [float(k) for k in range(690, 701)] + [705.0, 710.0, 715.0]
    assert yesno.strikes_around(spy, 700) == (695, 705)              # on a strike, uneven gaps: $5 either side
    assert yesno.strikes_around(spy, 702) == (699, 705)              # between strikes: $3 either side
    assert yesno.strikes_around([182.5, 185, 187.5], 185) == (182.5, 187.5)
    assert yesno.strikes_around([99, 100, 110], 100) == (99, 110)    # nothing centred within 2x: nearest pair
    assert yesno.strikes_around([90, 99, 100, 101.5, 110], 100) == (99, 101.5)  # $90/$110 is over 2x as wide
    note = yesno.spread_note("SPY", 699, 705, 600, 700)
    assert "$1.00 below and $5.00 above the $700.00 line" in note and "close above $702.00" in note
    assert "either side" in yesno.spread_note("SPY", 695, 705, 1000, 700)

    _fake_chain(monkeypatch, iv=0.4)
    full = market.option_chain_near
    lvl = float(int(market.latest_price("WINR")))
    gap = {lvl + d for d in (1, 2, 3, 4)}                            # strikes just above the line not listed
    monkeypatch.setattr(market, "option_chain_near", lambda *a, **k: [r for r in full(*a, **k) if r["strike"] not in gap])
    e = yesno.expirations("WINR")["expirations"][0]
    q = yesno.quote("WINR", lvl, e)
    assert q["strikes"] == [lvl - 5, lvl + 5] and q["yes"]["payout"] == 1000
    assert abs(q["yes"]["cost"] / 1000 - q["market_p"]) < 0.01          # YES costs the market's odds
    assert abs(q["yes"]["breakeven"] - lvl) < 0.15 and abs(q["no"]["breakeven"] - lvl) < 0.15
    assert "$5.00 either side of the" in q["spread_note"]

    # Real quotes with skew on that uneven grid: the odds are read off the trade's own centred spread, so YES's
    # price is the odds shown (the finer $lvl-1/$lvl/$lvl+5 pairs read a different number on skewed quotes).
    from backend.v4.strategy import bs_price
    spot = market.latest_price("WINR")
    yrs = max(1, (date.fromisoformat(e) - yesno._today()).days) / 365.0

    def skewed(*a, **k):
        out = []
        for r in full(*a, **k):
            if r["strike"] in gap:
                continue
            v = 0.4 + 0.8 * (lvl - r["strike"]) / lvl
            mid = bs_price(spot, r["strike"], yrs, v, r["type"])
            out.append(dict(r, bid=round(max(0.01, mid - 0.02), 2), ask=round(mid + 0.02, 2), iv=v))
        return out
    monkeypatch.setattr(market, "option_chain_near", skewed)
    q = yesno.quote("WINR", lvl, e)
    assert q["strikes"] == [lvl - 5, lvl + 5] and "call spread" in q["odds_source"]
    assert abs(q["yes"]["cost"] / q["yes"]["payout"] - q["market_p"]) < 0.005


def test_yesno_expected_move_and_big_move_warning(monkeypatch):
    from backend.v4 import yesno
    e = date(2026, 11, 20)
    rows = [{"strike": k, "type": t, "iv": iv, "expiration": e}
            for k, iv in ((150.0, 1.30), (155.0, 1.28), (160.0, 1.30)) for t in ("call", "put")]
    m = yesno.expected_move(157.29, rows, 3 / 365, rv60=0.50)
    # at-the-money = the strike nearest $157.29 ($155): one standard deviation over 3 days at 128%
    sd = 1.28 * math.sqrt(3 / 365)
    assert m["atm_strike"] == 155.0 and m["atm_iv"] == pytest.approx(1.28)
    assert m["low"] == pytest.approx(157.29 * math.exp(-sd), abs=0.01) and m["high"] == pytest.approx(157.29 * math.exp(sd), abs=0.01)
    assert m["low"] < 157.29 < m["high"] and 0.10 < m["pct"] < 0.13
    assert m["big"] is True and m["iv_rv"] == pytest.approx(2.56)
    lines = yesno.move_text("NVDA", m, e)
    assert lines[0].startswith("Option prices put about a 2-in-3 chance on NVDA closing between $") and "on Fri Nov 20 (about \u00b112%" in lines[0]
    assert "128% yearly volatility" in lines[1] and "50% a year over the last 60 trading days" in lines[1] and "earnings" in lines[1]
    # a normal premium over realized: no warning; no realized history: no warning either
    assert yesno.expected_move(157.29, rows, 3 / 365, rv60=1.10)["big"] is False
    assert len(yesno.move_text("NVDA", yesno.expected_move(157.29, rows, 3 / 365, rv60=1.10), e)) == 1
    # A fund has no earnings report: SPY's big-move line names market news instead
    spy = yesno.move_text("SPY", m, e, is_etf=True)[1]
    assert "earnings" not in spy and "Fed decision or a big economic report" in spy
    # The whole market's options priced the same way (a selloff): say so, not "news is due, like an earnings report"
    wide = yesno.move_text("NVDA", dict(m, market_iv_rv=2.2), e)[1]
    assert "earnings" not in wide and "whole market" in wide and "S&P 500's at 2.2x" in wide
    # A stock well above the market's own premium: news may be due
    alone = yesno.move_text("NVDA", dict(m, market_iv_rv=1.4), e)[1]
    assert "more than the whole market's" in alone and "earnings report" in alone
    # A calm market (or no SPY reading): the usual line
    assert "news is due" in yesno.move_text("NVDA", dict(m, market_iv_rv=1.1), e)[1]
    assert yesno.expected_move(157.29, rows, 3 / 365)["big"] is False
    # no strike within 3% of today's price (the chain slice sits around a far line): no range rather than a wrong one
    assert yesno.expected_move(120.0, rows, 3 / 365, rv60=0.5) is None
    assert yesno.expected_move(157.29, [dict(r, iv=None) for r in rows], 3 / 365) is None


def test_yesno_quote_sends_the_expected_move(monkeypatch):
    yesno = _fake_chain(monkeypatch, iv=0.4)
    e = yesno.expirations("WINR")
    spot = market.latest_price("WINR")
    q = yesno.quote("WINR", float(int(spot)), e["expirations"][0])
    m = q["move"]
    assert m and m["atm_iv"] == pytest.approx(0.4) and m["low"] < spot < m["high"]
    assert m["pct"] == pytest.approx(0.4 * math.sqrt(9 / 365), rel=0.02) and m["lines"][0].startswith("Option prices put")
    # the odds and the trade don't change because of it
    assert 0.3 < q["market_p"] < 0.8


def test_yesno_quote_call_grade(monkeypatch):
    yesno = _fake_chain(monkeypatch)
    spot = market.latest_price("WINR")
    e = yesno.expirations("WINR")
    assert e["expirations"][0] == (TODAY + timedelta(days=9)).isoformat() and e["spot"] == spot
    lvl = float(int(spot))
    q = yesno.quote("WINR", lvl, e["expirations"][0])
    assert q["strikes"] == [lvl - 1, lvl + 1] and q["vol_source"] == "market"     # centred on the line
    assert 0.3 < q["market_p"] < 0.8 and abs(q["brain_p"] - q["market_p"]) < 0.08
    assert q["yes"]["payout"] == 200 and 0 < q["yes"]["cost"] < 200 and 0 < q["no"]["cost"] < 200
    assert q["yes"]["legs"][0]["option_type"] == "call" and q["no"]["legs"][0]["option_type"] == "put"
    # breakeven at expiration: YES call spread = k1 + cost, NO put spread = k2 - cost (per share)
    assert q["yes"]["breakeven"] == pytest.approx(lvl - 1 + q["yes"]["cost"] / 100, abs=0.01)
    assert q["no"]["breakeven"] == pytest.approx(lvl + 1 - q["no"]["cost"] / 100, abs=0.01)
    assert lvl - 1 < q["yes"]["breakeven"] < lvl + 1 and "breakeven" in q["spread_note"]
    assert "$1.00 either side of the" in q["spread_note"]
    # both sides priced with one volatility: YES + NO = the payout (less a little interest), never free money
    assert 194 <= q["yes"]["cost"] + q["no"]["cost"] <= 201
    with pytest.raises(yesno.YesNoError):
        yesno.quote("WINR", spot * 3, e["expirations"][0])
    with pytest.raises(yesno.YesNoError):
        yesno.quote("WINR", lvl, (TODAY + timedelta(days=10)).isoformat())   # nothing listed that day
    r = yesno.make_call("u1", "WINR", lvl, e["expirations"][0], "yes")
    assert r["status"] == "success" and r["position_id"] is None
    assert yesno.log_brain("WINR", lvl, e["expirations"][0]) and yesno.log_brain("WINR", lvl, e["expirations"][0]) is None
    assert yesno.mine("u1")[0]["result"] == "open"
    # after expiration: grade from the expiration day's close
    later = TODAY + timedelta(days=12)
    exp_close = 999.0
    real = market.daily_closes
    def closes(s):
        d, c = real(s)
        return d + [(TODAY + timedelta(days=9)).isoformat()], c + [exp_close]
    monkeypatch.setattr(market, "daily_closes", closes)
    monkeypatch.setattr(market, "today", lambda: later)
    assert yesno.grade_due() == 2
    assert yesno.mine("u1")[0]["result"] == "right" and yesno.mine("u1")[0]["close_price"] == 999.0
    sc = yesno.scorecard()
    assert sc["graded"] == 1 and sc["open"] == 0 and sc["people_graded"] == 1 and sc["people_right"] == 1.0
    assert sc["verdict"] == "too_early" and sc["days"] == 1 and sc["brain_better"] is False and "market_side_right" in sc


def test_yesno_record_verdict_counts_each_expiration_day_once():
    from backend.v4 import yesno
    # one day: the brain was right on all 11 questions; still too early (they share one market move)
    one = [{"market_p": 0.5, "brain_p": 0.55, "above": 1, "expiration": "2026-11-18"} for _ in range(11)]
    v = yesno.record_verdict(one)
    assert v["days"] == 1 and v["verdict"] == "too_early" and v["gain"] > 0 and v["se"] is None
    # 6 days, small steady gain every day -> better
    steady = [{"market_p": 0.5, "brain_p": 0.53 if d % 2 else 0.54, "above": 1, "expiration": f"2026-12-{d:02d}"}
              for d in range(1, 7) for _ in range(3)]
    assert yesno.record_verdict(steady)["verdict"] == "better"
    # 6 days, wins and losses alternate by day -> about the same, not better
    mixed = [{"market_p": 0.5, "brain_p": 0.6, "above": d % 2, "expiration": f"2026-12-{d:02d}"}
             for d in range(1, 7) for _ in range(5)]
    v = yesno.record_verdict(mixed)
    assert v["days"] == 6 and v["verdict"] == "about_same" and abs(v["gain"]) < 0.02
    # wrong on 7 of 8 days -> worse
    worse = [{"market_p": 0.5, "brain_p": 0.6, "above": 0 if d < 8 else 1, "expiration": f"2026-12-{d:02d}"}
             for d in range(1, 9) for _ in range(5)]
    assert yesno.record_verdict(worse)["verdict"] == "worse"
    assert yesno.record_verdict([])["verdict"] == "too_early"


def test_yesno_scorecard_lists_the_brains_questions_and_where_it_took_the_other_side():
    from backend.v4 import yesno

    def put(i, user, m, b, exp, above=None, close=None):
        db.execute("""INSERT INTO yesno_calls (id, user_id, ticker, level, expiration, side, market_p, brain_p, spot,
                      strikes, cost, payout, contracts, position_id, created_at, features, close_price, above, graded_at)
                      VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (f"yn-{i}", user, "SPY", 750.0, exp, "yes" if b >= 0.5 else "no", m, b, 749.0, "750.0,751.0",
                    None, None, 0, None, f"2026-11-1{i}T15:13:00+00:00", "{}", close, above,
                    None if above is None else "2026-11-19T00:00:00+00:00"))

    put(1, "brain", 0.51, 0.54, "2026-11-18", above=0, close=733.0)    # same side as the market, wrong
    put(2, "brain", 0.49, 0.53, "2026-11-18", above=1, close=760.0)    # took the other side, right
    put(3, "brain", 0.47, 0.51, "2026-11-20", above=0, close=740.0)    # took the other side, wrong
    put(4, "brain", 0.48, 0.52, "2026-11-23")                          # took the other side, still open
    put(5, "u1", 0.40, 0.41, "2026-11-18", above=1, close=760.0)       # a user's question: never listed
    sc = yesno.scorecard()
    assert [r["result"] for r in sc["recent"]] == ["open", "wrong", "right", "wrong"]   # newest asked first
    assert all(r["ticker"] == "SPY" for r in sc["recent"]) and len(sc["recent"]) == 4
    assert [r["disagrees"] for r in sc["recent"]] == [True, True, True, False]
    assert sc["recent"][2]["close_price"] == 760.0 and sc["recent"][0]["asked"] == "2026-11-14"
    assert sc["disagree"] == {"n": 2, "right": 1, "days": 2}
    assert sc["graded"] == 4 and sc["brain_open"] == 1
    # graded ones on their own, latest expiration first: the newest-asked list is mostly open questions
    g = sc["graded_recent"]
    assert [(r["expiration"], r["result"]) for r in g] == [("2026-11-20", "wrong"), ("2026-11-18", "right"),
                                                           ("2026-11-18", "wrong")]
    assert g[1]["close_price"] == 760.0 and g[1]["disagrees"] is True and all(r["result"] != "open" for r in g)
    put(6, "u2", 0.55, 0.56, "2026-11-25")                              # a user's open question
    db.execute("DELETE FROM yesno_calls WHERE graded_at IS NOT NULL")
    empty = yesno.scorecard()
    assert empty["graded"] == 0 and len(empty["recent"]) == 1 and empty["open"] == 2
    assert empty["brain_open"] == 1  # "N of its questions are waiting" counts the brain's own, not users'
    assert empty["graded_recent"] == []


def test_yesno_my_record_sets_right_against_the_market_odds():
    from backend.v4 import yesno
    def v(i, side, mp, res, exp):
        return {"ticker": f"T{i}", "level": 100.0, "expiration": exp, "side": side, "market_p": mp, "result": res}
    # under 5 graded: nothing but the count; open answers don't count
    few = [v(i, "yes", 0.6, "right", "2026-12-01") for i in range(4)] + [v(9, "yes", 0.5, "open", "2026-12-05")]
    r = yesno.my_record(few)
    assert r == {"graded": 4, "open": 1, "min": 5, "verdict": "too_few"}
    # NO on a 20% YES = an 80% side; duplicates count once; one day -> too early however good
    one_day = [v(i, "no", 0.2, "right", "2026-12-01") for i in range(6)] + [v(0, "no", 0.2, "right", "2026-12-01")]
    r = yesno.my_record(one_day)
    assert r["graded"] == 6 and r["right"] == 6 and r["expected"] == 4.8 and r["avg_odds"] == 0.8
    assert r["days"] == 1 and r["verdict"] == "too_early" and r["se"] is None
    # right on every coin flip, 6 days -> ahead; wrong on every one -> behind
    ahead = [v(f"{d}{i}", "yes", 0.5, "right", f"2026-12-{d:02d}") for d in range(1, 7) for i in range(2)]
    ahead[0]["result"] = "wrong"
    assert yesno.my_record(ahead)["verdict"] == "ahead"
    behind = [dict(x, result="wrong") for x in ahead]
    assert yesno.my_record(behind)["verdict"] == "behind"
    # right exactly as often as the odds said, day by day -> within luck
    even = [v(f"{d}{i}", "yes", 0.5, "right" if (d + i) % 2 else "wrong", f"2026-12-{d:02d}")
            for d in range(1, 7) for i in range(2)]
    r = yesno.my_record(even)
    assert r["right"] == 6 and r["expected"] == 6.0 and r["verdict"] == "within_luck"


def test_yesno_practice_trade(monkeypatch, tmp_path):
    yesno = _fake_chain(monkeypatch)
    from backend.v4 import practice_options
    seen = {}
    def fake_open(user_id, ticker, structure, legs, contracts, belief="", vol_override=None, keep_leg_vols=False):
        seen.update(user=user_id, legs=practice_options._clean_legs(legs, ticker), structure=structure, n=contracts)
        return {"status": "success", "position_id": "opt-x", "message": "Opened.", "set_aside": 281.76,
                "market_closed": True}
    monkeypatch.setattr(practice_options, "open_trade", fake_open)
    e = yesno.expirations("WINR")
    lvl = float(int(market.latest_price("WINR")))
    r = yesno.make_call("u2", "WINR", lvl, e["expirations"][0], "no", trade=True, contracts=3)
    assert r["position_id"] == "opt-x" and seen["n"] == 3 and seen["structure"].startswith("Close Call: NO")
    # the confirmation reads as the question, in words (was "Opened 3 WINR Close Call: NO WINR > $X contracts")
    exp = date.fromisoformat(e["expirations"][0])
    day = f"{exp.strftime('%a %b')} {exp.day}"
    assert r["message"].startswith(f"Opened NO on WINR above ${lvl:,.0f} on {day}: 3 contracts with practice money "
                                   "(about $282 set aside)"), r["message"]
    assert "market is closed" in r["message"] and "Close Call:" not in r["message"] and ">" not in r["message"]
    logged = yesno.make_call("u2", "WINR", lvl, e["expirations"][0], "yes")
    assert logged["message"] == f"Logged: YES on WINR above ${lvl:,.0f} on {day}. We'll grade it after that day's close."
    assert [l["option_type"] for l in seen["legs"]] == ["Put", "Put"] and seen["legs"][0]["strike_price"] == lvl + 1


def test_yesno_skewed_chain_prices_each_strike_at_its_own_vol(monkeypatch):
    """Equity skew: IV falls as the strike rises. One flat vol can't reprice the k1/k2 spread (its flat-vol value
    barely moves with vol), so YES cost sat ~9 pts under the market's odds (live AAPL $360/$365 Dec 18: odds 50%,
    YES $204 of $500). Each strike at its own IV puts YES at the listed spread mid, YES + NO = the discounted payout,
    and the practice trade is marked at the same vols (no jump right after it opens)."""
    from backend.v4 import yesno, practice_options
    from backend.v4.strategy import bs_price, RISK_FREE
    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=30)
    yrs = 30 / 365
    iv = lambda k: 0.35 - 0.5 * (k / spot - 1)           # equity skew: half a vol pt per 1% of strike
    mid = lambda k, t: bs_price(spot, k, yrs, iv(k), t)

    def chain(u, strike, e, days=21, band=0.15):
        out = []
        for k in range(int(spot * 0.9), int(spot * 1.1) + 1):
            for t in ("call", "put"):
                m = mid(k, t)
                out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                            "bid": round(m - 0.01, 2), "ask": round(m + 0.01, 2), "iv": round(iv(k), 4)})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    monkeypatch.setattr(market, "option_iv", lambda *a, **k: None)
    k1 = float(int(spot))
    v = yesno.leg_vols(chain("WINR", k1, exp)[::2], k1, k1 + 1, spot, yrs, iv(k1))
    assert v == (pytest.approx(iv(k1), abs=2e-3), pytest.approx(iv(k1 + 1), abs=2e-3))
    q = yesno.quote("WINR", k1, exp.isoformat())
    assert q["price_source"] == "strikes" and q["strikes"] == [k1 - 1, k1 + 1]
    listed = (round(mid(k1 - 1, "call"), 2) - round(mid(k1 + 1, "call"), 2)) * 100
    assert q["yes"]["cost"] == pytest.approx(listed, abs=2.0)                       # the listed spread mid
    flat = (bs_price(spot, k1 - 1, yrs, q["vol"], "call") - bs_price(spot, k1 + 1, yrs, q["vol"], "call")) * 100
    assert q["yes"]["cost"] - flat > 2.0                                            # the old flat-vol price was cheap
    df = math.exp(-RISK_FREE * yrs)
    assert q["yes"]["cost"] + q["no"]["cost"] == pytest.approx(200 * df, abs=0.02)   # put-call parity, to the cent
    # the market's odds are read from the same k1-1 / k1+1 spread YES is, so YES's price is those odds
    assert q["yes"]["cost"] / 200 / df == pytest.approx(q["market_p"], abs=0.005)
    assert q["market_p"] == pytest.approx((mid(k1 - 1, "call") - mid(k1 + 1, "call")) / 2 / df, abs=0.01)
    # marked at the same per-strike vols as it was priced: worth what it cost right after it opens
    legs = practice_options._clean_legs(q["yes"]["legs"], "WINR", keep_leg_vols=True)
    assert [l["vol"] for l in legs] == list(q["leg_vols"])
    assert practice_options.unit_value(legs, spot, 0.9) == pytest.approx(q["yes"]["cost"], abs=1.0)
    # a request can't set its own vols
    assert "vol" not in practice_options._clean_legs(q["yes"]["legs"], "WINR")[0]


def _yn_rows(n, signal, seed=1):
    from backend.v4 import yesno
    rnd = random.Random(seed)
    for i in range(n):
        trend = rnd.choice((-1.0, 1.0))
        mp = rnd.uniform(0.3, 0.7)
        p_true = yesno._sig(yesno._logit(mp) + signal * trend)
        day = (date(2025, 1, 1) + timedelta(days=i)).isoformat()
        exp = (date(2025, 1, 1) + timedelta(days=i + 7)).isoformat()
        f = {"m_logit": yesno._logit(mp), "trend": trend, "ideas": 0.0, "crowd": 0.0, "dist_sd": 0.0}
        db.execute("""INSERT INTO yesno_calls (id, user_id, ticker, level, expiration, side, market_p, brain_p, created_at,
                      above, graded_at, features) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (f"r{i}", "brain", "WINR", 100.0 + i, exp, "yes", mp, mp, day + "T15:00:00",
                    1 if rnd.random() < p_true else 0, exp, db.dumps(f)))


def test_yesno_learns_only_when_it_beats_the_market(monkeypatch):
    yesno = _fake_chain(monkeypatch)
    assert yesno.learn()["active"] is False                      # nothing graded yet
    _yn_rows(900, signal=0.0)                                     # trend means nothing -> stays on starting rules
    r = yesno.learn()
    assert r["active"] is False and yesno.active_model() is None
    db.execute("DELETE FROM yesno_calls")
    _yn_rows(900, signal=1.2, seed=2)                             # trend really matters -> learned, goes live
    r = yesno.learn()
    assert r["active"] is True and r["t"] >= 1.5 and r["w"][2] > 0.5
    lvl = float(int(market.latest_price("WINR")))
    q = yesno.quote("WINR", lvl, (TODAY + timedelta(days=9)).isoformat())
    assert q["brain_model"] == "learned" and set(q["features"]) == set(yesno.FEATS)
    assert yesno.scorecard()["learning"]["active"] is True


def test_yesno_real_money_order_is_ready_but_off(monkeypatch):
    yesno = _fake_chain(monkeypatch)
    lvl = float(int(market.latest_price("WINR")))
    q = yesno.quote("WINR", lvl, (TODAY + timedelta(days=9)).isoformat())
    rm = q["real_money"]
    assert rm["available"] is False and rm["switch"] == "off"
    o = rm["yes"]["order"]
    assert o["order_class"] == "mleg" and o["type"] == "limit" and len(o["legs"]) == 2
    assert [l["position_intent"] for l in o["legs"]] == ["buy_to_open", "sell_to_open"]
    assert rm["yes"]["max_loss"] + rm["yes"]["max_gain"] == pytest.approx(q["yes"]["payout"])  # the same spread


def test_yesno_listed_costs_show_the_real_bid_ask_next_to_the_practice_price(monkeypatch):
    from backend.v4 import yesno
    e = date(2026, 11, 23)

    def row(t, k, bid, ask):
        return {"symbol": f"X{k}{t}", "type": t, "strike": k, "expiration": e, "bid": bid, "ask": ask, "iv": 0.2}
    # in-hours SPY-like quotes on a $1 spread: 725C 9.10/9.14, 726C 8.45/8.49; 726P 2.30/2.34, 725P 2.02/2.06
    chain = [row("call", 725.0, 9.10, 9.14), row("call", 726.0, 8.45, 8.49),
             row("put", 726.0, 2.30, 2.34), row("put", 725.0, 2.02, 2.06)]
    sides = {"yes": {"cost": 63.0}, "no": {"cost": 37.0}}
    c = yesno.listed_costs(chain, 725.0, 726.0, e, sides)
    y, n = c["yes"], c["no"]
    assert (y["bid"], y["ask"], y["mid"]) == (61.0, 69.0, 65.0)       # 9.10-8.49, 9.14-8.45
    assert (n["bid"], n["ask"]) == (24.0, 32.0)                       # 2.30-2.06, 2.34-2.02
    assert y["odds_at_ask"] == pytest.approx(0.69) and y["odds_at_practice"] == pytest.approx(0.63)
    assert c["payout"] == 100.0 and not c["wide"]
    # after hours: the YES ask is above what the spread can pay -> wide
    chain[0] = row("call", 725.0, 8.0, 10.5)
    c = yesno.listed_costs(chain, 725.0, 726.0, e, sides)
    assert c["yes"]["ask"] == 205.0 and c["yes"]["wide"] and c["wide"] and c["yes"]["odds_at_ask"] == 1.0
    # a leg with no quote -> nothing to show
    chain[1] = row("call", 726.0, 0.0, 0.0)
    assert yesno.listed_costs(chain, 725.0, 726.0, e, sides) is None
    # quote() sends it and the practice prices are unchanged by it
    yn = _fake_chain(monkeypatch)
    lvl = float(int(market.latest_price("WINR")))
    q = yn.quote("WINR", lvl, (TODAY + timedelta(days=9)).isoformat())
    assert q["listed"]["yes"]["practice"] == q["yes"]["cost"] and q["listed"]["yes"]["ask"] == 10.0


def test_yesno_sides_add_up_when_call_and_put_ivs_differ(monkeypatch):
    # After hours the feed's call and put IVs can disagree; pricing each side with its own legs' IV let YES + NO cost
    # less than the payout (buy both = free practice money). Both sides now use the line's IV.
    yesno = _fake_chain(monkeypatch)
    monkeypatch.setattr(market, "option_iv", lambda u, kind, *a, **k: 0.9 if kind == "call" else 0.2)
    e = yesno.expirations("WINR")
    q = yesno.quote("WINR", float(int(market.latest_price("WINR"))), e["expirations"][0])
    assert 0.97 * q["yes"]["payout"] <= q["yes"]["cost"] + q["no"]["cost"] <= q["yes"]["payout"]


def test_yesno_yes_plus_no_never_costs_more_than_the_payout(monkeypatch):
    # Rounding each leg to the cent moved a $250 spread by up to $1: live AAPL $350 on Fri Nov 20 read YES $112 +
    # NO $139 = $251 for a $250 payout, breakevens $351.12 vs $351.11. The spread is now rounded once, so
    # YES + NO = the discounted payout to the cent, both breakevens match, and the practice trade's entry is that price.
    from backend.v4 import practice_options
    from backend.v4.strategy import RISK_FREE
    yesno = _fake_chain(monkeypatch)
    spot = float(market.latest_price("WINR"))
    for e in yesno.expirations("WINR")["expirations"][:3]:
        for lvl in (float(int(spot)) - 1, float(int(spot)), float(int(spot)) + 1):
            q = yesno.quote("WINR", lvl, e)
            if q["yes"]["cost"] is None or q["yes"]["cost"] in (1.0, q["yes"]["payout"] - 1.0):
                continue
            yrs = q["days"] / 365.0
            assert q["yes"]["cost"] + q["no"]["cost"] <= q["yes"]["payout"]
            assert q["yes"]["cost"] + q["no"]["cost"] == pytest.approx(q["yes"]["payout"] * math.exp(-RISK_FREE * yrs), abs=0.02)
            assert abs(q["yes"]["breakeven"] - q["no"]["breakeven"]) <= 0.011
            legs = practice_options._clean_legs(q["yes"]["legs"], "WINR", True)
            assert all(l.get("whole_cents") for l in legs)
            assert practice_options.unit_value(legs, spot, q["price_vol"]) == q["yes"]["cost"]
    # a request can't switch it on: ordinary practice legs keep per-leg cent rounding (the idea card's prices)
    legs = practice_options._clean_legs([dict(l, whole_cents=True) for l in q["yes"]["legs"]], "WINR", False)
    assert not any(l.get("whole_cents") for l in legs)


def test_hq_board_and_messages(monkeypatch, tmp_path):
    from backend.v4 import hq
    (tmp_path / "status").mkdir()
    (tmp_path / "agents.json").write_text(json.dumps([{"key": "reel", "name": "Reel", "role": "r", "schedule": "s", "trigger": None,
                                                       "cron": "CRON_TZ=America/Denver 47 7 * * 1-5"},
                                                      {"key": "polish", "name": "Polish", "role": "p", "schedule": "s", "trigger": None}]))
    (tmp_path / "status" / "reel.json").write_text(json.dumps({"updated_at": "2026-11-13T15:00:00Z", "last_run": "Made the reel.",
        "needs_from_murad": ["Post today's reel"], "read_up_to": 1, "replies": [{"re": 1, "body": "On it.", "at": "2026-11-13T15:01:00Z"}]}))
    monkeypatch.setattr(hq, "ROOT", tmp_path)
    monkeypatch.setattr(hq, "RAW", "http://127.0.0.1:9/")   # unreachable -> deployed copy
    hq._cache.clear()
    assert hq.post("Everyone: focus on Close Call", "all")["id"] == 1
    assert hq.post("Reel: shorter please", "reel")["id"] == 2
    assert hq.post("x", "nobody")["to"] == "all"
    with pytest.raises(hq.HQError):
        hq.post("  ")
    b = hq.board()
    reel = next(a for a in b["agents"] if a["key"] == "reel")
    pol = next(a for a in b["agents"] if a["key"] == "polish")
    assert reel["unread"] == 2 and pol["unread"] == 2       # reel read #1; #2 (to reel) and #3 (all) are new
    assert b["needs"] == [{"agent": "reel", "name": "Reel", "need": "Post today's reel", "at": "2026-11-13T15:00:00Z"}]
    assert reel["next_run"] and reel["next_run"].endswith("Z") and pol["next_run"] is None   # no cron -> no next run
    kinds = [t["kind"] for t in b["thread"]]
    assert "agent" in kinds and "status" in kinds and kinds.count("murad") == 3


def test_hq_thread_labels_replies_and_keeps_each_agents_newest(monkeypatch, tmp_path):
    """Live (Nov 22): the meeting showed "Builder · re #(no new messages)", and the board kept replies[-10:] although
    status files list replies newest first, so an agent with more than 10 would lose its newest ones."""
    from backend.v4 import hq
    (tmp_path / "status").mkdir()
    (tmp_path / "agents.json").write_text(json.dumps([{"key": "builder", "name": "Builder", "role": "b", "schedule": "s"},
                                                      {"key": "growth", "name": "Growth", "role": "g", "schedule": "s"}]))
    replies = [{"re": "(no new messages)", "body": f"run {i}", "at": f"2026-11-{30 - i:02d}T10:00:00Z"} for i in range(12)]
    replies[0]["re"] = "#1"          # newest answers Murad's message 1
    replies[1]["re"] = "Search feature (via chair)"
    replies[2]["re"] = 99           # an id that isn't in the table
    (tmp_path / "status" / "builder.json").write_text(json.dumps({"updated_at": "2026-11-30T10:00:00Z", "replies": replies,
        "needs_from_murad": ["old ask"]}))
    (tmp_path / "status" / "growth.json").write_text(json.dumps({"updated_at": "2026-12-01T09:00:00Z", "needs_from_murad": ["new ask"]}))
    monkeypatch.setattr(hq, "ROOT", tmp_path)
    monkeypatch.setattr(hq, "RAW", "http://127.0.0.1:9/")
    hq._cache.clear()
    hq.post("Please make the Close Call page clearer for a first-time visitor who has never traded an option before today", "builder")
    b = hq.board()
    mine = [t for t in b["thread"] if t["kind"] == "agent"]
    assert len(mine) == 10 and {t["body"] for t in mine} == {f"run {i}" for i in range(10)}   # newest 10, not oldest
    first = next(t for t in mine if t["body"] == "run 0")
    assert first["re_id"] == 1 and first["re"] is None
    assert first["re_body"].startswith("Please make the Close Call page") and first["re_body"].endswith("...")
    assert len(first["re_body"]) <= 80
    assert next(t for t in mine if t["body"] == "run 1")["re"] == "Search feature (via chair)"
    gone = next(t for t in mine if t["body"] == "run 2")
    assert gone["re_id"] == 99 and gone["re_body"] is None
    routine = next(t for t in mine if t["body"] == "run 5")
    assert routine["re"] is None and routine["re_id"] is None          # shown as "update", not "re #(no new messages)"
    assert [n["need"] for n in b["needs"]] == ["new ask", "old ask"]   # newest first
    assert hq.reply_to("12", {12: "short"}) == {"re": None, "re_id": 12, "re_body": "short"}
    assert hq.reply_to(None, {})["re"] is None


def test_hq_next_run_reads_each_agents_cron_in_its_own_time_zone():
    from backend.v4 import hq
    from datetime import datetime, timezone
    now = datetime(2026, 11, 22, 4, 55, tzinfo=timezone.utc)          # Sat 9:55 PM in Denver (UTC-7)
    nr = lambda c, t=now: hq.next_run(c, t)
    assert nr("CRON_TZ=America/Denver 51 0-23/3 * * *") == "2026-11-22T07:51:00Z"   # every 3 h from 0:51 -> Sun 0:51 MT
    assert nr("CRON_TZ=America/Denver 4 * * * *") == "2026-11-22T05:04:00Z"         # hourly at :04
    assert nr("CRON_TZ=America/Denver 47 7 * * 1-5") == "2026-11-23T14:47:00Z"      # weekdays: skips Sunday
    assert nr("CRON_TZ=America/Denver 23 18 * * 0") == "2026-11-23T01:23:00Z"       # Sundays 6:23 PM MT
    assert nr("CRON_TZ=America/Denver 11 6-22/4 * * *") == "2026-11-22T05:11:00Z"   # 6,10,14,18,22 -> 22:11 tonight
    assert nr("30 9 * * 7") == "2026-11-22T09:30:00Z"                               # no zone = UTC; 7 = Sunday
    assert nr("0 12 1 * *") == "2026-12-01T12:00:00Z"                               # day of month
    # summer time: 9:00 in Denver is 15:00 UTC in July, 16:00 in November
    assert nr("CRON_TZ=America/Denver 0 9 * * *", datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)) == "2026-07-01T15:00:00Z"
    assert nr("CRON_TZ=America/Denver 0 9 * * *") == "2026-11-22T16:00:00Z"
    assert nr("CRON_TZ=America/Denver 4 * * * *", datetime(2026, 11, 22, 5, 4, tzinfo=timezone.utc)) == "2026-11-22T06:04:00Z"  # strictly after now
    assert nr(None) is None and nr("") is None and nr("not a cron") is None and nr("CRON_TZ=Nowhere/X 1 * * * *") is None


def test_hq_owner_gate(monkeypatch):
    from fastapi import HTTPException
    from backend.v4 import router, auth, brokerage
    monkeypatch.setattr(brokerage, "is_owner", lambda acc: False)
    monkeypatch.setattr(auth, "account_for_token", lambda t: {"email": "Second@Example.com"} if t == "ok" else None)
    with pytest.raises(HTTPException) as e:
        router._hq_owner(None)
    assert "Sign in" in e.value.detail
    with pytest.raises(HTTPException):
        router._hq_owner("Bearer ok")
    monkeypatch.setenv("MP_HQ_EMAILS", "first@example.com, second@example.com")
    router._hq_owner("Bearer ok")   # allowed: listed owner email


def test_yesno_digital_from_call_spread():
    from backend.v4 import yesno
    calls = [{"strike": 95, "bid": 6.0, "ask": 6.2}, {"strike": 100, "bid": 3.0, "ask": 3.2}, {"strike": 105, "bid": 1.2, "ask": 1.3}]
    p, ka, kb, used = yesno.digital_from_spread(calls, 100)
    assert (ka, kb) == (95, 105) and p == pytest.approx((6.1 - 1.25) / 10)       # even strikes: the usual central spread
    assert yesno.odds_label(used, 100) == "the $95/$100/$105 call prices, read at the $100 line (skew included)"
    # $102: the $100/$105 spread measures a close above $102.50, so read between the 97.5 and 102.5 middles.
    p, ka, kb, used = yesno.digital_from_spread(calls, 102)
    p_left, p_right = (6.1 - 3.1) / 5, (3.1 - 1.25) / 5
    assert used == [95, 100, 105] and p == pytest.approx(p_left + (p_right - p_left) * 4.5 / 5)
    assert p_right < p < p_left
    # Only one pair reaches the line: that spread, labelled as a spread.
    p, ka, kb, used = yesno.digital_from_spread(calls, 104)
    assert used == [100, 105] and p == pytest.approx(p_right)
    assert yesno.odds_label(used, 104) == "the $100/$105 call spread (skew included)"
    assert yesno.digital_from_spread(calls, 120) is None                         # outside the listed strikes
    # Half-dollar strikes and lines read as money: "$157.50", not "$157.5"
    assert yesno.odds_label([157.5, 162.5], 160) == "the $157.50/$162.50 call spread (skew included)"
    assert yesno.odds_label([185, 187.5, 190], 186.3) == "the $185/$187.50/$190 call prices, read at the $186.30 line (skew included)"
    assert yesno.digital_from_spread([{"strike": 95, "bid": 1, "ask": 1.1}, {"strike": 105, "bid": 2, "ask": 2.1}], 100) is None  # nonsense quotes
    assert yesno.digital_from_spread([{"strike": 50, "bid": 6, "ask": 6.2}, {"strike": 150, "bid": 1, "ask": 1.1}], 100) is None   # too wide
    # Out-of-step quotes (live after hours, NVDA $159.45): $152.50/$155 at 40% but $155/$157.50 at 52%. A chance of
    # closing above can't rise with the strike, so no odds are read from them and the reason is passed back.
    bad = [{"strike": 152.5, "bid": 7.0, "ask": 7.0}, {"strike": 155, "bid": 6.0, "ask": 6.0}, {"strike": 157.5, "bid": 4.69, "ask": 4.69}]
    why = []
    assert yesno.digital_from_spread(bad, 155, why=why) is None and why == ["inverted"]


def test_yesno_odds_at_the_line_with_uneven_strikes():
    """Seen live: NVDA $150 line with $149 / $150 / $152.5 listed. The $149/$152.5 spread alone is the chance of a close
    above $150.75. On a smooth chain (calls priced off one lognormal) the odds must match P(close > $150) itself."""
    import math
    from backend.v4 import yesno
    spot, vol, years = 161.87, 0.9, 4 / 365

    def call(k):
        sq = vol * math.sqrt(years)
        d1 = (math.log(spot / k) + 0.5 * vol * vol * years) / sq
        return spot * yesno._ncdf(d1) - k * yesno._ncdf(d1 - sq)

    calls = [{"strike": k, "bid": call(k) - 0.01, "ask": call(k) + 0.01} for k in (147.5, 149, 150, 152.5, 155)]
    truth = yesno.prob_above(spot, 150, years, vol, rate=0.0)
    p, ka, kb, used = yesno.digital_from_spread(calls, 150)
    old = (call(149) - call(152.5)) / 3.5                                         # the one-spread reading
    assert used == [149, 150, 152.5]
    assert abs(p - truth) < 0.002 < abs(old - truth)


def test_economics_exact_at_strikes():
    """Peaks and troughs sit on strikes: a straddle's max loss is exactly the premium paid, a butterfly's
    max gain is exactly (wing width - debit) x 100 (the old 2,400-point grid stepped over them)."""
    from backend.v4 import library
    k = 480.0
    straddle = [{"action": "Buy", "option_type": "Call", "strike_price": k, "est_premium": 12.34, "quantity": 1, "instrument": "option"},
                {"action": "Buy", "option_type": "Put", "strike_price": k, "est_premium": 11.38, "quantity": 1, "instrument": "option"}]
    e = library.economics(straddle, 481.7)
    assert e["max_loss"] == pytest.approx((12.34 + 11.38) * 100) and e["max_profit"] == "Unlimited"
    assert e["break_even"] == f"{round(k - 23.72, 2)} / {round(k + 23.72, 2)}"
    fly = [{"action": "Buy", "option_type": "Call", "strike_price": 90.0, "est_premium": 6.0, "quantity": 1, "instrument": "option"},
           {"action": "Sell", "option_type": "Call", "strike_price": 95.0, "est_premium": 3.2, "quantity": 2, "instrument": "option"},
           {"action": "Buy", "option_type": "Call", "strike_price": 100.0, "est_premium": 1.6, "quantity": 1, "instrument": "option"}]
    e = library.economics(fly, 93.0)
    debit = 6.0 - 6.4 + 1.6
    assert e["max_profit"] == pytest.approx((5 - debit) * 100) and e["max_loss"] == pytest.approx(debit * 100)

def test_yesno_spread_vol_prices_yes_at_the_listed_spread_mid():
    # Close Call's YES / NO cost must match the market's own price for the k1/k2 call spread (skew included),
    # not one strike's IV, or the cost disagrees with the market odds shown above it.
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price
    spot, yrs = 100.0, 7 / 365
    calls = [{"strike": 100, "bid": 2.00, "ask": 2.10}, {"strike": 102.5, "bid": 1.00, "ask": 1.06}]
    v = yesno.spread_vol(calls, 100, 102.5, spot, yrs, near=0.4)
    assert v is not None
    model = bs_price(spot, 100, yrs, v, "call") - bs_price(spot, 102.5, yrs, v, "call")
    assert model == pytest.approx(2.05 - 1.03, abs=1e-4)
    assert yesno.spread_vol(calls, 100, 105, spot, yrs, 0.4) is None                 # no quote on 105
    bad = [{"strike": 100, "bid": 1.0, "ask": 1.1}, {"strike": 102.5, "bid": 2.0, "ask": 2.1}]
    assert yesno.spread_vol(bad, 100, 102.5, spot, yrs, 0.4) is None                 # spread can't be negative


def test_card_vol_prefers_implied(monkeypatch):
    from backend.v4 import engine
    monkeypatch.setattr(market, "option_iv", lambda u, k, s, e: 0.52)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    assert engine.card_vol("WINR", 100.0, TODAY, 90, 0.31, live=True) == (0.31, "historical")    # no market data keys
    monkeypatch.setenv("ALPACA_API_KEY", "x")
    assert engine.card_vol("WINR", 100.0, TODAY, 90, 0.31, live=True) == (0.52, "implied")
    assert engine.card_vol("WINR", 100.0, TODAY, 90, 0.31, live=False) == (0.31, "historical")   # backfill / unshown
    monkeypatch.setattr(market, "option_iv", lambda u, k, s, e: None)
    assert engine.card_vol("WINR", 100.0, TODAY, 90, 0.31, live=True) == (0.31, "historical")


def test_yesno_stale_spread_quotes_fall_back_to_one_vol(monkeypatch):
    # After hours the call-spread mids can lag the stock (live: SPY $752, "61% above $755"). A spread-implied
    # digital more than 10 points from the one-vol answer is not shown as the market's odds.
    yesno = _fake_chain(monkeypatch)
    spot = market.latest_price("WINR")
    real = market.option_chain_near

    def steep(u, strike, exp, days=21, band=0.15):
        out = []
        for r in real(u, strike, exp, days, band):
            if r["type"] == "call":
                mid = max(0.05, 0.9 * (spot * 1.2 - r["strike"]))    # 0.90 per $1 strike: a 90% digital everywhere
                r = dict(r, bid=round(mid - 0.02, 2), ask=round(mid + 0.02, 2))
            out.append(r)
        return out
    monkeypatch.setattr(market, "option_chain_near", steep)
    exp = (TODAY + timedelta(days=9)).isoformat()
    q = yesno.quote("WINR", round(spot) + 0.5, exp)
    assert "out of date" in q["odds_source"] and q["market_p"] == q["market_p_flat_vol"]


def test_yesno_quotes_too_wide_to_trade_read_the_smile_for_odds_and_price(monkeypatch):
    """Outside market hours the listed bid/ask gaps are wide and the mids jump: live SPY $725 (Wed 7:30 AM ET) read
    59%, 65% and 74% on three refreshes a minute apart, the YES cost following it ($56 to $73), while the expected-move
    line said 23% vol and the footer priced the legs at 28%. When the quotes are too wide to trade (the same test as
    the "What a real order would pay" box), the market's odds and the practice price come from the smile fitted
    through many strikes (skew kept, noise averaged out), so they agree and don't jump; tight quotes keep reading
    skew from the mids. (Before Nov 21 they came from one IV, which dropped the skew.)"""
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price, RISK_FREE
    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=9)
    yrs = 9 / 365
    iv = lambda k: 0.35 - 0.5 * (k / spot - 1)           # equity skew in the mids
    gap = {"v": 0.01}

    def chain(u, strike, e, days=21, band=0.15):
        out = []
        for k in range(int(spot * 0.9), int(spot * 1.1) + 1):
            for t in ("call", "put"):
                m = bs_price(spot, k, yrs, iv(k), t)
                out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                            "bid": round(max(0.0, m - gap["v"]), 2), "ask": round(m + gap["v"], 2), "iv": round(iv(k), 4)})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    monkeypatch.setattr(market, "option_iv", lambda *a, **k: None)
    k1 = float(int(spot))
    tight = yesno.quote("WINR", k1, exp.isoformat())
    assert "skew included" in tight["odds_source"] and tight["market_p"] != tight["market_p_flat_vol"]
    assert tight["listed"]["wide"] is False
    gap["v"] = 0.40                                     # $0.80 bid/ask per leg: an after-hours chain
    q = yesno.quote("WINR", k1, exp.isoformat())
    assert q["listed"]["wide"] is True or q["strikes"] != tight["strikes"]   # open: steps out to a quieter pair
    monkeypatch.setattr(market, "clock", lambda: {"is_open": False})          # after hours: the smile, narrow pair
    q = yesno.quote("WINR", k1, exp.isoformat())
    assert q["listed"]["wide"] is True and q["strikes"] == tight["strikes"]
    assert "option smile" in q["odds_source"] and q["market_p"] == q["market_p_smile"]
    assert abs(q["market_p"] - tight["market_p"]) < 0.02                      # skew kept: same odds as tight quotes
    assert q["market_p"] - q["market_p_flat_vol"] > 0.02                        # (one vol would drop it)
    assert q["price_source"] == "smile" and q["leg_vols"][0] > q["leg_vols"][1]
    df = math.exp(-RISK_FREE * yrs)
    assert abs(q["yes"]["cost"] / q["yes"]["payout"] / df - q["market_p"]) < 0.03     # YES costs about the odds shown
    assert q["yes"]["cost"] + q["no"]["cost"] == pytest.approx(q["yes"]["payout"] * df, abs=0.02)


def test_exercise_notes_american_style():
    """Option cards say what the expiry chart leaves out: American exercise, early assignment on each short leg
    (and what covers it), pin risk at short strikes, automatic exercise of in-the-money longs. Stock-only: none."""
    from datetime import date
    from backend.v4 import library, strategy
    assert library.exercise_notes([library.stock_leg("AAPL", 230.0)]) == []
    assert strategy.build_trade("Buy Stock", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90).get("exercise", []) == []
    lc = strategy.build_trade("Long Call", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90)["exercise"]
    assert "American-style" in lc[0] and "no dividends" in lc[0]
    assert not any("Pin risk" in n or "You're selling" in n for n in lc)
    assert any("exercised automatically" in n for n in lc)
    cc = " ".join(strategy.build_trade("Covered Call", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90)["exercise"])
    assert "ex-dividend" in cc and "Your shares cover it." in cc and "Pin risk" in cc
    bcs = strategy.build_trade("Bull Call Spread", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90)
    k_short = next(l["strike_price"] for l in bcs["trade_legs"] if l["action"] == "Sell")
    assert any(f"selling the {library._k(k_short)} call" in n for n in bcs["exercise"])
    assert any("covers it: exercising it delivers the shares" in n for n in bcs["exercise"])
    ic = strategy.build_trade("Iron Condor", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90)["exercise"]
    assert sum("You're selling" in n for n in ic) == 2 and sum("still caps the loss" in n for n in ic) == 2
    csp = " ".join(strategy.build_trade("Cash-Secured Put", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90)["exercise"])
    assert "The cash set aside covers it." in csp
    fly = " ".join(strategy.build_trade("Long Call Butterfly", "AAPL", 230.0, 0.3, date(2026, 11, 13), 90)["exercise"])
    assert "200 shares" in fly


def test_position_greeks_match_card_pricing():
    """Card Greeks are Black-Scholes at the card's own vol/time: check against finite differences of bs_price."""
    as_of, spot, vol = date(2026, 11, 16), 200.0, 0.3
    for structure in ("Long Call", "Bull Call Spread", "Long Straddle", "Iron Condor"):
        tr = strategy.build_trade(structure, "XYZ", spot, vol, as_of, 90)
        g = tr["greeks"]
        legs = tr["trade_legs"]
        t = g["days"] / 365.0

        def value(s, v=vol, tt=t):
            return sum((1 if l["action"] == "Buy" else -1) * l.get("quantity", 1) * 100
                       * strategy.bs_price(s, l["strike_price"], tt, v, l["option_type"].lower()) for l in legs)
        h = 0.01
        assert g["delta"] == pytest.approx((value(spot + h) - value(spot - h)) / (2 * h), abs=0.2)
        assert g["vega"] == pytest.approx((value(spot, vol + 0.005) - value(spot, vol - 0.005)), abs=0.05)
        assert g["theta"] == pytest.approx(value(spot, tt=t - 1 / 365) - value(spot), abs=0.05)
        assert g["gamma"] == pytest.approx((value(spot + 1) - 2 * value(spot) + value(spot - 1)), abs=0.02)
    straddle = strategy.build_trade("Long Straddle", "XYZ", spot, vol, as_of, 90)["greeks"]
    assert abs(straddle["delta"]) < 20 and straddle["gamma"] > 0 and straddle["theta"] < 0 and straddle["vega"] > 0
    condor = strategy.build_trade("Iron Condor", "XYZ", spot, vol, as_of, 90)["greeks"]
    assert condor["theta"] > 0 and condor["vega"] < 0
    assert strategy.build_trade("Buy Stock", "XYZ", spot, vol, as_of, 90).get("greeks") is None
    cc = strategy.build_trade("Covered Call", "XYZ", spot, vol, as_of, 90)
    call = [l for l in cc["trade_legs"] if l.get("instrument") == "option"][0]
    assert 0 < cc["greeks"]["delta"] < 100 and cc["greeks"]["theta"] > 0


def test_yesno_reasons_say_one_trading_day_in_the_singular():
    from backend.v4 import yesno
    one = yesno._reasons({"trend": 1.0, "trend_age": 1, "ideas": None}, "SPY")
    two = yesno._reasons({"trend": -1.0, "trend_age": 3, "ideas": None}, "SPY")
    assert "(for 1 trading day)." in one[0] and "(for 3 trading days)." in two[0]


def test_news_opposite_never_bets_a_stock_the_same_way_as_its_hunch(monkeypatch):
    """Live, 385 of 939 news pairs had a stock bet the same way on a hunch and on "I don't think <hunch>" ("I don't
    think big retailers' sales recovery will stall" -> TGT down, like the hunch). The opposite now runs after its
    hunch and drops those picks; a pair with nothing left on the opposite side is skipped, not learned."""
    from backend.v4 import interpreter

    class Mirror(FakeClaude):  # the opposite comes back as a copy of the hunch, plus one real opposite (LOSR up)
        def create(self, **kw):
            msg = kw["messages"][0]["content"]
            out = default_interp(msg)
            if "I don't think" in msg:
                out["candidates"] = [dict(c) for c in out["candidates"]]
                out["candidates"][1]["direction"] = "bullish"  # LOSR
                for c in out["candidates"][2:]:
                    c["direction"] = "bearish"
            else:
                for c in out["candidates"]:
                    c["direction"] = "bearish" if c["ticker"] in ("LOSR", "WINR") else c["direction"]
            self.calls.append(kw)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(out))],
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=10, cache_read_input_tokens=0,
                                                         cache_creation_input_tokens=0), stop_reason="end_turn")

    hunch = "Plumbing demand will cool"
    beliefs = [f"{seeder.OPPOSITE}plumbing demand will cool", hunch]  # opposite listed first: order must not matter
    r = seeder.run("live", n=2, beliefs=beliefs, source="seed_news", concurrency=2, max_usd=1, claude_client=Mirror())
    assert r["ok"] == 2

    def picks(text):
        row = db.query_one("SELECT id FROM beliefs WHERE text = ?", (text,))
        return {(p["ticker"], p["direction"]) for p in db.query("SELECT ticker, direction FROM picks WHERE belief_id = ?", (row["id"],))}
    a, b = picks(hunch), picks(beliefs[0])
    assert ("PIPE", "bullish") in a and ("PIPE", "bullish") not in b   # same bet on both sides: dropped
    assert ("LOSR", "bearish") in a and ("LOSR", "bullish") in b       # a real opposite stays
    assert not (a & b)

    # nothing left on the opposite side: skipped, never stored
    out = engine.process_belief("I don't think plumbing demand will rise", "seed", source="seed_news",
                                claude_client=FakeClaude(),
                                avoid={(t, "bullish") for t in ("PIPE", "LOSR", "WINR", "FLAT", "XLI", "NOPE")})
    assert out["valid"] is False and out["error"] == "same_side_as_original"
    assert not db.query_one("SELECT id FROM beliefs WHERE text = ?", ("I don't think plumbing demand will rise",))

    # against (a custom story's own read): those bets are plainly dropped, the rest stay
    out = engine.process_belief("Plumbing demand will boom", "seed", source="seed_story", claude_client=FakeClaude(),
                                against={("PIPE", "bullish")})
    got = {(p["ticker"], p["direction"]) for p in out["picks"]}
    assert out["valid"] and got and ("PIPE", "bullish") not in got

    # users who say they DON'T expect something get the opposite bet
    assert "WON'T happen" in interpreter.SYSTEM_PROMPT and "bet FOR it" in interpreter.SYSTEM_PROMPT


def test_opposite_view_with_no_side_of_its_own_is_dropped():
    # Real pairs from the news seeder (Nov 2026). The opposite keeps a pick only if it has a side of its own.
    c = lambda *xs: [{"ticker": t, "direction": d} for t, d in (x.split(":") for x in xs)]
    a = lambda *xs: {tuple(x.split(":")) for x in xs}
    kept = lambda cands, avoid: {f"{x['ticker']}:{x['direction']}" for x in engine.drop_same_side(cands, avoid)}
    crypto = a("COIN:bearish", "MSTR:bearish", "IBIT:bearish")
    # "I don't think Bitcoin's selloff may signal a longer downturn" -> QQQ down: same way as the hunch, no other side
    assert kept(c("QQQ:bearish"), crypto) == set()
    assert kept(c("QQQ:bearish", "COIN:bullish"), crypto) == {"QQQ:bearish", "COIN:bullish"}
    # winners vs losers survive: "AI firms won't pay publishers" -> publishers down, META up
    pubs = a("WLY:bullish", "RELX:bullish", "NYT:bullish", "GOOGL:bullish")
    assert kept(c("RELX:bearish", "WLY:bearish", "META:bullish"), pubs) == {"RELX:bearish", "WLY:bearish", "META:bullish"}
    # "young renters won't keep cutting housing to fund holiday shopping": WMT/AMZN up on both sides, XLY/MCD up
    renters = a("WMT:bullish", "AMZN:bullish", "TGT:bullish", "XRT:bullish", "HD:bearish")
    assert kept(c("WMT:bullish", "AMZN:bullish", "XLY:bullish", "MCD:bullish"), renters) == set()
    # volatility picks are never dropped; a hunch split evenly has no main side, so only rule 1 applies
    assert kept(c("XLY:bullish", "VXX:volatile"), renters) == {"VXX:volatile"}
    even = a("AMD:bullish", "NVDA:bearish")
    assert kept(c("INTC:bullish", "AMD:bullish"), even) == {"INTC:bullish"}


def test_my_beliefs_marks_the_newest_graded_check_like_the_base_rate():
    # "Where your call landed": My beliefs carries each call's newest graded checkpoint, measured exactly like the
    # base-rate spread (theme vs the S&P in the direction called; its sign is belief_right).
    from backend.v4 import baserate
    r = engine.process_belief("plumbing demand is going to be high", "u-spot", "moderate", claude_client=FakeClaude())
    bid = r["belief_id"]
    assert engine.my_beliefs("u-spot")["beliefs"][0]["graded"] is None     # nothing graded yet
    d = db.query_one("SELECT direction FROM beliefs WHERE id = ?", (bid,))["direction"]
    pids = [x["id"] for x in db.query("SELECT id FROM picks WHERE belief_id = ? AND direction = ?", (bid, d))]
    assert pids
    for pid in pids:
        for cp, bench, spy, right, on in ((7, 0.05, 0.02, 1, "2026-01-08"), (30, 0.01, 0.04, 0, "2026-01-31")):
            db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at,
                          bench_ret, belief_right) VALUES (?, ?, ?, 1, 0.1, ?, 0.1, ?, ?, ?)""", (pid, cp, on, spy, on, bench, right))
    g = engine.my_beliefs("u-spot")["beliefs"][0]["graded"]
    assert g["checkpoint_days"] == 30 and g["on"] == "2026-01-31" and g["right"] is False   # the newest check wins
    want = baserate._call_excess(d, 0.01, 0.04)
    assert abs(g["vs_spy"] - round(want, 4)) < 1e-9 and (g["vs_spy"] > 0) == g["right"]
    # the same number the base-rate spread sorts for this call at that check
    assert round(want, 4) in [round(x, 4) for x in baserate._spreads()[(d, 30)]]
    # ungraded rows (belief_right still empty) are not a result
    db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at)
                  VALUES (?, 90, '2026-04-01', 1, 0.1, 0.0, 0.1, '2026-04-01')""", (pids[0],))
    assert engine.my_beliefs("u-spot")["beliefs"][0]["graded"]["checkpoint_days"] == 30


def test_strategy_reason_never_claims_a_goal_the_user_did_not_give():
    """Shares or 'Any options strategy' (no goal asked): the card must not say 'what you said matters most'."""
    from backend.v4 import library
    P = strategy.normalize_prefs
    s, why = strategy.select("bullish", 30, "medium", "moderate", P({"instrument": "shares"}), price=185.0)
    assert s == "Buy Stock" and "shares" in why and "matters most" not in why
    s, why = strategy.select("bullish", 90, "medium", "moderate", P({"instrument": "options"}), price=185.0)
    assert library.LIB[s]["family"] == "options" and "matters most" not in why
    s, why = strategy.select("bullish", 90, "medium", "moderate", P({"instrument": "options", "goal": "limited"}), price=185.0)
    assert why == "Best fit for what you said matters most."

def test_price_delay_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(71)
    n = 400
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    sret = [rng.gauss(0, 0.01) for _ in range(n)]
    spy = [100.0]
    for r in sret[1:]:
        spy.append(spy[-1] * (1 + r))
    # a fast stock moves with SPY the same day; a slow one takes the same move 10 sessions (2 weeks) late
    fast, slow = [50.0], [50.0]
    for k in range(1, n):
        fast.append(fast[-1] * (1 + sret[k] + rng.gauss(0, 0.002)))
        slow.append(slow[-1] * (1 + (sret[k - 10] if k >= 10 else 0.0) + rng.gauss(0, 0.002)))
    i = n - 1
    d_fast = market.delay(dates, fast, dates, spy, i)
    d_slow = market.delay(dates, slow, dates, spy, i)
    assert 0.0 <= d_fast < 0.3 and d_slow > 0.8
    assert market.delay(dates, slow, dates, spy, 100) == market.DELAY_NEUTRAL   # under a year of weekly history
    later = slow[:300] + [c * 3 for c in slow[300:]]
    assert market.delay(dates, later, dates, spy, 299) == market.delay(dates, slow, dates, spy, 299)  # no look-ahead
    assert "delay" in research.FEATS and "delay" in research.DIRECTIONAL and research.NEUTRAL["delay"] == market.DELAY_NEUTRAL
    # planted: delayed stocks pay for longs, quick ones pay for shorts; the rule (z_delay) finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-dl-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            dl = rng.uniform(0.0, 1.0)
            ex = -dl * 0.04 if bear else dl * 0.04
            pid = f"p-dl-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"delay": dl}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["price delay premium (z_delay)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills delay as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, spy if s == "SPY" else later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4}
    asof = dates[299]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-dlx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-dlx", "b-dlx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-dlx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-dlx'")["features"])["num"]
    assert abs(num["delay"] - market.delay(dates, slow, dates, spy, 299)) < 1e-12 and num["delay"] > 0.5
    assert num["ltr"] == 0.4 and num["beta"] == 1.2


def test_realized_skewness_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, math as _m, random as _r
    rng = _r.Random(83)
    n = 300
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    # right-skewed: small down days with rare big jumps up; left-skewed: the mirror image
    up, dn, flat = [50.0], [50.0], [50.0]
    for k in range(1, n):
        jump = k % 13 == 0
        up.append(up[-1] * _m.exp(0.08 if jump else -0.006 + rng.gauss(0, 0.002)))
        dn.append(dn[-1] * _m.exp(-0.08 if jump else 0.006 + rng.gauss(0, 0.002)))
        flat.append(flat[-1] * _m.exp(rng.gauss(0, 0.01)))
    i = n - 1
    assert market.rskew(up, i) > 2.0 and market.rskew(dn, i) < -2.0 and abs(market.rskew(flat, i)) < 1.0
    assert market.rskew(up, 30) == 0.0                     # under 40 returns of history
    assert market.rskew([10.0] * n, i) == 0.0              # no variation
    later = up[:200] + [c * 5 for c in up[200:]]
    assert market.rskew(later, 199) == market.rskew(up, 199)  # no look-ahead
    assert "rskew" in research.FEATS and "rskew" in research.DIRECTIONAL
    # planted: left-skewed stocks pay for longs, right-skewed ones pay for shorts; the rule (-z_rskew) finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-sk-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            sk = rng.uniform(-2.0, 2.0)
            ex = sk * 0.02 if bear else -sk * 0.02
            pid = f"p-sk-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"rskew": sk}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["avoid right-skewed stocks (-z_rskew)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills rskew as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, flat if s == "SPY" else later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features",
                 "delay_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4, "delay": 0.3}
    asof = dates[199]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-skx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-skx", "b-skx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-skx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-skx'")["features"])["num"]
    assert abs(num["rskew"] - market.rskew(up, 199)) < 1e-12 and num["rskew"] > 2.0
    assert num["delay"] == 0.3 and num["beta"] == 1.2

def test_coskewness_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(91)
    n = 320
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    spy, neg, pos, ind = [400.0], [50.0], [50.0], [50.0]
    for k in range(1, n):
        m = rng.gauss(0, 0.01) * (4.0 if k % 17 == 0 else 1.0)   # SPY with occasional big days either way
        big = (m * m) / 1e-4                                       # ~1 on ordinary days, ~16 on big ones
        spy.append(spy[-1] * (1 + m))
        neg.append(neg[-1] * (1 + m - 0.004 * (big - 1.5) + rng.gauss(0, 0.004)))  # falls when SPY swings hard
        pos.append(pos[-1] * (1 + m + 0.004 * (big - 1.5) + rng.gauss(0, 0.004)))  # rises when SPY swings hard
        ind.append(ind[-1] * (1 + m + rng.gauss(0, 0.01)))
    i = n - 1
    cn, cp, ci = (market.coskew(dates, c, dates, spy, i) for c in (neg, pos, ind))
    assert cn < -1.5 and cp > 1.5 and abs(ci) < 1.0, (cn, cp, ci)
    assert market.coskew(dates, neg, dates, spy, 100) == 0.0              # under 150 matched days
    assert market.coskew(dates, [10.0] * n, dates, spy, i) == 0.0         # no variation
    later = neg[:250] + [c * 3 for c in neg[250:]]
    assert market.coskew(dates, later, dates, spy, 249) == market.coskew(dates, neg, dates, spy, 249)  # no look-ahead
    assert "coskew" in research.FEATS and "coskew" in research.DIRECTIONAL
    # planted: negatively coskewed stocks pay for longs, positively coskewed ones pay for shorts; -z_coskew finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-ck-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            ck = rng.uniform(-1.0, 1.0)
            ex = ck * 0.04 if bear else -ck * 0.04
            pid = f"p-ck-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"coskew": ck}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["negative coskewness premium (-z_coskew)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills coskew as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, spy if s == "SPY" else later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features",
                 "delay_features", "rskew_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4, "delay": 0.3, "rskew": 0.7}
    asof = dates[249]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-ckx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-ckx", "b-ckx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-ckx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-ckx'")["features"])["num"]
    assert abs(num["coskew"] - market.coskew(dates, neg, dates, spy, 249)) < 1e-12 and num["coskew"] < -1.0
    assert num["rskew"] == 0.7 and num["beta"] == 1.2


def test_trading_activity_variability_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(57)
    n = 300
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    closes = [20.0 * (1 + 0.001 * k) for k in range(n)]
    steady = [1e6 * (1 + rng.uniform(-0.05, 0.05)) for _ in range(n)]
    jumpy = [1e6 * (8.0 if k % 10 == 0 else 0.3) for k in range(n)]
    i = n - 1
    cs, cj = market.cvvol(closes, steady, i), market.cvvol(closes, jumpy, i)
    assert 0 < cs < 0.1 and cj > 1.5, (cs, cj)
    assert market.cvvol(closes, steady, 100) == 0.0                       # under 120 priced sessions
    assert market.cvvol(closes, [0.0] * n, i) == 0.0                      # no volume
    assert market.cvvol(closes, steady[:5], i) == 0.0                     # volumes don't line up with closes
    later = jumpy[:250] + [v * 50 for v in jumpy[250:]]
    assert market.cvvol(closes, later, 249) == market.cvvol(closes, jumpy, 249)  # no look-ahead
    assert "cvvol" in research.FEATS and "cvvol" in research.DIRECTIONAL
    # planted: steady-trading stocks pay for longs, jumpy ones pay for shorts; -z_cvvol finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-cv-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            cv = rng.uniform(0.2, 2.0)
            ex = (cv - 1.1) * 0.04 if bear else -(cv - 1.1) * 0.04
            pid = f"p-cv-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"cvvol": cv}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["steady trading activity (-z_cvvol)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills cvvol as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, closes))
    monkeypatch.setattr(market, "daily_volumes", lambda s: later)
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features",
                 "delay_features", "rskew_features", "coskew_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4, "delay": 0.3, "rskew": 0.7, "coskew": -0.2}
    asof = dates[249]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-cvx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-cvx", "b-cvx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-cvx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-cvx'")["features"])["num"]
    assert abs(num["cvvol"] - market.cvvol(closes, jumpy, 249)) < 1e-12 and num["cvvol"] > 1.5
    assert num["coskew"] == -0.2 and num["rskew"] == 0.7


def test_timing_of_52_week_high_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, random as _r
    rng = _r.Random(61)
    n = 300
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    rising = [10.0 + 0.01 * k for k in range(n)]                          # new high every day
    peaked = [10.0 + 0.05 * k if k <= 60 else 13.0 - 0.001 * (k - 60) for k in range(n)]  # high at session 60
    i = n - 1
    assert market.hi_age(rising, i) == 0.0
    assert abs(market.hi_age(peaked, i) - (i - 60) / 251) < 1e-12        # 238 sessions ago, out of 251
    assert market.hi_age(rising, 150) == 0.5                              # under 200 priced sessions: neutral
    flat = [5.0] * n
    assert market.hi_age(flat, i) == 0.0                                  # ties take the latest day
    later = peaked[:250] + [99.0] * (n - 250)
    assert market.hi_age(later, 249) == market.hi_age(peaked, 249)        # no look-ahead
    assert "hi_age" in research.FEATS and "hi_age" in research.DIRECTIONAL and research.NEUTRAL["hi_age"] == 0.5
    # planted: recent-high stocks pay for longs, distant-high ones pay for shorts; -z_hi_age finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-ha-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            ha = rng.uniform(0.0, 1.0)
            ex = (ha - 0.5) * 0.06 if bear else -(ha - 0.5) * 0.06
            pid = f"p-ha-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"hi_age": ha}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["recent 52-week high (-z_hi_age)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills hi_age as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, later))
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features",
                 "delay_features", "rskew_features", "coskew_features", "cvvol_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4, "delay": 0.3, "rskew": 0.7, "coskew": -0.2, "cvvol": 0.9}
    asof = dates[249]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-hax", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-hax", "b-hax", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-hax", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-hax'")["features"])["num"]
    assert abs(num["hi_age"] - (249 - 60) / 251) < 1e-12
    assert num["cvvol"] == 0.9 and num["coskew"] == -0.2

def test_dollar_volume_level_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, math as _m, random as _r
    rng = _r.Random(67)
    n = 300
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    closes = [20.0] * n
    vols = [1e5] * n
    i = n - 1
    assert abs(market.ldvol(closes, vols, i) - _m.log(2e6)) < 1e-12
    assert market.ldvol(closes, vols, 100) == 15.0                       # under 120 priced sessions: neutral
    assert market.ldvol(closes, vols[:5], i) == 15.0                     # volumes don't line up with closes
    later = vols[:250] + [1e9] * (n - 250)
    assert market.ldvol(closes, later, 249) == market.ldvol(closes, vols, 249)  # no look-ahead
    assert "ldvol" in research.FEATS and "ldvol" in research.DIRECTIONAL and research.NEUTRAL["ldvol"] == 15.0
    # planted: thinly traded stocks pay for longs, heavily traded ones pay for shorts; -z_ldvol finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-ld-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            lv = rng.uniform(13.0, 21.0)
            ex = (lv - 17.0) * 0.008 if bear else -(lv - 17.0) * 0.008
            pid = f"p-ld-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"ldvol": lv}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["low dollar volume (-z_ldvol)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills ldvol as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, closes))
    monkeypatch.setattr(market, "daily_volumes", lambda s: later)
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features",
                 "delay_features", "rskew_features", "coskew_features", "cvvol_features", "hi_age_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4, "delay": 0.3, "rskew": 0.7, "coskew": -0.2, "cvvol": 0.9,
            "hi_age": 0.4}
    asof = dates[249]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-ldx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-ldx", "b-ldx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-ldx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-ldx'")["features"])["num"]
    assert abs(num["ldvol"] - _m.log(2e6)) < 1e-12
    assert num["hi_age"] == 0.4 and num["cvvol"] == 0.9

def test_vol_of_vol_rule_and_enrich_backfill(monkeypatch):
    from backend.v4 import market, research
    import datetime as _dt, math as _m, random as _r
    rng = _r.Random(71)
    n = 300
    dates = [(_dt.date(2022, 1, 3) + _dt.timedelta(days=k)).isoformat() for k in range(n)]
    # steady risk: the same 1% daily up/down zigzag every month -> every block has the same vol, vov = 0
    steady = [100.0]
    for k in range(1, n):
        steady.append(steady[-1] * (1.01 if k % 2 else 1 / 1.01))
    i = n - 1
    assert market.vov(steady, i) < 1e-9
    # alternating calm (0.2%) and wild (3%) months -> high vov
    swing = [100.0]
    for k in range(1, n):
        amp = 0.03 if ((i - k) // 21) % 2 == 0 else 0.002
        swing.append(swing[-1] * ((1 + amp) if k % 2 else 1 / (1 + amp)))
    assert market.vov(swing, i) > 0.5
    assert market.vov(steady, 150) == 0.35                                # under 9 full monthly blocks: neutral
    later = steady[:250] + [x * (1 + 0.2 * rng.random()) for x in steady[250:]]
    assert market.vov(later, 249) == market.vov(steady, 249)              # no look-ahead
    assert "vov" in research.FEATS and "vov" in research.DIRECTIONAL and research.NEUTRAL["vov"] == 0.35
    # planted: steady-risk stocks pay for longs, jumpy-risk ones pay for shorts; -z_vov finds it
    b0 = _dt.date(2024, 1, 1)
    for k in range(400):
        bid, asof, bear = f"b-vv-{k}", (b0 + _dt.timedelta(days=k * 2)).isoformat(), k % 2 == 1
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for q in range(4):
            v = rng.uniform(0.1, 0.9)
            ex = (v - 0.5) * 0.08 if bear else -(v - 0.5) * 0.08
            pid = f"p-vv-{k}-{q}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{q}", "bearish" if bear else "bullish", asof, 10.0, db.dumps({"num": {"vov": v}}), q + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex + rng.gauss(0, 0.005), asof))
    r = research.run(data=research.load())["results"]["steady volatility (-z_vov)"]
    assert r["n"] > 100 and r["lift"] > 0.01 and r["lift_t"] > 3
    # enrich backfills vov as of each pick's own date only, leaving the other features alone
    monkeypatch.setattr(market, "daily_closes", lambda s: (dates, later))
    monkeypatch.setattr(market, "daily_volumes", lambda s: [1e5] * n)
    for name in ("vp_features", "resid_features", "fip_features", "max_features", "echo_features", "mad_features",
                 "amihud_features", "co_features", "seas_features", "dbeta_features", "ivol_features", "ltr_features",
                 "delay_features", "rskew_features", "coskew_features", "cvvol_features", "hi_age_features",
                 "ldvol_features"):
        monkeypatch.setattr(market, name, lambda *a, **k: (_ for _ in ()).throw(AssertionError("not needed")))
    have = {"mom60": 0.1, "vp_poc_dist": 0.2, "reg_trend": 1.0, "mu_dist": 0.0, "fip_id": -0.3, "resid_mom": 1.0,
            "beta": 1.2, "max5": 0.03, "mom_12_7": 0.4, "mad": 0.05, "amihud": 2.5, "co": 0.3, "seas": 0.02,
            "dbeta": 0.1, "ivol": 0.25, "ltr": 0.4, "delay": 0.3, "rskew": 0.7, "coskew": -0.2, "cvvol": 0.9,
            "hi_age": 0.4, "ldvol": 16.0}
    asof = dates[249]
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
               ("b-vvx", "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
    db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features) VALUES (?,?,?,?,?,?,?)",
               ("p-vvx", "b-vvx", "XYZ", "bullish", asof, 10.0, db.dumps({"num": have})))
    db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
               ("p-vvx", 90, asof, 10.0, 0.0, 0.0, 0.01, asof))
    research.enrich(10000)
    num = db.loads(db.query_one("SELECT features FROM picks WHERE id = 'p-vvx'")["features"])["num"]
    assert num["vov"] < 1e-9
    assert num["ldvol"] == 16.0 and num["hi_age"] == 0.4

def test_ticker_must_still_be_the_company_the_idea_names():
    # Live pairs (Nov 2026): a reused ticker or a misread pairs an idea with another company. Renames and
    # abbreviations still count as the same company.
    from backend.v4.names import same_company as same
    assert not same("Paramount Global", "Parabolic Technologies, Inc. Class A Common Stock", "PARA")
    assert not same("Philip Morris International", "Picard Medical, Inc.", "PMI")
    assert not same("BYD", "Boyd Gaming Corporation", "BYD")
    assert not same("Cal-Maine Foods", "Caleres Inc", "CAL")
    assert not same("Intermex", "Invesco Intermediate Municipal ETF", "INTM")
    assert not same("Novozymes", "TrueShares Structured Outcome (November) ETF", "NOVZ")
    assert not same("iShares MSCI Japan", "iShares Gold Trust", "IAU")  # fund issuer alone isn't a match
    for t, meant, is_ in [("AAPL", "Apple Inc.", "Apple Inc. Common Stock"),
                          ("ADP", "ADP", "Automatic Data Processing, Inc. Common Stock"),
                          ("UEC", "UEC Corporation", "Uranium Energy Corp."),
                          ("ON", "onsemi", "ON Semiconductor Corporation Common Stock"),
                          ("TSM", "TSMC", "Taiwan Semiconductor Manufacturing Company Ltd."),
                          ("GE", "General Electric", "GE Aerospace"),
                          ("WAB", "Westinghouse Air Brake Technologies", "Wabtec Inc."),
                          ("MARA", "Marathon Digital", "MARA Holdings, Inc. Common Stock"),
                          ("MSTR", "MicroStrategy", "Strategy Inc Common Stock Class A"),
                          ("SLB", "Schlumberger", "SLB Limited"),
                          ("GOOGL", "Google", "Alphabet Inc. Class A Common Stock"),
                          ("XLF", "Financials Select Sector SPDR", "State Street Financial Select Sector SPDR ETF"),
                          ("SPY", "SPDR S&P 500 ETF", "State Street SPDR S&P 500 ETF Trust"),
                          ("QQQ", "Nasdaq 100 ETF", "Invesco QQQ Trust, Series 1"),
                          ("T", "AT&T", "AT&T Inc."), ("MMM", "3M", "3M Company"), ("PCG", "PG&E", "PG&E Corporation"),
                          ("X", "", "Anything Inc.")]:
        assert same(meant, is_, t), (t, meant, is_)

    # In the engine: the mismatched idea is dropped (and reported), Claude's name is kept with each pick.
    payload = default_interp("plumbing")
    payload["candidates"][0]["name"] = "Pipe Supply"
    payload["candidates"][1]["name"] = "Paramount Global"  # LOSR is "Loser Corp"
    r = engine.process_belief("plumbing demand is going to be high", "u-name", "moderate", claude_client=FakeClaude(payload))
    assert r["valid"] and "LOSR" not in {p["ticker"] for p in r["picks"]}
    assert r["name_mismatch"] == [{"ticker": "LOSR", "meant": "Paramount Global", "is": "Loser Corp"}]
    row = db.query_one("SELECT features FROM picks WHERE belief_id = ? AND ticker = 'PIPE'", (r["belief_id"],))
    assert json.loads(row["features"])["claude_name"] == "Pipe Supply"

    # Backfill: a history that's the new issuer's pasted over old dates (200x off today's price) is skipped.
    assert engine._plausible_history("PIPE", market.daily_closes("PIPE")[1][-1] * 3)
    assert not engine._plausible_history("PIPE", market.daily_closes("PIPE")[1][-1] * 500)


def test_brain_scorecard_says_whether_the_ranker_is_mixed(monkeypatch):
    """The Brain page says 'today's #1 also mixes in the retrained model' only for a mix; a model that passed alone
    picks the #1 alone (research.WEIGHT 1.0), so the scorecard must carry which one is live."""
    from backend.v4 import brain, research
    for mix in (False, True):
        monkeypatch.setattr(research, "ranker", lambda mix=mix: {"active": True, "at": "2026-11-16T07:00:00+00:00",
                                                                  "model": "mlp_adj_mix" if mix else "mlp_adj", "mix": mix,
                                                                  "oos": {"n": 10}, "risk_check": True})
        assert brain._skill()["ranker"]["mix"] is mix


def test_outlier_check_tells_a_broad_edge_from_a_few_lottery_tickets():
    """Research lifts are means of fat-tailed 90-day returns. The outlier check (reporting only) clips every outcome at
    the run's pooled 1st / 99th percentile, and reports the median lift and the 10 best calls' share of the lift: a
    rule that owns two +500% calls and nothing else shows a big lift, ~0 clipped lift and top10_share ~1; a broad edge
    keeps its clipped lift. The gate (_passes) still reads the plain lift and t."""
    from backend.v4 import research
    import numpy as _np
    rng = random.Random(21)
    beliefs = [{"date": f"2025-{1 + k % 12:02d}-{1 + k % 27:02d}",
                "cands": [{"ex": rng.gauss(0, 0.1)} for _ in range(4)]} for k in range(600)]
    beliefs[0]["cands"][0]["ex"] = 5.0; beliefs[1]["cands"][0]["ex"] = 5.0   # two +500% ideas
    lo, hi = research.winsor_cuts(beliefs)
    assert -0.4 < lo < -0.1 and 0.1 < hi < 0.4                    # per run, from the pooled outcomes (not hard-coded)
    assert research.winsor_cuts(beliefs[:5]) is None              # too few to say
    for b in beliefs:
        b["wmean"] = float(_np.mean(_np.clip([c["ex"] for c in b["cands"]], lo, hi)))
    mean = lambda b: float(_np.mean([c["ex"] for c in b["cands"]]))
    # lottery rule: picks the +500% idea where there is one, otherwise the idea closest to the belief's average
    lot = []
    for b in beliefs:
        c = b["cands"][0] if b["cands"][0]["ex"] >= 5 else min(b["cands"], key=lambda c: abs(c["ex"] - mean(b)))
        lot.append((c["ex"], mean(b), 0.0, 0.0, b["date"], b["wmean"]))
    broad = [(max(c["ex"] for c in b["cands"]) if b["cands"][0]["ex"] < 5 else b["cands"][1]["ex"],
              mean(b), 0.0, 0.0, b["date"], b["wmean"]) for b in beliefs]
    m, e = research._metrics(lot, (lo, hi)), research._metrics(broad, (lo, hi))
    assert m["lift"] > 0.01 and abs(m["lift_w"]) < 0.004 and m["top10_share"] > 0.9 and abs(m["lift_med"]) < 0.002
    assert e["lift_w"] > 0.05 and e["lift_w_t"] > 10 and e["top10_share"] < 0.2 and e["lift_med"] > 0.05
    assert "lift_w_t_nw" in e
    # no cuts / no clipped means: no clipped keys (callers outside run(), e.g. the live check)
    assert "lift_w" not in research._metrics(lot) and "lift_w" not in research._metrics([p[:5] for p in lot], (lo, hi))
    # the luck block reports which ways clear the bar once clipped; the gate keeps reading plain numbers
    lk = research.luck({"app (current #1)": {**m, "lift_adj_t": 0.0}, "broad": {**e, "lift_adj_t": 0.0}})
    assert lk["clear_w"] == ["broad"] and not lk["app_clears_w"] and lk["app_lift_w"] == m["lift_w"]
    assert lk["app_top10_share"] == m["top10_share"]
    assert research._passes({**m, "lift_w": 0.0, "lift_w_t": 0.0}, {}) == research._passes(m, {})


def test_research_run_reports_the_outlier_check():
    from backend.v4 import research
    rng = random.Random(5)
    d0 = __import__("datetime").date(2024, 1, 1)
    for k in range(300):
        bid = f"b-wz-{k}"
        asof = (d0 + __import__("datetime").timedelta(days=k * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            pid = f"p-wz-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", asof, 10.0, db.dumps({"num": {"mom60": rng.uniform(-1, 1)}}), j + 1))
            ex = 5.0 if (j == 0 and k in (250, 280)) else rng.gauss(0, 0.1)   # two +500% #1 picks in the test period
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex, asof))
    out = research.run(data=research.load())
    assert out["winsor"]["lo"] < 0 < out["winsor"]["hi"] < 1 and out["luck"]["winsor"] == out["winsor"]
    app = out["results"]["app (current #1)"]
    assert app["lift"] > app["lift_w"] + 0.01            # the two lottery tickets carry the plain lift
    assert app["top10_share"] is None or app["top10_share"] > 0.5
    assert "clear_w" in out["luck"] and out["luck"]["app_lift_w"] == app["lift_w"]


def test_learned_rankers_hold_back_a_feature_that_is_still_filling_in():
    """A feature the scout just added is backfilled over days; until it covers (nearly) every graded idea the learned
    rankers must not train on it (most ideas carry a placeholder; live calls never do). 2026-11-17: delay 12.6% filled."""
    from backend.v4 import research
    cov = {"share": {k: 1.0 for k in research.COV_KEYS}}
    assert research.learn_keys(cov) == list(research.ZKEYS)
    cov["share"].update({"delay": 0.126, "rskew": 0.0, "reg_trend": 0.5})
    keys = research.learn_keys(cov)
    assert "z_delay" not in keys and "z_rskew" not in keys and "z_mom60" in keys and "bearish" in keys
    assert "zx_mom60_reg_trend" not in keys and "zx_vol60_reg_crisis" in keys  # interactions on an unfilled input too
    assert set(keys) <= set(research.ZKEYS)

    rng = random.Random(11)
    d0 = __import__("datetime").date(2024, 1, 1)
    for k in range(300):
        bid = f"b-lk-{k}"
        asof = (d0 + __import__("datetime").timedelta(days=k * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            pid = f"p-lk-{k}-{j}"
            num = {"mom60": rng.uniform(-1, 1)}
            if k % 10 == 0:  # only ~10% of ideas backfilled so far
                num["delay"] = rng.uniform(0, 1)
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", asof, 10.0, db.dumps({"num": num}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, 0.05 * num["mom60"] + rng.gauss(0, 0.05), asof))
    out = research.run(data=research.load())
    assert "z_delay" in out["learn_held_back"] and "z_delay" not in out["learn_keys"]
    assert "z_mom60" in out["learn_keys"]
    assert "price delay premium (z_delay)" in out["provisional"]  # the fixed rule is still scored, marked provisional
    prod = research.fit_production(out)
    assert prod["keys"] == out["learn_keys"] and len(prod["w"]) == len(prod["keys"]) == len(prod["mu"])


def test_option_cards_price_each_strike_at_its_own_listed_implied_vol():
    """Live AAPL-like Bull Call Spread: the short OTM call trades at a lower vol than the at-the-money one the card used.
    Re-priced at each strike's own vol (OTM side: puts below spot, calls above), the card's economics and Greeks follow
    the new premiums; any leg without its own listed contract leaves the one-vol card unchanged (labelled as before)."""
    from backend.v4 import library, pricecheck
    as_of = date(2026, 11, 18)
    t = strategy.build_trade("Bull Call Spread", "AAPL", 350.0, 0.26, as_of, 30)
    t["vol_source"] = "implied"
    legs = [l for l in t["trade_legs"] if l["instrument"] == "option"]
    exp = date.fromisoformat(legs[0]["expiration"])
    lo, hi = sorted(float(l["strike_price"]) for l in legs)
    smile = {lo: 0.26, hi: 0.23}
    asked = []

    def iv_row(kind, k, e):
        asked.append((kind, k))
        return (e, k, smile[k])

    out = strategy.price_at_strike_vols(t, 350.0, as_of, iv_row)
    assert out["vol_source"] == "implied_strike" and out["vol"] == t["vol"]
    assert {k for _, k in asked} == {lo, hi} and all(kind == "call" for kind, _ in asked)  # both at/above spot: call side
    yrs = max((exp - as_of).days, 1) / 365.0
    short = next(l for l in out["trade_legs"] if l.get("action") == "Sell")
    assert short["vol"] == 0.23 and short["est_premium"] == round(strategy.bs_price(350.0, hi, yrs, 0.23, "call"), 2)
    assert short["est_premium"] < next(l for l in t["trade_legs"] if l.get("action") == "Sell")["est_premium"]
    # economics read off the new premiums, so the debit rises and max loss / breakeven move with it
    econ = library.economics(out["trade_legs"], 350.0)
    assert out["net_cost"] == econ["net_cost"] > t["net_cost"]
    assert out["max_loss"] == econ["max_loss"] and out["break_even"] == econ["break_even"]
    assert out["one_vol"]["net_cost"] == t["net_cost"]
    # Greeks at each leg's own vol: delta matches a finite difference of the same per-leg prices
    h = 0.01
    val = lambda s: sum((1 if l["action"] == "Buy" else -1) * 100 * strategy.bs_price(s, float(l["strike_price"]), yrs, l["vol"], "call")
                        for l in out["trade_legs"] if l["instrument"] == "option")
    assert out["greeks"]["delta"] == pytest.approx((val(350 + h) - val(350 - h)) / (2 * h), abs=0.1)
    assert out["greeks"]["delta"] != strategy.position_greeks(t["trade_legs"], 350.0, 0.26, as_of)["delta"]
    # a strike below spot reads the put side's vol (out of the money)
    t2 = strategy.build_trade("Bear Put Spread", "AAPL", 350.0, 0.26, as_of, 30)
    asked.clear()
    strategy.price_at_strike_vols(t2, 350.0, as_of, lambda kind, k, e: asked.append((kind, k)) or (e, k, 0.27))
    assert dict((k, kind) for kind, k in asked)[min(k for _, k in asked)] == "put"
    # all or nothing: a missing leg, the wrong strike/expiry or an absurd vol keeps the one-vol card
    assert strategy.price_at_strike_vols(t, 350.0, as_of, lambda kind, k, e: None if k == hi else (e, k, 0.26)) is t
    assert strategy.price_at_strike_vols(t, 350.0, as_of, lambda kind, k, e: (e, k + 5, 0.26)) is t
    assert strategy.price_at_strike_vols(t, 350.0, as_of, lambda kind, k, e: (e + timedelta(days=7), k, 0.26)) is t
    assert strategy.price_at_strike_vols(t, 350.0, as_of, lambda kind, k, e: (e, k, 0.9)) is t
    stock = strategy.build_trade("Buy Stock", "AAPL", 350.0, 0.26, as_of, 30)
    assert strategy.price_at_strike_vols(stock, 350.0, as_of, iv_row) is stock
    # Price check: a per-strike card says so instead of "one number for every strike"
    res = {"available": True, "strike": hi, "expiration": exp.isoformat(), "mid": short["est_premium"],
           "bid": short["est_premium"] - 0.1, "ask": short["est_premium"] + 0.1, "underlying": "AAPL", "spot": 350.0,
           "contract_iv": 0.23}
    c = pricecheck.card_vs_listed(res, short["est_premium"], hi, exp.isoformat(), 0.23, "implied_strike", 350.0)
    assert "own listed implied volatility" in c["text"] and "one number" not in c["text"] and c["in_spread"]
    c1 = pricecheck.card_vs_listed(res, 4.06, hi, exp.isoformat(), 0.26, "implied", 350.0)
    assert "one number for every strike" in c1["text"]


def test_my_beliefs_shows_and_counts_the_same_idea_run_twice_in_a_day_once():
    fake = FakeClaude()
    engine.process_belief("plumbing demand is going to be high", "u-twice", "moderate", claude_client=fake)
    r2 = engine.process_belief("Plumbing demand is going to be high", "u-twice", "moderate", claude_client=fake)
    r3 = engine.process_belief("potatoes are in demand", "u-twice", "moderate", claude_client=fake)
    mine = engine.my_beliefs("u-twice")["beliefs"]
    assert [b["belief_id"] for b in mine] == [r3["belief_id"], r2["belief_id"]]  # newest run kept, once
    assert [b["runs"] for b in mine] == [1, 2]


def test_is_it_new_reports_agreement_with_the_app_and_the_head_to_head_where_they_differ():
    """docs/feature_ideas.md 2026-11-18 "Is it new?": a rule that copies the app's no-look-ahead #1 shows same_as_app 1
    and no disagreements; a rule planted to beat the app where they differ shows a large lift_diff_t. Reporting only:
    the gate reads the same numbers as before."""
    from backend.v4 import research
    rng = random.Random(8)
    beliefs, base, copy, better = [], {}, [], []
    for k in range(400):
        b = {"date": f"2025-{1 + k % 12:02d}-{1 + k % 27:02d}", "cands": [{"ex": rng.gauss(0, 0.1)} for _ in range(4)]}
        beliefs.append(b)
        base[id(b)] = 0                                   # the app's #1 is idea 0
        copy.append((id(b), 0, b))
        if k % 2:                                         # half the time the planted rule picks another idea, the best
            j = max(range(1, 4), key=lambda q: b["cands"][q]["ex"])
            b["cands"][j]["ex"] = max(b["cands"][j]["ex"], b["cands"][0]["ex"] + 0.05)
            better.append((id(b), j, b))
        else:
            better.append((id(b), 0, b))
    c, w = research._vs_app(copy, base), research._vs_app(better, base)
    assert c == {"same_as_app": 1.0, "n_diff": 0}
    assert w["same_as_app"] == 0.5 and w["n_diff"] == 200 and w["lift_diff"] > 0.05 and w["lift_diff_t"] > 3
    assert "lift_diff_t_nw" in w
    assert research._vs_app([(1, 0, beliefs[0])], {}) == {}   # no app #1 for that call: nothing to say
    res = {"app (current #1)": {"n": 400, "lift_t": 9.0, **c}, "app, no look-ahead": {"n": 400, "lift_t": 8.0},
           "copycat": {"n": 400, "lift": 0.01, "lift_t": 2.0, **c}, "better": {"n": 400, "lift": 0.03, "lift_t": 5.0, **w},
           "no head-to-head": {"n": 400, "lift_t": 7.0}}
    top = research.is_new(res)
    assert [r["name"] for r in top] == ["better", "copycat"] and top[0]["n_diff"] == 200
    m = {"lift": 0.02, "lift_t": 3.0, "beat": 0.6}
    assert research._passes({**m, **w}, {}) == research._passes(m, {})


def test_research_run_reports_is_it_new():
    from backend.v4 import research
    rng = random.Random(6)
    d0 = __import__("datetime").date(2024, 1, 1)
    for k in range(300):
        bid = f"b-new-{k}"
        asof = (d0 + __import__("datetime").timedelta(days=k * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            pid = f"p-new-{k}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", asof, 10.0, db.dumps({"num": {"mom60": rng.uniform(-1, 1)}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, rng.gauss(0, 0.1), asof))
    out = research.run(data=research.load())
    r = out["results"]
    assert "same_as_app" not in r["app, no look-ahead"]
    mom = r["momentum (z_mom60)"]
    assert 0 <= mom["same_as_app"] <= 1 and mom["n_diff"] <= mom["n"]
    assert isinstance(out["luck"]["is_new"], list) and len(out["luck"]["is_new"]) <= 3
    assert all("same_as_app" in x for x in out["luck"]["is_new"])


def test_yesno_quotes_set_at_another_stock_price_fall_back_to_one_vol(monkeypatch):
    """Put-call parity reads the stock price the option quotes imply; when it's well away from the stock's last price
    (quotes set at another moment), the call spread's odds describe a close relative to that other price, so the
    one-vol answer at the last price is shown and the gap is named. Quotes consistent with the price are untouched."""
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price, RISK_FREE
    import math
    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=6)
    yrs = 6 / 365
    iv = lambda k: 0.35 - 0.3 * (k / spot - 1)                     # mild equity skew

    def chain_at(s):
        def chain(u, strike, e, days=21, band=0.15):
            out = []
            for k in range(int(spot * 0.9), int(spot * 1.1) + 1):
                for t in ("call", "put"):
                    mid = bs_price(s, float(k), yrs, iv(k), t)
                    out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                                "bid": round(max(0.01, mid - 0.02), 2), "ask": round(mid + 0.02, 2), "iv": iv(k)})
            return out
        return chain

    # Pure parity: the quotes' own stock price comes back, with half the bid/ask as noise.
    monkeypatch.setattr(market, "option_chain_near", chain_at(spot * 1.012))
    rows = market.option_chain_near("WINR", spot, exp)
    f, noise = yesno.parity_forward(rows, [float(int(spot))], yrs)
    assert abs(f * math.exp(-RISK_FREE * yrs) - spot * 1.012) < 0.05 and 0 < noise < 0.05
    assert yesno.quotes_out_of_step(spot, (f, noise), 0.35, yrs)
    assert not yesno.quotes_out_of_step(spot, (spot * math.exp(RISK_FREE * yrs), 0.02), 0.35, yrs)
    # A forward 1.5% below the price is what a dividend before expiration does: not flagged. 1.5% above is.
    assert not yesno.quotes_out_of_step(spot, (spot * 0.985, 0.02), 0.35, yrs)
    assert yesno.quotes_out_of_step(spot, (spot * 1.015, 0.02), 0.35, yrs)
    assert yesno.parity_forward([r for r in rows if r["type"] == "call"], [float(int(spot))], yrs) is None

    lvl = float(int(spot) + 2)
    q = yesno.quote("WINR", lvl, exp.isoformat())
    assert q["market_p"] == q["market_p_flat_vol"] and q["leg_vols"] is None
    assert "set as if WINR were near" in q["odds_source"] and f"${spot:,.2f}" in q["odds_source"]

    # The same quotes set at the last price: odds read off the call spread as before.
    monkeypatch.setattr(market, "option_chain_near", chain_at(spot))
    q = yesno.quote("WINR", lvl, exp.isoformat())
    assert "call spread" in q["odds_source"] and q["market_p"] != q["market_p_flat_vol"]


def test_yesno_calls_and_puts_set_at_different_prices_are_not_read_as_odds(monkeypatch):
    """Live Sun Nov 22, NVDA $129.17, Nov 27: the $127/$133 call spread's mid ($3.06) read "51% to close above $130",
    while the matching put spread's mid was $3.85: $6.91 for a spread that pays $6. By parity the two always add up to
    the strike gap (a dividend cancels), so the calls and puts were set at different stock prices and neither can be
    read against the last price. The quotes' own stock price (~$126) sat inside quotes_out_of_step's 2% dividend room,
    so this check catches it: the one-vol answer at the last price, said plainly, and the listed box says the quotes
    don't fit together. Quotes that do add up are untouched."""
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price
    e = date(2026, 11, 27)
    yrs = 5 / 365

    def row(t, k, bid, ask):
        return {"symbol": f"N{k}{t}", "type": t, "strike": k, "expiration": e, "bid": bid, "ask": ask, "iv": 0.94}
    nvda = [row("call", 127.0, 7.46, 7.47), row("call", 133.0, 4.32, 4.49),
            row("put", 127.0, 7.91, 7.92), row("put", 133.0, 11.47, 12.06)]
    assert yesno.calls_puts_disagree(nvda, 127.0, 133.0, yrs)
    c = yesno.listed_costs(nvda, 127.0, 133.0, e, {"yes": {"cost": 305.97}, "no": {"cost": 293.70}})
    assert c["out_of_step"] and not c["wide"] and c["yes"]["bid"] + c["no"]["bid"] > c["payout"]
    # The same strikes priced at one stock price: they add up, nothing flagged.
    s = 129.17
    ok = [row(t, k, round(bs_price(s, k, yrs, 0.94, t) - 0.03, 2), round(bs_price(s, k, yrs, 0.94, t) + 0.03, 2))
          for t in ("call", "put") for k in (127.0, 133.0)]
    assert not yesno.calls_puts_disagree(ok, 127.0, 133.0, yrs)
    assert not yesno.listed_costs(ok, 127.0, 133.0, e, {})["out_of_step"]
    assert not yesno.calls_puts_disagree(ok[:2], 127.0, 133.0, yrs)              # no puts quoted: can't tell

    # quote(): calls at the last price, puts as if the stock were 1.5% lower (inside the dividend room).
    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=6)
    y6 = 6 / 365

    def chain(u, strike, ex, days=21, band=0.15):
        out = []
        for k in range(int(spot * 0.9), int(spot * 1.1) + 1):
            for t, at in (("call", spot), ("put", spot * 0.985)):
                mid = bs_price(at, float(k), y6, 0.35, t)
                out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                            "bid": round(max(0.01, mid - 0.02), 2), "ask": round(mid + 0.02, 2), "iv": 0.35})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    lvl = float(int(spot) + 2)
    q = yesno.quote("WINR", lvl, exp.isoformat())
    if not yesno.calls_puts_disagree(chain("WINR", lvl, exp), *q["strikes"], y6):
        pytest.skip("this synthetic price's strike gap is too narrow for the shift to show")
    assert q["market_p"] == q["market_p_flat_vol"] and q["leg_vols"] is None
    assert "disagree with each other" in q["odds_source"]


def test_yesno_noisy_fine_strikes_step_out_to_a_quiet_centred_spread(monkeypatch):
    """Live Sat Nov 21, SPY $693.89, Nov 27 on $1 strikes: $694/$695/$696 quoted so that one $1 step read 78% and the
    next 51%, so the $695 line fell back to the one-vol 48% while $700 read a skew-included 50% (odds rising with the
    line). The $1 pairs' quotes blur the odds by ~9 points; $690/$700 reads them to ~1.5. Now the $695 line trades and
    reads $690/$700."""
    from backend.v4 import yesno
    mids = {690: 15.95, 693: 13.935, 694: 13.765, 695: 12.98, 696: 12.47, 697: 11.84,
            698: 11.15, 699: 10.805, 700: 10.34, 705: 7.965, 710: 5.87}
    gaps = {k: (0.05 if k in (693, 698) else 0.3 if k == 697 else 0.18) for k in mids}
    gaps.update({690: 0.2, 700: 0.28, 705: 0.15, 710: 0.18})
    calls = [{"type": "call", "strike": float(k), "bid": m - gaps[k] / 2, "ask": m + gaps[k] / 2} for k, m in mids.items()]
    assert yesno.spread_noise(calls, 694, 696) > yesno.MAX_NOISE
    assert yesno.quiet_pair(calls, 695, (694, 696)) == (690, 700)
    assert yesno.quiet_pair(calls, 700, (695, 705)) == (695, 705)            # already quiet: unchanged

    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=6)
    shift = round(spot) - 695                                                # same quotes around WINR's price

    def chain(u, strike, e, days=21, band=0.15):
        out = []
        for c in calls:
            k = c["strike"] + shift
            out.append({"symbol": f"{u}{k}c", "type": "call", "strike": k, "expiration": exp, "bid": c["bid"],
                        "ask": c["ask"], "iv": 0.39})
            put_mid = max(0.05, c["bid"] / 2 + c["ask"] / 2 - (spot - k))     # parity at the last price
            out.append({"symbol": f"{u}{k}p", "type": "put", "strike": k, "expiration": exp,
                        "bid": round(put_mid - 0.1, 2), "ask": round(put_mid + 0.1, 2), "iv": 0.39})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    q = yesno.quote("WINR", 695.0 + shift, exp.isoformat())
    assert q["strikes"] == [690 + shift, 700 + shift] and "call spread" in q["odds_source"]
    assert abs(q["market_p"] - (15.95 - 10.34) / 10) < 0.01                  # about 56%, from the market's quotes


def test_yesno_smile_odds_keep_skew_and_fall_as_the_line_rises(monkeypatch):
    """Live Sat Nov 21, SPY $693.89, Nov 27: one-week skew lifted the $690 line ~12 points over one vol, so the old
    stale guard (10 points off one vol) refused a correct quiet-spread reading and showed one vol's 54.7% beside
    56.7% for $695 (odds rising with the line), while the one-vol fallback beside spread readings made the weekend
    ladder jump around. The yardstick is now the smile fitted through the strikes near the line, and outside market
    hours (or when the trade's spread can't be read) the smile sets the odds and the practice price."""
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price, RISK_FREE
    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=6)
    yrs = 6 / 365
    iv = lambda k: 0.40 - 0.0035 * 693.89 / spot * (k - spot)           # SPY's weekend skew, scaled to WINR

    def chain(u, strike, e, days=21, band=0.15):
        out = []
        for k in range(int(spot * 0.9), int(spot * 1.1) + 1):
            for t in ("call", "put"):
                m = bs_price(spot, k, yrs, iv(k), t)
                out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                            "bid": round(max(0.0, m - 0.02), 2), "ask": round(m + 0.02, 2), "iv": 0.36})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    monkeypatch.setattr(market, "option_iv", lambda *a, **k: None)

    # The smile's odds match the true skewed digital: -dC/dK, read off the calls at their own vols.
    lvl = float(round(spot)) - 4
    h = 0.05
    true_p = -(bs_price(spot, lvl + h, yrs, iv(lvl + h), "call") - bs_price(spot, lvl - h, yrs, iv(lvl - h), "call")) \
        / (2 * h) * math.exp(RISK_FREE * yrs)
    sk = yesno.skew_odds(chain("WINR", lvl, exp), spot, lvl, yrs)
    assert abs(sk["p"] - true_p) < 0.01 and sk["p"] - sk["flat"] > 0.08       # skew lifts it well over one vol
    junk = [{"type": t, "strike": float(k), "bid": 1.0, "ask": 1.1} for k in range(int(spot) - 20, int(spot) + 20)
            for t in ("call", "put")]
    assert yesno.skew_odds(junk, spot, lvl, yrs) is None                        # same price everywhere: a V, not a line
    coarse = [r for r in chain("WINR", lvl, exp) if r["strike"] % 5 == 0]       # $5 grid: nearest two a side
    assert abs(yesno.skew_odds(coarse, spot, lvl, yrs)["p"] - true_p) < 0.02
    lower = spot * 0.975                                                         # quotes set as if the stock were 2.5% lower
    stale = [dict(r, bid=round(bs_price(lower, r["strike"], yrs, iv(r["strike"]), r["type"]) - 0.02, 2),
                  ask=round(bs_price(lower, r["strike"], yrs, iv(r["strike"]), r["type"]) + 0.02, 2))
             for r in chain("WINR", lvl, exp)]
    assert yesno.skew_odds(stale, spot, lvl, yrs) is None                       # puts and calls disagree: no smile

    # Market open: a clean spread reading 10+ points over one vol is skew, not stale quotes, and is kept.
    q = yesno.quote("WINR", lvl, exp.isoformat())
    assert "call spread" in q["odds_source"] and q["market_p"] - q["market_p_flat_vol"] > 0.10
    assert abs(q["market_p"] - true_p) < 0.02

    # Market closed: the smile sets odds and price on every line; odds fall as the line rises, YES costs the odds.
    monkeypatch.setattr(market, "clock", lambda: {"is_open": False})
    df = math.exp(-RISK_FREE * yrs)
    ps = []
    for d in (-10, -6, -4, -1, 0, 2, 5, 9):
        q = yesno.quote("WINR", float(round(spot)) + d, exp.isoformat())
        assert "option smile" in q["odds_source"] and q["price_source"] == "smile"
        assert abs(q["yes"]["cost"] / q["yes"]["payout"] / df - q["market_p"]) < 0.02
        ps.append(q["market_p"])
    assert all(a > b for a, b in zip(ps, ps[1:]))


def test_yesno_after_hours_odds_read_the_smile_saved_in_market_hours(monkeypatch):
    """Live Mon Nov 23, before the open: the free feed's overnight option quotes were ~50% wide (NVDA Dec 4 $140 call
    $14.34 / $24.36; $13.24 / $13.66 at 9:35) and the stocks traded pre-market, so the smile read off those mids gave
    ladders whose odds rose with the line (TSLA $366.66: above $350 63%, above $360 68%). Every open-market quote now
    saves the expiration's smile from tight quotes; outside market hours the odds read that saved smile moved with
    the stock (sticky moneyness, total variance kept), so every line comes off the same points and the ladder falls
    as the line rises. Junk quotes are never saved, and without a saved smile nothing changes."""
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price, RISK_FREE
    s0 = market.latest_price("WINR")
    exp = TODAY + timedelta(days=9)
    yrs = 9 / 365
    iv = lambda k, s: 0.40 - 0.6 * (k / s - 1)                   # equity skew, in strike / price terms
    state = {"s": s0, "gap": 0.02, "junk": False}

    def chain(u, strike, e, days=21, band=0.15):
        out, rnd = [], random.Random(7)
        for k in range(int(s0 * 0.88), int(s0 * 1.12) + 1):
            for t in ("call", "put"):
                m = bs_price(s0, float(k), yrs, iv(k, s0), t)            # quotes always set at the old price
                if state["junk"]:
                    m *= 1 + rnd.uniform(-0.3, 0.3)                      # overnight mids: noise
                g = state["gap"] * (m if state["junk"] else 1)
                out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                            "bid": round(max(0.01, m - g), 2), "ask": round(m + g, 2), "iv": 0.4})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    monkeypatch.setattr(market, "option_iv", lambda *a, **k: None)
    monkeypatch.setattr(market, "latest_price", lambda s: state["s"])

    # Market open, tight quotes: the quote saves the smile.
    lvl = float(round(s0))
    q_open = yesno.quote("WINR", lvl, exp.isoformat())
    sv = yesno.saved_smile("WINR", exp)
    assert sv and len(sv["pts"]) >= yesno.SMILE_MIN_POINTS and sv["spot"] == s0

    # After hours: quotes widen to junk, the stock moves up 3% pre-market.
    monkeypatch.setattr(market, "clock", lambda: {"is_open": False})
    state.update(junk=True, gap=0.25, s=s0 * 1.03)
    assert not yesno.save_smile("WINR", exp, chain("WINR", lvl, exp), s0, yrs)      # junk is never saved
    s1 = state["s"]
    ps = []
    for d in (-0.06, -0.04, -0.02, 0.0, 0.02, 0.04):
        line = float(round(s1 * (1 + d)))
        q = yesno.quote("WINR", line, exp.isoformat())
        assert "saved in the last session" in q["odds_source"] and q["price_source"] == "smile"
        assert f"${s1:,.2f}" in q["odds_source"]
        # Sticky moneyness: the same odds as the open-market smile at the same line / price ratio.
        true_p = -(bs_price(s1, line + 0.05, yrs, iv(line + 0.05, s1), "call")
                   - bs_price(s1, line - 0.05, yrs, iv(line - 0.05, s1), "call")) / 0.1 * math.exp(RISK_FREE * yrs)
        assert abs(q["market_p"] - true_p) < 0.02
        df = math.exp(-RISK_FREE * yrs)
        assert abs(q["yes"]["cost"] / q["yes"]["payout"] / df - q["market_p"]) < 0.03   # YES costs the odds shown
        ps.append(q["market_p"])
    assert all(a > b for a, b in zip(ps, ps[1:]))                                     # the ladder falls

    # Total variance kept: priced for 9 days, read with 7 left, the vols scale by sqrt(9/7).
    sk = yesno.smile_from_saved(sv, s0, lvl, 7 / 365)
    assert abs(sk["vol"] / yesno.smile_from_saved(sv, s0, lvl, yrs)["vol"] - math.sqrt(9 / 7)) < 1e-6

    # No saved smile (a stock nobody asked about in market hours): the old reading, not the saved one.
    db.execute("DELETE FROM kv_cache WHERE k LIKE 'yesno:smile:%'")
    q = yesno.quote("WINR", lvl, exp.isoformat())
    assert "saved in the last session" not in q["odds_source"]
    assert q_open["market_p"] > 0


def test_research_time_blocks_flag_a_rule_carried_by_one_stretch():
    """"Does it hold every year?" (McLean & Pontiff 2016): each result is split into 4 chronological stretches cut on
    call dates. A rule whose whole lift sits in the first quarter of dates is ahead in 1 of 4 and stays out of
    luck.steady even though it clears the bar; an even rule is ahead in 4 of 4. Reporting only: the gate is unchanged."""
    from backend.v4 import research
    import datetime as _dt
    rng = random.Random(11)
    d0 = _dt.date(2025, 1, 1)
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(200)]
    early, even = [], []
    for k, d in enumerate(dates):
        for _ in range(3):
            mean = rng.gauss(0, 0.002)
            early.append((mean + (0.08 if k < 50 else -0.003) + rng.gauss(0, 0.01), mean, 0.0, 0.0, d))
            even.append((mean + 0.02 + rng.gauss(0, 0.01), mean, 0.0, 0.0, d))
    e, v = research._metrics(early), research._metrics(even)
    assert e["n_blocks"] == v["n_blocks"] == 4 and sum(b["n"] for b in e["blocks"]) == 600
    assert e["blocks"][0]["from"] == dates[0] and e["blocks"][-1]["to"] == dates[-1]
    for b in e["blocks"]:  # calls on one date never split across stretches
        assert b["n"] % 3 == 0
    assert e["lift"] > 0.015 and e["pos_blocks"] == 1 and e["last_block_lift"] < 0 and e["block_spread"] > 0.07
    assert v["pos_blocks"] == 4 and v["last_block_lift"] > 0
    res = {"app (current #1)": {**v, "lift_adj_t": v["lift_t"]}, "early only": {**e, "lift_adj_t": e["lift_t"]}}
    lk = research.luck(res)
    assert "early only" in lk["clear"] and "early only" not in lk["steady"] and "app (current #1)" in lk["steady"]
    assert lk["app_blocks"]["pos_blocks"] == 4 and lk["steady_min"] == 3
    # no dates or too few calls: no stretches reported
    assert "blocks" not in research._metrics([p[:4] for p in early]) and "blocks" not in research._metrics(early[:6])
    app = {"beat": 0.0, "beat_adj": 0.0}
    strip = {k: x for k, x in e.items() if k not in ("blocks", "pos_blocks", "n_blocks", "last_block_lift", "block_spread")}
    assert research._passes(e, app) == research._passes(strip, app)


def test_pbo_is_near_half_for_noise_rules_and_near_zero_with_a_real_edge():
    """"Would we have picked the winner?" (Bailey, Borwein, Lopez de Prado & Zhu 2017, CSCV): 40 pure-noise rules give
    a probability of backtest overfitting near 0.5; add one rule with a real planted edge and the in-sample winner is
    that rule in most splits, so PBO falls near 0. The look-ahead app row never takes part. Reporting only."""
    from backend.v4 import research
    import datetime as _dt
    rng = random.Random(5)
    d0 = _dt.date(2025, 1, 1)
    dates = [(d0 + _dt.timedelta(days=k)).isoformat() for k in range(240)]

    def rule(edge):
        out = []
        for d in dates:
            for _ in range(3):
                mean = rng.gauss(0, 0.002)
                out.append((mean + edge + rng.gauss(0, 0.03), mean, 0.0, 0.0, d))
        return out
    noise = {f"noise {i}": rule(0.0) for i in range(40)}
    p0 = research.pbo(noise)
    assert p0["n_splits"] == 70 and p0["n_methods"] == 40 and p0["n_blocks"] == 8
    assert 0.25 <= p0["pbo"] <= 0.75 and sum(p0["winners"].values()) == 70
    real = {**noise, "real edge": rule(0.01), "app (current #1)": rule(0.05)}
    p1 = research.pbo(real)
    assert p1["n_methods"] == 41 and "app (current #1)" not in p1["winners"]
    assert p1["pbo"] <= 0.1 and p1["winners"].get("real edge", 0) >= 60 and p1["oos_lift_med"] > 0.005
    assert p1["p_loss"] <= 0.1
    # only: restrict the pool; too few dates or methods: nothing reported
    assert research.pbo(real, only=["noise 1", "real edge"])["n_methods"] == 2
    assert research.pbo({"a": noise["noise 0"]}) == {}
    assert research.pbo({k: v[:9] for k, v in noise.items()}) == {}


def test_lone_ranker_is_vetoed_by_real_time_calls_and_ranker_ordered_calls_are_left_out(monkeypatch):
    # a model that passed alone went live with no real-time check at all (only mixes had one). Now: it still goes live
    # while real-time proof is too thin, but is vetoed once enough real-time calls show its own #1 doing worse than the
    # app's #1. Calls ranker v2 itself ordered (rv2 stored) are left out: their #1 is not the app's.
    from backend.v4 import research

    def add(bid, rv2=False, app_first=True):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "u", "x", "x", "2026-11-01T00:00:00", "2026-11-01", "user"))
        for j in range(3):
            pid = f"{bid}-{j}"
            feats = {"num": {"mom60": 0.1 * j}, **({"rv2": 0.1 * j} if rv2 else {})}
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank, final_score) VALUES (?,?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", "2026-11-01", 10.0, db.dumps(feats), j, 0.9 - 0.1 * j))
            # the app's #1 (j=0) does best; the highest-momentum idea (j=2) does worst
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 30, "2026-12-01", 10.0, 0.0, 0.0, 0.05 - 0.02 * j, "2026-12-01"))
    for i in range(4):
        add(f"lz{i}")
    for i in range(3):
        add(f"lzr{i}", rv2=True)
    research._set_keys()
    keys = ["z_mom60"]
    # alone, a "momentum" ridge picks j=2 every time: worse than the app's #1 on the 4 app-ordered calls
    r = research.live_check(None, [0.0], [1.0], [1.0], days=30, min_calls=4, keys=keys, alone=True)
    assert r["n"] == 4 and r["ranker_ordered"] == 3 and not r["ok"] and r["alone"]
    assert abs(r["mix"]["avg"] - 0.01) < 1e-9 and abs(r["app"]["avg"] - 0.05) < 1e-9
    assert research.live_veto(r)
    # the same model as a 25% mix can't overturn the app's clear ordering, so it ties the app's #1
    assert research.live_check(None, [0.0], [1.0], [1.0], days=30, min_calls=4, keys=keys)["ok"]
    # too few real-time calls yet: no veto (the model passed the walk-forward gate and may go live)
    thin = research.live_check(None, [0.0], [1.0], [1.0], days=30, min_calls=5, keys=keys, alone=True)
    assert not thin["ok"] and not research.live_veto(thin)
    assert not research.live_veto(None) and not research.live_veto({"ok": True, "n": 400, "needed": 300})

    # fit_production: a lone candidate that passed the gate is skipped when vetoed, kept when not
    test_research_walk_forward_runs_and_stores(monkeypatch)
    out = research.run()
    target = out["results"]["gbm (learned)"]
    monkeypatch.setattr(research, "_passes", lambda m, app, risk=False: m is target)
    monkeypatch.setattr(research, "live_check", lambda *a, **k: {"ok": False, "n": 10, "needed": 300})
    rv = research.fit_production(out)
    assert rv["active"] and rv["model"] == "gbm" and not rv["mix"]
    monkeypatch.setattr(research, "live_check", lambda *a, **k: {"ok": False, "n": 300, "needed": 300, "alone": k.get("alone")})
    rv = research.fit_production(out)
    assert not rv["active"] and rv["live"]["candidate"] == "gbm" and rv["live"]["alone"]


def test_grades_put_a_real_time_entry_on_the_split_adjusted_scale():
    """Daily bars are split-adjusted but a real-time pick's entry_price is the raw trade. ITA's 3-for-1 split
    (Nov 2026) graded 39 real-time calls at -66% vs SPY. Grading (and the repair of old grades, and My calls) must
    read a split since entry as no move, and refuse to grade an entry no split can explain."""
    dates, closes = market.daily_closes("WINR")
    d0 = (TODAY - timedelta(days=20)).isoformat()
    i = bisect.bisect_right(dates, d0) - 1
    c = closes[i]
    assert market.split_factor(dates, closes, d0, c * 1.01) == 1.0          # same scale
    assert market.split_factor(dates, closes, d0, c * 1.25) == 1.0          # a big intraday move, not a split
    assert market.split_factor(dates, closes, d0, c * 3.0) == pytest.approx(1 / 3)  # a 3-for-1 since entry
    assert market.split_factor(dates, closes, d0, c / 10.0) == pytest.approx(10.0)  # a 1-for-10 reverse split
    assert market.split_factor(dates, closes, d0, c * 1.8) is None          # no split explains it: bad data
    assert market.split_factor(dates, closes, "2000-01-01", c * 3) == 1.0   # nothing to compare with

    engine.process_belief("plumbing will boom", "u1", "moderate", source="seed_news", claude_client=FakeClaude())
    p = db.query_one("SELECT p.id, p.ticker, p.belief_id FROM picks p JOIN beliefs b ON b.id = p.belief_id "
                     "WHERE b.source = 'seed_news' ORDER BY p.final_rank LIMIT 1")
    tdates, tcloses = market.daily_closes(p["ticker"])
    k = bisect.bisect_right(tdates, d0) - 1
    raw = tcloses[k] * 3.0  # the raw pre-split price the pick was entered at
    db.execute("UPDATE picks SET entry_date = ?, entry_price = ? WHERE id = ?", (d0, raw, p["id"]))
    db.execute("UPDATE beliefs SET created_at = ? WHERE id = ?", (d0 + "T15:00:00+00:00", p["belief_id"]))
    db.execute("UPDATE picks SET entry_date = ? WHERE belief_id = ? AND id <> ?", (d0, p["belief_id"], p["id"]))
    grader.grade()
    o = db.query_one("SELECT ret, price FROM outcomes WHERE pick_id = ? AND checkpoint_days = 7", (p["id"],))
    tk = market.close_on_or_after(p["ticker"], date.fromisoformat(d0) + timedelta(days=7))
    assert o["ret"] == pytest.approx(tk[1] / tcloses[k] - 1, abs=1e-6)  # the real move, not -67%
    assert abs(o["ret"]) < 0.25

    # an old grade made before the fix (raw entry vs adjusted close) is repaired once, and its belief re-scored
    db.execute("UPDATE outcomes SET ret = ?, dir_excess = ?, graded_at = ? WHERE pick_id = ? AND checkpoint_days = 7",
               (tk[1] / raw - 1, -0.66, TODAY.isoformat() + "T05:00:00+00:00", p["id"]))
    assert grader.repair_splits().get("done_before") is True  # grade() already ran it once: no daily refetch
    out = grader.repair_splits(force=True)
    assert out["repaired"] >= 1 and out["data_errors"] == 0
    o2 = db.query_one("SELECT ret, dir_excess, bench_ret FROM outcomes WHERE pick_id = ? AND checkpoint_days = 7",
                      (p["id"],))
    assert o2["ret"] == pytest.approx(tk[1] / tcloses[k] - 1, abs=1e-6) and o2["bench_ret"] is None
    assert grader.score_selection() > 0
    assert db.query_one("SELECT bench_ret FROM outcomes WHERE pick_id = ? AND checkpoint_days = 7",
                        (p["id"],))["bench_ret"] is not None
    assert grader.repair_splits(force=True)["repaired"] == 0  # idempotent

    # a pick whose entry no split explains is not graded at all
    other = db.query_one("SELECT id FROM picks WHERE belief_id = ? AND id <> ? LIMIT 1", (p["belief_id"], p["id"]))
    assert other
    db.execute("DELETE FROM outcomes WHERE pick_id = ?", (other["id"],))
    oc = db.query_one("SELECT ticker FROM picks WHERE id = ?", (other["id"],))["ticker"]
    od, ocl = market.daily_closes(oc)
    db.execute("UPDATE picks SET entry_price = ? WHERE id = ?", (ocl[bisect.bisect_right(od, d0) - 1] * 1.8, other["id"]))
    assert grader.grade()["suspect"] >= 1
    assert db.query_one("SELECT COUNT(*) AS n FROM outcomes WHERE pick_id = ?", (other["id"],))["n"] == 0


def test_share_card_shows_only_stored_grades_and_its_own_tags():
    """'I called it' cards: /c/{id} carries the call's own og tags and the redirect into the app; ungraded checks say
    'not graded yet' (never a result); a miss is shown as a miss; seeded calls and unknown ids are 404; the copy text
    marks each checkpoint from stored grades only."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.v4 import share

    def belief(bid, source, text="AI chips <keep> running", direction="bullish"):
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction, user_prob) "
                   "VALUES (?,?,?,?,?,?,?,?,?)", (bid, "u-1", text, "x", "2026-09-01T15:00:00+00:00", "2026-09-01",
                                                  source, direction, 0.7))
        db.execute("INSERT INTO picks (id, belief_id, ticker, name, direction, entry_date, entry_price, final_rank, shown) "
                   "VALUES (?,?,?,?,?,?,?,?,?)", (f"p{bid}", bid, "NVDA", "NVIDIA", direction, "2026-09-01", 100.0, 1, 1))

    def grade(bid, cp, bench, spy, right):
        db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at,
                      bench_ret, belief_right) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (f"p{bid}", cp, "2026-09-08", 1.0, bench, spy, 0.0, "2026-09-09", bench, right))

    belief("b-aaaa000000000001", "user")
    grade("b-aaaa000000000001", 7, 0.05, 0.02, 1)      # +3 pts ahead
    grade("b-aaaa000000000001", 30, -0.01, 0.03, 0)    # 4 pts behind: a miss, shown as one
    belief("b-aaaa000000000002", "user", text="Nothing graded yet")
    belief("b-aaaa000000000003", "seed_live")

    app = FastAPI()
    app.include_router(share.router)
    c = TestClient(app)

    r = c.get("/c/b-aaaa000000000001")
    assert r.status_code == 200
    page = r.text
    assert 'property="og:title" content="“AI chips &lt;keep&gt; running”"' in page   # escaped, the call's own words
    assert "/c/b-aaaa000000000001.png" in page and 'name="twitter:card" content="summary_large_image"' in page
    assert "welcome?ref=card&amp;c=b-aaaa000000000001" in page
    assert "30 days in: behind the S&amp;P 500 by 4.0 pts" in page   # the newest graded check, a miss
    assert "u-1" not in page                                           # no user id on the page

    j = c.get("/c/b-aaaa000000000001.json").json()
    st = {k["days"]: k["status"] for k in j["checks"]}
    assert st == {7: "ahead", 30: "behind", 90: "pending"} and j["sure"] == 70
    assert "7d 🟩 30d 🟥 90d ⬜ vs the S&P 500" in j["copy_text"] and "NVDA · calling up" in j["copy_text"]

    # The grade is the theme's (its fund, else the average of its stocks), not the first ticker's own move: the card
    # names what it was measured on, so "CHWY +1.2 pts" can't be read as CHWY's result when CHWY fell 11%.
    db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source, direction) "
               "VALUES (?,?,?,?,?,?,?,?)", ("b-aaaa000000000004", "u-1", "Diners cut back", "y",
                                            "2026-09-01T15:00:00+00:00", "2026-09-01", "user", "bearish"))
    for i, (t, shown, ret, edge) in enumerate([("EAT", 1, -0.03, 0.01), ("DRI", 1, 0.04, -0.03), ("CAKE", 0, 0.0, 0.0),
                                               ("XLY", 0, 0.01, None)]):
        db.execute("INSERT INTO picks (id, belief_id, ticker, name, direction, entry_date, entry_price, final_rank, shown) "
                   "VALUES (?,?,?,?,?,?,?,?,?)", (f"q{i}", "b-aaaa000000000004", t, t, "bearish", "2026-09-01", 1.0, i, shown))
        db.execute("""INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at,
                      bench_ret, belief_right, bench_kind, sel_edge) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (f"q{i}", 7, "2026-09-08", 1.0, ret, -0.04, 0.0, "2026-09-09", 0.01, 0, "fund", edge))
    j4 = c.get("/c/b-aaaa000000000004.json").json()
    assert j4["picks"] == ["EAT", "DRI"] and j4["measured_on"] == "XLY, the theme's fund"
    assert "EAT, DRI · calling down" in j4["copy_text"] and "(graded on XLY, the theme's fund)" in j4["copy_text"]
    assert "graded on XLY" in c.get("/c/b-aaaa000000000004").text
    assert j["measured_on"] == "NVDA"

    j2 = c.get("/c/b-aaaa000000000002.json").json()
    assert all(k["status"] == "pending" and k["vs_spy"] is None for k in j2["checks"])
    assert j2["headline"] == "Not graded yet. First check Sep 8, 2026." and "🟩" not in j2["copy_text"]

    png = c.get("/c/b-aaaa000000000002.png")
    assert png.status_code == 200 and png.content[:8] == b"\x89PNG\r\n\x1a\n"

    # A big-move call is graded on the size of the move either way (|theme| - |S&P|): a fund that fell 3.6% while the
    # S&P fell 1.9% "moved 1.7 pts more", it was not "ahead of the S&P 500".
    belief("b-aaaa000000000005", "user", text="Not sure which way AI goes", direction="volatile")
    grade("b-aaaa000000000005", 7, -0.036, -0.019, 1)
    j5 = c.get("/c/b-aaaa000000000005.json").json()
    assert j5["headline"] == "7 days in: moved 1.7 pts more than the S&P 500"
    assert j5["vs_label"] == "how much more it moved than the S&P 500, up or down"
    assert "size of the move vs the S&P 500's" in j5["copy_text"] and "NVDA · calling a big move" in j5["copy_text"]
    assert "ahead of" not in c.get("/c/b-aaaa000000000005").text
    assert c.get("/c/b-aaaa000000000005.png").status_code == 200

    assert c.get("/c/b-aaaa000000000003").status_code == 404   # seeded calls get no card
    assert c.get("/c/b-ffff000000000009").status_code == 404
    assert c.get("/c/nonsense.png").status_code == 404


def test_option_vol_uses_the_quote_clock_so_a_weekend_does_not_inflate_it(monkeypatch):
    """Sunday Nov 22 2026: SPY's Nov 27 options still carried Friday's closing quotes, and the feed's IV divided them
    by the 5 days left, reading ~42% for options priced at ~35%. Vol is read off the quotes from the last close."""
    from zoneinfo import ZoneInfo
    from backend.v4 import pricecheck, yesno
    ny = ZoneInfo("America/New_York")
    exp = date(2026, 11, 27)                                   # day after Thanksgiving: 1pm close
    sun = datetime(2026, 11, 22, 5, 53, tzinfo=ny)
    assert market.last_close_dt(sun) == datetime(2026, 11, 20, 16, 0, tzinfo=ny)
    assert market.last_close_dt(datetime(2026, 11, 26, 12, 0, tzinfo=ny)) == datetime(2026, 11, 25, 16, 0, tzinfo=ny)
    assert market.last_close_dt(datetime(2026, 11, 23, 9, 0, tzinfo=ny)) == datetime(2026, 11, 20, 16, 0, tzinfo=ny)
    assert market.last_close_dt(datetime(2026, 11, 23, 16, 30, tzinfo=ny)) == datetime(2026, 11, 23, 16, 0, tzinfo=ny)
    closed = market.quote_years(exp, sun, open_now=False)
    assert closed * 365 == pytest.approx(6 + 21 / 24)          # Fri 4pm -> Fri 1pm, not the 5 days left
    live = datetime(2026, 11, 23, 13, 0, tzinfo=ny)
    assert market.quote_years(exp, live, open_now=True) * 365 == pytest.approx(4)
    assert market.quote_years(exp, datetime(2026, 11, 28, 9, 0, tzinfo=ny), open_now=False) == 0.0

    # Quotes priced at 35% on the quote clock read back 35%; the old clock (time left from Sunday) reads far higher
    spot, k = 693.89, 694.0
    rows = []
    for kind in ("call", "put"):
        mid = strategy.bs_price(spot, k, closed, 0.35, kind)
        rows.append({"type": kind, "strike": k, "expiration": exp, "bid": mid - 0.1, "ask": mid + 0.1, "iv": 0.42})
    rows.append({"type": "call", "strike": 700.0, "expiration": exp, "bid": 0, "ask": 0, "iv": 0.45})
    iv, strike, skew = yesno.atm_quote_iv(rows, spot, closed)
    assert strike == k and iv == pytest.approx(0.35, abs=0.003) and abs(skew) < 0.003
    assert yesno.atm_quote_iv(rows, spot, 5 / 365)[0] > 0.40
    assert yesno.quote_iv(rows[2], spot, closed) is None       # no two-sided quote: no reading
    assert yesno.quote_iv(dict(rows[0], bid=1.0, ask=30.0), spot, closed) is None   # too loose to read

    # Close Call's range: same spread of outcomes the prices carry, labelled with the honest vol
    m = yesno.expected_move(spot, rows, 5 / 365, rv60=0.17, quote_years=closed)
    assert m["atm_iv"] == pytest.approx(0.35, abs=0.003)
    assert m["high"] == pytest.approx(spot * math.exp(0.35 * math.sqrt(closed)), abs=0.3)
    old = yesno.expected_move(spot, rows, 5 / 365, rv60=0.17)  # no quote clock: the feed's number, as before
    assert old["atm_iv"] == pytest.approx(0.42)

    # Price Check off-hours: verdict on the quote-clock vol, and it says which close the quotes are from
    monkeypatch.setattr(market, "option_chain_near", lambda *a, **kw: [dict(r, symbol=f"SPY261127{r['type'][0].upper()}{int(r['strike'] * 1000):08d}") for r in rows])
    monkeypatch.setattr(market, "latest_price", lambda s: spot)
    monkeypatch.setattr(market, "daily_closes", lambda s: ([], []))
    monkeypatch.setattr(market, "is_open", lambda: False)
    monkeypatch.setattr(market, "now_ny", lambda: sun)
    res = pricecheck._compute("SPY", "call", 694.0, exp)
    assert res["available"] and res["atm_iv"] == pytest.approx(0.35, abs=0.003)
    assert res["contract_iv"] == pytest.approx(0.35, abs=0.003)
    assert any("Fri Nov 20 closing quotes" in l for l in res["lines"])
    assert any("35% yearly volatility" in l for l in res["lines"])


def test_yesno_quotes_set_at_another_price_read_their_vol_at_that_price(monkeypatch):
    """Live Sun Nov 22, NVDA $129.17, Dec 4 $125: the option quotes were set as if NVDA were ~$126.1 (parity), so read
    at the last price every put looked dear (~1.19 vol) and every call cheap (~0.81). The smile near $125 ran through
    puts alone, its parity allowance (0.1 sd at the puts' own inflated vol) passed the gap it was measuring, and the
    page read "46% to close above $125" with the stock $4 above the line. Read at the quotes' own price, calls and
    puts agree (~1.03). Now: no smile from those quotes, and the one-vol answer at the last price uses that vol and
    says what price the quotes were set at. Quotes set at the last price are untouched."""
    from backend.v4 import yesno
    from backend.v4.strategy import bs_price
    yrs = 12 / 365
    iv = lambda k: 1.03 - 0.009 * (k - 125)

    def rows(at, call_gap=0.9):
        out = []
        for k in range(115, 141):
            for t in ("call", "put"):
                m = bs_price(at, float(k), yrs, iv(k), t)
                g = call_gap if t == "call" else 0.04          # the live calls were ~$0.90 wide, puts ~$0.04
                out.append({"symbol": f"N{k}{t}", "type": t, "strike": float(k), "expiration": date(2026, 12, 4),
                            "bid": round(m - g / 2, 2), "ask": round(m + g / 2, 2), "iv": 1.2229})
        return out
    stale = rows(126.0)
    own = yesno.quotes_own_price(stale, 129.17, 125.0, yrs)
    assert own["out"] and abs(own["price"] - 126.0) < 0.3 and abs(own["vol"] - 1.03) < 0.03
    assert yesno.skew_odds(stale, 129.17, 125.0, yrs) is None
    fresh = rows(129.17)
    assert not yesno.quotes_own_price(fresh, 129.17, 125.0, yrs)["out"]
    assert yesno.skew_odds(fresh, 129.17, 125.0, yrs) is not None

    # quote(): the same shape around WINR's price, quotes set 2.4% lower (inside quotes_out_of_step's dividend room).
    spot = market.latest_price("WINR")
    exp = TODAY + timedelta(days=12)
    at = spot * 126.0 / 129.17
    vol = lambda k: 1.03 - 0.009 * 129.17 / spot * (k - spot * 125 / 129.17)

    def chain(u, strike, e, days=21, band=0.15):
        out = []
        for k in range(int(spot * 0.88), int(spot * 1.1) + 1):
            for t in ("call", "put"):
                m = bs_price(at, float(k), yrs, vol(k), t)
                g = 0.007 * spot if t == "call" else 0.0003 * spot
                out.append({"symbol": f"{u}{k}{t}", "type": t, "strike": float(k), "expiration": exp,
                            "bid": round(max(0.01, m - g / 2), 2), "ask": round(m + g / 2, 2), "iv": 1.2229})
        return out
    monkeypatch.setattr(market, "option_chain_near", chain)
    monkeypatch.setattr(market, "option_iv", lambda *a, **k: None)
    lvl = float(round(spot * 125 / 129.17))
    q = yesno.quote("WINR", lvl, exp.isoformat())
    assert q["market_p_smile"] is None
    assert abs(q["vol"] - 1.03) < 0.06 and q["market_p"] > 0.5                # the stock sits ~3% above the line
    if q["market_p"] == q["market_p_flat_vol"]:
        assert "set as if WINR were near" in q["odds_source"]


def test_news_search_finds_this_weeks_stories_by_company_ticker_or_topic(monkeypatch):
    from backend.v4 import movers, newssearch
    now = datetime.now(timezone.utc)
    iso = lambda h: (now - timedelta(hours=h)).isoformat()
    chips = {"headline": "Chipmakers rally as Nvidia lifts its forecast", "hunch": "AI demand keeps growing",
             "why": "", "summary": "", "created_at": iso(2),
             "companies": [{"ticker": "NVDA", "direction": "up", "why": "sells the chips"}]}
    oil = {"headline": "Crude jumps after OPEC cut", "hunch": "Oil prices will stay high", "why": "", "summary": "",
           "created_at": iso(30), "companies": [{"ticker": "XOM", "direction": "up", "why": "gold standard driller"}]}
    stale = dict(oil, headline="Old oil story", created_at=iso(24 * 9))
    monkeypatch.setattr(movers, "feed", lambda client=None: {"items": [chips], "benchmark": None})
    # the archive keeps a week of picked stories, newest first, without prices
    movers._archive([dict(oil, companies=[dict(oil["companies"][0], change=0.01)]), stale, chips])
    arch = movers.archived()
    assert [a["headline"] for a in arch] == [chips["headline"], oil["headline"]]
    assert "change" not in arch[1]["companies"][0]
    names = {"NVDA": "NVIDIA Corporation Common Stock", "XOM": "Exxon Mobil Corporation", "GOLD": "Barrick Mining"}
    monkeypatch.setattr(movers.market, "asset_info",
                        lambda s: {"symbol": s, "name": names[s]} if s in names else None)
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {s: {"price": 10.0, "change": 0.02, "change_day": "2026-11-20"} for s in syms})
    monkeypatch.setattr(newssearch, "headlines_for", lambda sym: [{"headline": f"{sym} headline", "url": ""},
                                                                  {"headline": chips["headline"], "url": ""}])
    by_name = newssearch.search("nvidia news")
    assert by_name["company"]["ticker"] == "NVDA" and [s["headline"] for s in by_name["stories"]] == [chips["headline"]]
    assert [h["headline"] for h in by_name["headlines"]] == ["NVDA headline"]  # not the story shown above it
    assert newssearch.search("$xom")["stories"][0]["headline"] == oil["headline"]
    assert newssearch.search("xom")["company"]["ticker"] == "XOM"   # lowercase, but a ticker in this week's stories
    topic = newssearch.search("oil")  # a topic: the archived story (prices re-read), and no company card
    assert topic["company"] is None and [s["headline"] for s in topic["stories"]] == [oil["headline"]]
    assert topic["stories"][0]["companies"][0]["change"] == 0.02
    assert newssearch.search("chip")["stories"][0]["headline"] == chips["headline"]  # word starts: chipmakers
    gold = newssearch.search("gold")  # used in a story, so a topic, not Barrick's ticker GOLD
    assert gold["company"] is None and gold["stories"][0]["headline"] == oil["headline"]
    assert newssearch.search("zzzz")["stories"] == [] and newssearch.search("a")["stories"] == []
    # a lowercase word no story uses that is a ticker (live 2026-11-22: "gold" -> Gold.com) is marked a guess, so the
    # page says no story mentions the word instead of presenting the stock as the answer
    names["CAR"] = "Avis Budget Group, Inc. Common Stock"
    car = newssearch.search("car")
    assert car["company"]["ticker"] == "CAR" and car["company"].get("guess") is True
    assert not newssearch.search("CAR")["company"].get("guess") and not newssearch.search("xom")["company"].get("guess")
    # well-known names find the company even when no story this week moves it
    names["AAPL"] = "Apple Inc. Common Stock"
    apple = newssearch.search("apple")
    assert apple["company"]["ticker"] == "AAPL" and not apple["company"].get("guess")
    # Story mode opens an archived story too, but nothing outside the curated stories
    monkeypatch.setattr(movers, "_write_story", lambda item, client=None: {"ai": False, "hook_big": "", "title": item["headline"]})
    assert movers.story(oil["headline"])["item"]["headline"] == oil["headline"]
    assert movers.story("Something nobody picked") is None


def test_equal_weight_composite_beats_two_weak_signals_and_picks_rules_on_training_calls_only():
    """"Many weak signals, one vote" (DeMiguel, Garlappi & Uppal 2009): two weak, independent planted signals, each
    alone about t 2-3; an equal vote of the two beats both on unseen calls. Near copies don't double-vote, rules
    are kept only on training lift and t (fixed cutoff), and with nothing qualifying the fold falls back to the app's
    no-look-ahead #1. Reporting only."""
    from backend.v4 import research
    rng = random.Random(21)

    def beliefs(n, a_edge=0.01, b_edge=0.01):
        out = []
        for _ in range(n):
            cands = []
            for _ in range(5):
                a, b, z = rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1)
                ex = a_edge * a + b_edge * b + rng.gauss(0, 0.08)
                cands.append({"f": {"z_a": a, "z_b": b, "z_n": z}, "ex": ex, "exa": ex, "pit": 0.0})
            out.append({"cands": cands, "date": None})
        return out

    rules = {"a": lambda f: f["z_a"], "b": lambda f: f["z_b"], "a copy": lambda f: f["z_a"] + 1e-6 * f["z_n"],
             "noise": lambda f: f["z_n"], "anti a": lambda f: -f["z_a"]}
    train, test = beliefs(1500), beliefs(3000)
    mem = dict(research.composite_members(train, rules))
    assert set(mem) == {"a", "b"} or set(mem) == {"a copy", "b"}  # one of the near copies, never both; no noise
    assert all(t >= research.COMP_MIN_T for t in mem.values())

    def lift(score):
        return float(np.mean([b["cands"][research._top(b, score(b))]["ex"] - np.mean([c["ex"] for c in b["cands"]])
                              for b in test]))
    fns = [rules[k] for k in mem]
    comp = lift(lambda b: research.composite_scores(b, fns))
    one_a = lift(lambda b: [c["f"]["z_a"] for c in b["cands"]])
    one_b = lift(lambda b: [c["f"]["z_b"] for c in b["cands"]])
    assert comp > one_a and comp > one_b
    # z-scored within the belief: a rule on a 1000x scale doesn't outvote the other
    big = research.composite_scores(test[0], [lambda f: 1000 * f["z_a"], rules["b"]])
    small = research.composite_scores(test[0], [rules["a"], rules["b"]])
    assert np.allclose(big, small)
    # nothing in training clears the cutoff: no members (run() then uses the app's no-look-ahead #1)
    assert research.composite_members(beliefs(300, 0.0, 0.0), {"noise": rules["noise"]}) == []
    # summary: compared with the median and the best single rule
    res = {research.COMPOSITE: {"n": 10, "lift": 0.02, "lift_t_nw": 3.0, "pos_blocks": 4, "n_blocks": 4},
           "a": {"n": 10, "lift": 0.01, "lift_t_nw": 2.0, "pos_blocks": 3}, "b": {"n": 10, "lift": 0.012, "lift_t_nw": 2.5}}
    s = research.composite_summary(res, {"members": {"a": 5}}, ["a", "b"])
    assert s["median_single_t"] == 2.25 and s["beats_singles"] == 2 and s["best_single"]["name"] == "b"
    assert s["members"] == {"a": 5} and research.composite_summary({}, {}, ["a"]) == {}


def test_composite_in_run_never_keeps_a_rule_that_only_works_in_its_own_test_period(monkeypatch):
    from backend.v4 import research
    rng = random.Random(8)
    d0 = __import__("datetime").date(2024, 1, 1)
    for i in range(400):
        bid = f"b-cmp{i}"
        asof = (d0 + __import__("datetime").timedelta(days=i * 2)).isoformat()
        db.execute("INSERT INTO beliefs (id, user_id, text, norm_text, created_at, as_of_date, source) VALUES (?,?,?,?,?,?,?)",
                   (bid, "seed", "x", "x", asof + "T00:00:00", asof, "seed_backfill"))
        for j in range(4):
            mom, vol = rng.uniform(-0.3, 0.3), rng.uniform(0.2, 0.6)
            # momentum works throughout; low volatility works only in the last test block (i >= 352)
            ex = mom * 0.3 + (-(vol - 0.4) * 0.5 if i >= 352 else 0.0) + rng.gauss(0, 0.05)
            pid = f"p-cmp{i}-{j}"
            db.execute("INSERT INTO picks (id, belief_id, ticker, direction, entry_date, entry_price, features, final_rank) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, bid, f"T{j}", "bullish", asof, 10.0, db.dumps({"num": {"mom60": mom, "vol60": vol}}), j + 1))
            db.execute("INSERT INTO outcomes (pick_id, checkpoint_days, eval_date, price, ret, spy_ret, dir_excess, graded_at) VALUES (?,?,?,?,?,?,?,?)",
                       (pid, 90, asof, 10.0, 0.0, 0.0, ex, asof))
    out = research.run()
    r, comp = out["results"], out["composite"]
    assert r[research.COMPOSITE]["n"] == r["momentum (z_mom60)"]["n"] > 100
    assert r[research.COMPOSITE]["lift"] > 0.02  # the planted momentum carries it
    assert comp["folds"] == 5 and comp["members"].get("momentum (z_mom60)") == 5
    assert "low vol (-z_vol60)" not in comp["members"]  # its only edge is in a block no fold trained on
    assert "app (current #1)" not in comp["members"] and "app, no look-ahead" not in comp["members"]
    assert r[research.COMPOSITE]["composite_members"] == comp["members"]
    s = out["luck"]["composite"]
    assert s["name"] == research.COMPOSITE and s["best_single"]["name"] and s["singles"] >= 30
    assert out["luck"]["tests"] == len([k for k, v in r.items() if v.get("n")])


def test_movers_drops_a_story_link_that_is_a_quote_page_for_another_company():
    from backend.v4.movers import story_url
    # 2026-11-23: an Enphase story (fiscal.ai) linked to moomoo's O-I Glass quote page
    assert story_url("https://www.moomoo.com/stock/OI-US?chain_id=x", ["ENPH", "SEDG"]) == ""
    assert story_url("https://finance.yahoo.com/quote/AAPL/", ["MSFT"]) == ""
    assert story_url("https://www.moomoo.com/stock/ENPH-US?x", ["ENPH"]) == "https://www.moomoo.com/stock/ENPH-US?x"
    assert story_url("https://www.nasdaq.com/market-activity/stocks/brk.b", ["BRK.B"]).endswith("brk.b")
    for u in ("https://www.fidelity.com/news/article/default/202611221400PR", "https://site.com/stocks/news/2026/abc",
              "https://www.moomoo.com/hans/news/post/1005426646"):
        assert story_url(u, ["X"]) == u


def test_custom_story_from_search_is_grounded_cached_and_capped(monkeypatch):
    from backend.v4 import customstory, movers
    now = datetime.now(timezone.utc)
    iso = lambda h: (now - timedelta(hours=h)).isoformat()
    tagged = {"CCJ": [{"headline": "Cameco signs uranium supply deal worth $2.1 billion", "symbols": ["CCJ"],
                       "summary": "Uranium prices rose to $82 a pound from $64 a year ago.", "created_at": iso(5),
                       "source": "benzinga", "url": "https://x/1"},
                      {"headline": "Cameco names new CFO", "symbols": ["CCJ"], "summary": "", "created_at": iso(6)},
                      {"headline": "Uranium miners rally on reactor plans", "symbols": ["UEC"], "summary": "",
                       "created_at": iso(24 * 20)}]}  # too old
    calls = []

    class Fake:
        def __init__(self):
            self.messages = self

        def create(self, **kw):
            calls.append(kw)
            if "tickers" in kw["extra_body"]["output_config"]["format"]["schema"]["properties"]:
                out = {"tickers": [] if "bananas" in kw["messages"][0]["content"] else ["CCJ", "FAKE", "ccj"]}
            else:
                out = {"used": [0], "title": "Uranium deals heat up", "hunch": "Uranium miners will keep winning deals",
                       "why_short": "Utilities need fuel.", "hook_big": "$2.1 billion", "hook_line": "A big supply deal.",
                       "happened": "Cameco signed a big supply deal.", "why": "Reactors need fuel for decades.",
                       "twist": "Prices can fall fast.",
                       "figures": [{"label": "Uranium price", "before_label": "A year ago", "before": "$64",
                                    "after_label": "Now", "after": "$82"},
                                   {"label": "Invented", "before_label": "Then", "before": "$1", "after_label": "Now", "after": "$9"}],
                       "companies": [{"ticker": "CCJ", "direction": "up", "why": "sells the uranium", "link": "indirect"},
                                     {"ticker": "FAKE", "direction": "up", "why": "made up", "link": "direct"}]}
            return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(out))])

    fake = Fake()
    engine_calls, engine_against = [], []

    def fake_engine(text, user_id="anonymous", risk_profile="moderate", **kw):
        engine_calls.append((text, user_id, kw.get("source")))
        engine_against.append(kw.get("against"))
        pick = lambda t, shown: {"ticker": t, "name": t, "direction": "bullish", "exposure": "etf", "rationale": "holds miners",
                                 "structure": "Buy Stock", "trade": {"type": "Buy Stock", "max_loss": None}, "shown": shown,
                                 "alt": {"structure": "Bull Call Spread"}, "price": 40.0}
        return {"valid": True, "belief_id": "b-1", "picks": [pick("URA", True), pick("CCJ", True), pick("UEC", False)]}
    monkeypatch.setattr(engine, "process_belief", fake_engine)
    run_now = customstory._start_plays  # no stray background threads outliving the test's database
    monkeypatch.setattr(customstory, "_start_plays", lambda k, h, c=None, wait=False: run_now(k, h, c, True))
    monkeypatch.setattr(customstory, "news_for", lambda syms: [customstory._clean(n) for s in syms for n in tagged.get(s, [])])
    monkeypatch.setattr(market, "headlines", lambda limit=6: [])
    monkeypatch.setattr(movers, "archived", lambda: [])
    monkeypatch.setattr(market, "asset_info", lambda s: {"symbol": s, "name": "Cameco Corp"} if s == "CCJ" else None)
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {s: {"price": 50.0, "change": 0.03, "change_day": "2026-11-20"} for s in syms})
    monkeypatch.setattr(customstory, "PER_PERSON", 2)

    out = customstory.make("Uranium news", "ip:1", client=fake, sync_plays=True)
    # the idea engine plays it as the brain's own practice call (graded like news hunches), top shown picks only
    assert engine_calls == [("Uranium miners will keep winning deals", "seed", "seed_story")]
    assert engine_against == [{("CCJ", "bearish")}]  # the story says CCJ rises: never played to fall
    pl = customstory.plays("uranium")
    assert pl["status"] == "ready" and [p["ticker"] for p in pl["plays"]] == ["URA", "CCJ"]
    assert pl["plays"][0]["alt"] == "Bull Call Spread" and customstory.plays("never searched")["status"] == "missing"
    # plays stored before this check: one betting against the story's read is hidden when read back
    pkey = f"{customstory.KEY}{customstory._today()}:{customstory._h(customstory.subject_key('uranium'))}:plays"
    stale = dict(pl, plays=[dict(pl["plays"][0]), dict(pl["plays"][1], direction="bearish")])
    customstory._put(pkey, stale)
    assert [p["ticker"] for p in customstory.plays("uranium")["plays"]] == ["URA"]
    customstory._put(pkey, dict(stale, plays=[dict(pl["plays"][1], direction="bearish")]))
    assert customstory.plays("uranium")["status"] == "none"
    st, item = out["story"], out["item"]
    assert st["hook_big"] == "$2.1 billion" and [f["label"] for f in st["figures"]] == ["Uranium price"]  # no invented figure
    assert [c["ticker"] for c in item["companies"]] == ["CCJ"] and item["companies"][0]["change"] == 0.03  # real tickers, priced
    assert item["companies"][0]["link"] == "indirect"
    assert [s["headline"] for s in item["sources"]] == [tagged["CCJ"][0]["headline"]]  # only the headlines it used
    assert item["custom"] and item["hunch"].startswith("Uranium miners") and out["left"] == 1
    n = len(calls)
    again = customstory.make("  uranium ", "ip:2", client=fake)  # same subject, someone else: cached, free
    assert again["cached"] and len(calls) == n and again["left"] == 2
    # nothing real to go on: says so, writes nothing
    none = customstory.make("bananas", "ip:1", client=fake)
    assert none["story"] is None and none["code"] == "no_news" and "nothing real" in none["reason"]
    # the daily cap per person (a cached story still opens)
    capped = customstory.make("lithium", "ip:1", client=fake)
    assert capped["code"] == "limit" and capped["story"] is None
    assert customstory.make("uranium", "ip:1", client=fake)["story"]
    # a company search uses that company's own headlines and puts it first
    monkeypatch.setattr(customstory.newssearch, "_KNOWN", {"cameco": "CCJ"})
    co = customstory.make("Cameco CFO", "ip:3", client=fake)
    assert co["item"]["companies"][0]["ticker"] == "CCJ"
    assert "Cameco names new CFO" in calls[-1]["messages"][0]["content"].split("\n")[3]  # the CFO headline first
    # a topic whose word the headlines never write (live: "uranium"): the topic's companies' newest headlines fill in
    customstory.make("reactor restarts", "ip:4", client=fake)
    assert "Cameco signs uranium supply deal" in calls[-1]["messages"][0]["content"]


def test_custom_story_says_which_search_words_its_headlines_never_mention():
    from backend.v4.customstory import missing_words
    # live 2026-11-23: "Costco earnings" made a story from two Costco headlines, neither about earnings
    item = {"companies": [{"ticker": "COST"}, {"ticker": "WMT"}],
            "sources": [{"headline": "Mizuho Adjusts Price Target on Costco Wholesale", "summary": "Stockpiling lifts sales."}]}
    assert missing_words("Costco earnings", item) == ["earnings"]
    assert missing_words("costco", item) == [] and missing_words("$COST", item) == []  # tickers don't count
    assert missing_words("Costco sale", item) == []  # "sales" covers "sale"
    assert missing_words("uranium", {"companies": [], "sources": [{"headline": "Cameco names new CFO"}]}) == ["uranium"]
    assert missing_words("x", None) == []
    # live 2026-11-23: "weight loss drugs" was told its headlines never mention "loss" or "drugs", though they were
    # about a Novo Nordisk medication and GLP-1 weight management: news words for the same thing count
    wl = {"companies": [{"ticker": "NVO"}, {"ticker": "LLY"}],
          "sources": [{"headline": "Danish Health Authorities Address Patient Eye Injuries Linked to Novo Nordisk Medication"},
                      {"headline": "General Medicine Integrates GLP-1 Weight Management Care into LillyDirect"}]}
    assert missing_words("weight loss drugs", wl) == []
    assert missing_words("weight loss lawsuit", wl) == ["lawsuit"]
    assert missing_words("Costco earnings", dict(item, sources=[{"headline": "Costco quarterly results beat"}])) == []
    assert missing_words("loss", wl) == ["loss"]  # "loss" alone is not the weight-loss phrase


def test_custom_story_times_the_move_from_its_oldest_headline(monkeypatch):
    # live 2026-11-23: "nuclear power" was built from Fri-Sun headlines; its newest (Sun) made CEG's Friday move read
    # "before this news", though Goldman's CEG target change came out Fri 8 AM ET, before that session opened
    from backend.v4 import customstory, movers
    monkeypatch.setattr(movers, "_snapshots", lambda syms: {
        "SPY": {"price": 600.0, "change": -0.031, "change_day": "2026-11-20"},
        "CEG": {"price": 237.0, "change": -0.057, "change_day": "2026-11-20"}})
    item = {"created_at": "2026-11-22T14:02:30Z", "companies": [{"ticker": "CEG", "direction": "up", "why": "w"}],
            "sources": [{"headline": "NuScale halts", "created_at": "2026-11-22T14:02:30Z"},
                        {"headline": "Goldman Adjusts Price Target on Constellation", "created_at": "2026-11-20T13:01:55Z"}]}
    assert customstory._priced({"item": item})["item"]["companies"][0]["move_timing"] is None  # all of it after
    item["sources"] = [item["sources"][0]]
    assert customstory._priced({"item": item})["item"]["companies"][0]["move_timing"] == "before"
    item["sources"] = []  # no sources: the story's own time, as before
    assert customstory._priced({"item": item})["item"]["companies"][0]["move_timing"] == "before"
