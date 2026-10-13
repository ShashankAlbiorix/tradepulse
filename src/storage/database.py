import os
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import duckdb

from config.settings import settings
from src.models.schemas import NewsArticle, SentimentResult, SentimentLabel, ShortTermVerdict, VerdictSignal
from src.utils.logger import logger


class DatabaseManager:
    """
    DuckDB persistence manager handling embedded analytical storage for
    raw news articles, individual sentiment classifications, and synthesized verdicts.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize DuckDB database connection and ensure tables are created.
        """
        self.db_path = db_path or settings.DATABASE_PATH or "data/news_agent.duckdb"
        self._ensure_directory()
        self._conn = duckdb.connect(self.db_path)
        self.init_tables()

    def _ensure_directory(self):
        """Ensure parent directory exists for file-based duckdb storage."""
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

    def init_tables(self):
        """
        Create schema tables for articles, sentiments, and verdicts if not present.
        """
        try:
            # 1. Articles Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    article_id VARCHAR PRIMARY KEY,
                    title VARCHAR,
                    source VARCHAR,
                    url VARCHAR,
                    published_at TIMESTAMP,
                    summary VARCHAR,
                    content VARCHAR,
                    ingested_at TIMESTAMP
                )
            """)

            # 2. Sentiments Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS sentiments (
                    id VARCHAR PRIMARY KEY,
                    article_id VARCHAR,
                    symbol VARCHAR,
                    sentiment VARCHAR,
                    confidence DOUBLE,
                    reasoning VARCHAR,
                    key_catalysts VARCHAR,
                    analyzed_at TIMESTAMP
                )
            """)

            # 3. Verdicts Table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS verdicts (
                    id VARCHAR PRIMARY KEY,
                    symbol VARCHAR,
                    verdict VARCHAR,
                    confidence DOUBLE,
                    bullish_pct DOUBLE,
                    bearish_pct DOUBLE,
                    neutral_pct DOUBLE,
                    timeframe VARCHAR,
                    executive_summary VARCHAR,
                    key_drivers VARCHAR,
                    analyzed_articles_count INTEGER,
                    generated_at TIMESTAMP
                )
            """)
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB tables: {e}")

    def clear_all(self):
        """Truncate and remove all records from articles, sentiments, and verdicts tables."""
        try:
            self._conn.execute("DELETE FROM articles;")
            self._conn.execute("DELETE FROM sentiments;")
            self._conn.execute("DELETE FROM verdicts;")
            logger.info("Successfully cleared all data from DuckDB tables.")
        except Exception as e:
            logger.error(f"Failed to clear DuckDB tables: {e}")

    def save_article(self, article: NewsArticle):
        """Persist or upsert an ingested news article."""
        try:
            self._conn.execute("""
                INSERT OR REPLACE INTO articles VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                article.article_id,
                article.title,
                article.source,
                article.url,
                article.published_at,
                article.summary or "",
                article.content or "",
                article.ingested_at
            ])
        except Exception as e:
            logger.error(f"Failed to save article {article.article_id}: {e}")

    def save_sentiment(self, sentiment: SentimentResult):
        """Persist an individual sentiment analysis record."""
        try:
            record_id = f"sent_{sentiment.article_id}_{sentiment.symbol}"
            catalysts_json = json.dumps(sentiment.key_catalysts)
            self._conn.execute("""
                INSERT OR REPLACE INTO sentiments VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                record_id,
                sentiment.article_id,
                sentiment.symbol.upper(),
                sentiment.sentiment.value,
                sentiment.confidence,
                sentiment.reasoning,
                catalysts_json,
                sentiment.analyzed_at
            ])
        except Exception as e:
            logger.error(f"Failed to save sentiment for {sentiment.symbol}: {e}")

    def save_verdict(self, verdict: ShortTermVerdict):
        """Persist a synthesized short-term verdict record."""
        try:
            record_id = f"verdict_{verdict.symbol}_{int(verdict.generated_at.timestamp())}"
            drivers_json = json.dumps(verdict.key_drivers)
            bullish_pct = verdict.sentiment_distribution.get("BULLISH", 0.0)
            bearish_pct = verdict.sentiment_distribution.get("BEARISH", 0.0)
            neutral_pct = verdict.sentiment_distribution.get("NEUTRAL", 0.0)

            self._conn.execute("""
                INSERT OR REPLACE INTO verdicts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                record_id,
                verdict.symbol.upper(),
                verdict.verdict.value,
                verdict.confidence,
                bullish_pct,
                bearish_pct,
                neutral_pct,
                verdict.timeframe,
                verdict.executive_summary,
                drivers_json,
                verdict.analyzed_articles_count,
                verdict.generated_at
            ])
        except Exception as e:
            logger.error(f"Failed to save verdict for {verdict.symbol}: {e}")

    def get_latest_verdict(self, symbol: str) -> Optional[ShortTermVerdict]:
        """Fetch the most recent verdict for a given ticker."""
        try:
            res = self._conn.execute("""
                SELECT symbol, verdict, confidence, bullish_pct, bearish_pct, neutral_pct,
                       timeframe, executive_summary, key_drivers, analyzed_articles_count, generated_at
                FROM verdicts
                WHERE symbol = ?
                ORDER BY generated_at DESC
                LIMIT 1
            """, [symbol.upper()]).fetchone()

            if not res:
                return None

            drivers = json.loads(res[8]) if res[8] else []
            return ShortTermVerdict(
                symbol=res[0],
                verdict=VerdictSignal(res[1]),
                confidence=float(res[2]),
                sentiment_distribution={"BULLISH": res[3], "BEARISH": res[4], "NEUTRAL": res[5]},
                timeframe=res[6],
                executive_summary=res[7],
                key_drivers=drivers,
                analyzed_articles_count=int(res[9]),
                generated_at=res[10]
            )
        except Exception as e:
            logger.error(f"Error fetching latest verdict for {symbol}: {e}")
            return None

    def get_latest_verdicts_all(self) -> List[ShortTermVerdict]:
        """Fetch the latest verdict per unique ticker."""
        try:
            rows = self._conn.execute("""
                WITH RankedVerdicts AS (
                    SELECT *, ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY generated_at DESC) as rn
                    FROM verdicts
                )
                SELECT symbol, verdict, confidence, bullish_pct, bearish_pct, neutral_pct,
                       timeframe, executive_summary, key_drivers, analyzed_articles_count, generated_at
                    FROM RankedVerdicts
                    WHERE rn = 1
                    ORDER BY symbol ASC
            """).fetchall()

            verdicts: List[ShortTermVerdict] = []
            for row in rows:
                drivers = json.loads(row[8]) if row[8] else []
                verdicts.append(ShortTermVerdict(
                    symbol=row[0],
                    verdict=VerdictSignal(row[1]),
                    confidence=float(row[2]),
                    sentiment_distribution={"BULLISH": row[3], "BEARISH": row[4], "NEUTRAL": row[5]},
                    timeframe=row[6],
                    executive_summary=row[7],
                    key_drivers=drivers,
                    analyzed_articles_count=int(row[9]),
                    generated_at=row[10]
                ))
            return verdicts
        except Exception as e:
            logger.error(f"Error fetching all latest verdicts: {e}")
            return []

    def get_recent_articles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent articles for Streamlit tables."""
        try:
            rows = self._conn.execute("""
                SELECT article_id, title, source, url, published_at, summary
                FROM articles
                ORDER BY published_at DESC
                LIMIT ?
            """, [limit]).fetchall()

            return [
                {
                    "article_id": r[0],
                    "title": r[1],
                    "source": r[2],
                    "url": r[3],
                    "published_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "summary": r[5]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching recent articles: {e}")
            return []

    def get_recent_articles_with_sentiments(self, limit: int = 150) -> List[Dict[str, Any]]:
        """Retrieve recent articles joined with their analyzed sentiments, deduplicated by headline and ordered newest first."""
        try:
            rows = self._conn.execute("""
                WITH ranked_articles AS (
                    SELECT a.article_id, a.title, a.source, a.url, a.published_at, a.summary,
                           ROW_NUMBER() OVER(PARTITION BY LOWER(TRIM(a.title)) ORDER BY a.published_at DESC) as art_rn
                    FROM articles a
                ),
                ranked_sentiments AS (
                    SELECT article_id, symbol, sentiment, confidence, reasoning,
                           ROW_NUMBER() OVER(PARTITION BY article_id ORDER BY confidence DESC) as rn
                    FROM sentiments
                )
                SELECT ra.article_id, ra.title, ra.source, ra.url, ra.published_at, ra.summary,
                       COALESCE(s.symbol, 'MARKET') as symbol,
                       COALESCE(s.sentiment, 'NEUTRAL') as sentiment,
                       COALESCE(s.confidence, 0.6) as confidence,
                       COALESCE(s.reasoning, '') as reasoning
                FROM ranked_articles ra
                LEFT JOIN ranked_sentiments s ON ra.article_id = s.article_id AND s.rn = 1
                WHERE ra.art_rn = 1
                ORDER BY ra.published_at DESC
                LIMIT ?
            """, [limit]).fetchall()

            return [
                {
                    "article_id": r[0],
                    "title": r[1],
                    "source": r[2],
                    "url": r[3],
                    "published_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "summary": r[5],
                    "symbol": r[6],
                    "sentiment": r[7],
                    "confidence": float(r[8]),
                    "reasoning": r[9]
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Error fetching articles with sentiments: {e}")
            return self.get_recent_articles(limit)

    def close(self):
        """Close database connection."""
        try:
            self._conn.close()
        except Exception:
            pass
