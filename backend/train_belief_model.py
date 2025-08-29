# backend/train_belief_model.py
"""
Belief Tag Classifier — trains a model to classify belief text into tags.

What’s included (fully merged):
1) Super-tag remap to stabilize small/imbalanced data (directional_bull/bear, volatility, etc.)
2) Rare-label collapse (MIN_SAMPLES_PER_CLASS=5) → rolls tiny classes into "other"
3) Stratified 5-fold CV for stable metrics + final fit on ALL data
4) Optional Alpaca feature enrichment if a 'ticker' column exists (or auto-detected)
   - pct_change_1d / 5d / 20d, realized_vol_20d
   - cached per ticker; safe fallbacks if creds/data unavailable
Also:
- Writes belief_model.joblib, belief_vectorizer.joblib, and belief_model_metrics.json
- Returns a metrics dict (never None) so the retrain worker logs real JSON
- Works as module (-m) and as script

CSV expected columns:
- REQUIRED:  belief, tag
- OPTIONAL:  ticker   (if absent, we try to auto-detect; else default to SPY)
"""

from __future__ import annotations

import os
import sys
import json
import math
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

import pandas as pd
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.utils.class_weight import compute_class_weight
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import classification_report
from scipy.sparse import hstack, csr_matrix

# ── Import shim so this file works both as module and as script ────────────────
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Optional structured logger (won’t crash if not available)
try:
    from backend.utils.logger import write_training_log
except Exception:  # pragma: no cover
    def write_training_log(*args, **kwargs):
        pass

# Optional ticker detector (used if training CSV lacks a 'ticker' column)
def _safe_detect_ticker(txt: str) -> str:
    try:
        from backend.dynamic_ticker_detector import detect_ticker_from_text
        return detect_ticker_from_text(txt) or "SPY"
    except Exception:
        return "SPY"


# ── Config paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "training_data" / "clean_belief_tags.csv"
MODEL_PATH = BASE_DIR / "belief_model.joblib"
VECTORIZER_PATH = BASE_DIR / "belief_vectorizer.joblib"
METRICS_PATH = BASE_DIR / "belief_model_metrics.json"

# Alpaca premium data host (set env to your paid endpoint)
ALPACA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")
ALPACA_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_API_SECRET", "")


# ── Tiny Alpaca fetcher (used only if 'ticker' column exists / is added) ──────
def _alpaca_headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": ALPACA_KEY or "",
        "APCA-API-SECRET-KEY": ALPACA_SECRET or "",
    }

def _fetch_bars(symbol: str, timeframe: str = "1Day", limit: int = 60) -> list:
    """
    Return list of bars [{t,o,h,l,c,v}] from Alpaca premium data.
    Safe fallback: returns [] on any failure (no crashes).
    """
    import requests  # local import to keep this dependency optional
    try:
        url = f"{ALPACA_BASE}/v2/stocks/{symbol}/bars"
        r = requests.get(url, headers=_alpaca_headers(),
                         params={"timeframe": timeframe, "limit": limit}, timeout=12)
        if r.status_code == 200:
            return (r.json() or {}).get("bars", []) or []
        return []
    except Exception:
        return []

def _recent_features(symbol: str) -> Dict[str, float]:
    """
    Minimal numeric features from daily bars:
      - pct_change_1d / 5d / 20d
      - realized_vol_20d (stdev of daily returns)
    Returns {} if not enough data / unavailable.
    """
    bars = _fetch_bars(symbol, "1Day", 60)
    closes = [b.get("c") for b in bars if isinstance(b, dict) and "c" in b][-60:]
    if len(closes) < 21:
        return {}

    def pct(a, b): return (a / b - 1.0) if b else 0.0
    rets = [pct(closes[i], closes[i - 1]) for i in range(1, len(closes))]

    def chg(n):
        if len(closes) <= n:
            return 0.0
        return pct(closes[-1], closes[-1 - n])

    def vol(n):
        if len(rets) < n:
            return 0.0
        mu = sum(rets[-n:]) / n
        var = sum((x - mu) ** 2 for x in rets[-n:]) / max(1, n - 1)
        return math.sqrt(var)

    return {
        "pct_change_1d": chg(1),
        "pct_change_5d": chg(5),
        "pct_change_20d": chg(20),
        "realized_vol_20d": vol(20),
        "bars_used": float(len(closes)),
    }


# ── Training knobs ─────────────────────────────────────────────────────────────
MIN_SAMPLES_PER_CLASS = 5         # Step A: raise threshold to collapse tiny classes
RARE_LABEL = "other"
VEC_MAX_FEATURES = 5000
RANDOM_STATE = 42
N_SPLITS = 5                      # Step C: stratified CV folds


@dataclass
class TrainPaths:
    input_file: Path = DEFAULT_INPUT
    model_path: Path = MODEL_PATH
    vectorizer_path: Path = VECTORIZER_PATH
    metrics_path: Path = METRICS_PATH


