import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import httpx

from config.settings import settings
from src.ingestion.base_fetcher import BaseNewsFetcher
from src.models.schemas import NewsArticle
from src.utils.logger import logger


class NewsAPIFetcher(BaseNewsFetcher):
    """
    Ingests financial news articles via REST API providers (NewsAPI / Finnhub).
    Gracefully handles missing keys by logging warnings.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        """
        Args:
            api_key: NewsAPI developer key. Defaults to settings.NEWS_API_KEY.
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key or settings.NEWS_API_KEY
        self.timeout = timeout
        self.base_url = "https://newsapi.org/v2/everything"

    def _generate_article_id(self, url: str, title: str) -> str:
        raw_key = f"{url.strip()}|{title.strip()}"
        return f"api_{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()[:16]}"

    async def fetch_articles_for_query(self, query: str = "Indian stock market", limit: int = 15) -> List[NewsArticle]:
        """
        Fetch news articles matching a specific financial query or ticker symbol.
        """
        if not self.api_key:
            logger.warning("NewsAPI key not configured in settings. Skipping NewsAPI fetch.")
            return []

        articles: List[NewsArticle] = []
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(limit, 50),
            "apiKey": self.api_key
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params, timeout=self.timeout)
                if response.status_code != 200:
                    logger.error(f"NewsAPI error: HTTP {response.status_code} - {response.text}")
                    return []

                payload = response.json()
                raw_articles = payload.get("articles", [])

                for item in raw_articles:
                    title = item.get("title") or ""
                    url = item.get("url") or ""
                    source_name = item.get("source", {}).get("name") or "NewsAPI"
                    description = item.get("description") or ""
                    content = item.get("content") or description
                    published_str = item.get("publishedAt")

                    if not title or not url or title == "[Removed]":
                        continue

                    try:
                        published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    except Exception:
                        published_at = datetime.now(timezone.utc)

                    article_id = self._generate_article_id(url, title)

                    articles.append(
                        NewsArticle(
                            article_id=article_id,
                            title=title,
                            source=source_name,
                            url=url,
                            published_at=published_at,
                            summary=description,
                            content=content
                        )
                    )

        except Exception as e:
            logger.error(f"Failed to fetch articles from NewsAPI: {str(e)}")

        return articles

    async def fetch_articles(self, limit: int = 20) -> List[NewsArticle]:
        """
        Default fetcher method querying major market headlines.
        """
        return await self.fetch_articles_for_query("Sensex Nifty Indian stock market", limit=limit)
