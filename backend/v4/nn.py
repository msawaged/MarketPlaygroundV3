"""
MarketPlayground's own neural network.

What it learns: for a (belief, candidate ticker) pair, how much that ticker
will beat SPY in the direction the belief called for over the next
MP_LABEL_DAYS (default 30) days. It trains on every graded pick from every
user plus seeded beliefs.

How it is kept honest:
- Features are frozen at the moment the pick is made (stored with the pick),
  so training never sees information from after the entry date.
- Walk-forward test: train only on picks whose grade was known before the
  test period starts; test on the later picks.
- A new version is only ACTIVE if, on that unseen later period, its top pick
  per belief beats both "average candidate" and Claude's own top pick.
  Otherwise it is saved in SHADOW mode: it scores picks for monitoring but
  does not change what users see.
- Backfilled (historical seed) rows never expose Claude's score/rank as a
  feature, because Claude may know how those years played out.

Start: scikit-learn MLP (runs on Render starter). The feature pipeline is
plain arrays, so it can move to PyTorch and a bigger network later.
"""
from __future__ import annotations

import io
import math
import os
import pickle
import threading
import time
import uuid
from datetime import date, datetime, timezone
from typing import Optional

import numpy as np

from . import db

LABEL_DAYS = int(os.getenv("MP_LABEL_DAYS", "30"))
MIN_TRAIN = int(os.getenv("MP_NN_MIN_TRAIN", "300"))
MIN_TEST = int(os.getenv("MP_NN_MIN_TEST", "80"))
MAX_WEIGHT = float(os.getenv("MP_NN_MAX_WEIGHT", "0.6"))
TEXT_DIM = 2 ** 12
CAT_DIM = 2 ** 11

NUMERIC = [
    "cand_dir", "core_dir", "same_dir", "log_horizon", "conviction",
    "mom20", "mom60", "mom250", "vol20", "vol60", "rs60", "dist_high", "log_price",
    "has_claude", "claude_score", "claude_rank_frac", "n_cands", "is_etf", "backfill",
]

_load_lock = threading.Lock()
_loaded: dict = {"at": 0.0, "row": None, "model": None}


# ---------------- features ----------------

def make_features(
    *,
    belief_text: str,
    themes: list[str],
    core_direction: str,
    horizon_days: int,
    conviction: str,
    cand: dict,
    market: dict,
    rank: int,
    n_cands: int,
    is_etf: bool,
    backfill: bool,
) -> dict:
    """Plain-JSON feature record stored with each pick (frozen at entry time)."""
    dsign = {"bullish": 1.0, "bearish": -1.0}
    cdir = dsign.get(cand.get("direction", "bullish"), 1.0)
    core = dsign.get(core_direction, 0.0)
    has_claude = 0.0 if backfill else 1.0
    num = {
        "cand_dir": cdir,
        "core_dir": core,
        "same_dir": 1.0 if cdir == core else 0.0,
        "log_horizon": math.log(max(horizon_days, 1)) / math.log(730),
        "conviction": {"low": 0.0, "medium": 0.5, "high": 1.0}.get(conviction, 0.5),
        "mom20": market.get("mom20", 0.0),
        "mom60": market.get("mom60", 0.0),
        "mom250": market.get("mom250", 0.0),
        "vol20": market.get("vol20", 0.35),
        "vol60": market.get("vol60", 0.35),
        "rs60": market.get("rs60", 0.0),
        "dist_high": market.get("dist_high", 0.0),
        "log_price": market.get("log_price", 3.0) / 8.0,
        "has_claude": has_claude,
        "claude_score": has_claude * float(cand.get("score", 0.5)),
        "claude_rank_frac": has_claude * (1.0 - rank / max(n_cands, 1)),
        "n_cands": n_cands / 12.0,
        "is_etf": 1.0 if is_etf else 0.0,
        "backfill": 1.0 if backfill else 0.0,
    }
    ticker = cand["ticker"]
    cats = [f"tk={ticker}", f"exp={cand.get('exposure', '')}", f"cdir={cand.get('direction', '')}",
            f"core={core_direction}", f"conv={conviction}"]
    cats += [f"th={t}" for t in themes] + [f"th:tk={t}|{ticker}" for t in themes]
    text = f"{belief_text} {' '.join(themes)} {cand.get('rationale', '')}"
    return {"num": num, "cats": cats, "text": text}


