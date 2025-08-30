# backend/train_asset_model.py
"""
Asset Class Model — classifies an input (belief/news text) into asset classes.

What’s included:
1) Super-class mapping to fight sparsity (options/stock/etf/bond; rares -> other)
2) Rare-label collapse (MIN_SAMPLES_PER_CLASS=5)
3) Stratified 5-fold CV + class_weight="balanced"
4) Optional Alpaca feature enrichment per ticker (pct_change_1d/5d/20d, realized_vol_20d)
5) Writes:
   - backend/asset_class_model.joblib
   - backend/asset_vectorizer.joblib
   - backend/asset_model_metrics.json
6) Returns a metrics dict (never None) for the retrain worker
7) Works as module (-m) and as script

CSV schema: flexible. We auto-detect common columns.
- Text column: one of ['text', 'belief', 'input', 'content', 'sentence']
- Label column: one of ['asset', 'asset_class', 'label', 'tag', 'class']
- Optional: 'ticker' — if absent, we attempt to detect or default to SPY
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

# ── Import shim so this file works as both module and script ────────────────────
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Optional structured logger
try:
    from backend.utils.logger import write_training_log
except Exception:  # pragma: no cover
    def write_training_log(*args, **kwargs):
        pass

# Optional ticker detector
def _safe_detect_ticker(txt: str) -> str:
    try:
        from backend.dynamic_ticker_detector import detect_ticker_from_text
        return detect_ticker_from_text(txt) or "SPY"
    except Exception:
        return "SPY"


# ── Config paths ───────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
# Most likely file in your repo
DEFAULT_INPUT = BASE_DIR / "training_data" / "final_belief_asset_training.csv"

MODEL_PATH = BASE_DIR / "asset_class_model.joblib"
VECTORIZER_PATH = BASE_DIR / "asset_vectorizer.joblib"
METRICS_PATH = BASE_DIR / "asset_model_metrics.json"

# Alpaca premium data host
ALPACA_BASE = os.getenv("ALPACA_DATA_BASE", "https://data.alpaca.markets")
ALPACA_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET = os.getenv("ALPACA_API_SECRET", "")


# ── Tiny Alpaca fetcher (used only if 'ticker' exists/is added) ────────────────
def _alpaca_headers() -> Dict[str, str]:
    return {
        "APCA-API-KEY-ID": ALPACA_KEY or "",
        "APCA-API-SECRET-KEY": ALPACA_SECRET or "",
    }

def _fetch_bars(symbol: str, timeframe: str = "1Day", limit: int = 60) -> list:
    import requests
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
    bars = _fetch_bars(symbol, "1Day", 60)
    closes = [b.get("c") for b in bars if isinstance(b, dict) and "c" in b][-60:]
    if len(closes) < 21:
        return {}
    def pct(a,b): return (a/b - 1.0) if b else 0.0
    rets = [pct(closes[i], closes[i-1]) for i in range(1,len(closes))]
    def chg(n):
        if len(closes) <= n: return 0.0
        return pct(closes[-1], closes[-1-n])
    def vol(n):
        if len(rets) < n: return 0.0
        mu = sum(rets[-n:])/n
        var = sum((x-mu)**2 for x in rets[-n:]) / max(1, n-1)
        return math.sqrt(var)
    return {
        "pct_change_1d": chg(1),
        "pct_change_5d": chg(5),
        "pct_change_20d": chg(20),
        "realized_vol_20d": vol(20),
        "bars_used": float(len(closes)),
    }


# ── Training knobs ─────────────────────────────────────────────────────────────
MIN_SAMPLES_PER_CLASS = 5
RARE_LABEL = "other"
VEC_MAX_FEATURES = 5000
RANDOM_STATE = 42
N_SPLITS = 5

# Super-class remap to stabilize labels
SUPER_MAP = {
    "options": "options",
    "option": "options",
    "stock": "stock",
    "equity": "stock",
    "etf": "etf",
    "bond": "bond",
    "bonds": "bond",
    # keep rate-sensitive or crypto as-is if you have them; they’ll collapse if rare
}


@dataclass
class TrainPaths:
    input_file: Path = DEFAULT_INPUT
    model_path: Path = MODEL_PATH
    vectorizer_path: Path = VECTORIZER_PATH
    metrics_path: Path = METRICS_PATH


# ── Column auto-detection ──────────────────────────────────────────────────────
TEXT_CANDIDATES = ["text", "belief", "input", "content", "sentence"]
LABEL_CANDIDATES = ["asset", "asset_class", "label", "tag", "class"]

def _pick_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ── Rare collapse & super mapping ─────────────────────────────────────────────
def _apply_super_map(series: pd.Series) -> pd.Series:
    def map_one(x: str) -> str:
        x = str(x).strip().lower()
        return SUPER_MAP.get(x, x)
    return series.astype(str).map(map_one)

def _collapse_rare(series: pd.Series) -> pd.Series:
    counts = series.value_counts()
    rare = set(counts[counts < MIN_SAMPLES_PER_CLASS].index)
    if not rare:
        return series
    return series.apply(lambda x: RARE_LABEL if x in rare else x)


# ── Features ───────────────────────────────────────────────────────────────────
def _build_alpaca_matrix(df: pd.DataFrame) -> Optional[csr_matrix]:
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

def _cv_metrics(X, y, class_weight) -> Tuple[float, float]:
    skf = StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    f1s, accs = [], []
    for tr, va in skf.split(X, y):
        X_tr, X_va = X[tr], X[va]
        y_tr, y_va = y[tr], y[va]
        clf = LogisticRegression(max_iter=2000, class_weight=class_weight, solver="saga", n_jobs=-1)
        clf.fit(X_tr, y_tr)
        y_hat = clf.predict(X_va)
        rep = classification_report(y_va, y_hat, output_dict=True, zero_division=0)
        f1s.append(rep["macro avg"]["f1-score"])
        accs.append(rep.get("accuracy", 0.0))
    return float(np.mean(f1s)), float(np.mean(accs))


# ── Trainer ────────────────────────────────────────────────────────────────────
def train_asset_model(
    input_file: str | os.PathLike | None = None,
    model_output_path: str | os.PathLike | None = None,
    vectorizer_output_path: str | os.PathLike | None = None,
) -> Dict[str, Any]:
    t0 = time.time()
    paths = TrainPaths(
        input_file=Path(input_file) if input_file else DEFAULT_INPUT,
        model_path=Path(model_output_path) if model_output_path and str(model_output_path).endswith(".joblib")
        else (Path(model_output_path) if model_output_path else BASE_DIR) / "asset_class_model.joblib",
        vectorizer_path=Path(vectorizer_output_path) if vectorizer_output_path and str(vectorizer_output_path).endswith(".joblib")
        else (Path(vectorizer_output_path) if vectorizer_output_path else BASE_DIR) / "asset_vectorizer.joblib",
        metrics_path=METRICS_PATH,
    )

    if not paths.input_file.exists():
        msg = f"❌ Asset training data not found: {paths.input_file}"
        print(msg)
        m = {"status": "error", "error": msg}
        _write_metrics(m, paths.metrics_path)
        return m

    df = pd.read_csv(paths.input_file)
    text_col = _pick_column(df, TEXT_CANDIDATES)
    label_col = _pick_column(df, LABEL_CANDIDATES)
    if not text_col or not label_col:
        raise ValueError(f"CSV must contain a text col in {TEXT_CANDIDATES} and a label col in {LABEL_CANDIDATES}")

    df = df.dropna(subset=[text_col, label_col]).copy()
    if df.empty:
        m = {"status": "error", "error": "No valid asset training rows"}
        _write_metrics(m, paths.metrics_path)
        return m

    # Normalize labels: super-map then collapse rares
    df[label_col] = df[label_col].astype(str).str.lower().str.strip()
    df[label_col] = _apply_super_map(df[label_col])
    df[label_col] = _collapse_rare(df[label_col])

    if df[label_col].nunique() < 2:
        msg = "Only one asset label after collapse; skipping asset retrain."
        print("⚠️", msg)
        m = {"status": "skipped", "reason": "one_label_after_collapse", "labels": df[label_col].value_counts().to_dict()}
        _write_metrics(m, paths.metrics_path)
        return m

    # Ensure ticker column so Alpaca features can kick in
    if "ticker" not in df.columns:
        df["ticker"] = df[text_col].astype(str).apply(_safe_detect_ticker)

    # Text vectorizer
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=VEC_MAX_FEATURES)
    X_text = vectorizer.fit_transform(df[text_col].astype(str))

    # Optional numeric features
    X_num = _build_alpaca_matrix(df)
    if X_num is not None and X_num.shape[0] == X_text.shape[0]:
        X_all = hstack([X_text, X_num], format="csr")
        alpaca_used = True
    else:
        X_all = X_text
        alpaca_used = False

    y = df[label_col].to_numpy()

    # Class weights
    classes = np.unique(y)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=y)
    cw = {c: w for c, w in zip(classes, weights)}

    # Stable CV metrics
    cv_macro_f1, cv_acc = _cv_metrics(X_all, y, cw)

    # Final model on all data
    clf = LogisticRegression(max_iter=2000, class_weight=cw, solver="saga", n_jobs=-1)
    clf.fit(X_all, y)

    # Save artifacts
    joblib.dump(clf, paths.model_path)
    joblib.dump(vectorizer, paths.vectorizer_path)
    print(f"✅ Asset model saved → {paths.model_path}")
    print(f"✅ Asset vectorizer saved → {paths.vectorizer_path}")

    metrics: Dict[str, Any] = {
        "status": "ok",
        "duration_sec": round(time.time() - t0, 3),
        "macro_f1": cv_macro_f1,
        "accuracy": cv_acc,
        "weighted_f1": None,
        "dataset": {
            "n_rows": int(len(df)),
            "labels": df[label_col].value_counts().to_dict(),
            "alpaca_used": bool(alpaca_used),
        },
        "data_provenance": {
            "alpaca_premium": bool(alpaca_used and ALPACA_KEY and ALPACA_SECRET),
            "alpaca_base": ALPACA_BASE if alpaca_used else None,
            "features": (["pct_change_1d", "pct_change_5d", "pct_change_20d", "realized_vol_20d"]
                         if alpaca_used else []),
        },
    }

    _write_metrics(metrics, paths.metrics_path)

    try:
        write_training_log(("asset metrics: " + json.dumps({
            "status": metrics["status"],
            "macro_f1": metrics["macro_f1"],
            "accuracy": metrics["accuracy"],
            "alpaca_used": metrics["dataset"]["alpaca_used"],
            "labels": metrics["dataset"]["labels"],
        }))[:2000], source="train_asset_model")
    except Exception:
        pass

    print("\n📊 Asset CV Summary (5-fold):")
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


# ── CLI entry ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        out = train_asset_model()
        print(json.dumps({
            "status": out.get("status"),
            "accuracy": out.get("accuracy"),
            "macro_f1": out.get("macro_f1"),
            "alpaca_used": out.get("dataset", {}).get("alpaca_used"),
        }, indent=2))
    except Exception as e:
        print("❌ Asset training failed:", str(e))
        traceback.print_exc()
        sys.exit(1)
