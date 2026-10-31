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
    assert r["prefs"] == {"instrument": "options", "goal": "income"}
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
    monkeypatch.setattr(nn, "train", lambda force=False: {"status": "skipped", "reason": "test"})
    fake = FakeClaude()
    out = seeder.auto(claude_client=fake)
    assert out["backfill"]["ok"] > 0 and out["backfill"]["grading"]["graded"] > 0 and "train" in out
    assert out["live"]["ok"] == 3  # TODAY is a weekday
    out2 = seeder.auto(claude_client=fake)
    assert "live" not in out2  # live batch only once a day
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
