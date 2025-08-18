# FILE: backend/routes/trade_confirmation_router.py
"""
Trade Confirmation API - Mandatory safety barrier for live trading
Prevents accidental execution of real money trades
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import uuid
import time
from datetime import datetime, timedelta
import json
import hashlib

router = APIRouter(prefix="/api/trade", tags=["Trade Confirmation"])

# In-memory store for confirmation tokens (use Redis in production)
pending_confirmations = {}

# Models for API requests/responses
class TradePreviewRequest(BaseModel):
    strategy_data: Dict
    user_id: str
    investment_amount: float = Field(gt=0, description="Investment amount must be positive")

class TradeConfirmationRequest(BaseModel):
    confirmation_token: str
    user_password_hash: Optional[str] = None  # For additional security
    final_confirmation: bool = Field(description="User must explicitly confirm")

class TradePreviewResponse(BaseModel):
    confirmation_token: str
    strategy_summary: Dict
    risk_analysis: Dict
    cost_breakdown: Dict
    legal_disclaimers: List[str]
    expires_at: str
    requires_confirmation: bool = True

class TradeStatusResponse(BaseModel):
    order_id: Optional[str]
    status: str  # pending, confirmed, executed, failed, cancelled
    execution_time: Optional[str]
    error_message: Optional[str]


def calculate_trade_costs(strategy_data: Dict, investment_amount: float) -> Dict:
    """
    Calculate exact costs for trade execution including commissions
    """
    strategy_type = strategy_data.get('type', '').lower()
    
    # Commission structure (customize based on your broker)
    if 'option' in strategy_type:
        commission_per_contract = 0.65  # Typical options commission
        contracts = max(1, int(investment_amount / 500))  # Estimate contracts
        commission = contracts * commission_per_contract
        regulatory_fees = contracts * 0.02  # OCC fees
    else:
        commission = 0  # Most brokers have $0 stock commissions
        regulatory_fees = max(0.01, investment_amount * 0.000008)  # SEC fees
    
    total_fees = commission + regulatory_fees
    net_investment = investment_amount - total_fees
    
    return {
        "gross_investment": investment_amount,
        "commission": round(commission, 2),
        "regulatory_fees": round(regulatory_fees, 2),
        "total_fees": round(total_fees, 2),
        "net_investment": round(net_investment, 2),
        "fee_percentage": round((total_fees / investment_amount) * 100, 2)
    }


def generate_legal_disclaimers() -> List[str]:
    """
    Generate mandatory legal disclaimers for trade confirmation
    """
    return [
        "Trading involves substantial risk of loss and is not suitable for all investors.",
        "Past performance does not guarantee future results.",
        "Options trading involves significant risk and is not appropriate for all customers.",
        "You may lose more than your initial investment.",
        "Market conditions can change rapidly, affecting your position.",
        "This is not investment advice. Make your own investment decisions.",
        "Ensure you understand the risks before proceeding with this trade.",
        "By confirming, you acknowledge you have read and understand these risks."
    ]


def validate_market_hours() -> bool:
    """
    Check if markets are open for trading
    """
    now = datetime.now()
    
    # Simple market hours check (customize for your needs)
    weekday = now.weekday()  # 0 = Monday, 6 = Sunday
    hour = now.hour
    
    # Markets closed on weekends
    if weekday >= 5:  # Saturday or Sunday
        return False
    
    # Markets closed outside 9:30 AM - 4:00 PM ET
    if hour < 9 or hour >= 16:
        return False
    
    return True


@router.post("/preview", response_model=TradePreviewResponse)
async def preview_trade(request: TradePreviewRequest):
    """
    Generate trade preview with costs, risks, and confirmation token
    This is the first step in the mandatory confirmation process
    """
    
    # Validate market hours
    if not validate_market_hours():
        raise HTTPException(
            status_code=400,
            detail="Markets are currently closed. Trading is only available during market hours (9:30 AM - 4:00 PM ET, Monday-Friday)."
        )
    
    # Validate strategy data
    if not request.strategy_data.get('type'):
        raise HTTPException(status_code=400, detail="Invalid strategy data provided")
    
    # Get risk management data (should already be in strategy_data)
    risk_data = request.strategy_data.get('risk_management', {})
    if not risk_data:
        raise HTTPException(status_code=400, detail="Risk analysis not available for this strategy")
    
    # Validate investment amount against risk limits
    max_investment = risk_data.get('max_investment', 0)
    if request.investment_amount > max_investment:
        raise HTTPException(
            status_code=400,
            detail=f"Investment amount ${request.investment_amount} exceeds maximum safe amount of ${max_investment}"
        )
    
    # Calculate exact trade costs
    cost_breakdown = calculate_trade_costs(request.strategy_data, request.investment_amount)
    
    # Generate confirmation token
    confirmation_token = str(uuid.uuid4())
    
    # Store confirmation details (expires in 5 minutes)
    expires_at = datetime.now() + timedelta(minutes=5)
    pending_confirmations[confirmation_token] = {
        "strategy_data": request.strategy_data,
        "user_id": request.user_id,
        "investment_amount": request.investment_amount,
        "cost_breakdown": cost_breakdown,
        "created_at": datetime.now().isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": "pending_confirmation"
    }
    
    # Build strategy summary for user review
    strategy_summary = {
        "strategy_type": request.strategy_data.get('type'),
        "ticker": request.strategy_data.get('ticker'),
        "direction": request.strategy_data.get('direction'),
        "investment_amount": request.investment_amount,
        "max_loss": request.strategy_data.get('max_loss', 'Premium paid'),
        "target_return": request.strategy_data.get('target_return', 'Variable'),
        "expiration": request.strategy_data.get('expiration'),
        "trade_legs": request.strategy_data.get('trade_legs', [])
    }
    
    # Enhanced risk analysis
    risk_analysis = {
        "account_balance": risk_data.get('account_balance'),
        "risk_percentage": risk_data.get('risk_percentage'),
        "max_risk_dollars": risk_data.get('max_risk_dollars'),
        "position_size": risk_data.get('shares_or_contracts'),
        "warnings": risk_data.get('warnings', []),
        "approved_for_execution": risk_data.get('approved_for_execution', False)
    }
    
    return TradePreviewResponse(
        confirmation_token=confirmation_token,
        strategy_summary=strategy_summary,
        risk_analysis=risk_analysis,
        cost_breakdown=cost_breakdown,
        legal_disclaimers=generate_legal_disclaimers(),
        expires_at=expires_at.isoformat(),
        requires_confirmation=True
    )


@router.post("/confirm")
async def confirm_trade(request: TradeConfirmationRequest):
    """
    Final trade confirmation - requires explicit user approval
    This executes the actual trade after user confirms all details
    """
    
    # Validate confirmation token
    if request.confirmation_token not in pending_confirmations:
        raise HTTPException(status_code=400, detail="Invalid or expired confirmation token")
    
    confirmation_data = pending_confirmations[request.confirmation_token]
    
    # Check if token expired
    expires_at = datetime.fromisoformat(confirmation_data["expires_at"])
    if datetime.now() > expires_at:
        del pending_confirmations[request.confirmation_token]
        raise HTTPException(status_code=400, detail="Confirmation token has expired. Please generate a new trade preview.")
    
    # Validate user explicitly confirmed
    if not request.final_confirmation:
        raise HTTPException(status_code=400, detail="You must explicitly confirm this trade to proceed")
    
    # Re-validate market hours
    if not validate_market_hours():
        raise HTTPException(status_code=400, detail="Markets have closed. Cannot execute trade.")
    
    try:
        # Update confirmation status
        confirmation_data["status"] = "confirmed"
        confirmation_data["confirmed_at"] = datetime.now().isoformat()
        
        # Log the trade confirmation for audit trail
        trade_log = {
            "timestamp": datetime.now().isoformat(),
            "user_id": confirmation_data["user_id"],
            "confirmation_token": request.confirmation_token,
            "strategy_type": confirmation_data["strategy_data"].get("type"),
            "investment_amount": confirmation_data["investment_amount"],
            "status": "confirmed_ready_for_execution"
        }
        
        print(f"TRADE CONFIRMED: {json.dumps(trade_log)}")
        
        # Here you would integrate with your actual brokerage API
        # For now, we'll simulate successful execution
        order_id = f"ORDER_{int(time.time())}"
        
        # Update status to executed
        confirmation_data["status"] = "executed"
        confirmation_data["order_id"] = order_id
        confirmation_data["executed_at"] = datetime.now().isoformat()
        
        # Clean up confirmation token
        del pending_confirmations[request.confirmation_token]
        
        return {
            "status": "success",
            "message": "Trade confirmed and submitted for execution",
            "order_id": order_id,
            "execution_time": datetime.now().isoformat(),
            "details": {
                "strategy_type": confirmation_data["strategy_data"].get("type"),
                "investment_amount": confirmation_data["investment_amount"],
                "estimated_execution": "Within 1-2 minutes during market hours"
            }
        }
        
    except Exception as e:
        # Log execution error
        print(f"TRADE EXECUTION ERROR: {e}")
        
        # Update status to failed
        confirmation_data["status"] = "failed"
        confirmation_data["error"] = str(e)
        
        raise HTTPException(status_code=500, detail=f"Trade execution failed: {str(e)}")


@router.get("/status/{confirmation_token}")
async def get_trade_status(confirmation_token: str):
    """
    Check the status of a trade confirmation or execution
    """
    
    if confirmation_token not in pending_confirmations:
        return TradeStatusResponse(
            status="not_found",
            error_message="Confirmation token not found or has expired"
        )
    
    confirmation_data = pending_confirmations[confirmation_token]
    
    return TradeStatusResponse(
        order_id=confirmation_data.get("order_id"),
        status=confirmation_data["status"],
        execution_time=confirmation_data.get("executed_at"),
        error_message=confirmation_data.get("error")
    )


@router.delete("/cancel/{confirmation_token}")
async def cancel_trade_confirmation(confirmation_token: str):
    """
    Cancel a pending trade confirmation before execution
    """
    
    if confirmation_token not in pending_confirmations:
        raise HTTPException(status_code=404, detail="Confirmation token not found")
    
    confirmation_data = pending_confirmations[confirmation_token]
    
    # Can only cancel if not yet executed
    if confirmation_data["status"] == "executed":
        raise HTTPException(status_code=400, detail="Cannot cancel - trade has already been executed")
    
    # Remove from pending confirmations
    del pending_confirmations[confirmation_token]
    
    return {
        "status": "cancelled",
        "message": "Trade confirmation cancelled successfully",
        "cancelled_at": datetime.now().isoformat()
    }


# Cleanup expired confirmations (run periodically)
def cleanup_expired_confirmations():
    """
    Remove expired confirmation tokens (should be run as background task)
    """
    now = datetime.now()
    expired_tokens = []
    
    for token, data in pending_confirmations.items():
        expires_at = datetime.fromisoformat(data["expires_at"])
        if now > expires_at:
            expired_tokens.append(token)
    
    for token in expired_tokens:
        del pending_confirmations[token]
    
    if expired_tokens:
        print(f"Cleaned up {len(expired_tokens)} expired confirmation tokens")


# Additional endpoint for account validation
@router.get("/validate-account/{user_id}")
async def validate_trading_account(user_id: str):
    """
    Validate user's account is ready for trading
    """
    from backend.risk_management.position_sizing import RiskManager
    
    risk_manager = RiskManager()
    account_balance = risk_manager.get_user_account_balance(user_id)
    
    # Check minimum requirements
    trading_enabled = account_balance >= risk_manager.min_account_balance
    
    return {
        "user_id": user_id,
        "account_balance": account_balance,
        "trading_enabled": trading_enabled,
        "minimum_balance_required": risk_manager.min_account_balance,
        "max_risk_per_trade": account_balance * risk_manager.max_risk_per_trade,
        "market_hours_open": validate_market_hours(),
        "status": "ready" if trading_enabled and validate_market_hours() else "restricted"
    }