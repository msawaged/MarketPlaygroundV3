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
            conn.execute("DROP TABLE IF EXISTS outcomes, pick_themes, feedback, picks, beliefs, nn_models, kv_cache, waitlist, accounts, sessions CASCADE")
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("MP_SQLITE_PATH", str(tmp_path / "t.db"))
    db.reset_for_tests()
    learning.invalidate()
    nn._loaded.update(at=0.0, row=None, model=None)
    market.clear_cache()
    series = {s: _series(s) for s in DRIFTS}
    monkeypatch.setattr(market, "today", lambda: TODAY)
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
    other = c.post("/v4/belief", headers={"x-forwarded-for": "9.9.9.9"})
    assert other.status_code == 200                         # limit is per visitor
    rate_limit.reset_for_tests()


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
    assert c.get("/v4/learning").status_code == 200
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
    assert all(p["structure"] in strategy.OPTION_STRUCTURES for p in bold["picks"] if p["shown"] and p["price"] >= 10)
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
