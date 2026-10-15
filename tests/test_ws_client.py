"""
Unit and Integration Tests for TradePulse Real-Time WebSocket and REST Poller.

Tests:
- Local WebSocket server simulation and real-time tick streaming
- Reconnection and exponential backoff logic
- Message payload parsing and edge cases
- In-memory cache ring-buffer and persistence (file and SQLite)
- REST poller URL formatting and rate limiting
"""

import asyncio
import json
import os
import tempfile
from typing import Any, Dict

import pytest
import websockets

from src.ingestion.poller import RestMarketPoller
from src.ingestion.ws_client import WebSocketMarketClient
from src.storage.market_storage import MarketStorage
from src.utils.ws_utils import (
    AsyncRateLimiter,
    calculate_backoff,
    format_tick_console,
    normalize_timestamp,
    parse_tick_payload,
)


def test_backoff_calculation() -> None:
    """Verifies exponential progression, ceiling clamping, and jitter factor."""
    base = 1.0
    max_d = 16.0

    assert calculate_backoff(0, base_delay=base, max_delay=max_d, jitter=False) == 1.0
    assert calculate_backoff(1, base_delay=base, max_delay=max_d, jitter=False) == 2.0
    assert calculate_backoff(2, base_delay=base, max_delay=max_d, jitter=False) == 4.0
    assert calculate_backoff(3, base_delay=base, max_delay=max_d, jitter=False) == 8.0
    assert calculate_backoff(4, base_delay=base, max_delay=max_d, jitter=False) == 16.0
    assert calculate_backoff(5, base_delay=base, max_delay=max_d, jitter=False) == 16.0

    for attempt in range(4):
        val = calculate_backoff(attempt, base_delay=base, max_delay=max_d, jitter=True)
        raw_val = min(max_d, base * (2 ** attempt))
        assert 0.5 * raw_val <= val <= 1.0 * raw_val


def test_normalize_timestamp() -> None:
    """Verifies parsing of ISO strings, unix seconds, and milliseconds."""
    ts_sec = 1760000000
    res_sec = normalize_timestamp(ts_sec)
    assert res_sec.endswith("Z")

    ts_ms = 1760000000000
    res_ms = normalize_timestamp(ts_ms)
    assert res_ms.endswith("Z")

    iso_in = "2026-10-15T08:00:00Z"
    assert normalize_timestamp(iso_in) == "2026-10-15T08:00:00Z"

    default_ts = normalize_timestamp(None)
    assert "T" in default_ts and default_ts.endswith("Z")


def test_parse_tick_payload_success() -> None:
    """Verifies parsing of standard and alternative field names."""
    raw_std = {
        "symbol": "RELIANCE",
        "last_price": 2850.50,
        "timestamp": "2026-10-15T08:00:00Z",
        "volume": 12345,
        "change": 1.2,
    }
    parsed = parse_tick_payload(raw_std)
    assert parsed is not None
    assert parsed["symbol"] == "RELIANCE"
    assert parsed["last_price"] == 2850.50
    assert parsed["volume"] == 12345.0
    assert parsed["change"] == 1.2

    raw_alt = {
        "s": "tcs",
        "ltp": "3920.75",
        "vol": "5400",
        "pChange": "-0.45",
    }
    parsed_alt = parse_tick_payload(raw_alt)
    assert parsed_alt is not None
    assert parsed_alt["symbol"] == "TCS"
    assert parsed_alt["last_price"] == 3920.75
    assert parsed_alt["volume"] == 5400.0
    assert parsed_alt["change"] == -0.45


def test_parse_tick_payload_edge_cases() -> None:
    """Verifies edge cases: missing fields, invalid formats, non-dict payloads."""
    assert parse_tick_payload({"last_price": 100.0}) is None
    assert parse_tick_payload({"symbol": "INFY"}) is None
    assert parse_tick_payload("{malformed_json") is None
    assert parse_tick_payload("hello world") is None

    parsed = parse_tick_payload({"symbol": "HDFCBANK", "last_price": 1600.0})
    assert parsed is not None
    assert parsed["symbol"] == "HDFCBANK"
    assert parsed["last_price"] == 1600.0
    assert parsed["volume"] == 0.0
    assert parsed["change"] == 0.0