def _vectorizers():
    from sklearn.feature_extraction import FeatureHasher
    from sklearn.feature_extraction.text import HashingVectorizer

    tv = HashingVectorizer(n_features=TEXT_DIM, alternate_sign=False, ngram_range=(1, 2),
                           stop_words="english", norm="l2")
    ch = FeatureHasher(n_features=CAT_DIM, input_type="string", alternate_sign=False)
    return tv, ch


def _clip(v: float) -> float:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return 0.0
    return max(-3.0, min(3.0, float(v)))


def vectorize(records: list[dict]):
    from scipy.sparse import csr_matrix, hstack

    tv, ch = _vectorizers()
    xt = tv.transform([r["text"] for r in records])
    xc = ch.transform([r["cats"] for r in records])
    xn = csr_matrix(np.array([[_clip(r["num"].get(k, 0.0)) for k in NUMERIC] for r in records], dtype=np.float32))
    return hstack([xt, xc, xn]).tocsr()


# ---------------- training ----------------

def _training_rows() -> list[dict]:
    rows = db.query(
        """SELECT p.id, p.belief_id, p.features, p.claude_score, p.entry_date,
                  o.eval_date, o.dir_excess, b.source
           FROM picks p
           JOIN outcomes o ON o.pick_id = p.id AND o.checkpoint_days = ?
           JOIN beliefs b ON b.id = p.belief_id
           WHERE p.features IS NOT NULL""",
        (LABEL_DAYS,),
    )
    out = []
    for r in rows:
        f = db.loads(r["features"])
        if not f:
            continue
        r["features"] = f
        r["label"] = max(-0.5, min(0.5, float(r["dir_excess"])))
        out.append(r)
    return out


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3:
        return 0.0
    ra = a.argsort().argsort().astype(float)
    rb = b.argsort().argsort().astype(float)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def _top_pick_lift(belief_ids: list[str], scores: np.ndarray, labels: np.ndarray) -> tuple[float, int]:
    """Mean over beliefs of (label of top-scored pick − mean label of that belief's picks)."""
    groups: dict[str, list[int]] = {}
    for i, b in enumerate(belief_ids):
        groups.setdefault(b, []).append(i)
    lifts = []
    for idx in groups.values():
        if len(idx) < 2:
            continue
        idx_arr = np.array(idx)
        top = idx_arr[np.argmax(scores[idx_arr])]
        lifts.append(labels[top] - labels[idx_arr].mean())
    return (float(np.mean(lifts)) if lifts else 0.0), len(lifts)


