import asyncio
from typing import Dict, List, Optional, Any
from langgraph.graph import StateGraph, START, END

from src.agent.state import AgentState
from src.ingestion.rss_fetcher import RSSFetcher
from src.ingestion.base_fetcher import BaseNewsFetcher
from src.analysis.sentiment_engine import SentimentEngine
from src.verdict.verdict_generator import VerdictGenerator
from src.storage.cache import DeduplicationCache
from src.storage.database import DatabaseManager
from src.models.schemas import NewsArticle, SentimentResult, ShortTermVerdict
from src.utils.logger import logger
from src.ingestion.web_scraper import WebScraper


class NewsAnalysisWorkflow:
    """
    Streamlined StateGraph / LangGraph pipeline for Agentic News Intelligence:
    1. INGESTION: Concurrent RSS feed fetching & LiveMint market portal scraping
    2. DEDUPLICATION: Hash cache filtering
    3. SENTIMENT ANALYSIS: Direct LLM financial sentiment classification
    4. VERDICT GENERATION: Weighted synthesis & executive summaries
    5. PERSISTENCE: Storage in DuckDB
    """

    def __init__(
        self,
        fetcher: Optional[BaseNewsFetcher] = None,
        scraper: Optional[WebScraper] = None,
        sentiment_engine: Optional[SentimentEngine] = None,
        verdict_generator: Optional[VerdictGenerator] = None,
        cache: Optional[DeduplicationCache] = None,
        db: Optional[DatabaseManager] = None
    ):
        self.fetcher = fetcher or RSSFetcher()
        self.scraper = scraper or WebScraper()
        self.sentiment_engine = sentiment_engine or SentimentEngine()
        self.verdict_generator = verdict_generator or VerdictGenerator()
        self.cache = cache or DeduplicationCache()
        self.db = db or DatabaseManager()
        self.app = self._build_graph()

    def _build_graph(self):
        """
        Construct and compile the LangGraph StateGraph.
        """
        workflow = StateGraph(AgentState)

        workflow.add_node("ingest_news", self._ingest_news_node)
        workflow.add_node("deduplicate", self._deduplicate_node)
        workflow.add_node("analyze_sentiment", self._analyze_sentiment_node)
        workflow.add_node("generate_verdicts", self._generate_verdicts_node)
        workflow.add_node("persist_records", self._persist_records_node)

        # Build execution flow directly from deduplicate to analyze_sentiment
        workflow.add_edge(START, "ingest_news")
        workflow.add_edge("ingest_news", "deduplicate")
        workflow.add_edge("deduplicate", "analyze_sentiment")
        workflow.add_edge("analyze_sentiment", "generate_verdicts")
        workflow.add_edge("generate_verdicts", "persist_records")
        workflow.add_edge("persist_records", END)

        return workflow.compile()

    async def _ingest_news_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Fetch latest articles from configured feeds and direct portals."""
        logger.info("Node [1/5]: Fetching latest news articles from RSS & direct portal scrapers...")
        articles: List[NewsArticle] = []
        try:
            feed_articles, mint_articles = await asyncio.gather(
                self.fetcher.fetch_articles(),
                self.scraper.scrape_livemint_market(),
                return_exceptions=True
            )
            if isinstance(feed_articles, list):
                articles.extend(feed_articles)
            if isinstance(mint_articles, list):
                articles.extend(mint_articles)
                
            return {"raw_articles": articles, "current_step": "ingest_news"}
        except Exception as e:
            logger.error(f"Error in ingest_news_node: {e}")
            return {"raw_articles": articles, "errors": [str(e)]}

    async def _deduplicate_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Filter out previously processed articles using hash cache."""
        raw_articles = state.get("raw_articles", [])
        new_articles: List[NewsArticle] = []

        for article in raw_articles:
            if not self.cache.is_duplicate(article.url, article.title):
                self.cache.mark_seen(article.url, article.title)
                new_articles.append(article)

        logger.info(f"Node [2/5]: Deduplication kept {len(new_articles)}/{len(raw_articles)} fresh articles.")
        return {"new_articles": new_articles, "current_step": "deduplicate"}

    async def _analyze_sentiment_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Directly analyze financial sentiment for each ingested article in batch."""
        articles = state.get("new_articles", [])
        sentiment_results: List[SentimentResult] = await self.sentiment_engine.analyze_sentiment_batch(articles, symbol="MARKET")

        logger.info(f"Node [3/5]: Generated {len(sentiment_results)} individual sentiment ratings via FinBERT.")
        return {"sentiment_results": sentiment_results, "current_step": "analyze_sentiment"}

    async def _generate_verdicts_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Aggregate sentiments into overall market verdicts."""
        sentiments = state.get("sentiment_results", [])
        by_symbol: Dict[str, List[SentimentResult]] = {}

        for s in sentiments:
            by_symbol.setdefault(s.symbol, []).append(s)

        verdicts: Dict[str, ShortTermVerdict] = {}
        for symbol, symbol_sentiments in by_symbol.items():
            verdict = await self.verdict_generator.generate_verdict(symbol, symbol_sentiments)
            verdicts[symbol] = verdict

        logger.info(f"Node [4/5]: Compiled market verdicts.")
        return {"verdicts": verdicts, "current_step": "generate_verdicts"}

    async def _persist_records_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 5: Persist articles, sentiments, and generated verdicts to database."""
        articles = state.get("new_articles", [])
        sentiments = state.get("sentiment_results", [])
        verdicts = state.get("verdicts", {})

        for article in articles:
            self.db.save_article(article)

        for sentiment in sentiments:
            self.db.save_sentiment(sentiment)

        for verdict in verdicts.values():
            self.db.save_verdict(verdict)

        logger.info(f"Node [5/5]: Persisted {len(articles)} articles, {len(sentiments)} sentiments, and {len(verdicts)} verdicts.")
        return {"current_step": "completed"}

    async def run(self, initial_state: Optional[AgentState] = None) -> AgentState:
        """
        Execute the compiled LangGraph workflow asynchronously.

        Args:
            initial_state: Optional input state dictionary.

        Returns:
            AgentState: Final mutated state dictionary containing verdicts.
        """
        state_input: AgentState = initial_state or {
            "raw_articles": [],
            "new_articles": [],
            "extracted_entities": {},
            "sentiment_results": [],
            "verdicts": {},
            "errors": [],
            "current_step": "start"
        }

        final_state = await self.app.ainvoke(state_input)
        return final_state