def test_format_tick_console() -> None:
    """Verifies console string formatting matches expected template."""
    tick = {
        "symbol": "RELIANCE",
        "last_price": 2850.50,
        "timestamp": "2026-10-15T08:00:00Z",
        "volume": 12345.0,
        "change": 1.20,
    }
    rendered = format_tick_console(tick)
    assert "2026-10-15T08:00:00Z" in rendered
    assert "RELIANCE" in rendered
    assert "2850.50" in rendered
    assert "+1.20%" in rendered
    assert "vol: 12345" in rendered


@pytest.mark.asyncio
async def test_storage_in_memory_and_file() -> None:
    """Tests ring-buffer limit enforcement and JSONL file output."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = os.path.join(tmp_dir, "test_ticks.jsonl")
        storage = MarketStorage(
            in_memory_limit=3,
            enable_file=True,
            file_path=file_path,
            enable_sqlite=False,
        )
        await storage.initialize()

        for p in [100.0, 101.0, 102.0, 103.0, 104.0]:
            tick = {
                "symbol": "RELIANCE",
                "last_price": p,
                "timestamp": "2026-10-15T08:00:00Z",
                "volume": 100.0,
                "change": 0.5,
            }
            await storage.store_tick(tick)

        history = storage.get_history("RELIANCE", limit=10)
        assert len(history) == 3
        assert [h["last_price"] for h in history] == [102.0, 103.0, 104.0]

        latest = storage.get_latest("RELIANCE")
        assert latest is not None
        assert latest["last_price"] == 104.0

        assert os.path.exists(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        assert len(lines) == 5
        assert lines[-1]["last_price"] == 104.0

        await storage.close()


@pytest.mark.asyncio
async def test_storage_sqlite() -> None:
    """Tests SQLite database initialization and async insertion."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_market.db")
        storage = MarketStorage(
            in_memory_limit=10,
            enable_file=False,
            enable_sqlite=True,
            sqlite_db_path=db_path,
        )
        await storage.initialize()

        tick = {
            "symbol": "NIFTY50",
            "last_price": 25000.0,
            "timestamp": "2026-10-15T08:00:00Z",
            "volume": 99999.0,
            "change": 0.85,
        }
        await storage.store_tick(tick, source="ws")

        import aiosqlite
        async with aiosqlite.connect(db_path) as db:
            async with db.execute("SELECT symbol, last_price, source FROM market_ticks") as cursor:
                row = await cursor.fetchone()
                assert row is not None
                assert row[0] == "NIFTY50"
                assert row[1] == 25000.0
                assert row[2] == "ws"

        await storage.close()


@pytest.mark.asyncio
async def test_async_rate_limiter() -> None:
    """Verifies AsyncRateLimiter permits requests within bounds."""
    limiter = AsyncRateLimiter(max_requests=5, window_seconds=1.0)
    for _ in range(5):
        await limiter.acquire()
    assert len(limiter._timestamps) == 5


def test_poller_url_formatting() -> None:
    """Tests symbol list replacement in poller URL."""
    poller = RestMarketPoller(
        polling_url="https://api.example.com/quotes?symbols={symbols}",
        symbols=["RELIANCE", "TCS"],
    )
    assert poller.format_request_url() == "https://api.example.com/quotes?symbols=RELIANCE,TCS"

    poller_no_placeholder = RestMarketPoller(
        polling_url="https://api.example.com/quotes",
        symbols=["NIFTY50"],
    )
    assert poller_no_placeholder.format_request_url() == "https://api.example.com/quotes?symbols=NIFTY50"


