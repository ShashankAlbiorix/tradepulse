import asyncio
import sys
from datetime import datetime, timezone

from src.models.schemas import NewsArticle, SentimentResult, SentimentLabel, VerdictSignal, ShortTermVerdict
from src.analysis.llm_factory import LLMFactory, MockChatModel
from src.analysis.entity_extractor import EntityExtractor
from src.analysis.sentiment_engine import SentimentEngine
from src.analysis.impact_analyzer import ImpactAnalyzer
from src.verdict.confidence_scorer import ConfidenceScorer
from src.verdict.summarizer import VerdictSummarizer
from src.verdict.verdict_generator import VerdictGenerator
from src.agent.workflow import NewsAnalysisWorkflow
from src.agent.scheduler import AgentScheduler
from src.ingestion.rss_fetcher import RSSFetcher
from src.ingestion.base_fetcher import BaseNewsFetcher
from src.storage.cache import DeduplicationCache
from src.storage.database import DatabaseManager


class MockTestFetcher(BaseNewsFetcher):
    """Deterministic Mock Fetcher for end-to-end graph tests."""
    async def fetch_articles(self, limit: int = 10):
        return [
            NewsArticle(
                article_id="mock_art_1",
                title="Reliance Industries Q3 profits jump 18% on retail margin surge",
                source="Moneycontrol",
                url="https://example.com/ril-q3",
                published_at=datetime.now(timezone.utc),
                summary="Mukesh Ambani led Reliance Industries posted stellar performance."
            ),
            NewsArticle(
                article_id="mock_art_2",
                title="TCS signs $750M digital transformation deal with European insurer",
                source="ET",
                url="https://example.com/tcs-deal",
                published_at=datetime.now(timezone.utc),
                summary="Tata Consultancy Services announced a landmark deal win."
            )
        ]


