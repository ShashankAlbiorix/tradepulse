from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class SentimentLabel(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class VerdictSignal(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class NewsArticle(BaseModel):
    """
    Standardized schema for raw and ingested news articles.
    """
    article_id: str
    title: str
    source: str
    url: str
    published_at: datetime
    content: Optional[str] = None
    summary: Optional[str] = None
    raw_html: Optional[str] = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EntityMention(BaseModel):
    """
    Represents an extracted entity or stock symbol linked to an article.
    """
    symbol: str
    company_name: str
    relevance_score: float = Field(default=1.0, ge=0.0, le=1.0)


class SentimentResult(BaseModel):
    """
    Represents LLM or FinBERT sentiment output for a specific entity in an article.
    """
    article_id: str
    symbol: str
    sentiment: SentimentLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    key_catalysts: List[str] = []
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShortTermVerdict(BaseModel):
    """
    Synthesized short-term verdict across recent news flow for a ticker.
    """
    symbol: str
    verdict: VerdictSignal
    confidence: float = Field(ge=0.0, le=1.0)
    sentiment_distribution: Dict[str, float] = {}
    timeframe: str = "1-5 Trading Days"
    executive_summary: str
    key_drivers: List[str] = []
    analyzed_articles_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
