# backend/ai_engine/expiry_utils.py

"""
Maps parsed timeframe strings (like 'next week', 'in 3 months') to real expiry dates.
"""

from datetime import datetime, timedelta
import re
import calendar

def get_next_friday(start_date: datetime = None) -> datetime:
    """
    Returns the next Friday from today or a given start_date.
    """
    if not start_date:
        start_date = datetime.today()
    days_ahead = (4 - start_date.weekday() + 7) % 7
    return start_date + timedelta(days=days_ahead or 7)

def parse_timeframe_to_expiry(timeframe: str) -> str:
    """
    Converts a natural language timeframe string to a real expiry date in 'YYYY-MM-DD' format.

    Args:
        timeframe (str): e.g. "next week", "in 3 months", "by next friday"

    Returns:
        str: date string suitable for options expiry (e.g. "2024-07-05")
    """
    today = datetime.today()

    # Common timeframes
    if "next week" in timeframe:
        return get_next_friday(today + timedelta(weeks=1)).strftime("%Y-%m-%d")
    if "this week" in timeframe:
        return get_next_friday(today).strftime("%Y-%m-%d")
    if "next month" in timeframe:
        next_month = (today.month % 12) + 1
        year = today.year + (today.month // 12)
        return get_next_friday(datetime(year, next_month, 1)).strftime("%Y-%m-%d")

    # e.g. "in 2 weeks", "in 3 months"
    match = re.search(r"in\s+(\d+)\s+(day|week|month|year)s?", timeframe)
    if match:
        num = int(match.group(1))
        unit = match.group(2)

        if unit == "day":
            target = today + timedelta(days=num)
        elif unit == "week":
            target = today + timedelta(weeks=num)
        elif unit == "month":
            month = today.month - 1 + num
            year = today.year + month // 12
            month = month % 12 + 1
            day = min(today.day, calendar.monthrange(year, month)[1])
            target = datetime(year, month, day)
        elif unit == "year":
            target = datetime(today.year + num, today.month, today.day)

        return get_next_friday(target).strftime("%Y-%m-%d")

    # Fallback to next Friday
    return get_next_friday().strftime("%Y-%m-%d")
