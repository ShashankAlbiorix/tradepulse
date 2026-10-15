"""
WebSocket and Market Data Utility Helpers for TradePulse.

Provides exponential backoff with randomized jitter, robust tick payload parsing,
timestamp normalization with UTC conversion, console formatting, and rate limiting.
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
) -> float:
    """
    Calculates exponential backoff with randomized jitter.

    Formula: min(max_delay, base_delay * (2 ** attempt)) + jitter

    :param attempt: Current zero-indexed retry attempt number.
    :param base_delay: Starting delay in seconds.
    :param max_delay: Ceiling limit for the delay.
    :param jitter: Whether to apply a randomized uniform jitter (50%-100% factor).
    :return: Delay duration in seconds.
    """
    backoff = min(max_delay, base_delay * (2 ** attempt))
    if jitter:
        # Full jitter between 50% and 100% of computed exponential interval
        backoff = backoff * (0.5 + random.random() * 0.5)
    return max(0.0, backoff)


def normalize_timestamp(raw_ts: Any) -> str:
    """
    Converts various timestamp formats (epoch seconds, milliseconds, ISO strings)
    into a standardized UTC ISO-8601 string (e.g., '2026-10-15T08:00:00Z').

    :param raw_ts: Input timestamp representation.
    :return: Formatted UTC string.
    """
    if raw_ts is None:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # Numeric epoch detection
        if isinstance(raw_ts, (int, float)):
            # Epoch milliseconds threshold (> 1e11 is beyond year 5138 in seconds)
            if raw_ts > 1e11:
                dt = datetime.fromtimestamp(raw_ts / 1000.0, tz=timezone.utc)
            else:
                dt = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        if isinstance(raw_ts, str):
            clean_str = raw_ts.strip()
            # Check if string contains epoch number
            if clean_str.isdigit():
                val = float(clean_str)
                return normalize_timestamp(val)

            # Clean trailing Z for standard ISO parsing
            if clean_str.endswith("Z"):
                clean_str = clean_str[:-1] + "+00:00"
            
            # Support space separator (e.g. '2026-10-15 15:26:45' from NSE India in IST)
            if " " in clean_str and "T" not in clean_str:
                clean_str = clean_str.replace(" ", "T")
                if "+" not in clean_str and "-" not in clean_str[10:]:
                    # Default NSE date to IST (UTC+05:30)
                    clean_str += "+05:30"

            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        if isinstance(raw_ts, datetime):
            if raw_ts.tzinfo is None:
                raw_ts = raw_ts.replace(tzinfo=timezone.utc)
            else:
                raw_ts = raw_ts.astimezone(timezone.utc)
            return raw_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    except Exception as exc:
        logger.debug("Failed parsing timestamp %r (%s). Fallback to current UTC time.", raw_ts, exc)

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_tick_payload(raw_data: Union[str, bytes, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Parses a raw market message into a standardized Tick dictionary.

    Expected standard schema:
        - symbol: str
        - last_price: float
        - timestamp: str (ISO-8601 UTC)
        - volume: float
        - change: float (percentage change)

    Gracefully handles varied key aliases (e.g. 'ltp', 'price', 's', 'p', 'vol').
    Returns None if essential pricing or symbol identifiers cannot be extracted.

    :param raw_data: Raw JSON string, bytes, or parsed dictionary.
    :return: Standardized tick dictionary or None if unparseable.
    """
    if isinstance(raw_data, (str, bytes)):
        try:
            payload = json.loads(raw_data)
        except Exception:
            return None
    elif isinstance(raw_data, dict):
        payload = raw_data
    else:
        return None

    if not isinstance(payload, dict):
        return None

    # Resolve Symbol
    symbol = None
    for sym_key in ("symbol", "sym", "ticker", "instrument", "s", "name"):
        if sym_key in payload and payload[sym_key]:
            symbol = str(payload[sym_key]).strip().upper()
            break

    if not symbol:
        return None

    # Resolve Last Traded Price (LTP)
    last_price = None
    for price_key in ("last_price", "price", "lastPrice", "ltp", "close", "p", "val"):
        if price_key in payload and payload[price_key] is not None:
            try:
                last_price = float(payload[price_key])
                break
            except (ValueError, TypeError):
                continue

    if last_price is None:
        return None

    # Resolve Timestamp
    raw_time = None
    for time_key in ("timestamp", "time", "ts", "t", "datetime", "date", "lastUpdateTime"):
        if time_key in payload and payload[time_key] is not None:
            raw_time = payload[time_key]
            break
    normalized_time = normalize_timestamp(raw_time)

    # Resolve Volume (default to 0.0 if missing)
    volume = 0.0
    for vol_key in ("volume", "vol", "v", "qty", "size", "traded_quantity", "totalTradedVolume"):
        if vol_key in payload and payload[vol_key] is not None:
            try:
                volume = float(payload[vol_key])
                break
            except (ValueError, TypeError):
                pass

    # Resolve Change Percentage (prioritize percentage fields before rupee difference)
    change = 0.0
    for chg_key in ("pChange", "percentChange", "pct_change", "change_pct", "change", "chg", "c"):
        if chg_key in payload and payload[chg_key] is not None:
            try:
                change = float(payload[chg_key])
                break
            except (ValueError, TypeError):
                pass

    return {
        "symbol": symbol,
        "last_price": last_price,
        "timestamp": normalized_time,
        "volume": volume,
        "change": change,
    }


def format_tick_console(tick: Dict[str, Any]) -> str:
    """
    Renders standardized tick data for console output.
    Format: 2026-10-15T08:00:00Z | RELIANCE | 2850.50 | +1.2% | vol: 12345

    :param tick: Parsed tick dictionary.
    :return: String representation.
    """
    ts = tick.get("timestamp", "UNKNOWN_TIME")
    symbol = tick.get("symbol", "N/A")
    price = tick.get("last_price", 0.0)
    change = tick.get("change", 0.0)
    vol = tick.get("volume", 0.0)

    # Format change with explicit sign
    sign = "+" if change > 0 else ""
    change_str = f"{sign}{change:.2f}%"

    # Format volume as integer if whole number
    vol_str = f"{int(vol)}" if vol.is_integer() else f"{vol:.2f}"

    return f"{ts} | {symbol:<10} | {price:>10.2f} | {change_str:>7} | vol: {vol_str}"


class AsyncRateLimiter:
    """
    Asynchronous Sliding Window Rate Limiter.
    Ensures outbound HTTP or poll requests do not exceed the specified quota.
    """

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max(1, max_requests)
        self.window_seconds = window_seconds
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Blocks until a request permit is available within the window."""
        async with self._lock:
            now = time.monotonic()
            cutoff = now - self.window_seconds
            # Evict expired timestamps
            self._timestamps = [t for t in self._timestamps if t > cutoff]

            if len(self._timestamps) >= self.max_requests:
                sleep_duration = self._timestamps[0] + self.window_seconds - now
                if sleep_duration > 0:
                    logger.debug("Rate limit reached. Sleeping for %.2f seconds.", sleep_duration)
                    await asyncio.sleep(sleep_duration)
                now = time.monotonic()
                cutoff = now - self.window_seconds
                self._timestamps = [t for t in self._timestamps if t > cutoff]

            self._timestamps.append(now)
