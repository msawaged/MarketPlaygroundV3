# FILE: backend/market_events/event_strategy_generator.py
"""
Generate trading strategies based on upcoming market events
"""

from typing import List, Dict, Optional
from backend.market_events.event_calendar import MarketEvent, EventType, EventImpact
from backend.ai_engine.ai_engine import run_ai_engine

class EventStrategyGenerator:
    """
    Creates trading strategies based on upcoming market events
    """
    
    def __init__(self):
        self.strategy_templates = {
            EventType.EARNINGS: {
                "bullish_expectation": "Expected earnings beat for {ticker} - revenue guidance likely positive",
                "bearish_expectation": "Earnings miss risk for {ticker} - guidance may disappoint", 
                "neutral_volatility": "High volatility expected around {ticker} earnings - range-bound strategy"
            },
            EventType.ECONOMIC_DATA: {
                "positive_data": "Strong {event_name} expected - market optimism likely",
                "negative_data": "Weak {event_name} could pressure markets",
                "mixed_signals": "{event_name} results may create mixed market reaction"
            },
            EventType.FED_MEETING: {
                "hawkish": "Fed likely to signal rate increases - defensive positioning",
                "dovish": "Fed may signal rate cuts - growth stocks could benefit",
                "neutral": "Fed policy uncertainty - volatility strategies appropriate"
            }
        }
    
    def generate_event_strategies(self, event: MarketEvent) -> List[Dict]:
        """
        Generate multiple strategy options for a single event
        """
        strategies = []
        
        if event.event_type == EventType.EARNINGS:
            strategies.extend(self._generate_earnings_strategies(event))
        elif event.event_type == EventType.ECONOMIC_DATA:
            strategies.extend(self._generate_economic_data_strategies(event))
        elif event.event_type == EventType.FED_MEETING:
            strategies.extend(self._generate_fed_meeting_strategies(event))
        
        return strategies
    
    def _generate_earnings_strategies(self, event: MarketEvent) -> List[Dict]:
        """Generate strategies for earnings events"""
        strategies = []
        
        # Bullish earnings expectation
        bullish_belief = f"I think {event.company_ticker} will beat earnings expectations and provide strong guidance"
        try:
            bullish_strategy = run_ai_engine(bullish_belief, "moderate", "event_system")
            if bullish_strategy and bullish_strategy.get('strategy'):
                strategies.append({
                    "scenario": "Earnings Beat",
                    "belief": bullish_belief,
                    "strategy": bullish_strategy,
                    "probability": "35%",
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating bullish earnings strategy: {e}")
        
        # Bearish earnings expectation  
        bearish_belief = f"I expect {event.company_ticker} to miss earnings and lower guidance"
        try:
            bearish_strategy = run_ai_engine(bearish_belief, "moderate", "event_system")
            if bearish_strategy and bearish_strategy.get('strategy'):
                strategies.append({
                    "scenario": "Earnings Miss",
                    "belief": bearish_belief, 
                    "strategy": bearish_strategy,
                    "probability": "25%",
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating bearish earnings strategy: {e}")
        
        # Volatility play
        volatility_belief = f"{event.company_ticker} earnings will create high volatility regardless of direction"
        try:
            vol_strategy = run_ai_engine(volatility_belief, "moderate", "event_system")
            if vol_strategy and vol_strategy.get('strategy'):
                strategies.append({
                    "scenario": "High Volatility",
                    "belief": volatility_belief,
                    "strategy": vol_strategy, 
                    "probability": "40%",
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating volatility strategy: {e}")
        
        return strategies
    
    def _generate_economic_data_strategies(self, event: MarketEvent) -> List[Dict]:
        """Generate strategies for economic data releases"""
        strategies = []
        
        # Positive economic data scenario
        positive_belief = f"The upcoming {event.title} will show strong economic growth"
        try:
            positive_strategy = run_ai_engine(positive_belief, "moderate", "event_system")
            if positive_strategy and positive_strategy.get('strategy'):
                strategies.append({
                    "scenario": "Strong Economic Data", 
                    "belief": positive_belief,
                    "strategy": positive_strategy,
                    "probability": "45%",
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating positive economic strategy: {e}")
        
        # Negative economic data scenario
        negative_belief = f"The {event.title} will disappoint and show economic weakness"
        try:
            negative_strategy = run_ai_engine(negative_belief, "moderate", "event_system")
            if negative_strategy and negative_strategy.get('strategy'):
                strategies.append({
                    "scenario": "Weak Economic Data",
                    "belief": negative_belief,
                    "strategy": negative_strategy, 
                    "probability": "30%",
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating negative economic strategy: {e}")
        
        return strategies
    
    def _generate_fed_meeting_strategies(self, event: MarketEvent) -> List[Dict]:
        """Generate strategies for Federal Reserve meetings"""
        strategies = []
        
        # Hawkish Fed scenario
        hawkish_belief = "The Federal Reserve will signal more aggressive rate increases"
        try:
            hawkish_strategy = run_ai_engine(hawkish_belief, "conservative", "event_system")
            if hawkish_strategy and hawkish_strategy.get('strategy'):
                strategies.append({
                    "scenario": "Hawkish Fed",
                    "belief": hawkish_belief,
                    "strategy": hawkish_strategy,
                    "probability": "30%", 
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating hawkish Fed strategy: {e}")
        
        # Dovish Fed scenario
        dovish_belief = "The Federal Reserve will signal potential rate cuts or pause"
        try:
            dovish_strategy = run_ai_engine(dovish_belief, "moderate", "event_system")
            if dovish_strategy and dovish_strategy.get('strategy'):
                strategies.append({
                    "scenario": "Dovish Fed",
                    "belief": dovish_belief,
                    "strategy": dovish_strategy,
                    "probability": "35%",
                    "event_context": event
                })
        except Exception as e:
            print(f"Error generating dovish Fed strategy: {e}")
        
        return strategies
