"""
Market Data Storage Engine for TradePulse.

Provides multi-tiered persistence:
1. Low-latency in-memory ring-buffer per symbol for instant lookup.
2. Optional appending JSON-Lines (JSONL) file storage.
3. Optional asynchronous SQLite database persistence with indexed queries.
"""

import asyncio
import json
import logging
import os
from collections import deque
from typing import Any, Dict, List, Optional

try:
    import aiosqlite
except ImportError:
    aiosqlite = None

logger = logging.getLogger(__name__)


class MarketStorage:
    """
    Manages in-memory caching and optional file/SQLite persistence for tick updates.
    """

    def __init__(
        self,
        in_memory_limit: int = 100,
        enable_file: bool = False,
        file_path: Optional[str] = "data/ticks.jsonl",
        enable_sqlite: bool = False,
        sqlite_db_path: Optional[str] = "data/market_data.db",
    ):
        self.in_memory_limit = max(1, in_memory_limit)
        self.enable_file = enable_file
        self.file_path = file_path
        self.enable_sqlite = enable_sqlite and (aiosqlite is not None)
        self.sqlite_db_path = sqlite_db_path

        # In-memory storage: symbol -> deque of last N updates
        self._cache: Dict[str, deque[Dict[str, Any]]] = {}
        self._latest: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._db_conn: Optional[Any] = None

    async def initialize(self) -> None:
        """Initializes destination folders and SQLite database schema if enabled."""
        if self.enable_file and self.file_path:
            file_dir = os.path.dirname(os.path.abspath(self.file_path))
            os.makedirs(file_dir, exist_ok=True)
            logger.info("JSONL file storage enabled at: %s", self.file_path)

        if self.enable_sqlite and self.sqlite_db_path:
            db_dir = os.path.dirname(os.path.abspath(self.sqlite_db_path))
            os.makedirs(db_dir, exist_ok=True)
            self._db_conn = await aiosqlite.connect(self.sqlite_db_path)
            await self._db_conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_ticks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    last_price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    volume REAL DEFAULT 0.0,
                    change REAL DEFAULT 0.0,
                    source TEXT DEFAULT 'ws',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await self._db_conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ticks_sym_time 
                ON market_ticks(symbol, timestamp);
                """
            )
            await self._db_conn.commit()
            logger.info("SQLite persistence initialized at: %s", self.sqlite_db_path)

    async def store_tick(self, tick: Dict[str, Any], source: str = "ws") -> None:
        """
        Stores a standardized tick into in-memory ring-buffer and secondary stores.

        :param tick: Standardized tick dictionary.
        :param source: Origin identifier ('ws' or 'poll').
        """
        symbol = tick["symbol"]
        record = {**tick, "source": source}

        async with self._lock:
            # 1. Update in-memory ring-buffer
            if symbol not in self._cache:
                self._cache[symbol] = deque(maxlen=self.in_memory_limit)
            self._cache[symbol].append(record)
            self._latest[symbol] = record

        # 2. Append to JSONL file if enabled
        if self.enable_file and self.file_path:
            await self._append_file(record)

        # 3. Insert to SQLite if enabled
        if self.enable_sqlite and self._db_conn:
            await self._insert_sqlite(record)

    async def _append_file(self, record: Dict[str, Any]) -> None:
        """Appends a single JSON line to the target file in a thread pool."""
        try:
            line = json.dumps(record) + "\n"
            await asyncio.to_thread(self._sync_write, self.file_path, line)
        except Exception as exc:
            logger.error("Failed writing tick to file %s: %s", self.file_path, exc)

    @staticmethod
    def _sync_write(path: str, content: str) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)

    async def _insert_sqlite(self, record: Dict[str, Any]) -> None:
        """Inserts record asynchronously into SQLite database."""
        try:
            await self._db_conn.execute(
                """
                INSERT INTO market_ticks (symbol, last_price, timestamp, volume, change, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record["symbol"],
                    record["last_price"],
                    record["timestamp"],
                    record.get("volume", 0.0),
                    record.get("change", 0.0),
                    record.get("source", "ws"),
                ),
            )
            await self._db_conn.commit()
        except Exception as exc:
            logger.error("Failed inserting tick into SQLite: %s", exc)

    def get_latest(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Retrieves most recent tick for a given symbol."""
        return self._latest.get(symbol.upper())

    def get_all_latest(self) -> Dict[str, Dict[str, Any]]:
        """Retrieves latest tick snapshot for all cached symbols."""
        return dict(self._latest)

    def get_history(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the recent updates for a given symbol from the ring-buffer."""
        sym = symbol.upper()
        if sym in self._cache:
            items = list(self._cache[sym])
            return items[-limit:]
        return []

    async def close(self) -> None:
        """Closes any persistent database connections."""
        if self._db_conn:
            try:
                await self._db_conn.close()
                logger.debug("Closed SQLite storage connection.")
            except Exception as exc:
                logger.error("Error closing SQLite connection: %s", exc)
            self._db_conn = None
