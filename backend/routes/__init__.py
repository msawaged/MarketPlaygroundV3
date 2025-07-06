# backend/routes/__init__.py
# ✅ Combines all sub-routers into a unified router for FastAPI app

from fastapi import APIRouter

# 🔗 Import individual routers
from backend.routes.strategy_router import router as strategy_router
from backend.routes.feedback_router import router as feedback_router
from backend.routes.auth_router import router as auth_router
from backend.routes.portfolio_router import router as portfolio_router
from backend.routes.strategy_logger_router import router as strategy_logger_router
from backend.routes.hot_trades_router import router as hot_trades_router  # ✅ NEW: Hot trades route

# ✅ Master router object
router = APIRouter()

# ✅ Register all sub-routers with relevant prefixes and tags
router.include_router(strategy_router, prefix="/strategy", tags=["Strategy"])
router.include_router(feedback_router, prefix="/feedback", tags=["Feedback"])
router.include_router(auth_router, prefix="/auth", tags=["Auth"])
router.include_router(portfolio_router, prefix="/portfolio", tags=["Portfolio"])
router.include_router(strategy_logger_router, prefix="/strategy", tags=["Strategy Logger"])
router.include_router(hot_trades_router, tags=["Hot Trades"])  # ✅ NEW: Include hot trades
