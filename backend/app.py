# backend/app.py
"""
MarketPlayground API — FastAPI entrypoint.

Belief -> strategy goes through backend/engine_switch.py:
  ENGINE_VERSION=v4 (default) uses the Claude-powered v4 engine (backend/v4),
  ENGINE_VERSION=legacy uses the original GPT-4 + ML engine (needs OPENAI_API_KEY).
"""
import os
import traceback
from collections import Counter
from datetime import datetime
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

load_dotenv()

from backend.engine_switch import engine_version
from backend.rate_limit import CostlyEndpointRateLimit
from backend.feedback_handler import save_feedback_entry
from backend.user_models import init_db

from backend.routes.alpaca_probe_router import ROUTER as alpaca_probe_router
from backend.routes.alpaca_router import router as alpaca_router
from backend.routes.analytics_router import router as analytics_router
from backend.routes.auth_router import router as auth_router
from backend.routes.basket_router import router as basket_router
from backend.routes.debug_router import router as debug_router
from backend.routes.execution_router import router as execution_router
from backend.routes.feedback_predictor import router as feedback_predictor
from backend.routes.feedback_router import router as feedback_router
from backend.routes.hot_trades_router import router as hot_trades_router
from backend.routes.ibkr_router import router as ibkr_router
from backend.routes.market_events_router import router as market_events_router
from backend.routes.market_router import router as market_router
from backend.routes.market_ticker_router import ROUTER as market_ticker_router
from backend.routes.news_router import router as news_router
from backend.routes.paper_trading_router import router as paper_trading_router
from backend.routes.pnl_router import router as pnl_router
from backend.routes.portfolio_router import router as portfolio_router
from backend.routes.strategy_logger_router import router as strategy_logger_router
from backend.routes.strategy_router import router as strategy_router
from backend.routes.trade_confirmation_router import router as trade_confirmation_router
from backend.v4.router import router as v4_router

app = FastAPI(title="MarketPlayground API")


@app.on_event("startup")
def _start_notify() -> None:
    from backend.v4 import notify, feeder, lineages
    notify.start_background()
    feeder.start_background()
    lineages.bootstrap_background()