async def run_all_checks():
    print("=== RUNNING NEWS SENTIMENT AGENT TEST SUITE ===")
    
    # 1. Test LLM Factory
    print("[1/9] Testing LLM Factory...", end=" ", flush=True)
    model = LLMFactory.get_chat_model(provider="mock")
    assert isinstance(model, MockChatModel)
    print("PASSED")

    # 2. Test Entity Extractor
    print("[2/9] Testing Entity Extractor...", end=" ", flush=True)
    extractor = EntityExtractor()
    sample_article = NewsArticle(
        article_id="art_101",
        title="Reliance and Jio announce record 5G subscriptions",
        source="Moneycontrol",
        url="https://example.com/ril",
        published_at=datetime.now(timezone.utc),
        summary="Mukesh Ambani led RIL posted solid digital metrics."
    )
    entities = await extractor.extract_entities(sample_article)
    symbols = {e.symbol for e in entities}
    assert "RELIANCE" in symbols
    print(f"PASSED (Found: {symbols})")

    # 3. Test Sentiment Engine
    print("[3/9] Testing Sentiment Engine...", end=" ", flush=True)
    engine = SentimentEngine(llm=model)
    res = await engine.analyze_sentiment(sample_article, symbol="RELIANCE")
    assert isinstance(res, SentimentResult)
    assert res.sentiment == SentimentLabel.BULLISH
    assert 0.0 <= res.confidence <= 1.0
    print(f"PASSED (Sentiment: {res.sentiment.value}, Confidence: {res.confidence:.2f})")

    # 4. Test Impact Analyzer
    print("[4/9] Testing Impact Analyzer...", end=" ", flush=True)
    analyzer = ImpactAnalyzer()
    earnings_art = NewsArticle(
        article_id="art_102",
        title="TCS posts 14% rise in quarterly net profit and robust EBITDA margin",
        source="ET",
        url="https://example.com/tcs",
        published_at=datetime.now(timezone.utc),
        summary="Quarterly results outperform street expectations."
    )
    impact = analyzer.evaluate_impact(earnings_art)
    assert impact["category"] == "EARNINGS"
    assert impact["severity_score"] >= 4
    print(f"PASSED (Category: {impact['category']}, Severity: {impact['severity_score']}/5)")

    # 5. Test Confidence Scorer
    print("[5/9] Testing Confidence Scorer...", end=" ", flush=True)
    scorer = ConfidenceScorer()
    sentiments_list = [
        SentimentResult(
            article_id="art_1", symbol="TCS", sentiment=SentimentLabel.BULLISH,
            confidence=0.90, reasoning="Deal win", key_catalysts=["Multi-year deal"]
        ),
        SentimentResult(
            article_id="art_2", symbol="TCS", sentiment=SentimentLabel.BULLISH,
            confidence=0.85, reasoning="Margin beat", key_catalysts=["Margin beat"]
        ),
        SentimentResult(
            article_id="art_3", symbol="TCS", sentiment=SentimentLabel.NEUTRAL,
            confidence=0.70, reasoning="Market movement", key_catalysts=[]
        ),
    ]
    conf_score = scorer.calculate_confidence(sentiments_list)
    assert 0.0 <= conf_score <= 1.0
    print(f"PASSED (Computed Confidence: {conf_score:.2f})")

    # 6. Test Verdict Generator
    print("[6/9] Testing Verdict Generator...", end=" ", flush=True)
    generator = VerdictGenerator()
    verdict = await generator.generate_verdict("TCS", sentiments_list)
    assert isinstance(verdict, ShortTermVerdict)
    assert verdict.symbol == "TCS"
    assert verdict.verdict in [VerdictSignal.BUY, VerdictSignal.STRONG_BUY]
    assert len(verdict.key_drivers) > 0
    print(f"PASSED (Verdict: {verdict.verdict.value}, Confidence: {verdict.confidence:.2f})")

    # 7. Test Deduplication Cache & DuckDB Storage
    print("[7/9] Testing DuckDB Persistence & Cache...", end=" ", flush=True)
    cache = DeduplicationCache()
    assert not cache.is_duplicate("https://example.com/item1", "Headline 1")
    cache.mark_seen("https://example.com/item1", "Headline 1")
    assert cache.is_duplicate("https://example.com/item1", "Headline 1")

    db = DatabaseManager(db_path=":memory:")
    db.save_article(sample_article)
    db.save_sentiment(sentiments_list[0])
    db.save_verdict(verdict)

    latest_verdict = db.get_latest_verdict("TCS")
    assert latest_verdict is not None
    assert latest_verdict.symbol == "TCS"
    assert latest_verdict.verdict in [VerdictSignal.BUY, VerdictSignal.STRONG_BUY]
    print("PASSED (DuckDB :memory: tables & operations verified)")

    # 8. Test LangGraph Workflow End-to-End Execution
    print("[8/9] Testing LangGraph Workflow DAG...", end=" ", flush=True)
    workflow = NewsAnalysisWorkflow(
        fetcher=MockTestFetcher(),
        sentiment_engine=engine,
        verdict_generator=generator,
        cache=cache,
        db=db
    )
    final_state = await workflow.run()
    assert "verdicts" in final_state
    assert len(final_state["verdicts"]) >= 1
    assert "MARKET" in final_state["verdicts"]
    print(f"PASSED (Generated {len(final_state['verdicts'])} market verdicts across LangGraph nodes)")

    # 9. Test Agent Scheduler
    print("[9/10] Testing Agent Scheduler Telemetry...", end=" ", flush=True)
    scheduler = AgentScheduler(workflow=workflow, interval_seconds=60)
    status = scheduler.get_status()
    assert status["is_running"] is False
    assert status["interval_seconds"] == 60
    print("PASSED")

    # 10. Test FinBERT Engine
    print("[10/10] Testing FinBERT Neural Classifier & Inference...", end=" ", flush=True)
    from src.analysis.finbert_engine import FinBERTEngine
    fb = FinBERTEngine()
    fb_res = fb.predict_sentiment("Company signs major multi-billion expansion agreement and boosts earnings guidance")
    assert fb_res["sentiment"] == "BULLISH"
    assert fb_res["confidence"] >= 0.70
    print(f"PASSED (FinBERT: {fb_res['sentiment']}, Confidence: {fb_res['confidence']:.2f})")

    print("\n=======================================================")
    print("ALL 10 CORE TEST SUITES PASSED CLEANLY (100% SUCCESS) [PASS]")
    print("=======================================================")


if __name__ == "__main__":
    asyncio.run(run_all_checks())
