import asyncio
import hashlib
import html
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import httpx
import feedparser
from dateutil import parser as date_parser

from src.ingestion.base_fetcher import BaseNewsFetcher
from src.models.schemas import NewsArticle
from src.utils.logger import logger


# Comprehensive Active Indian & Global Financial RSS Feeds
DEFAULT_RSS_FEEDS: Dict[str, str] = {
    "LiveMint Markets": "https://www.livemint.com/rss/markets",
    "LiveMint Companies": "https://www.livemint.com/rss/companies",
    "LiveMint Economy": "https://www.livemint.com/rss/economy",
    "LiveMint Industry": "https://www.livemint.com/rss/industry",
    "Economic Times Markets": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "Economic Times Stocks": "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "NDTV Profit": "https://feeds.feedburner.com/ndtvprofit-latest",
    "Business Standard Markets": "https://www.business-standard.com/rss/markets-106.rss",
    "Business Standard Companies": "https://www.business-standard.com/rss/companies-101.rss",
    "Financial Express": "https://www.financialexpress.com/market/feed/"
}


class RSSFetcher(BaseNewsFetcher):
    """
    Asynchronous RSS news fetcher that polls financial RSS feeds,
    normalizes feed payloads, and generates structured NewsArticle instances.
    """

    def __init__(self, feed_endpoints: Optional[Dict[str, str]] = None, timeout: float = 12.0):
        """
        Args:
            feed_endpoints: Dictionary mapping source names to RSS XML URLs.
            timeout: HTTP request timeout in seconds.
        """
        self.feed_endpoints = feed_endpoints or DEFAULT_RSS_FEEDS
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml, */*"
        }

    def _clean_text(self, text: str) -> str:
        """Sanitize feed text, unescape HTML entities and normalize quotes."""
        if not text:
            return ""
        clean = html.unescape(text)
        clean = (
            clean.replace("\x91", "'")
            .replace("\x92", "'")
            .replace("\x93", '"')
            .replace("\x94", '"')
            .replace("\x96", "-")
            .replace("\x97", "--")
            .replace("\u2018", "'")
            .replace("\u2019", "'")
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\ufffd", "'")
        )
        return clean.strip()

    def _generate_article_id(self, url: str, title: str) -> str:
        """
        Generate deterministic SHA-256 hash id for deduplication and identification.
        """
        raw_key = f"{url.strip()}|{title.strip()}"
        return f"art_{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()[:16]}"

    def _parse_published_date(self, entry: Any) -> datetime:
        """
        Extract and parse publication timestamp from RSS entry with multi-strategy fallback.
        """
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass
        for attr in ["published", "pubDate", "updated", "created"]:
            raw_val = getattr(entry, attr, None)
            if raw_val and isinstance(raw_val, str):
                try:
                    dt = date_parser.parse(raw_val)
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                except Exception:
                    pass
        return datetime.now(timezone.utc)

    async def _fetch_single_feed(self, client: httpx.AsyncClient, source_name: str, feed_url: str) -> List[NewsArticle]:
        """
        Fetch and parse a single RSS feed endpoint using raw content decoding.
        """
        articles: List[NewsArticle] = []
        try:
            response = await client.get(feed_url, headers=self.headers, timeout=self.timeout)
            if response.status_code != 200:
                logger.warning(f"RSS Fetch Error for {source_name} ({feed_url}): HTTP {response.status_code}")
                return []

            # Parse XML feed content from raw bytes for native encoding detection
            parsed_feed = feedparser.parse(response.content)
            
            for entry in parsed_feed.entries:
                raw_title = getattr(entry, "title", "")
                link = getattr(entry, "link", "").strip()
                raw_summary = getattr(entry, "summary", "") or getattr(entry, "description", "")

                title = self._clean_text(raw_title)
                summary = self._clean_text(raw_summary)

                if not title or not link or len(title) < 18:
                    continue

                # Filter out aggregator boilerplate and navigation headers
                title_lower = title.lower().strip()
                junk_headers = {
                    "from the house of hindustan times", "trending stories", "top stories",
                    "live events", "market dashboard", "quick reads", "most popular",
                    "latest news", "web stories", "mint epaper", "subscribe to mint",
                    "view all stories", "stock market live", "today's top news"
                }
                if title_lower in junk_headers or any(j in title_lower and len(title_lower) < 35 for j in junk_headers):
                    continue

                published_at = self._parse_published_date(entry)
                article_id = self._generate_article_id(link, title)

                article = NewsArticle(
                    article_id=article_id,
                    title=title,
                    source=source_name,
                    url=link,
                    published_at=published_at,
                    summary=summary,
                    content=summary
                )
                articles.append(article)

            logger.info(f"Successfully fetched {len(articles)} articles from {source_name}")
            return articles

        except Exception as e:
            logger.error(f"Exception fetching RSS feed {source_name}: {e}")
            return []

    async def fetch_articles(self, limit: Optional[int] = None) -> List[NewsArticle]:
        """
        Concurrently poll all configured financial RSS feeds.
        """
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tasks = [
                self._fetch_single_feed(client, source_name, url)
                for source_name, url in self.feed_endpoints.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles: List[NewsArticle] = []
        for res in results:
            if isinstance(res, list):
                all_articles.extend(res)

        # Sort newest first by default
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        if limit:
            all_articles = all_articles[:limit]
        return all_articles
