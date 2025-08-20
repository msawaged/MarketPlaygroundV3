# FILE: backend/risk_management/position_sizing.py
"""
Production Risk Management System for Live Trading
Prevents users from risking more than they can afford
"""

import json
from typing import Dict, Optional, Tuple
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)

class RiskManager:
    """
    Production-grade risk management for live trading
    """
    
    def __init__(self):
        self.max_risk_per_trade = 0.02  # 2% of account balance
        self.max_portfolio_risk = 0.20  # 20% total portfolio risk
        self.min_account_balance = 500   # Minimum $500 to trade
        
    def calculate_position_size(self, 
                              account_balance: float, 
                              strategy_data: dict,
                              risk_percentage: float = None) -> Dict:
        """
        Calculate safe position size based on account balance and strategy risk
        
        Args:
            account_balance: User's available cash balance
            strategy_data: Strategy details including max loss
            risk_percentage: Custom risk % (default uses class setting)
            
        Returns:
            Dict with position sizing recommendations
        """
        
        if risk_percentage is None:
            risk_percentage = self.max_risk_per_trade
            
        # Calculate maximum dollars to risk
        max_risk_dollars = account_balance * risk_percentage
        
        # Extract strategy risk information
        strategy_type = strategy_data.get('type', '').lower()
        max_loss = self._parse_max_loss(strategy_data.get('max_loss', ''))
        
        # Calculate position size based on strategy type
        if 'option' in strategy_type:
            position_size = self._calculate_options_position_size(
                max_risk_dollars, max_loss, strategy_data
            )
        elif any(x in strategy_type for x in ['stock', 'equity', 'etf']):
            position_size = self._calculate_equity_position_size(
                max_risk_dollars, strategy_data
            )
        else:
            # Conservative fallback for unknown strategies
            position_size = {
                'max_investment': min(max_risk_dollars, account_balance * 0.01),
                'shares_or_contracts': 1,
                'reasoning': 'Conservative sizing for unknown strategy type'
            }
        
        # Add safety validations
        position_size.update({
            'account_balance': account_balance,
            'max_risk_dollars': max_risk_dollars,
            'risk_percentage': risk_percentage * 100,
            'warnings': self._generate_warnings(account_balance, position_size),
            'approved_for_execution': self._validate_for_execution(
                account_balance, position_size, strategy_data
            )
        })
        
        return position_size
    
    def _parse_max_loss(self, max_loss_str: str) -> float:
        """
        Parse maximum loss from strategy response
        """
        if not max_loss_str:
            return 0
            
        # Handle common formats
        max_loss_lower = max_loss_str.lower()
        
        if 'premium paid' in max_loss_lower or 'premium' in max_loss_lower:
            return 500  # Estimate $500 premium for options
        
        # Try to extract dollar amount
        import re
        dollar_match = re.search(r'\$?(\d+(?:,\d{3})*(?:\.\d{2})?)', max_loss_str)
        if dollar_match:
            return float(dollar_match.group(1).replace(',', ''))
            
        return 1000  # Conservative fallback
    
    def _calculate_options_position_size(self, max_risk_dollars: float, 
                                       max_loss: float, strategy_data: dict) -> Dict:
        """
        Calculate position size for options strategies
        """
        # For options, max loss is typically the premium paid
        estimated_premium_per_contract = max_loss or 500
        
        # Calculate number of contracts
        max_contracts = int(max_risk_dollars / estimated_premium_per_contract)
        max_contracts = max(1, min(max_contracts, 10))  # Limit to 10 contracts max
        
        total_cost = max_contracts * estimated_premium_per_contract
        
        return {
            'max_investment': total_cost,
            'shares_or_contracts': max_contracts,
            'contract_type': 'options',
            'estimated_premium_per_contract': estimated_premium_per_contract,
            'reasoning': f'Limited to {max_contracts} contracts to stay within risk limits'
        }
    
    def _calculate_equity_position_size(self, max_risk_dollars: float, 
                                      strategy_data: dict) -> Dict:
        """
        Calculate position size for stock/ETF strategies
        """
        current_price = float(strategy_data.get('price', 100))
        
        # Assume 10% stop loss for equity positions
        stop_loss_percentage = 0.10
        risk_per_share = current_price * stop_loss_percentage
        
        # Calculate number of shares
        max_shares = int(max_risk_dollars / risk_per_share)
        max_shares = max(1, max_shares)
        
        total_investment = max_shares * current_price
        
        return {
            'max_investment': total_investment,
            'shares_or_contracts': max_shares,
            'contract_type': 'equity',
            'price_per_share': current_price,
            'stop_loss_price': current_price * (1 - stop_loss_percentage),
            'reasoning': f'Position sized for {stop_loss_percentage*100}% stop loss'
        }
    
    def _generate_warnings(self, account_balance: float, position_size: Dict) -> list:
        """
        Generate risk warnings for the user
        """
        warnings = []
        
        if account_balance < self.min_account_balance:
            warnings.append(f"Account balance below recommended minimum of ${self.min_account_balance}")
        
        investment_percentage = (position_size['max_investment'] / account_balance) * 100
        if investment_percentage > 5:
            warnings.append(f"This trade represents {investment_percentage:.1f}% of your account")
        
        if position_size['shares_or_contracts'] == 1:
            warnings.append("Position size limited to minimum due to risk constraints")
            
        return warnings
    
    def _validate_for_execution(self, account_balance: float, 
                              position_size: Dict, strategy_data: dict) -> bool:
        """
        Final validation before allowing trade execution
        """
        # Check minimum balance
        if account_balance < self.min_account_balance:
            return False
        
        # Check if investment exceeds balance
        if position_size['max_investment'] > account_balance:
            return False
        
        # Check maximum risk per trade
        risk_percentage = position_size.get('max_risk_dollars', 0) / account_balance if account_balance > 0 else 0
        if risk_percentage > self.max_risk_per_trade:
            return False
        
        return True
    
    def get_user_account_balance(self, user_id: str) -> float:
        """
        Get user's current account balance from Alpaca
        """
        try:
            from backend.alpaca_client import get_account_info
            account_data = get_account_info()
            
            if account_data:
                buying_power = float(account_data.get('buying_power', 0))
                print(f"Live Alpaca account balance: ${buying_power:,.2f}")
                return buying_power
            else:
                print("Alpaca account fetch failed, using fallback")
                return 10000.0
                
        except Exception as e:
            print(f"Error fetching Alpaca account: {str(e)}")
            return 10000.0
        
        return mock_balances.get(user_id, 1000.0)  # Default $1000 for new users
    
    def log_risk_decision(self, user_id: str, strategy_data: dict, 
                         position_size: Dict, approved: bool):
        """
        Log all risk management decisions for audit trail
        """
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'strategy_type': strategy_data.get('type'),
            'account_balance': position_size.get('account_balance'),
            'max_investment': position_size.get('max_investment'),
            'risk_percentage': position_size.get('risk_percentage'),
            'approved': approved,
            'warnings': position_size.get('warnings', [])
        }
        
        logger.info(f"Risk Decision: {json.dumps(log_entry)}")
        
        # In production, also save to database
        # save_risk_log_to_db(log_entry)


