import re
import html
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from src.utils.logger import logger

IST_TZ = timezone(timedelta(hours=5, minutes=30))


class ArticleReader:
    """
    Production-grade financial news web scraper that extracts rich article data:
    headline, publication date, author, publisher, lead image, clean paragraphs,
    reading time, and structured meta tags.
    """

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
        }

    def _clean_text(self, text: str) -> str:
        """Sanitize text and replace escaped symbols."""
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
        return re.sub(r"\s+", " ", clean).strip()

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain name from URL."""
        match = re.search(r"https?://(?:www\.)?([^/]+)", url)
        return match.group(1) if match else "Web"

    def _parse_date_to_ist(self, raw_val: str) -> Optional[datetime]:
        """Parse various date formats into timezone-aware IST datetime."""
        if not raw_val:
            return None
        try:
            dt = date_parser.parse(raw_val)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(IST_TZ)
        except Exception:
            return None

    def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Scrape and parse full article webpage data.
        Returns dictionary containing all extracted metadata, content, and paragraphs.
        """
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return {
                "status": "error",
                "message": "Invalid URL. URL must start with http:// or https://",
                "url": url,
            }

        domain = self._extract_domain(url)

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # 1. Headline / Title
            title = ""
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif soup.title and soup.title.string:
                title = soup.title.string.strip()
            elif soup.find("h1"):
                title = soup.find("h1").get_text().strip()

            # Clean trailing publication branding from title (e.g. " | Mint" or " - Moneycontrol")
            clean_title = re.sub(r"\s*[\-|\|]\s*(?:Mint|Moneycontrol|The Economic Times|Livemint|Reuters|Bloomberg|CNBC).*$", "", title, flags=re.IGNORECASE)
            title = clean_title or title

            # 2. Description / Summary
            description = ""
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                description = og_desc["content"].strip()
            elif soup.find("meta", attrs={"name": "description"}):
                description = soup.find("meta", attrs={"name": "description"})["content"].strip()

            # 3. Lead Image
            lead_image = ""
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                lead_image = og_img["content"].strip()

            # 4. Author / Byline
            author = ""
            author_meta = (
                soup.find("meta", attrs={"name": "author"})
                or soup.find("meta", property="article:author")
                or soup.find("meta", attrs={"name": "article:author"})
            )
            if author_meta and author_meta.get("content"):
                author = author_meta["content"].strip()
            else:
                author_elem = soup.find(["span", "div", "a"], class_=re.compile(r"author|byline", re.IGNORECASE))
                if author_elem:
                    author = author_elem.get_text(strip=True)

            # 5. Publisher / Source Name
            source_name = domain.capitalize()
            og_site = soup.find("meta", property="og:site_name")
            if og_site and og_site.get("content"):
                source_name = og_site["content"].strip()
            elif "livemint" in domain:
                source_name = "Livemint"
            elif "moneycontrol" in domain:
                source_name = "Moneycontrol"
            elif "economictimes" in domain:
                source_name = "Economic Times"
            elif "ndtvprofit" in domain or "ndtv" in domain:
                source_name = "NDTV Profit"
            elif "business-standard" in domain:
                source_name = "Business Standard"

            # 6. Publication Date & Time Extraction (Robust Multi-Strategy)
            published_dt: Optional[datetime] = None
            date_candidates = [
                soup.find("meta", property="article:published_time"),
                soup.find("meta", property="og:article:published_time"),
                soup.find("meta", attrs={"name": "publish-date"}),
                soup.find("meta", attrs={"name": "publication-date"}),
                soup.find("meta", attrs={"name": "pubdate"}),
                soup.find("meta", attrs={"name": "date"}),
                soup.find("meta", attrs={"name": "Last-Modified-Time"}),
            ]
            for cand in date_candidates:
                if cand and cand.get("content"):
                    dt = self._parse_date_to_ist(cand["content"])
                    if dt:
                        published_dt = dt
                        break

            # Check JSON-LD Schemas if meta tags didn't yield a date
            if not published_dt:
                for script in soup.find_all("script", type="application/ld+json"):
                    try:
                        data = json.loads(script.string or "{}")
                        if isinstance(data, list):
                            items = data
                        elif isinstance(data, dict):
                            items = [data] + data.get("@graph", [])
                        else:
                            items = []
                        for item in items:
                            if isinstance(item, dict):
                                for key in ["datePublished", "dateModified", "uploadDate"]:
                                    if key in item and item[key]:
                                        dt = self._parse_date_to_ist(str(item[key]))
                                        if dt:
                                            published_dt = dt
                                            break
                            if published_dt:
                                break
                    except Exception:
                        pass
                    if published_dt:
                        break

            # Check <time> tags or visible date containers
            if not published_dt:
                time_elem = soup.find("time")
                if time_elem:
                    raw_time = time_elem.get("datetime") or time_elem.get_text(strip=True)
                    published_dt = self._parse_date_to_ist(raw_time)

            # Fallback to current time if unparseable
            if not published_dt:
                published_dt = datetime.now(IST_TZ)

            formatted_pub_date = published_dt.strftime("%d %b %Y, %I:%M %p IST")

            # 7. Clean Paragraphs Extraction
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]):
                tag.decompose()

            raw_paras = soup.find_all("p")
            clean_paragraphs: List[str] = []
            junk_filters = [
                "subscribe to", "download the app", "all rights reserved",
                "copyright", "read more:", "also read:", "click here", "sign up",
                "advertisement", "disclaimer:", "follow us on", "terms of use"
            ]

            for p in raw_paras:
                text = self._clean_text(p.get_text(" ", strip=True))
                if len(text) >= 35 and not any(j in text.lower() for j in junk_filters):
                    clean_paragraphs.append(text)

            full_body_text = " ".join(clean_paragraphs)
            word_count = len(full_body_text.split())
            reading_time_min = max(1, round(word_count / 200))

            # 8. Extract Discovered Meta Tags Map
            meta_map = {}
            for m in soup.find_all("meta"):
                key = m.get("property") or m.get("name")
                val = m.get("content")
                if key and val and len(val) < 250:
                    meta_map[key] = val

            return {
                "status": "success",
                "url": url,
                "domain": domain,
                "source": source_name,
                "title": title or "Financial Article",
                "description": description,
                "author": author or source_name,
                "lead_image": lead_image,
                "published_at_raw": published_dt.isoformat(),
                "published_at_formatted": formatted_pub_date,
                "paragraphs": clean_paragraphs,
                "full_text": full_body_text,
                "word_count": word_count,
                "reading_time_min": reading_time_min,
                "meta_tags": meta_map,
            }

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return {
                "status": "error",
                "message": str(e),
                "url": url,
                "domain": domain,
            }
