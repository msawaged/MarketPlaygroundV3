# FILE: backend/routes/market_events_router.py
"""
Market Events API - Upcoming events and auto-generated strategies
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from backend.market_events.event_calendar import EventCalendarAPI, MarketEvent
from backend.market_events.event_strategy_generator import EventStrategyGenerator

router = APIRouter(prefix="/api/market-events", tags=["Market Events"])

# Initialize services
event_calendar = EventCalendarAPI()
strategy_generator = EventStrategyGenerator()

@router.get("/upcoming")
async def get_upcoming_events(days_ahead: int = 14):
    """
    Get upcoming market events for the next N days
    """
    try:
        events = event_calendar.get_all_upcoming_events(days_ahead)
        
        # Convert to JSON-serializable format
        events_data = []
        for event in events:
            events_data.append({
                "event_id": event.event_id,
                "title": event.title,
                "company_ticker": event.company_ticker,
                "event_type": event.event_type.value,
                "scheduled_time": event.scheduled_time.isoformat(),
                "impact_level": event.impact_level.value,
                "description": event.description,
                "consensus_estimate": event.consensus_estimate,
                "previous_result": event.previous_result,
                "days_until": (event.scheduled_time - datetime.now()).days,
                "hours_until": (event.scheduled_time - datetime.now()).total_seconds() / 3600
            })
        
        return {
            "events": events_data,
            "total_events": len(events_data),
            "date_range": f"{datetime.now().date()} to {(datetime.now() + timedelta(days=days_ahead)).date()}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching events: {str(e)}")

@router.get("/strategies/{event_id}")
async def get_event_strategies(event_id: str):
    """
    Get AI-generated strategies for a specific event
    """
    try:
        # Get all events and find the requested one
        all_events = event_calendar.get_all_upcoming_events(30)
        target_event = None
        
        for event in all_events:
            if event.event_id == event_id:
                target_event = event
                break
        
        if not target_event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Generate strategies for this event
        strategies = strategy_generator.generate_event_strategies(target_event)
        
        return {
            "event": {
                "event_id": target_event.event_id,
                "title": target_event.title,
                "scheduled_time": target_event.scheduled_time.isoformat(),
                "description": target_event.description
            },
            "strategies": strategies,
            "total_strategies": len(strategies),
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating strategies: {str(e)}")

@router.get("/today")
async def get_todays_events():
    """
    Get events happening today
    """
    try:
        all_events = event_calendar.get_all_upcoming_events(1)
        today = datetime.now().date()
        
        todays_events = [
            event for event in all_events 
            if event.scheduled_time.date() == today
        ]
        
        events_data = []
        for event in todays_events:
            events_data.append({
                "event_id": event.event_id,
                "title": event.title,
                "company_ticker": event.company_ticker,
                "scheduled_time": event.scheduled_time.isoformat(),
                "impact_level": event.impact_level.value,
                "description": event.description,
                "time_until": (event.scheduled_time - datetime.now()).total_seconds() / 3600
            })
        
        return {
            "events": events_data,
            "total_events": len(events_data),
            "date": today.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching today's events: {str(e)}")

@router.get("/earnings")
async def get_upcoming_earnings(days_ahead: int = 7):
    """
    Get upcoming earnings announcements only
    """
    try:
        earnings_events = event_calendar.get_upcoming_earnings(days_ahead)
        
        earnings_data = []
        for event in earnings_events:
            earnings_data.append({
                "event_id": event.event_id,
                "title": event.title,
                "company_ticker": event.company_ticker,
                "scheduled_time": event.scheduled_time.isoformat(),
                "consensus_estimate": event.consensus_estimate,
                "description": event.description,
                "days_until": (event.scheduled_time - datetime.now()).days
            })
        
        return {
            "earnings": earnings_data,
            "total_earnings": len(earnings_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching earnings: {str(e)}")

@router.get("/economic-calendar") 
async def get_economic_calendar(days_ahead: int = 14):
    """
    Get upcoming economic data releases
    """
    try:
        economic_events = event_calendar.get_economic_calendar(days_ahead)
        
        economic_data = []
        for event in economic_events:
            economic_data.append({
                "event_id": event.event_id,
                "title": event.title,
                "scheduled_time": event.scheduled_time.isoformat(),
                "impact_level": event.impact_level.value,
                "description": event.description,
                "consensus_estimate": event.consensus_estimate,
                "previous_result": event.previous_result,
                "days_until": (event.scheduled_time - datetime.now()).days
            })
        
        return {
            "economic_events": economic_data,
            "total_events": len(economic_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching economic calendar: {str(e)}")