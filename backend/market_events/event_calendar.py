# FILE: backend/market_events/event_calendar.py
"""
Market Events Calendar - Track upcoming market-moving events
Generates trading strategies based on scheduled economic releases
"""

import requests
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

class EventType(Enum):
    EARNINGS = "earnings"
    ECONOMIC_DATA = "economic_data"
    FED_MEETING = "fed_meeting"
    CORPORATE_ACTION = "corporate_action"
    SECTOR_EVENT = "sector_event"

class EventImpact(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class MarketEvent:
    """Represents a single market event"""
    event_id: str
    title: str
    company_ticker: Optional[str]
    event_type: EventType
    scheduled_time: datetime
    impact_level: EventImpact
    description: str
    historical_volatility: Optional[float] = None
    consensus_estimate: Optional[str] = None
    previous_result: Optional[str] = None

class EventCalendarAPI:
    """
    Aggregates market events from multiple sources
    """
    
    def __init__(self):
        # In production, use actual API keys
        self.alpha_vantage_key = "demo"  # Replace with actual key
        self.finnhub_key = "demo"       # Replace with actual key
        
    def get_upcoming_earnings(self, days_ahead: int = 14) -> List[MarketEvent]:
        """
        Get upcoming earnings announcements
        """
        events = []
        
        # Mock earnings data - replace with actual API calls
        mock_earnings = [
   {
       "ticker": "AAPL",
       "company": "Apple Inc.",
       "date": "2025-08-22",
       "time": "after_market",
       "estimate_eps": "2.35",
       "estimate_revenue": "123.5B"
   },
   {
       "ticker": "MSFT", 
       "company": "Microsoft Corp.",
       "date": "2025-08-26",
       "time": "after_market",
       "estimate_eps": "3.12",
       "estimate_revenue": "68.2B"
   },
   {
       "ticker": "GOOGL",
       "company": "Alphabet Inc.",
       "date": "2025-08-30",
       "time": "after_market",
       "estimate_eps": "1.85",
       "estimate_revenue": "88.1B"
   }
]

        
        for earning in mock_earnings:
            event_date = datetime.strptime(earning["date"], "%Y-%m-%d")
            if event_date <= datetime.now() + timedelta(days=days_ahead):
                events.append(MarketEvent(
                    event_id=f"earnings_{earning['ticker']}_{earning['date']}",
                    title=f"{earning['company']} Earnings",
                    company_ticker=earning["ticker"],
                    event_type=EventType.EARNINGS,
                    scheduled_time=event_date,
                    impact_level=EventImpact.HIGH,
                    description=f"Q4 earnings release. EPS estimate: {earning['estimate_eps']}, Revenue estimate: {earning['estimate_revenue']}",
                    consensus_estimate=earning["estimate_eps"]
                ))
        
        return events
    
    def get_economic_calendar(self, days_ahead: int = 14) -> List[MarketEvent]:
        """
        Get upcoming economic data releases
        """
        events = []
        
        # Mock economic events - replace with actual government calendars
        mock_economic_events = [
   {
       "title": "Non-Farm Payrolls",
       "date": "2025-08-23",
       "time": "08:30",
       "impact": "high",
       "description": "Monthly employment report - key indicator of economic health",
       "estimate": "185K jobs added",
       "previous": "227K"
   },
   {
       "title": "Consumer Price Index (CPI)",
       "date": "2025-08-28", 
       "time": "08:30",
       "impact": "high",
       "description": "Monthly inflation data - affects Fed policy decisions",
       "estimate": "2.9% YoY",
       "previous": "3.4%"
   },
   {
       "title": "Federal Reserve Meeting",
       "date": "2025-09-01",
       "time": "14:00",
       "impact": "high", 
       "description": "FOMC interest rate decision and policy statement",
       "estimate": "Rate hold expected",
       "previous": "5.25-5.50%"
   }
]
        
        for event in mock_economic_events:
            event_date = datetime.strptime(f"{event['date']} {event['time']}", "%Y-%m-%d %H:%M")
            if event_date <= datetime.now() + timedelta(days=days_ahead):
                impact = EventImpact.HIGH if event["impact"] == "high" else EventImpact.MEDIUM
                event_type = EventType.FED_MEETING if "Federal Reserve" in event["title"] else EventType.ECONOMIC_DATA
                
                events.append(MarketEvent(
                    event_id=f"econ_{event['title'].lower().replace(' ', '_')}_{event['date']}",
                    title=event["title"],
                    company_ticker=None,
                    event_type=event_type,
                    scheduled_time=event_date,
                    impact_level=impact,
                    description=event["description"],
                    consensus_estimate=event["estimate"],
                    previous_result=event["previous"]
                ))
        
        return events
    
    def get_all_upcoming_events(self, days_ahead: int = 14) -> List[MarketEvent]:
        """
        Get all upcoming market events sorted by date
        """
        all_events = []
        all_events.extend(self.get_upcoming_earnings(days_ahead))
        all_events.extend(self.get_economic_calendar(days_ahead))
        
        # Sort by scheduled time
        all_events.sort(key=lambda x: x.scheduled_time)
        
        return all_events