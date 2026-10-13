import sys
import os
from datetime import datetime, timezone
import pytest

# Ensure root directory is on python path for tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.models.schemas import NewsArticle, SentimentResult, SentimentLabel, ShortTermVerdict, VerdictSignal


@pytest.fixture
def sample_article():
    """
    Returns a standardized sample NewsArticle instance for testing.
    """
    return NewsArticle(
        article_id="art_12345",
        title="Reliance Industries reports 15% YoY net profit growth",
        source="Moneycontrol",
        url="https://www.moneycontrol.com/news/reliance-results-123",
        published_at=datetime.now(timezone.utc),
        summary="RIL reported higher operating profits from retail and digital services segments.",
        content="Full article content text for testing body parser..."
    )


@pytest.fixture
def sample_sentiment(sample_article):
    """
    Returns a sample SentimentResult instance for testing.
    """
    return SentimentResult(
        article_id=sample_article.article_id,
        symbol="RELIANCE",
        sentiment=SentimentLabel.BULLISH,
        confidence=0.88,
        reasoning="Strong earnings growth and margin expansion across retail and Jio.",
        key_catalysts=["15% profit growth", "Margin expansion"]
    )
