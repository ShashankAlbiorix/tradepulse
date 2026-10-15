"""
TradePulse Real-Time Stock & Index Streaming Runner.

Executes WebSocket streaming client or REST polling fallback directly within
the TradePulse application environment.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from typing import Any, Dict, List, Optional

import yaml

# Ensure project root is on Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.ingestion.poller import RestMarketPoller
from src.ingestion.ws_client import WebSocketMarketClient
from src.storage.market_storage import MarketStorage
from src.utils.logger import get_logger
from src.utils.ws_utils import format_tick_console

logger = get_logger("realtime_market_runner")


def load_yaml_config(config_path: str) -> Dict[str, Any]:
    """Loads and returns dictionary configuration from YAML file."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parses CLI arguments."""
    parser = argparse.ArgumentParser(
        description="TradePulse Real-Time Stock & Index Streaming Client",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/realtime_config.yaml",
        help="Path to YAML configuration file.",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated list of symbols to override config (e.g., RELIANCE,TCS,NIFTY50).",
    )
    parser.add_argument(
        "--mode",
        choices=["ws", "poll", "both"],
        default=None,
        help="Execution mode (ws: WebSocket only, poll: REST polling only, both: parallel).",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Override WebSocket endpoint URL directly from CLI.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run built-in mock market WebSocket server to stream realistic simulated ticks for development.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose DEBUG logging.",
    )
    return parser.parse_args(argv)


async def async_main(args: argparse.Namespace) -> None:
    """Main asynchronous runner."""
    # 1. Load YAML configuration
    try:
        config = load_yaml_config(args.config)
    except Exception as exc:
        print(f"[ERROR] Failed to load configuration from {args.config}: {exc}", file=sys.stderr)
        sys.exit(1)

    # Configure root logger so all components log with consistent formatting
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
    if not args.debug:
        # Suppress websockets keepalive chatter
        logging.getLogger("websockets").setLevel(logging.WARNING)

    logger.info("Starting TradePulse Real-Time Streaming Client...")

    # 2. Resolve Target Symbols
    symbols = config.get("symbols", ["RELIANCE", "TCS", "HDFCBANK", "INFY", "NIFTY50"])
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    logger.info("Active Target Symbols: %s", symbols)

    # 3. Storage Setup
    output_modes = config.get("output", ["console"])
    enable_console = "console" in output_modes
    enable_file = "file" in output_modes
    enable_sqlite = "sqlite" in output_modes

    storage_cfg = config.get("storage", {})
    in_memory_limit = storage_cfg.get("in_memory_limit", 100)
    file_path = storage_cfg.get("file_path", "data/ticks.jsonl")
    sqlite_path = storage_cfg.get("sqlite_db_path", "data/market_data.db")

    storage = MarketStorage(
        in_memory_limit=in_memory_limit,
        enable_file=enable_file,
        file_path=file_path,
        enable_sqlite=enable_sqlite,
        sqlite_db_path=sqlite_path,
    )
    await storage.initialize()

    # 4. Tick Output Handler
    async def on_tick_received(tick: Dict[str, Any]) -> None:
        if enable_console:
            print(format_tick_console(tick), flush=True)

    # 5. Initialize Ingestion Clients
    ws_client: Optional[WebSocketMarketClient] = None
    poller: Optional[RestMarketPoller] = None

    mode = args.mode or config.get("mode", "ws")
    logger.info("Active Ingestion Mode: %s", mode.upper())

    api_key = config.get("api_key") or os.getenv("MARKET_API_KEY", "")
    api_key_header = config.get("api_key_header", "X-API-Key")

    if mode in ("poll", "both"):
        polling_url = config.get("polling_url", "https://example-data-provider/api/quotes?symbols={symbols}")
        poll_interval = float(config.get("poll_interval_seconds", 5.0))
        rate_limit = int(config.get("poll_rate_limit_per_minute", 60))
        poller = RestMarketPoller(
            polling_url=polling_url,
            symbols=symbols,
            poll_interval_seconds=poll_interval,
            api_key=api_key if api_key else None,
            api_key_header=api_key_header,
            storage=storage,
            rate_limit_per_minute=rate_limit,
            on_tick=on_tick_received,
        )

    mock_server = None
    if mode in ("ws", "both"):
        ws_url = args.url or config.get("websocket_url", "wss://example-data-provider/realtime")
        
        # If user explicitly requested --mock, or URL is still the default placeholder
        if args.mock or ("example-data-provider" in ws_url and not args.url):
            from src.ingestion.mock_ws_server import MockWebSocketServer
            mock_server = MockWebSocketServer(host="127.0.0.1", port=0)
            ws_url = await mock_server.start()
            logger.info("Auto-started local Mock WebSocket Server at: %s", ws_url)
            print("\n" + "=" * 75)
            print("  [LIVE] TRADEPULSE REAL-TIME MARKET STREAM (DEVELOPMENT SIMULATION)")
            print(f"  Feed URL   : {ws_url}")
            print(f"  Monitoring : {', '.join(symbols)}")
            print("  Persistence: In-Memory Ring Buffer + data/ticks.jsonl + data/market_data.db")
            print("  [Tip] To connect to a live broker, edit 'websocket_url' in config/realtime_config.yaml")
            print("=" * 75 + "\n")

        sub_msg = config.get("subscribe_message")
        reconnect_max = int(config.get("reconnect_max_attempts", 10))
        base_delay = float(config.get("reconnect_base_delay_seconds", 1.0))
        max_delay = float(config.get("reconnect_max_delay_seconds", 30.0))
        ping_interval = float(config.get("ping_interval_seconds", 20.0))
        ping_timeout = float(config.get("ping_timeout_seconds", 10.0))

        ws_client = WebSocketMarketClient(
            url=ws_url,
            symbols=symbols,
            subscribe_message=sub_msg,
            api_key=api_key if api_key else None,
            api_key_header=api_key_header,
            storage=storage,
            reconnect_max_attempts=reconnect_max,
            reconnect_base_delay=base_delay,
            reconnect_max_delay=max_delay,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            on_tick=on_tick_received,
        )

    # 6. Signal Handling
    stop_event = asyncio.Event()

    def handle_exit_signal() -> None:
        logger.info("Shutdown signal received. Teardown initiated...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, handle_exit_signal)

    # 7. Start Services
    if poller:
        await poller.start()
    if ws_client:
        await ws_client.start()

    logger.info("TradePulse Real-Time Ingestion running. Press Ctrl+C to terminate.")

    try:
        if sys.platform == "win32":
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        else:
            await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Keyboard interrupt received.")
    finally:
        logger.info("Shutting down TradePulse Real-Time Ingestion...")
        if ws_client:
            await ws_client.stop()
        if poller:
            await poller.stop()
        if mock_server:
            await mock_server.stop()
        await storage.close()
        logger.info("Teardown complete.")


def main() -> None:
    args = parse_arguments()
    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