# Integration function for your existing strategy system
def add_risk_management_to_strategy(strategy_response: dict, user_id: str) -> dict:
    """
    Add position sizing and risk management to existing strategy response
    """
    risk_manager = RiskManager()
    
    # Get user account balance
    account_balance = risk_manager.get_user_account_balance(user_id)
    
    # Calculate position sizing
    position_sizing = risk_manager.calculate_position_size(
        account_balance, 
        strategy_response.get('strategy', {})
    )
    
    # Log the decision
    risk_manager.log_risk_decision(
        user_id, 
        strategy_response.get('strategy', {}),
        position_sizing,
        position_sizing['approved_for_execution']
    )
    
    # Add to strategy response
    strategy_response['risk_management'] = position_sizing
    strategy_response['safe_to_execute'] = position_sizing['approved_for_execution']
    
    return strategy_response


# API endpoint integration
def create_risk_management_endpoints():
    """
    Flask/FastAPI endpoints for risk management
    """
    
    # This would be added to your main API file
    example_endpoints = """
    
    @app.post("/api/risk/calculate-position-size")
    async def calculate_position_size(request: Request):
        data = await request.json()
        
        risk_manager = RiskManager()
        account_balance = risk_manager.get_user_account_balance(data['user_id'])
        
        position_size = risk_manager.calculate_position_size(
            account_balance,
            data['strategy_data']
        )
        
        return position_size
    
    @app.get("/api/risk/account-status/{user_id}")
    async def get_account_status(user_id: str):
        risk_manager = RiskManager()
        account_balance = risk_manager.get_user_account_balance(user_id)
        
        return {
            'account_balance': account_balance,
            'max_risk_per_trade': account_balance * risk_manager.max_risk_per_trade,
            'trading_enabled': account_balance >= risk_manager.min_account_balance
        }
    
    """
    
    return example_endpoints