# === CORS ===
# Local dev servers, the GitHub Pages landing page, any Render-hosted frontend,
# plus anything listed in ALLOWED_ORIGINS (comma-separated).
_origins = [
    "http://localhost:3000", "http://localhost:3001", "http://localhost:5173",
    "http://127.0.0.1:3000", "http://127.0.0.1:5173",
    "https://msawaged.github.io",
] + [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://[a-z0-9-]+\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(CostlyEndpointRateLimit)

init_db()

# Legacy analytics read this CSV; create a header-only file if missing.
strategy_csv_path = os.path.join("backend", "strategy_outcomes.csv")
if not os.path.exists(strategy_csv_path):
    pd.DataFrame(columns=["timestamp", "belief", "strategy", "ticker", "pnl_percent", "result", "risk", "notes"]).to_csv(
        strategy_csv_path, index=False
    )

from backend.security import admin_only  # noqa: E402

_ADMIN = [Depends(admin_only)]

# === Routers ===
app.include_router(auth_router,              prefix="/auth",              tags=["Auth"], dependencies=_ADMIN)
app.include_router(feedback_router,          prefix="/feedback",          tags=["Feedback"], dependencies=_ADMIN)
app.include_router(feedback_predictor,       prefix="/predict",           tags=["Predictor"], dependencies=_ADMIN)
app.include_router(portfolio_router,         prefix="/portfolio",         tags=["Portfolio"], dependencies=_ADMIN)
app.include_router(strategy_router,          prefix="/strategy",          tags=["Strategy"])
app.include_router(strategy_logger_router,   prefix="/strategy",          tags=["Strategy Logger"], dependencies=_ADMIN)
app.include_router(news_router,              prefix="/news",              tags=["News"], dependencies=_ADMIN)
app.include_router(hot_trades_router,                                     tags=["Hot Trades"], dependencies=_ADMIN)
app.include_router(basket_router,            prefix="/basket",            tags=["Asset Baskets"])
app.include_router(alpaca_router,            prefix="/alpaca",            tags=["Alpaca"], dependencies=_ADMIN)
app.include_router(execution_router,         prefix="/alpaca",            tags=["Execution"], dependencies=_ADMIN)
app.include_router(pnl_router,               prefix="/pnl",               tags=["PnL"], dependencies=_ADMIN)
app.include_router(market_router,            prefix="/market",            tags=["Market"], dependencies=_ADMIN)
app.include_router(analytics_router,         prefix="/analytics",         tags=["Analytics"], dependencies=_ADMIN)
app.include_router(debug_router,             prefix="/debug",             tags=["Debug"], dependencies=_ADMIN)
app.include_router(ibkr_router,              prefix="/ibkr",              tags=["IBKR"], dependencies=_ADMIN)
app.include_router(paper_trading_router,     prefix="/api/paper-trading", tags=["Paper Trading"])
app.include_router(trade_confirmation_router,                             tags=["Trade Confirmation"], dependencies=_ADMIN)
app.include_router(market_events_router, dependencies=_ADMIN)
app.include_router(alpaca_probe_router, dependencies=_ADMIN)
app.include_router(market_ticker_router)
app.include_router(v4_router,                prefix="/v4",                tags=["v4 Belief Engine"])


def _require_admin(token: Optional[str]) -> None:
    expected = os.getenv("MP_ADMIN_TOKEN")
    if not expected or token != expected:
        raise HTTPException(status_code=403, detail="admin token required (X-Admin-Token)")


class FeedbackRequest(BaseModel):
    belief: str
    strategy: str
    feedback: str


@app.get("/")
def read_root():
    return {"message": "Welcome to the MarketPlayground API", "engine": engine_version()}


@app.get("/health")
def health():
    """What's configured (true/false only, never the values)."""
    return {
        "status": "ok",
        "engine": engine_version(),
        "anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "alpaca_keys": bool(os.getenv("ALPACA_API_KEY") and os.getenv("ALPACA_SECRET_KEY")),
        "database": "postgres" if os.getenv("DATABASE_URL", "").startswith(("postgres://", "postgresql://")) else "sqlite",
        "openai_key": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.post("/submit_feedback", dependencies=_ADMIN)
def submit_feedback(request: FeedbackRequest):
    try:
        save_feedback_entry(request.belief, request.strategy, request.feedback)
        return {"message": "Feedback saved"}
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to save feedback")


@app.post("/force_retrain", response_class=PlainTextResponse)
@app.post("/retrain", response_class=PlainTextResponse)
def retrain_legacy_models(x_admin_token: Optional[str] = Header(None)):
    """Retrain the legacy ML models (legacy engine only). Admin only: it is CPU-heavy."""
    _require_admin(x_admin_token)
    try:
        from backend.train_all_models import train_all_models

        train_all_models()
        return "Legacy model retraining completed."
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Retrain failed: {e}")


@app.get("/analytics/strategy_distribution", dependencies=_ADMIN)
def strategy_distribution(asset_class: Optional[str] = Query(None), belief_contains: Optional[str] = Query(None)):
    try:
        df = pd.read_csv(strategy_csv_path, on_bad_lines="skip", engine="python")
        if asset_class:
            df = df[df["strategy"].str.contains(asset_class, case=False, na=False)]
        if belief_contains:
            df = df[df["belief"].str.contains(belief_contains, case=False, na=False)]
        return dict(Counter(df["strategy"]))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading strategy data: {e}")


@app.get("/analytics/trending_strategies", dependencies=_ADMIN)
def trending_strategies(limit: int = 5):
    try:
        df = pd.read_csv(strategy_csv_path, on_bad_lines="skip", engine="python")
        return {"top_strategies": df["strategy"].value_counts().head(limit).to_dict()}
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to load trending strategies")


@app.get("/analytics/top_tags", dependencies=_ADMIN)
def top_tags(limit: int = 10):
    try:
        df = pd.read_csv(strategy_csv_path, on_bad_lines="skip", engine="python")
        if "tags" not in df.columns:
            return {"top_tags": {}}
        all_tags = [t.strip() for tags in df["tags"].dropna().str.split(",") for t in tags]
        return {"top_tags": dict(Counter(all_tags).most_common(limit))}
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to compute top tags")


@app.get("/logs/recent", dependencies=_ADMIN)
def fetch_recent_logs(limit: int = 10):
    """Most recent entries from backend/logs/last_training_log.txt as {timestamp, message}."""
    log_path = os.path.join("backend", "logs", "last_training_log.txt")
    if not os.path.exists(log_path):
        return {"logs": []}
    try:
        with open(log_path, "r") as f:
            chunks = [c.strip() for c in f.read().strip().split("🕒") if c.strip()]
        out = []
        for chunk in chunks[-limit:]:
            lines = chunk.splitlines()
            if lines:
                out.append({"timestamp": lines[0].strip(), "message": "\n".join(lines[1:]).strip()})
        return {"logs": out}
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to read logs")


@app.get("/toggle/news_ingestion_status")
def news_ingestion_status():
    return {"paused": os.getenv("PAUSE_NEWS_INGESTION", "false").lower() == "true"}