@pytest.mark.asyncio
async def test_ws_client_mock_server() -> None:
    """
    Spins up a local test WebSocket server, connects the WebSocketMarketClient,
    sends tick frames, and verifies client parses and stores them in MarketStorage.
    """
    received_subscribe_msg = None
    server_running = True

    async def mock_handler(websocket: Any) -> None:
        nonlocal received_subscribe_msg
        try:
            sub_raw = await websocket.recv()
            received_subscribe_msg = json.loads(sub_raw)

            ticks = [
                {
                    "symbol": "RELIANCE",
                    "last_price": 2850.50,
                    "timestamp": "2026-10-15T08:00:00Z",
                    "volume": 12345,
                    "change": 1.2,
                },
                {
                    "symbol": "TCS",
                    "last_price": 3950.00,
                    "timestamp": "2026-10-15T08:00:01Z",
                    "volume": 6789,
                    "change": -0.4,
                },
            ]
            for tick in ticks:
                await websocket.send(json.dumps(tick))
                await asyncio.sleep(0.05)

            while server_running:
                await asyncio.sleep(0.1)
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    server = await websockets.serve(mock_handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    ws_url = f"ws://127.0.0.1:{port}"

    storage = MarketStorage(in_memory_limit=10)
    await storage.initialize()

    ticks_received = []

    async def on_tick(tick: Dict[str, Any]) -> None:
        ticks_received.append(tick)

    client = WebSocketMarketClient(
        url=ws_url,
        symbols=["RELIANCE", "TCS"],
        subscribe_message={"action": "subscribe", "symbols": ["RELIANCE", "TCS"]},
        storage=storage,
        on_tick=on_tick,
        reconnect_max_attempts=2,
    )

    try:
        await client.start()

        for _ in range(30):
            if len(ticks_received) >= 2:
                break
            await asyncio.sleep(0.1)

        assert received_subscribe_msg is not None
        assert received_subscribe_msg.get("action") == "subscribe"
        assert set(received_subscribe_msg.get("symbols", [])) == {"RELIANCE", "TCS"}

        assert len(ticks_received) >= 2
        rel_tick = storage.get_latest("RELIANCE")
        assert rel_tick is not None
        assert rel_tick["last_price"] == 2850.50
        assert rel_tick["volume"] == 12345.0

        tcs_tick = storage.get_latest("TCS")
        assert tcs_tick is not None
        assert tcs_tick["last_price"] == 3950.00

    finally:
        server_running = False
        await client.stop()
        server.close()
        await server.wait_closed()
        await storage.close()


def test_poller_nse_url_formatting() -> None:
    """Verifies RestMarketPoller recognizes NSE India equity market page URL."""
    poller = RestMarketPoller(
        polling_url="https://www.nseindia.com/market-data/live-equity-market?symbol=NIFTY%2050",
        symbols=["RELIANCE"],
    )
    assert poller._is_nse is True
    assert "marketWatchApi" in poller.format_request_url()
    assert "getIndicesData" in poller.format_request_url()
    assert "symbol=NIFTY%2050" in poller.format_request_url()


@pytest.mark.asyncio
async def test_poller_nse_payload_processing() -> None:
    """Verifies that nested NSE India JSON payload is extracted and filtered to RELIANCE only."""
    storage = MarketStorage(in_memory_limit=10)
    await storage.initialize()

    poller = RestMarketPoller(
        polling_url="https://www.nseindia.com/market-data/live-equity-market?symbol=NIFTY%2050",
        symbols=["RELIANCE"],
        storage=storage,
    )

    sample_nse_payload = {
        "data": {
            "aduCount": {"declines": 11, "advances": 39, "unchange": 0},
            "data": [
                {
                    "symbol": "NIFTY 50",
                    "lastPrice": 22939.95,
                    "pChange": 1.4,
                    "totalTradedVolume": 357864014,
                    "lastUpdateTime": "2026-10-15 15:27:04",
                },
                {
                    "symbol": "RELIANCE",
                    "lastPrice": 1205.20,
                    "pChange": 2.61,
                    "totalTradedVolume": 22194109,
                    "lastUpdateTime": "2026-10-15 15:26:45",
                },
                {
                    "symbol": "TCS",
                    "lastPrice": 3920.00,
                    "pChange": -0.5,
                    "totalTradedVolume": 1000000,
                    "lastUpdateTime": "2026-10-15 15:26:45",
                },
            ],
        }
    }

    await poller._process_poll_payload(sample_nse_payload)

    # RELIANCE should be stored
    rel_tick = storage.get_latest("RELIANCE")
    assert rel_tick is not None
    assert rel_tick["symbol"] == "RELIANCE"
    assert rel_tick["last_price"] == 1205.20
    assert rel_tick["volume"] == 22194109.0
    assert rel_tick["change"] == 2.61

    # TCS and NIFTY 50 should be filtered out
    assert storage.get_latest("TCS") is None
    assert storage.get_latest("NIFTY 50") is None

    await storage.close()