# ── Label processing helpers ───────────────────────────────────────────────────
def _collapse_rare_labels(series: pd.Series) -> pd.Series:
    """Collapse labels with < MIN_SAMPLES_PER_CLASS occurrences into RARE_LABEL."""
    counts = series.value_counts()
    rare = set(counts[counts < MIN_SAMPLES_PER_CLASS].index)
    if not rare:
        return series
    return series.apply(lambda x: RARE_LABEL if x in rare else x)

def _apply_super_tag_map(df: pd.DataFrame) -> pd.DataFrame:
    """
    Step B: Remap fine-grained tags to stable super-tags BEFORE rare collapse.
    """
    TAG_MAP = {
        # directional bull family
        "bull call spread": "directional_bull",
        "bullish": "directional_bull",
        "buy stock": "directional_bull",
        "call option": "directional_bull",

        # directional bear family
        "bearish": "directional_bear",
        "long put": "directional_bear",
        "put option": "directional_bear",

        # volatility structures
        "iron condor": "volatility",
        "straddle": "volatility",
        "strangle": "volatility",
        "volatility": "volatility",

        # rates & neutral
        "rate_sensitive": "rate_sensitive",
        "neutral": "neutral",
    }
    df = df.copy()
    df["tag"] = df["tag"].map(lambda t: TAG_MAP.get(t, t))
    return df


# ── Feature assembly ───────────────────────────────────────────────────────────
def _build_alpaca_matrix(df: pd.DataFrame) -> Optional[csr_matrix]:
    """
    Build numeric features per row using Alpaca data for the row’s 'ticker'.
    Returns a csr_matrix (n_rows x n_num_features) or None if unavailable.
    """
    if "ticker" not in df.columns:
        return None

    cache: Dict[str, Dict[str, float]] = {}
    feats: List[List[float]] = []
    for t in df["ticker"].astype(str).fillna("SPY"):
        t = (t or "SPY").upper().strip()
        if not t:
            t = "SPY"
        if t not in cache:
            cache[t] = _recent_features(t)
        f = cache[t] or {}
        feats.append([
            float(f.get("pct_change_1d", 0.0)),
            float(f.get("pct_change_5d", 0.0)),
            float(f.get("pct_change_20d", 0.0)),
            float(f.get("realized_vol_20d", 0.0)),
        ])
    arr = np.array(feats, dtype=np.float32)
    return csr_matrix(arr)


def _stratified_cv_metrics(X, y, class_weight) -> Tuple[float, float]:
    """
    Step C: 5-fold stratified CV metrics (macro_f1, accuracy) for stability on tiny datasets.
    """
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    f1s, accs = [], []
    for tr_idx, va_idx in skf.split(X, y):
        X_tr, X_va = X[tr_idx], X[va_idx]
        y_tr, y_va = y[tr_idx], y[va_idx]
        clf = LogisticRegression(max_iter=2000, class_weight=class_weight, solver="saga", n_jobs=-1)
        clf.fit(X_tr, y_tr)
        y_hat = clf.predict(X_va)
        rep = classification_report(y_va, y_hat, output_dict=True, zero_division=0)
        f1s.append(rep["macro avg"]["f1-score"])
        accs.append(rep.get("accuracy", 0.0))
    return float(np.mean(f1s)), float(np.mean(accs))


