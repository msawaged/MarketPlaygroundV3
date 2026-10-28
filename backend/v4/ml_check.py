"""
Offline proof that the learning loop works. No Claude, no Alpaca, no cost.

It builds a fake market where the truth is known, runs the REAL pipeline
(engine -> grader -> network training) on it, and checks:

1. SIGNAL world: in every theme some companies truly benefit and some don't,
   and a fake "Claude" only half-knows which. The network should learn the
   difference, beat Claude's own ordering on later beliefs it never saw,
   and get promoted to ACTIVE.
2. NO-SIGNAL world: every company is a coin flip. The network must NOT be
   promoted (no fooling itself on noise).
3. The live ranking: once active, the picks users see should be the ones that
   truly do better.

Run:  PYTHONPATH=./ python -m backend.v4.ml_check            (about 1-3 minutes)
      PYTHONPATH=./ python -m backend.v4.ml_check --quick    (smaller)
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import resource
import tempfile
import time
from datetime import date, timedelta
from types import SimpleNamespace

import numpy as np

TODAY = date(2026, 10, 15)
THEMES = {
    "plumbing": ["plumbing", "pipes", "water heaters", "home repair"],
    "potatoes": ["potatoes", "snack food", "french fries", "farm produce"],
    "air travel": ["air travel", "flights", "airlines", "vacations abroad"],
    "pets": ["pet ownership", "pet food", "vet visits", "dog adoption"],
    "ai chips": ["AI chips", "data centers", "GPUs", "machine learning compute"],
    "solar": ["solar power", "rooftop solar", "clean energy", "home batteries"],
    "restaurants": ["eating out", "restaurants", "fast casual dining", "food delivery"],
    "housing": ["home building", "new houses", "housing starts", "construction"],
}
PER_THEME = 6
TEMPLATES = [
    "demand for {w} is going to grow", "{w} will be huge next year", "I think {w} is about to boom",
    "more people will want {w}", "{w} is in demand", "spending on {w} keeps rising",
]
BEAR_TEMPLATES = ["{w} is going to slow down", "people will spend less on {w}", "{w} demand will fall"]


def build_world(signal: bool, seed: int):
    rnd = random.Random(seed)
    tickers, truth, theme_of = {}, {}, {}
    for t_i, theme in enumerate(THEMES):
        for k in range(PER_THEME):
            sym = f"{theme[:2].upper()}{chr(65 + k)}{chr(65 + t_i)}".replace(" ", "X")
            # truth = annual excess drift vs the market
            if signal:
                drift = [0.30, 0.22, 0.0, 0.0, -0.18, -0.25][k]
            else:
                drift = 0.0
            truth[sym] = drift
            theme_of[sym] = theme
            tickers[sym] = f"{theme.title()} Company {k}"
    series = {}
    start = TODAY - timedelta(days=365 * 5)
    days = []
    d = start
    while d <= TODAY:
        if d.weekday() < 5:
            days.append(d.isoformat())
        d += timedelta(days=1)
    mkt = np.cumsum([0.08 / 252 + rnd.gauss(0, 0.01) for _ in days])
    series["SPY"] = (days, list(np.round(400 * np.exp(mkt), 4)))
    for sym, drift in truth.items():
        r = random.Random(f"{seed}-{sym}")
        p0 = 20 + r.random() * 150
        lr = np.cumsum([drift / 252 + r.gauss(0, 0.018) for _ in days])
        series[sym] = (days, list(np.round(p0 * np.exp(mkt + lr), 4)))
    return tickers, truth, theme_of, series


class FakeClaude:
    """Returns the theme's companies with scores that only weakly track the truth."""

    def __init__(self, truth, theme_of, seed, claude_skill=0.35):
        self.truth, self.theme_of = truth, theme_of
        self.rnd = random.Random(seed + 99)
        self.skill = claude_skill
        self.messages = self

    def create(self, **kw):
        msg = kw["messages"][0]["content"].lower()
        theme = next((t for t, words in THEMES.items() if any(w.lower() in msg for w in words)), "plumbing")
        bearish = any(x in msg for x in ("slow down", "spend less", "will fall"))
        cands = []
        syms = [s for s, th in self.theme_of.items() if th == theme]
        for s in syms:
            true = self.truth[s] * (-1 if bearish else 1)
            score = 0.6 + self.skill * true + self.rnd.gauss(0, 0.12)
            cands.append({"ticker": s, "name": s, "exposure": "direct", "direction": "bearish" if bearish else "bullish",
                          "rationale": f"exposed to {theme}", "score": round(max(0.05, min(0.99, score)), 3)})
        out = {"is_market_belief": True, "note": "", "summary": f"{theme} {'falls' if bearish else 'rises'}",
               "direction": "bearish" if bearish else "bullish", "horizon_days": 90, "conviction": "medium",
               "themes": [theme], "causal_chain": "x", "candidates": cands}
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(out))],
                               usage=SimpleNamespace(input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
                                                     cache_creation_input_tokens=0),
                               stop_reason="end_turn")


def _install(tickers, series, db_path):
    os.environ.pop("DATABASE_URL", None)
    os.environ["MP_SQLITE_PATH"] = db_path
    from . import db, learning, market, nn
    db.reset_for_tests()
    learning.invalidate()
    nn._loaded.update(at=0.0, row=None, model=None)
    market.clear_cache()
    market.today = lambda: TODAY

    def closes(s):
        s = s.upper()
        if s not in series:
            raise market.MarketDataError("no data")
        return series[s]
    market.daily_closes = closes
    market.latest_price = lambda s: series[s.upper()][1][-1]
    market.asset_info = lambda s: ({"symbol": s, "name": tickers[s], "is_etf": False, "tradable": True}
                                   if s in tickers else None)