def train(force: bool = False, seed: int = 7) -> dict:
    """Train a new version, evaluate walk-forward, save as active/shadow/rejected."""
    from sklearn.neural_network import MLPRegressor

    rows = _training_rows()
    if len(rows) < MIN_TRAIN + MIN_TEST and not force:
        return {"status": "skipped", "reason": f"need {MIN_TRAIN + MIN_TEST} graded picks, have {len(rows)}"}
    if len(rows) < 20:
        return {"status": "skipped", "reason": f"only {len(rows)} graded picks"}

    entry_dates = sorted(r["entry_date"] for r in rows)
    cutoff = entry_dates[int(len(entry_dates) * 0.8)]
    train_rows = [r for r in rows if r["eval_date"] < cutoff]
    test_rows = [r for r in rows if r["entry_date"] >= cutoff]
    if len(train_rows) < 10 or len(test_rows) < 5:
        return {"status": "skipped", "reason": "not enough rows on both sides of the walk-forward split"}

    xtr = vectorize([r["features"] for r in train_rows])
    ytr = np.array([r["label"] for r in train_rows], dtype=np.float32)
    xte = vectorize([r["features"] for r in test_rows])
    yte = np.array([r["label"] for r in test_rows], dtype=np.float32)

    model = MLPRegressor(hidden_layer_sizes=(64, 32), activation="relu", alpha=1e-3,
                         learning_rate_init=1e-3, max_iter=300, early_stopping=len(train_rows) >= 50,
                         n_iter_no_change=15, random_state=seed)
    model.fit(xtr, ytr)
    pred = model.predict(xte)

    base_mse = float(np.mean((yte - ytr.mean()) ** 2))
    mse = float(np.mean((yte - pred) ** 2))
    bids = [r["belief_id"] for r in test_rows]
    nn_lift, n_groups = _top_pick_lift(bids, pred, yte)
    claude_scores = np.array([float(r["claude_score"] or 0.0) for r in test_rows])
    has_claude = np.array([r["source"] != "seed_backfill" for r in test_rows])
    claude_lift, _ = _top_pick_lift(
        [b for b, h in zip(bids, has_claude) if h], claude_scores[has_claude], yte[has_claude]
    ) if has_claude.any() else (0.0, 0)
    rho = _spearman(pred, yte)

    enough = len(train_rows) >= MIN_TRAIN and len(test_rows) >= MIN_TEST
    beats = rho > 0.03 and nn_lift > 0 and nn_lift > claude_lift
    status = "active" if (enough and beats) else "shadow" if rho > -0.05 else "rejected"
    metrics = {
        "label_days": LABEL_DAYS, "cutoff": cutoff,
        "mse": mse, "baseline_mse": base_mse, "spearman": rho,
        "top_pick_lift": nn_lift, "claude_top_pick_lift": claude_lift, "beliefs_in_test": n_groups,
        "train_backfill_share": float(np.mean([r["source"] == "seed_backfill" for r in train_rows])),
        "reason": ("beat baselines on unseen later beliefs" if status == "active" else
                   "needs more data" if not enough else "did not beat baselines yet"),
    }

    # Refit on all rows for the stored version (evaluation above is what decides status).
    final = MLPRegressor(**model.get_params())
    final.fit(vectorize([r["features"] for r in rows]), np.array([r["label"] for r in rows], dtype=np.float32))

    buf = io.BytesIO()
    pickle.dump(final, buf)
    mid = f"nn-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    if status == "active":
        db.execute("UPDATE nn_models SET status = 'retired' WHERE status = 'active'")
    db.execute(
        "INSERT INTO nn_models (id, created_at, status, n_train, n_test, metrics, blob) VALUES (?,?,?,?,?,?,?)",
        (mid, datetime.now(timezone.utc).isoformat(), status, len(train_rows), len(test_rows),
         db.dumps(metrics), buf.getvalue()),
    )
    with _load_lock:
        _loaded["at"] = 0.0
    return {"status": status, "id": mid, "n_train": len(train_rows), "n_test": len(test_rows), **metrics}


# ---------------- inference ----------------

def _current() -> tuple[Optional[dict], object]:
    with _load_lock:
        if time.time() - _loaded["at"] < 600:
            return _loaded["row"], _loaded["model"]
        row = db.query_one(
            """SELECT id, status, n_train, n_test, metrics, blob FROM nn_models
               WHERE status IN ('active','shadow')
               ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, created_at DESC LIMIT 1"""
        )
        model = None
        if row:
            blob = row.pop("blob")
            model = pickle.loads(bytes(blob))
            row["metrics"] = db.loads(row["metrics"], {})
        _loaded.update(at=time.time(), row=row, model=model)
        return row, model


def status() -> dict:
    row, _ = _current()
    if not row:
        return {"status": "none", "weight": 0.0}
    return {**row, "weight": blend_weight(row)}


def blend_weight(row: Optional[dict]) -> float:
    if not row or row.get("status") != "active":
        return 0.0
    return min(MAX_WEIGHT, row.get("n_train", 0) / 3000.0 + 0.1)


def predict(records: list[dict]) -> tuple[Optional[list[float]], float, Optional[str]]:
    """(predictions or None, blend weight, model id)."""
    row, model = _current()
    if model is None or not records:
        return None, 0.0, None
    preds = model.predict(vectorize(records))
    return [float(p) for p in preds], blend_weight(row), row["id"]
