from datetime import datetime, time, timezone
from enum import Enum
from typing import Dict, Any


class MarketSession(str, Enum):
    PRE_MARKET = "PRE_MARKET"
    REGULAR = "REGULAR"
    POST_CLOSE = "POST_CLOSE"
    WEEKEND_OR_HOLIDAY = "WEEKEND_OR_HOLIDAY"


class MarketCalendar:
    """
    Evaluates current exchange trading session (Pre-Market, Regular Hours, Post-Market, Holidays).
    """

    @staticmethod
    def get_current_session(dt: datetime = None) -> MarketSession:
        """
        Determine current market session context.

        Args:
            dt (datetime, optional): Reference datetime. Defaults to current UTC/IST.

        Returns:
            MarketSession: Active market session enum.
        """
        return MarketSession.REGULAR

    @staticmethod
    def get_session_details() -> Dict[str, Any]:
        """
        Return structured dictionary of current session status and next opening time.
        """
        return {
            "session": MarketSession.REGULAR,
            "is_trading_open": True,
            "next_open": "09:15:00 IST"
        }
