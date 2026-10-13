import pytest
import respx
import httpx
from datetime import datetime, timezone
from src.ingestion.rss_fetcher import RSSFetcher
from src.ingestion.news_api_fetcher import NewsAPIFetcher
from src.ingestion.web_scraper import WebScraper
from src.ingestion.base_fetcher import BaseNewsFetcher
from src.models.schemas import NewsArticle


SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Financial Markets Feed</title>
    <link>https://example.com/markets</link>
    <item>
      <title>TCS signs $500M deal with global bank</title>
      <link>https://example.com/tcs-500m-deal</link>
      <description>Tata Consultancy Services secured a multi-year digital transformation deal.</description>
      <pubDate>Tue, 06 Oct 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Infosys beats quarterly margin guidance</title>
      <link>https://example.com/infosys-results</link>
      <description>Infosys reported strong Q3 profit growth led by financial services.</description>
      <pubDate>Tue, 06 Oct 2026 09:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_rss_fetcher_instantiation():
    """Ensure RSS fetcher initializes with default financial feed endpoints."""
    fetcher = RSSFetcher()
    assert isinstance(fetcher, BaseNewsFetcher)
    assert len(fetcher.feed_endpoints) > 0


@pytest.mark.asyncio
@respx.mock
async def test_rss_fetcher_parse_feed():
    """Test RSS fetcher correctly parses XML and generates NewsArticle schemas."""
    respx.get("https://example.com/mock-rss.xml").mock(return_value=httpx.Response(200, text=SAMPLE_RSS_XML))
    fetcher = RSSFetcher(feed_endpoints={"TestFeed": "https://example.com/mock-rss.xml"})
    articles = await fetcher.fetch_articles(limit=10)

    assert len(articles) == 2
    assert articles[0].source == "TestFeed"
    assert "TCS signs" in articles[0].title
    assert articles[0].url == "https://example.com/tcs-500m-deal"
    assert articles[0].article_id.startswith("art_")


@pytest.mark.asyncio
@respx.mock
async def test_news_api_fetcher_mock():
    """Test NewsAPI fetcher handles responses and transforms to NewsArticle schemas."""
    mock_news_api_response = {
        "status": "ok",
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "title": "Reliance expanding green hydrogen capacity",
                "description": "Reliance Industries accelerates its green energy investments.",
                "url": "https://reuters.com/business/reliance-green-hydrogen",
                "publishedAt": "2026-10-06T08:00:00Z",
                "content": "Full story content regarding RIL green energy."
            }
        ]
    }

    respx.get("https://newsapi.org/v2/everything").mock(return_value=httpx.Response(200, json=mock_news_api_response))
    fetcher = NewsAPIFetcher(api_key="test_api_key")
    articles = await fetcher.fetch_articles_for_query("Reliance", limit=5)

    assert len(articles) == 1
    assert articles[0].title == "Reliance expanding green hydrogen capacity"
    assert articles[0].source == "Reuters"
    assert articles[0].article_id.startswith("api_")


@pytest.mark.asyncio
@respx.mock
async def test_web_scraper_html_cleaning():
    """Test web scraper cleans HTML boilerplate and extracts body text."""
    sample_html = """
    <html>
      <head><title>Test Article</title></head>
      <body>
        <nav><a href="#">Home</a><a href="#">Contact</a></nav>
        <article>
          <p>Tata Motors reported record quarterly vehicle sales across electric and commercial vehicle segments.</p>
          <p>Operating margins improved substantially due to robust Jaguar Land Rover cash flow generation and lower commodity input costs.</p>
        </article>
        <footer>Copyright 2026 Example Corp</footer>
      </body>
    </html>
    """
    respx.get("https://example.com/article-1").mock(return_value=httpx.Response(200, text=sample_html))
    scraper = WebScraper()
    text = await scraper.extract_clean_text("https://example.com/article-1")

    assert text is not None
    assert "Tata Motors reported record quarterly" in text
    assert "Home" not in text
    assert "Copyright" not in text
