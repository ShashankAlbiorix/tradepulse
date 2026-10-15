"""
Mock Real-Time WebSocket Market Server for TradePulse.

Spins up a local WebSocket server simulating live financial exchange ticks
with realistic random-walk price fluctuations, volume progression, and
subscription protocol handling.
"""

import asyncio
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import websockets

logger = logging.getLogger("mock_ws_server")

# Realistic live market prices from TradePulse NSE terminal screenshot
BASELINE_PRICES: Dict[str, float] = {
    # Top Gainers & Actives from Terminal
    "TECHM": 1646.30,
    "ICICIBANK": 1384.90,
    "BHARTIARTL": 1847.70,
    "HCLTECH": 1366.00,
    "BSE": 3426.20,
    "RELIANCE": 1205.30,
    "TCS": 2358.00,
    "MARUTI": 11417.00,
    "HDFCBANK": 725.05,
    "M&M": 2849.00,
    "JSWSTEEL": 1199.20,
    "EICHERMOT": 7217.50,
    "INFY": 1107.90,
    "KOTAKBANK": 445.90,
    "AXISBANK": 1287.00,
    "INDIGO": 4791.50,
    "HDFCLIFE": 551.70,
    "ETERNAL": 319.90,
    "BAJFINANCE": 968.60,
    "HINDALCO": 892.45,
    "SBILIFE": 1666.00,
    "TMPV": 286.10,
    "BAJAJ-AUTO": 10329.00,
    "SUNPHARMA": 1759.70,
    "MAXHEALTH": 858.55,
    "APOLLOHOSP": 7878.00,
    "ITC": 263.20,
    "TATASTEEL": 175.63,
    "BAJAJFINSV": 1732.20,
    "CIPLA": 1322.40,
    "NIFTY50": 25120.50,
}

# Previous close values calculated to align with terminal percentage changes
PREV_CLOSE_PRICES: Dict[str, float] = {
    "TECHM": 1575.25,        # +4.51%
    "ICICIBANK": 1338.60,     # +3.46%
    "BHARTIARTL": 1794.55,    # +2.96%
    "HCLTECH": 1326.98,      # +2.94%
    "BSE": 3338.07,          # +2.64%
    "RELIANCE": 1174.64,     # +2.61%
    "TCS": 2304.99,          # +2.30%
    "MARUTI": 11177.80,      # +2.14%
    "HDFCBANK": 710.69,      # +2.02%
    "M&M": 2793.68,          # +1.98%
    "JSWSTEEL": 1176.15,     # +1.96%
    "EICHERMOT": 7082.23,    # +1.91%
    "INFY": 1088.00,         # +1.83%
    "KOTAKBANK": 438.06,     # +1.79%
    "AXISBANK": 1264.62,     # +1.77%
    "INDIGO": 4718.37,       # +1.55%
    "HDFCLIFE": 544.03,      # +1.41%
    "ETERNAL": 316.01,       # +1.23%
    "BAJFINANCE": 957.02,    # +1.21%
    "HINDALCO": 882.48,      # +1.13%
    "SBILIFE": 1649.99,      # +0.97%
    "TMPV": 283.80,          # +0.81%
    "BAJAJ-AUTO": 10249.97,  # +0.77%
    "SUNPHARMA": 1746.43,    # +0.76%
    "MAXHEALTH": 852.49,     # +0.71%
    "APOLLOHOSP": 7823.99,   # +0.69%
    "ITC": 261.50,           # +0.65%
    "TATASTEEL": 174.49,     # +0.65%
    "BAJAJFINSV": 1721.70,   # +0.61%
    "CIPLA": 1314.64,        # +0.59%
    "NIFTY50": 25050.00,
}


