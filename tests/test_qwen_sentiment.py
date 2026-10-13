import pytest
from fastapi.testclient import TestClient
from api.main import app
from src.analysis.qwen_sentiment_engine import QwenFinancialSentimentEngine


def test_qwen_singleton():
    """Verify QwenFinancialSentimentEngine behaves as a singleton."""
    engine1 = QwenFinancialSentimentEngine()
    engine2 = QwenFinancialSentimentEngine()
    assert engine1 is engine2


def test_qwen_predict_sentiment_bullish():
    """Verify Qwen model predicts BULLISH for strong positive market news."""
    engine = QwenFinancialSentimentEngine()
    text = "Reliance Industries reports 25% surge in net profit, beating Street estimates across all segments."
    result = engine.predict_sentiment(text)
    assert result["sentiment"] == "BULLISH"
    assert result["confidence"] >= 0.70
    assert result["probabilities"]["bullish"] > result["probabilities"]["bearish"]


def test_qwen_predict_sentiment_bearish():
    """Verify Qwen model predicts BEARISH for negative market news."""
    engine = QwenFinancialSentimentEngine()
    text = "Sensex crashes 1,200 points as geopolitical tensions escalate and foreign funds dump shares."
    result = engine.predict_sentiment(text)
    assert result["sentiment"] == "BEARISH"
    assert result["confidence"] >= 0.70
    assert result["probabilities"]["bearish"] > result["probabilities"]["bullish"]


def test_api_health():
    """Verify FastAPI /api/health endpoint returns 200 OK."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "NOSIBLE/financial-sentiment-v1.1-base" in data["model"]


def test_api_sentiment_text():
    """Verify FastAPI /api/sentiment/text endpoint returns expected schema."""
    client = TestClient(app)
    response = client.post("/api/sentiment/text", json={
        "text": "Nifty surges to all-time high as tech stocks rally."
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["sentiment"] in ["BULLISH", "BEARISH", "NEUTRAL"]
    assert "confidence" in data
    assert "probabilities" in data
