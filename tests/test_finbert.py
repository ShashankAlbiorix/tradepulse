import pytest
from src.analysis.finbert_engine import FinBERTEngine


def test_finbert_singleton():
    """Verify FinBERTEngine maintains a singleton instance."""
    engine1 = FinBERTEngine()
    engine2 = FinBERTEngine()
    assert engine1 is engine2


def test_finbert_bullish_classification():
    """Verify strong positive financial news produces BULLISH output."""
    engine = FinBERTEngine()
    text = "Tata Consultancy Services beats market estimates with a massive 22% surge in Q2 net profit and announces record interim dividend."
    result = engine.predict_sentiment(text)

    assert result["sentiment"] == "BULLISH"
    assert result["confidence"] >= 0.70
    assert "bullish" in result["probabilities"]
    assert result["probabilities"]["bullish"] > result["probabilities"]["bearish"]


def test_finbert_bearish_classification():
    """Verify strong negative financial news produces BEARISH output."""
    engine = FinBERTEngine()
    text = "Company reports heavy quarterly net loss, faces severe regulatory penalties from SEBI, and defaults on loan repayment."
    result = engine.predict_sentiment(text)

    assert result["sentiment"] == "BEARISH"
    assert result["confidence"] >= 0.70
    assert result["probabilities"]["bearish"] > result["probabilities"]["bullish"]


def test_finbert_batch_classification():
    """Verify high-throughput batch prediction preserves order and structure."""
    engine = FinBERTEngine()
    texts = [
        "Strong growth and dividend declared.",
        "Severe loss and debt downgrade.",
        "Board of directors to meet next week for general review."
    ]
    results = engine.predict_sentiment_batch(texts, batch_size=2)

    assert len(results) == 3
    assert results[0]["sentiment"] == "BULLISH"
    assert results[1]["sentiment"] == "BEARISH"
    assert results[2]["sentiment"] == "NEUTRAL"
