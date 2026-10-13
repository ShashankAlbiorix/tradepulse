import pytest
from datetime import datetime, timezone
from src.analysis.llm_factory import LLMFactory, MockChatModel
from src.analysis.entity_extractor import EntityExtractor
from src.analysis.sentiment_engine import SentimentEngine
from src.analysis.impact_analyzer import ImpactAnalyzer
from src.models.schemas import NewsArticle, SentimentLabel, SentimentResult


def test_llm_factory_fallback():
    """Verify LLMFactory defaults gracefully to MockChatModel when no API keys are present."""
    model = LLMFactory.get_chat_model(provider="mock")
    assert isinstance(model, MockChatModel)


@pytest.mark.asyncio
async def test_entity_extractor():
    """Test EntityExtractor correctly detects symbols and company aliases."""
    extractor = EntityExtractor()

    sample_article_1 = NewsArticle(
        article_id="art_test_1",
        title="RIL and Reliance Jio announce major expansion in telecom infrastructure",
        source="Test",
        url="https://example.com/ril",
        published_at=datetime.now(timezone.utc),
        summary="Mukesh Ambani announced new 5G rollouts."
    )

    sample_article_2 = NewsArticle(
        article_id="art_test_2",
        title="Infosys signs large financial services cloud migration deal",
        source="Test",
        url="https://example.com/infy",
        published_at=datetime.now(timezone.utc),
        summary="Infosys expects higher constant currency revenue."
    )

    entities_1 = await extractor.extract_entities(sample_article_1)
    symbols_1 = {e.symbol for e in entities_1}
    assert "RELIANCE" in symbols_1

    entities_2 = await extractor.extract_entities(sample_article_2)
    symbols_2 = {e.symbol for e in entities_2}
    assert "INFY" in symbols_2


@pytest.mark.asyncio
async def test_sentiment_engine_classification(sample_article: NewsArticle):
    """Test SentimentEngine async analysis and structured output generation."""
    engine = SentimentEngine(llm=MockChatModel())
    result = await engine.analyze_sentiment(sample_article, symbol="RELIANCE")

    assert isinstance(result, SentimentResult)
    assert result.symbol == "RELIANCE"
    assert result.sentiment in [SentimentLabel.BULLISH, SentimentLabel.BEARISH, SentimentLabel.NEUTRAL]
    assert 0.0 <= result.confidence <= 1.0
    assert len(result.reasoning) > 0


def test_impact_analyzer_categorization():
    """Test ImpactAnalyzer catalyst detection logic."""
    analyzer = ImpactAnalyzer()

    earnings_article = NewsArticle(
        article_id="art_earn",
        title="TCS posts 12% rise in quarterly net profit and EBITDA margin expansion",
        source="Test",
        url="https://example.com/tcs",
        published_at=datetime.now(timezone.utc),
        summary="Strong performance."
    )

    impact = analyzer.evaluate_impact(earnings_article)
    assert impact["category"] == "EARNINGS"
    assert impact["severity_score"] >= 4
