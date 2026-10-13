import pytest
from src.verdict.confidence_scorer import ConfidenceScorer
from src.verdict.verdict_generator import VerdictGenerator
from src.models.schemas import VerdictSignal, SentimentResult


def test_confidence_scorer_calculation(sample_sentiment: SentimentResult):
    """
    Test confidence calculation algorithm with sample sentiments.
    """
    scorer = ConfidenceScorer()
    score = scorer.calculate_confidence([sample_sentiment])
    assert 0.0 <= score <= 1.0


def test_verdict_signals_enum():
    """
    Validate presence of all discrete verdict signal categories.
    """
    signals = {s.value for s in VerdictSignal}
    expected = {"STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"}
    assert expected.issubset(signals)
