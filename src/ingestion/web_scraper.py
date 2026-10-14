import asyncio
import hashlib
import html
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import httpx
try:
    import trafilatura
except ImportError:
    trafilatura = None
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.models.schemas import NewsArticle
from src.utils.logger import logger


class WebScraper:
    """
    Extracts, cleans, and strips boilerplate from raw article web pages using Trafilatura,
    falling back to BeautifulSoup if necessary. Includes dedicated market portal scraper
    for LiveMint Market (https://www.livemint.com/market).
    """

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

    def _clean_text(self, text: str) -> str:
        """Sanitize text and replace smart quotes/escaped entities."""
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
        """Generate deterministic hash ID."""
        raw_key = f"{url.strip()}|{title.strip()}"
        return f"art_{hashlib.sha256(raw_key.encode('utf-8')).hexdigest()[:16]}"

    async def scrape_livemint_market(self) -> List[NewsArticle]:
        """
        Directly scrape breaking market stories from https://www.livemint.com/market
        and https://www.livemint.com/market/stock-market-news.
        """
        urls = [
            "https://www.livemint.com/market",
            "https://www.livemint.com/market/stock-market-news"
        ]
        articles: List[NewsArticle] = []
        seen_urls = set()

        async with httpx.AsyncClient(follow_redirects=True, timeout=self.timeout) as client:
            for page_url in urls:
                try:
                    res = await client.get(page_url, headers=self.headers)
                    if res.status_code != 200:
                        logger.warning(f"LiveMint scraper HTTP {res.status_code} for {page_url}")
                        continue

                    soup = BeautifulSoup(res.text, "html.parser")
                    
                    # Find all article cards and headline elements
                    for card in soup.find_all(["div", "li", "article"]):
                        h_tag = card.find(["h2", "h3"])
                        if not h_tag:
                            continue

                        raw_title = h_tag.get_text(strip=True)
                        title = self._clean_text(raw_title)
                        if not title or len(title) < 15:
                            continue

                        # Extract anchor link
                        a_tag = h_tag.find("a") or card.find("a")
                        if not a_tag or not a_tag.get("href"):
                            continue

                        link = a_tag["href"]
                        if link.startswith("/"):
                            link = f"https://www.livemint.com{link}"

                        if not link.startswith("http") or link in seen_urls:
                            continue

                        # Extract summary snippet
                        p_tag = card.find("p")
                        summary = self._clean_text(p_tag.get_text(strip=True)) if p_tag else title

                        seen_urls.add(link)

                        # Extract published date from card text or relative timestamps
                        card_text = card.get_text(" ", strip=True)
                        published_at = datetime.now(timezone.utc)
                        date_found = False

                        date_match = re.search(
                            r'\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}(?:\s*,\s*\d{1,2}:\d{2}\s*(?:AM|PM|IST))?)\b',
                            card_text,
                            re.IGNORECASE
                        )
                        if date_match:
                            try:
                                dt = date_parser.parse(date_match.group(1))
                                if not dt.tzinfo:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                published_at = dt.astimezone(timezone.utc)
                                date_found = True
                            except Exception:
                                pass
                        else:
                            rel_match = re.search(r'(\d+)\s*(min|hour|hr|day)s?\s*ago', card_text, re.IGNORECASE)
                            if rel_match:
                                qty = int(rel_match.group(1))
                                unit = rel_match.group(2).lower()
                                if 'min' in unit:
                                    published_at = datetime.now(timezone.utc) - timedelta(minutes=qty)
                                elif 'hr' in unit or 'hour' in unit:
                                    published_at = datetime.now(timezone.utc) - timedelta(hours=qty)
                                elif 'day' in unit:
                                    published_at = datetime.now(timezone.utc) - timedelta(days=qty)
                                date_found = True

                        # Filter out stale archival sidebar articles older than 5 days
                        if date_found and (datetime.now(timezone.utc) - published_at).days > 5:
                            logger.info(f"Skipping stale archival story ({published_at.strftime('%d %b %Y')}): {title[:50]}")
                            continue

                        article_id = self._generate_article_id(link, title)

                        articles.append(
                            NewsArticle(
                                article_id=article_id,
                                title=title,
                                source="LiveMint Markets",
                                url=link,
                                published_at=published_at,
                                summary=summary,
                                content=summary
                            )
                        )

                except Exception as e:
                    logger.error(f"Error scraping LiveMint market URL {page_url}: {e}")

        logger.info(f"Direct LiveMint market scraper extracted {len(articles)} fresh stories.")
        return articles

    async def extract_clean_text(self, url: str) -> Optional[str]:
        """
        Fetch HTML from an article URL and parse clean body text.
        """
        if not url or not url.startswith("http"):
            return None

        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                response = await client.get(url, headers=self.headers, timeout=self.timeout)
                if response.status_code != 200:
                    logger.warning(f"Scraper received HTTP {response.status_code} for {url}")
                    return None

                html_content = response.text

                # 1. Primary extractor: Trafilatura (if available)
                if trafilatura is not None:
                    try:
                        extracted_text = trafilatura.extract(
                            html_content,
                            include_comments=False,
                            include_tables=True,
                            no_fallback=False
                        )
                        if extracted_text and len(extracted_text.strip()) > 80:
                            return extracted_text.strip()
                    except Exception as te:
                        logger.warning(f"Trafilatura extraction failed, falling back to BeautifulSoup: {te}")


                # 2. Secondary fallback: BeautifulSoup paragraph aggregation
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Strip script, style, nav, footer tags
                for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    element.decompose()

                paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
                fallback_text = "\n\n".join([p for p in paragraphs if len(p) > 30])

                if fallback_text:
                    return fallback_text

        except Exception as e:
            logger.error(f"WebScraper failed for URL '{url}': {str(e)}")

        return None
