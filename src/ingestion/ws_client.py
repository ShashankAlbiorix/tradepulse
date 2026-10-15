"""
Asynchronous WebSocket Market Data Client for TradePulse.

Connects to real-time market data providers, performs authentication, sends dynamic
subscription payloads, ingests incoming tick streams with ping/pong keepalive, and
executes resilient reconnection with exponential backoff and jitter.

COMPLIANCE NOTICE:
Ensure your usage conforms to your market data provider's Terms of Service (ToS)
and API usage limits. Use authorized, licensed feeds for production trading systems.
"""

import asyncio
import inspect
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from src.storage.market_storage import MarketStorage
from src.utils.ws_utils import calculate_backoff, parse_tick_payload

logger = logging.getLogger(__name__)

TickCallback = Callable[[Dict[str, Any]], Awaitable[None]]
StatusCallback = Callable[[str], Awaitable[None]]


class WebSocketMarketClient:
    """
    Robust Asynchronous WebSocket Market Stream Client.
    """

    def __init__(
        self,
        url: str,
        symbols: List[str],
        subscribe_message: Optional[Union[str, Dict[str, Any]]] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        storage: Optional[MarketStorage] = None,
        reconnect_max_attempts: int = 10,
        reconnect_base_delay: float = 1.0,
        reconnect_max_delay: float = 30.0,
        ping_interval: float = 20.0,
        ping_timeout: float = 10.0,
        on_tick: Optional[TickCallback] = None,
        on_status: Optional[StatusCallback] = None,
    ):
        self.url = url
        self.symbols = [s.strip().upper() for s in symbols if s.strip()]
        self.subscribe_template = subscribe_message or {"action": "subscribe", "symbols": self.symbols}
        self.api_key = api_key
        self.api_key_header = api_key_header
        self.storage = storage
        self.reconnect_max_attempts = max(1, reconnect_max_attempts)
        self.reconnect_base_delay = reconnect_base_delay
        self.reconnect_max_delay = reconnect_max_delay
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.on_tick = on_tick
        self.on_status = on_status

        self._running = False
        self._current_ws: Optional[websockets.WebSocketClientProtocol] = None
        self._task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0

    def build_subscribe_message(self) -> str:
        """Constructs the subscription payload string with active symbols."""
        if isinstance(self.subscribe_template, dict):
            payload = dict(self.subscribe_template)
            if "symbols" in payload:
                payload["symbols"] = self.symbols
            return json.dumps(payload)
        elif isinstance(self.subscribe_template, str):
            if "{symbols}" in self.subscribe_template:
                symbols_json = json.dumps(self.symbols)
                return self.subscribe_template.replace('"{symbols}"', symbols_json).replace("{symbols}", symbols_json)
            return self.subscribe_template
        return json.dumps({"action": "subscribe", "symbols": self.symbols})

    def _get_connect_kwargs(self) -> Dict[str, Any]:
        """Constructs connect kwargs compatible with multiple websockets versions."""
        kwargs: Dict[str, Any] = {
            "ping_interval": self.ping_interval,
            "ping_timeout": self.ping_timeout,
            "close_timeout": 5.0,
        }

        # Build headers if authentication key is supplied
        headers: Dict[str, str] = {}
        if self.api_key:
            headers[self.api_key_header] = self.api_key
            headers["Authorization"] = f"Bearer {self.api_key}"

        if headers:
            try:
                sig = inspect.signature(websockets.connect)
                if "additional_headers" in sig.parameters:
                    kwargs["additional_headers"] = headers
                else:
                    kwargs["extra_headers"] = headers
            except Exception:
                kwargs["additional_headers"] = headers

        return kwargs

    async def start(self) -> None:
        """Starts the WebSocket client connection supervisor task."""
        if self._running:
            logger.warning("WebSocketMarketClient is already running.")
            return

        self._running = True
        self._task = asyncio.create_task(self._supervise_connection(), name="ws-market-client-supervisor")
        logger.info("WebSocketMarketClient supervisor started.")

    async def stop(self) -> None:
        """Gracefully disconnects and stops the client supervisor."""
        if not self._running:
            return

        logger.info("Stopping WebSocketMarketClient...")
        self._running = False

        if self._current_ws is not None:
            try:
                await self._current_ws.close()
            except Exception as exc:
                logger.debug("Error while closing current websocket: %s", exc)
            self._current_ws = None

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        await self._set_status("DISCONNECTED")
        logger.info("WebSocketMarketClient successfully stopped.")

    async def _supervise_connection(self) -> None:
        """Main supervisor loop with exponential backoff and jitter."""
        while self._running:
            try:
                await self._set_status("CONNECTING")
                logger.info("Connecting to WebSocket feed: %s", self.url)

                connect_kwargs = self._get_connect_kwargs()
                async with websockets.connect(self.url, **connect_kwargs) as ws:
                    self._current_ws = ws
                    self._reconnect_attempts = 0
                    await self._set_status("CONNECTED")
                    logger.info("WebSocket connection established successfully.")

                    # Send subscription payload
                    sub_msg = self.build_subscribe_message()
                    logger.info("Transmitting subscription payload: %s", sub_msg)
                    await ws.send(sub_msg)

                    # Message processing loop
                    await self._message_reader(ws)

            except ConnectionClosed as c_err:
                logger.warning("WebSocket connection closed (code=%s, reason=%s)", c_err.code, c_err.reason)
            except WebSocketException as ws_err:
                logger.error("WebSocket protocol error: %s", ws_err)
            except OSError as os_err:
                # Catches socket.gaierror (Errno 11001) and ConnectionRefusedError
                if "example-data-provider" in self.url:
                    logger.warning(
                        "Cannot resolve '%s' (placeholder URL). "
                        "To test with live market ticks, run with '--mock' or update config/realtime_config.yaml",
                        self.url,
                    )
                else:
                    logger.warning("Network connection failed for '%s': %s", self.url, os_err)
            except asyncio.CancelledError:
                logger.debug("Supervisor received cancellation.")
                break
            except Exception as exc:
                logger.error("Unexpected WebSocket error: %s", exc, exc_info=True)
            finally:
                self._current_ws = None

            if not self._running:
                break

            self._reconnect_attempts += 1
            if self._reconnect_attempts > self.reconnect_max_attempts:
                logger.critical(
                    "Exceeded maximum reconnect attempts (%d). Aborting connection supervisor.",
                    self.reconnect_max_attempts,
                )
                await self._set_status("FAILED")
                self._running = False
                break

            delay = calculate_backoff(
                attempt=self._reconnect_attempts - 1,
                base_delay=self.reconnect_base_delay,
                max_delay=self.reconnect_max_delay,
                jitter=True,
            )
            await self._set_status("RECONNECTING")
            logger.info(
                "Scheduling reconnect attempt %d/%d in %.2f seconds...",
                self._reconnect_attempts,
                self.reconnect_max_attempts,
                delay,
            )
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break

    async def _message_reader(self, ws: Any) -> None:
        """Reads and routes incoming messages from the active WebSocket connection."""
        async for raw_message in ws:
            if not self._running:
                break

            try:
                await self._handle_message(raw_message)
            except Exception as exc:
                logger.error("Error processing incoming message: %s", exc, exc_info=True)

    async def _handle_message(self, raw_message: Union[str, bytes]) -> None:
        """Decodes raw frames and dispatches standardized tick updates."""
        try:
            payload = json.loads(raw_message)
        except Exception:
            logger.debug("Received non-JSON frame: %r", raw_message[:100] if len(raw_message) > 100 else raw_message)
            return

        # Case 1: Batch ticks list e.g. [{"symbol": "A", ...}, {"symbol": "B", ...}]
        if isinstance(payload, list):
            for item in payload:
                await self._process_single_tick(item)
            return

        # Case 2: Wrapped data payload e.g. {"data": [...]} or {"data": {...}}
        if isinstance(payload, dict):
            # Check for heartbeat or ack messages
            msg_type = str(payload.get("type", "")).lower()
            if msg_type in ("ping", "pong", "heartbeat", "ack", "subscription"):
                logger.debug("Received control message: %s", msg_type)
                return

            if "data" in payload:
                sub_data = payload["data"]
                if isinstance(sub_data, list):
                    for item in sub_data:
                        await self._process_single_tick(item)
                    return
                elif isinstance(sub_data, dict):
                    await self._process_single_tick(sub_data)
                    return

            # Case 3: Flat tick object
            await self._process_single_tick(payload)

    async def _process_single_tick(self, data: Any) -> None:
        """Parses and dispatches a single market tick update."""
        tick = parse_tick_payload(data)
        if not tick:
            return

        # Symbol filter match (if symbols list is non-empty)
        if self.symbols and tick["symbol"] not in self.symbols:
            return

        # Persist to storage engine
        if self.storage:
            await self.storage.store_tick(tick, source="ws")

        # Invoke callback hook if configured
        if self.on_tick:
            try:
                res = self.on_tick(tick)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as cb_err:
                logger.error("Error in on_tick callback: %s", cb_err)

    async def _set_status(self, status: str) -> None:
        """Emits connection status transitions."""
        logger.debug("WebSocket Status Changed: %s", status)
        if self.on_status:
            try:
                await self.on_status(status)
            except Exception as err:
                logger.error("Error in on_status callback: %s", err)
