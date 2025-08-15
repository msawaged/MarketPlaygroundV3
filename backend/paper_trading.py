# backend/paper_trading.py
class PaperTradingEngine:
    def __init__(self):
        pass
    
    def execute_paper_trade(self, user_id, strategy_data, belief):
        return {"status": "success", "message": "Paper trade executed"}
    
    def get_portfolio(self, user_id):
        return {"user_id": user_id, "cash": 100000, "positions": {}}
    
    def get_leaderboard(self):
        return {"leaderboard": []}

# Create the instance your router expects
paper_engine = PaperTradingEngine()
