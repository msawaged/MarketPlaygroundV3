# backend/routes/paper_trading_router.py
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import time
import logging

from backend.paper_trading import paper_engine

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class TradeRequest(BaseModel):
    user_id: str
    strategy_data: dict
    belief: str

@router.get("/portfolio/{user_id}")
def get_portfolio(user_id: str):
    portfolio = paper_engine.get_portfolio(user_id, force_refresh=True)
    return JSONResponse(
        content=portfolio,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )

@router.post("/execute")
async def execute_paper_trade(request: TradeRequest):
    """Execute a paper trade"""
    try:
        result = paper_engine.execute_paper_trade(
            user_id=request.user_id,
            strategy_data=request.strategy_data,
            belief=request.belief
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Trade execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/close_position")
def close_position(
    user_id: str = Query(...),
    position_id: str = Query(...),
    qty: Optional[int] = Query(None)
):
    """Close a position and return fresh portfolio"""
    try:
        # Close the position
        result = paper_engine.close_position(user_id, position_id, qty)
        
        if result["status"] == "error":
            return JSONResponse(
                content=result,
                status_code=400,
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                    "Pragma": "no-cache",
                    "Expires": "0",
                }
            )
        
        # Poll for position removal
        max_polls = 10
        poll_interval = 0.5  # 500ms
        
        for attempt in range(max_polls):
            portfolio = paper_engine.get_portfolio(user_id, force_refresh=True)
            
            # Check if position is gone
            position_exists = any(
                pos.get('position_id') == position_id 
                for pos in portfolio.get('positions', [])
            )
            
            if not position_exists:
                # Position removed successfully
                return JSONResponse(
                    content={
                        "status": "success",
                        "message": "Position closed successfully",
                        "portfolio": portfolio,
                        **result  # Include realized_pnl, proceeds, commission
                    },
                    status_code=200,
                    headers={
                        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    }
                )
            
            # Wait before next poll
            time.sleep(poll_interval)
        
        # Still syncing after max polls
        portfolio = paper_engine.get_portfolio(user_id, force_refresh=True)
        return JSONResponse(
            content={
                "status": "syncing",
                "message": "Position closed but still syncing",
                "portfolio": portfolio,
                **result
            },
            status_code=202,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
        
    except Exception as e:
        logger.error(f"Close position error: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )

@router.get("/leaderboard")
def get_leaderboard():
    """Get performance leaderboard"""
    try:
        leaderboard = paper_engine.get_leaderboard()
        return JSONResponse(
            content=leaderboard,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            }
        )
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        raise HTTPException(status_code=500, detail=str(e))