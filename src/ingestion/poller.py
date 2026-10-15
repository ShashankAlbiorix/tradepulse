"""
REST Polling Fallback Client for TradePulse.

Periodically queries REST market endpoints to fetch stock quotes when WebSocket
is disconnected or as an auxiliary polling stream. Implements rate limiting,
exponential backoff on HTTP errors, and unified tick data ingestion.

COMPLIANCE NOTICE:
Respect API rate limits and data provider Terms of Service. Aggressive polling
without licensing or permission may violate service agreements.
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

import aiohttp

from src.storage.market_storage import MarketStorage
from src.utils.ws_utils import AsyncRateLimiter, calculate_backoff, normalize_timestamp, parse_tick_payload

logger = logging.getLogger(__name__)

TickCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class RestMarketPoller:
    """
    Asynchronous REST Quote Poller with rate limiting and exponential backoff.
    """

    def __init__(
        self,
        polling_url: str,
        symbols: List[str],
        poll_interval_seconds: float = 5.0,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        storage: Optional[MarketStorage] = None,
        rate_limit_per_minute: int = 60,
        on_tick: Optional[TickCallback] = None,
        request_timeout_seconds: float = 10.0,
    ):
        self.polling_url = polling_url
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.poll_interval = max(0.5, poll_interval_seconds)
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.storage = storage
        self.on_tick = on_tick
        self.request_timeout = request_timeout_seconds

        self.rate_limiter = AsyncRateLimiter(
            max_requests=rate_limit_per_minute,
            window_seconds=60.0,
        )

        # Detect NSE India endpoints
        self._is_nse = "nseindia.com" in self.polling_url
        if self._is_nse:
            if "marketWatchApi" in self.polling_url:
                self._nse_api_url = self.polling_url
                self._nse_warmup_url = "https://www.nseindia.com/market-data/live-equity-market?symbol=NIFTY%2050"
            elif "live-equity-market" in self.polling_url:
                self._nse_warmup_url = self.polling_url
                # Extract index symbol if present, default to NIFTY 50
                sym_match = "NIFTY%2050"
                if "symbol=" in self.polling_url:
                    parts = self.polling_url.split("symbol=", 1)
                    sym_match = parts[1].split("&")[0] or "NIFTY%2050"
                self._nse_api_url = f"https://www.nseindia.com/api/NextApi/apiClient/marketWatchApi?functionName=getIndicesData&symbol={sym_match}"
            else:
                self._nse_warmup_url = "https://www.nseindia.com/market-data/live-equity-market?symbol=NIFTY%2050"
                self._nse_api_url = self.polling_url
        else:
            self._nse_api_url = self.polling_url
            self._nse_warmup_url = ""

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._consecutive_errors = 0

    def format_request_url_for_symbol(self, symbol: str) -> str:
        """Formats the URL for a specific individual symbol."""
        sym = symbol.strip().upper()
        url = self.polling_url
        if "{symbol}" in url:
            return url.replace("{symbol}", sym)
        if "{symbols}" in url:
            return url.replace("{symbols}", sym)
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}symbol={sym}"

    def format_request_url(self) -> str:
        """Substitutes symbol list into polling URL template."""
        if self._is_nse:
            return self._nse_api_url
        symbols_str = ",".join(self.symbols)
        if "{symbols}" in self.polling_url:
            return self.polling_url.replace("{symbols}", symbols_str)
        if "{symbol}" in self.polling_url and self.symbols:
            return self.polling_url.replace("{symbol}", self.symbols[0])
        
        # If no placeholder, append as query parameter
        sep = "&" if "?" in self.polling_url else "?"
        return f"{self.polling_url}{sep}symbols={symbols_str}"

    async def _warmup_nse_session(self) -> bool:
        """Warms up cookies on NSE India website to allow API calls."""
        if not self._is_nse or not self._session:
            return True
        try:
            logger.info("Warming up NSE India session at: %s", self._nse_warmup_url)
            warmup_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            async with self._session.get(self._nse_warmup_url, headers=warmup_headers) as resp:
                status = resp.status
                await resp.read()
                logger.info("NSE session warm-up completed with HTTP %d", status)
                return status == 200
        except Exception as exc:
            logger.warning("NSE session warm-up encountered: %s", exc)
            return False

    async def start(self) -> None:
        """Initializes aiohttp session and launches periodic polling loop."""
        if self._running:
            logger.warning("RestMarketPoller is already running.")
            return

        self._running = True
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if self.api_key:
            headers[self.api_key_header] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Use CookieJar for cookie persistence (crucial for NSE India session cookies)
        cookie_jar = aiohttp.CookieJar()
        self._session = aiohttp.ClientSession(timeout=timeout, headers=headers, cookie_jar=cookie_jar)

        if self._is_nse:
            await self._warmup_nse_session()

        self._task = asyncio.create_task(self._poll_loop(), name="rest-market-poller-task")
        logger.info(
            "RestMarketPoller started (interval: %.1fs, symbols: %s, url: %s)",
            self.poll_interval,
            self.symbols,
            self.polling_url,
        )

    async def stop(self) -> None:
        """Halts polling loop and closes HTTP session."""
        if not self._running:
            return

        logger.info("Stopping RestMarketPoller...")
        self._running = False

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

        logger.info("RestMarketPoller successfully stopped.")

    async def _poll_loop(self) -> None:
        """Core periodic polling loop with rate limiting and exponential backoff."""
        while self._running:
            try:
                if self._is_nse:
                    await self.rate_limiter.acquire()
                    headers = {
                        "Referer": self._nse_warmup_url,
                        "X-Requested-With": "XMLHttpRequest",
                        "Accept": "*/*",
                    }
                    logger.debug("Dispatching NSE India poll request: %s", self._nse_api_url)
                    async with self._session.get(self._nse_api_url, headers=headers) as response:
                        if response.status == 200:
                            self._consecutive_errors = 0
                            payload = await response.json(content_type=None)
                            await self._process_poll_payload(payload)
                        elif response.status in (401, 403, 404):
                            self._consecutive_errors += 1
                            logger.warning("NSE returned HTTP %d. Re-warming session...", response.status)
                            await self._warmup_nse_session()
                            backoff = calculate_backoff(self._consecutive_errors, base_delay=2.0, max_delay=30.0)
                            await asyncio.sleep(backoff)
                        elif response.status == 429:
                            self._consecutive_errors += 1
                            backoff = calculate_backoff(self._consecutive_errors, base_delay=3.0, max_delay=60.0)
                            logger.warning("HTTP 429 Rate Limit hit. Backing off for %.2fs", backoff)
                            await asyncio.sleep(backoff)
                        else:
                            self._consecutive_errors += 1
                            logger.warning("HTTP %d received from %s", response.status, self._nse_api_url)
                # If polling template specifies single symbol per request or Yahoo chart endpoint
                elif "{symbol}" in self.polling_url or "yahoo" in self.polling_url:
                    for sym in self.symbols:
                        if not self._running:
                            break
                        await self.rate_limiter.acquire()
                        url = self.format_request_url_for_symbol(sym)
                        logger.debug("Dispatching REST poll request: %s", url)

                        async with self._session.get(url) as response:
                            if response.status == 200:
                                self._consecutive_errors = 0
                                payload = await response.json(content_type=None)
                                await self._process_poll_payload(payload)
                            elif response.status == 429:
                                self._consecutive_errors += 1
                                backoff = calculate_backoff(self._consecutive_errors, base_delay=2.0, max_delay=60.0)
                                logger.warning("HTTP 429 Rate Limit hit. Backing off for %.2fs", backoff)
                                await asyncio.sleep(backoff)
                            else:
                                self._consecutive_errors += 1
                                logger.warning("HTTP %d received from %s", response.status, url)
                else:
                    await self.rate_limiter.acquire()
                    url = self.format_request_url()
                    logger.debug("Dispatching REST poll request: %s", url)

                    async with self._session.get(url) as response:
                        if response.status == 200:
                            self._consecutive_errors = 0
                            payload = await response.json(content_type=None)
                            await self._process_poll_payload(payload)
                        elif response.status == 429:
                            self._consecutive_errors += 1
                            backoff = calculate_backoff(self._consecutive_errors, base_delay=2.0, max_delay=60.0)
                            logger.warning("HTTP 429 Rate Limit hit. Backing off for %.2fs", backoff)
                            await asyncio.sleep(backoff)
                        else:
                            self._consecutive_errors += 1
                            logger.warning("HTTP %d received from %s", response.status, url)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._consecutive_errors += 1
                backoff = calculate_backoff(self._consecutive_errors, base_delay=1.0, max_delay=30.0)
                logger.error("REST poll exception: %s. Backing off for %.2fs", exc, backoff)
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    break

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break

    async def _process_poll_payload(self, payload: Any) -> None:
        """Parses response payload and updates storage."""
        # Handle NSE India NextApi market watch payload
        if isinstance(payload, dict) and "data" in payload:
            data_field = payload["data"]
            if isinstance(data_field, dict) and "data" in data_field and isinstance(data_field["data"], list):
                for item in data_field["data"]:
                    await self._process_single_tick(item)
                return

        # Handle Yahoo Finance live chart payload
        if isinstance(payload, dict) and "chart" in payload:
            result = payload.get("chart", {}).get("result", [])
            if result and isinstance(result, list):
                meta = result[0].get("meta", {})
                raw_sym = meta.get("symbol", "").replace(".NS", "").replace(".BO", "")
                price = meta.get("regularMarketPrice")
                if price is not None:
                    prev_close = meta.get("chartPreviousClose", price)
                    change_pct = round(((price - prev_close) / prev_close) * 100.0, 2) if prev_close else 0.0
                    volume = meta.get("regularMarketVolume", 0.0)
                    ts = meta.get("regularMarketTime")

                    parsed_tick = {
                        "symbol": raw_sym.upper(),
                        "last_price": float(price),
                        "timestamp": normalize_timestamp(ts),
                        "volume": float(volume or 0.0),
                        "change": change_pct,
                    }
                    await self._process_single_tick(parsed_tick)
                    return

        if isinstance(payload, list):
            for item in payload:
                await self._process_single_tick(item)
        elif isinstance(payload, dict):
            if "quotes" in payload and isinstance(payload["quotes"], list):
                for item in payload["quotes"]:
                    await self._process_single_tick(item)
            elif "data" in payload and isinstance(payload["data"], list):
                for item in payload["data"]:
                    await self._process_single_tick(item)
            elif "data" in payload and isinstance(payload["data"], dict):
                await self._process_single_tick(payload["data"])
            else:
                possible_symbol = payload.get("symbol") or payload.get("s")
                if possible_symbol:
                    await self._process_single_tick(payload)
                else:
                    for val in payload.values():
                        if isinstance(val, dict):
                            await self._process_single_tick(val)

    async def _process_single_tick(self, data: Any) -> None:
        """Parses individual quote and routes to storage & callbacks."""
        tick = parse_tick_payload(data)
        if not tick:
            return

        if self.symbols and tick["symbol"] not in self.symbols:
            return

        if self.storage:
            await self.storage.store_tick(tick, source="poll")

        if self.on_tick:
            try:
                res = self.on_tick(tick)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as exc:
                logger.error("Error in poller on_tick callback: %s", exc)