class MockWebSocketServer:
    """
    Simulates a broker/exchange real-time WebSocket tick stream.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.server: Optional[Any] = None
        self._running = False
        self._current_prices: Dict[str, float] = dict(BASELINE_PRICES)
        self._cumulative_volumes: Dict[str, int] = {k: random.randint(5000, 50000) for k in BASELINE_PRICES}
        self.clients: Set[Any] = set()

    async def start(self) -> str:
        """Starts the local mock WebSocket server."""
        self._running = True
        self.server = await websockets.serve(self._handle_client, self.host, self.port)
        # In case port was 0 (ephemeral), retrieve actual assigned port
        actual_port = self.server.sockets[0].getsockname()[1]
        self.port = actual_port
        url = f"ws://{self.host}:{self.port}"
        logger.info("Mock WebSocket Market Server running on %s", url)
        return url

    async def stop(self) -> None:
        """Halts the server and closes all active client connections."""
        self._running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        logger.info("Mock WebSocket Market Server stopped.")

    async def _handle_client(self, websocket: Any) -> None:
        """Handles an individual client connection session."""
        self.clients.add(websocket)
        logger.info("New client connected from %s", websocket.remote_address)
        subscribed_symbols: List[str] = list(BASELINE_PRICES.keys())

        try:
            # 1. Listen for initial subscription message
            try:
                raw_init = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                init_payload = json.loads(raw_init)
                if isinstance(init_payload, dict):
                    req_symbols = init_payload.get("symbols")
                    if isinstance(req_symbols, list) and req_symbols:
                        subscribed_symbols = [str(s).upper() for s in req_symbols]
                        logger.info("Client subscribed to: %s", subscribed_symbols)
                        # Acknowledge subscription
                        await websocket.send(json.dumps({
                            "type": "ack",
                            "action": "subscribe",
                            "symbols": subscribed_symbols,
                            "status": "success",
                        }))
            except asyncio.TimeoutError:
                logger.info("No subscribe payload received in 5s. Defaulting to all baseline symbols.")
            except Exception as exc:
                logger.debug("Non-fatal subscribe parse issue: %s", exc)

            # Ensure all subscribed symbols have a baseline price
            for s in subscribed_symbols:
                if s not in self._current_prices:
                    self._current_prices[s] = 1000.00
                    self._cumulative_volumes[s] = 1000

            # 2. Continuous real-time tick streaming loop
            while self._running:
                # Pick a symbol to update
                symbol = random.choice(subscribed_symbols)

                # Random walk: -0.25% to +0.25% step
                pct_step = random.uniform(-0.0025, 0.0026)
                old_price = self._current_prices[symbol]
                new_price = round(old_price * (1.0 + pct_step), 2)
                self._current_prices[symbol] = new_price

                base_price = PREV_CLOSE_PRICES.get(symbol, BASELINE_PRICES.get(symbol, old_price))
                net_change_pct = round(((new_price - base_price) / base_price) * 100.0, 2)

                vol_delta = random.randint(10, 500)
                self._cumulative_volumes[symbol] += vol_delta

                now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                tick_payload = {
                    "symbol": symbol,
                    "last_price": new_price,
                    "timestamp": now_iso,
                    "volume": self._cumulative_volumes[symbol],
                    "change": net_change_pct,
                }

                await websocket.send(json.dumps(tick_payload))

                # Broadcast interval: between 250ms and 750ms
                await asyncio.sleep(random.uniform(0.25, 0.75))

        except (websockets.ConnectionClosed, asyncio.CancelledError):
            logger.info("Client disconnected: %s", getattr(websocket, "remote_address", "client"))
        finally:
            self.clients.discard(websocket)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    server = MockWebSocketServer("127.0.0.1", 8765)
    url = await server.start()
    print(f"\n[+] Mock WebSocket Server started at {url}")
    print("[+] Emitting simulated real-time ticks for RELIANCE, TCS, HDFCBANK, INFY, NIFTY50")
    print("[+] Press Ctrl+C to terminate server.\n")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await server.stop()
        print("\n[+] Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())
