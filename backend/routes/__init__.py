# backend/routes/__init__.py

from fastapi import APIRouter
from backend.routes.strategy_router import router as strategy_router
from backend.routes.feedback_predictor import router as feedback_router
from backend.routes.auth_routes import router as auth_router
from backend.routes.portfolio_router import router as portfolio_router  # ✅ New import

router = APIRouter()

# Include all route modules
router.include_router(strategy_router)
router.include_router(feedback_router)
router.include_router(auth_router)
router.include_router(portfolio_router)  # ✅ Add this