# ── Main training function ─────────────────────────────────────────────────────
def train_belief_model(
    input_file: str | os.PathLike | None = None,
    model_output_path: str | os.PathLike | None = None,
    vectorizer_output_path: str | os.PathLike | None = None,
) -> Dict[str, Any]:
    """
    Train belief tag classification model and save it to disk.
    Returns a metrics dict (never None) for the retrain worker.

    Args:
      input_file: CSV with columns 'belief','tag' (optional 'ticker')
      model_output_path: directory or full path for model .joblib
      vectorizer_output_path: directory or full path for vectorizer .joblib
    """
    t0 = time.time()
    paths = TrainPaths(
        input_file=Path(input_file) if input_file else DEFAULT_INPUT,
        model_path=Path(model_output_path) if model_output_path and str(model_output_path).endswith(".joblib")
        else (Path(model_output_path) if model_output_path else BASE_DIR) / "belief_model.joblib",
        vectorizer_path=Path(vectorizer_output_path) if vectorizer_output_path and str(vectorizer_output_path).endswith(".joblib")
        else (Path(vectorizer_output_path) if vectorizer_output_path else BASE_DIR) / "belief_vectorizer.joblib",
        metrics_path=METRICS_PATH,
    )

    # Load data
    if not paths.input_file.exists():
        msg = f"❌ Training data not found: {paths.input_file}"
        print(msg)
        m = {"status": "error", "error": msg}
        _write_metrics(m, paths.metrics_path)
        return m

    df = pd.read_csv(paths.input_file)
    if not {"belief", "tag"}.issubset(df.columns):
        raise ValueError("CSV must contain 'belief' and 'tag' columns")

    # Clean base fields
    df = df.dropna(subset=["belief", "tag"]).copy()
    df["tag"] = df["tag"].astype(str).str.lower().str.strip()

    # Step B: Super-tag remap BEFORE rare collapse
    df = _apply_super_tag_map(df)

    # Step A: Collapse rare labels after remap
    df["tag"] = _collapse_rare_labels(df["tag"])

    # Bail out gracefully if only one label remains
    if df["tag"].nunique() < 2:
        msg = "Only one label after collapse; skipping belief retrain."
        print("⚠️", msg)
        m = {"status": "skipped", "reason": "one_label_after_collapse",
             "labels": df["tag"].value_counts().to_dict()}
        _write_metrics(m, paths.metrics_path)
        return m

    # Step D (optional): Ensure we have a 'ticker' column to unlock Alpaca features
    if "ticker" not in df.columns:
        # Try to detect; fallback to SPY to avoid missing column
        df["ticker"] = df["belief"].astype(str).apply(_safe_detect_ticker)

    # Text vectorizer
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=VEC_MAX_FEATURES)
    X_text = vectorizer.fit_transform(df["belief"].astype(str))

    # Optional Alpaca numeric features
    X_num = _build_alpaca_matrix(df)
    if X_num is not None and X_num.shape[0] == X_text.shape[0]:
        X_all = hstack([X_text, X_num], format="csr")
        alpaca_used = True
    else:
        X_all = X_text
        alpaca_used = False

    y = df["tag"].to_numpy()

    # Class weights for imbalance
    classes = np.unique(y)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)
    cw = {c: w for c, w in zip(classes, weights)}

    # Step C: Stable metrics via stratified 5-fold CV
    cv_macro_f1, cv_acc = _stratified_cv_metrics(X_all, y, cw)

    # Final model on ALL data
    clf = LogisticRegression(max_iter=2000, class_weight=cw, solver="saga", n_jobs=-1)
    clf.fit(X_all, y)

    # Save artifacts
    joblib.dump(clf, paths.model_path)
    joblib.dump(vectorizer, paths.vectorizer_path)
    print(f"✅ Model saved to → {paths.model_path}")
    print(f"✅ Vectorizer saved to → {paths.vectorizer_path}")

    # Build metrics dict
    metrics: Dict[str, Any] = {
        "status": "ok",
        "duration_sec": round(time.time() - t0, 3),
        "macro_f1": cv_macro_f1,
        "accuracy": cv_acc,
        "weighted_f1": None,  # not computed in CV; can be added if needed
        "dataset": {
            "n_rows": int(len(df)),
            "labels": df["tag"].value_counts().to_dict(),
            "alpaca_used": bool(alpaca_used),
        },
        "data_provenance": {
            "alpaca_premium": bool(alpaca_used and ALPACA_KEY and ALPACA_SECRET),
            "alpaca_base": ALPACA_BASE if alpaca_used else None,
            "features": (["pct_change_1d", "pct_change_5d", "pct_change_20d", "realized_vol_20d"]
                         if alpaca_used else []),
        },
    }

    # Persist metrics json (for worker & audits)
    _write_metrics(metrics, paths.metrics_path)

    # Log compact summary
    try:
        write_training_log(("belief metrics: " + json.dumps({
            "status": metrics["status"],
            "macro_f1": metrics["macro_f1"],
            "accuracy": metrics["accuracy"],
            "alpaca_used": metrics["dataset"]["alpaca_used"],
            "labels": metrics["dataset"]["labels"],
        }))[:2000], source="train_belief_model")
    except Exception:
        pass

    # Human-readable summary
    print("\n📊 CV Summary (5-fold):")
    print(json.dumps({
        "macro_f1": metrics["macro_f1"],
        "accuracy": metrics["accuracy"],
        "alpaca_used": metrics["dataset"]["alpaca_used"],
        "n_classes": int(len(metrics["dataset"]["labels"])),
    }, indent=2))

    return metrics


def _write_metrics(metrics: Dict[str, Any], path: Path) -> None:
    try:
        path.write_text(json.dumps(metrics, indent=2))
    except Exception:
        pass


# ── CLI entrypoint ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        out = train_belief_model()
        # print a compact JSON summary so it's obvious to the human
        print(json.dumps({
            "status": out.get("status"),
            "accuracy": out.get("accuracy"),
            "macro_f1": out.get("macro_f1"),
            "alpaca_used": out.get("dataset", {}).get("alpaca_used"),
        }, indent=2))
    except Exception as e:
        print("❌ Training failed:", str(e))
        traceback.print_exc()
        sys.exit(1)