def _belief_text(rnd):
    theme = rnd.choice(list(THEMES))
    w = rnd.choice(THEMES[theme])
    if rnd.random() < 0.2:
        return rnd.choice(BEAR_TEMPLATES).format(w=w)
    return rnd.choice(TEMPLATES).format(w=w)


def run_world(signal: bool, n_beliefs: int, seed: int = 1) -> dict:
    from . import engine, grader, nn

    tickers, truth, theme_of, series = build_world(signal, seed)
    tmp = tempfile.mkdtemp()
    _install(tickers, series, os.path.join(tmp, "sim.db"))
    claude = FakeClaude(truth, theme_of, seed)
    rnd = random.Random(seed)

    t0 = time.time()
    # Past beliefs spread over ~3 years (like the backfill seeder), graded with real prices.
    for i in range(n_beliefs):
        as_of = TODAY - timedelta(days=rnd.randint(100, 1095))
        while as_of.weekday() >= 5:
            as_of -= timedelta(days=1)
        engine.process_belief(f"{_belief_text(rnd)} #{i}", "sim", rnd.choice(["conservative", "moderate", "aggressive"]),
                              as_of=as_of, source="seed_backfill", claude_client=claude)
    g = grader.grade()
    t_seed = time.time() - t0

    t1 = time.time()
    rss0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    res = nn.train(force=True)
    rss1 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    t_train = time.time() - t1

    # What users would now see: fresh live beliefs; compare the TRUE quality of the top pick
    # with the network on vs off (same beliefs, same Claude answers via the interpretation cache).
    live_texts = [f"{_belief_text(rnd)} live{j}" for j in range(60)]

    def live_quality(network_on: bool):
        orig = nn.predict
        if not network_on:
            nn.predict = lambda records: (None, 0.0, None)
        try:
            shown, claude_only, best = [], [], []
            for text in live_texts:
                r = engine.process_belief(text, "u", "moderate", claude_client=claude)
                if not r.get("picks"):
                    continue
                sign = -1 if r["picks"][0]["direction"] == "bearish" else 1
                q = {p["ticker"]: sign * truth[p["ticker"]] for p in r["picks"]}
                shown.append(q[r["picks"][0]["ticker"]])
                claude_only.append(q[max(r["picks"], key=lambda p: p["claude_score"])["ticker"]])
                best.append(max(q.values()))
            return float(np.mean(shown)), float(np.mean(claude_only)), float(np.mean(best))
        finally:
            nn.predict = orig

    nn._loaded["at"] = 0.0
    off_shown, claude_q, best_q = live_quality(False)
    on_shown, _, _ = live_quality(True)

    # Does the network's opinion line up with the hidden truth? (only possible in a simulation)
    rows = nn._training_rows()
    rho_truth = None
    model_row, model = nn._current()
    if model is not None and rows:
        preds = model.predict(nn.vectorize([r["features"] for r in rows]))
        tv = [truth[next(c[3:] for c in r["features"]["cats"] if c.startswith("tk="))] * r["features"]["num"]["cand_dir"]
              for r in rows]
        rho_truth = nn._spearman(np.array(preds), np.array(tv))
    shown_true, claude_true, best_true = [on_shown], [claude_q], [best_q]

    return {
        "world": "signal" if signal else "no-signal",
        "beliefs": n_beliefs,
        "graded": g,
        "status": res.get("status"),
        "reason": res.get("reason"),
        "n_train": res.get("n_train"), "n_test": res.get("n_test"),
        "spearman": round(res.get("spearman", 0), 3),
        "nn_top_pick_lift_30d": round(res.get("top_pick_lift", 0), 4),
        "t_stat": round(res.get("top_pick_lift_t", 0), 2),
        "linear_lift_30d": round(res.get("linear_top_pick_lift", 0), 4),
        "blend_weight": (model_row or {}).get("metrics", {}).get("blend_weight") if model_row else None,
        "network_vs_truth_rho": None if rho_truth is None else round(rho_truth, 3),
        "top_pick_true_drift_network_on": round(on_shown, 3),
        "top_pick_true_drift_network_off": round(off_shown, 3),
        "claude_score_only_top_pick": round(claude_q, 3),
        "best_possible": round(best_q, 3),
        "seconds_pipeline": round(t_seed, 1), "seconds_train": round(t_train, 1),
        "train_peak_mb": round(max(rss0, rss1) / 1024, 0),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=2)
    a = ap.parse_args()
    sizes = [150, 400] if a.quick else [150, 400, 800]
    results = []
    for seed in range(1, a.seeds + 1):
        for n in sizes:
            for signal in (True, False):
                r = run_world(signal, n, seed)
                r["seed"] = seed
                results.append(r)
                print(json.dumps(r))
    ok_signal = [r for r in results if r["world"] == "signal" and r["beliefs"] == max(sizes)]
    ok_noise = [r for r in results if r["world"] == "no-signal"]
    passed = all(r["status"] == "active" for r in ok_signal) and not any(r["status"] == "active" for r in ok_noise)
    print("\nRESULT:", "PASS" if passed else "CHECK", "- signal worlds active at largest size:",
          [r["status"] for r in ok_signal], "| no-signal worlds active:",
          sum(r["status"] == "active" for r in ok_noise), "of", len(ok_noise))


if __name__ == "__main__":
    main()
