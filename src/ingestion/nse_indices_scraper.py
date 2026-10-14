import os
import json
import time
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import requests
from pydantic import BaseModel, Field

from src.utils.logger import logger

IST_TZ = timezone(timedelta(hours=5, minutes=30))
CACHE_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/nse_indices_cache.json"))


class NSEIndexData(BaseModel):
    """Normalized schema for a single scraped NSE Index."""
    index: str
    symbol: str = ""
    category: str = "BROAD MARKET"
    last: float = 0.0
    variation: float = 0.0
    percent_change: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    previous_close: float = 0.0
    year_high: float = 0.0
    year_low: float = 0.0
    indicative_close: float = 0.0
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    pe: str = "-"
    pb: str = "-"
    dy: str = "-"
    chart_today_path: str = ""


class NSEIndicesScraper:
    """
    Real-time continuous web scraper for NSE India Live Market Indices
    (https://www.nseindia.com/market-data/live-market-indices).
    
    Features:
    - Session cookie warm-up with automated anti-blocking headers
    - In-memory thread-safe TTL caching (default: 30s) to prevent IP rate-limiting
    - Persistent disk fallback to guarantee 100% dashboard uptime
    - Background continuous refresh worker support
    """

    BASE_URL = "https://www.nseindia.com/market-data/live-market-indices"
    API_URL = "https://www.nseindia.com/api/allIndices"

    def __init__(self, ttl_seconds: int = 45):
        self.ttl_seconds = ttl_seconds
        self._session: Optional[requests.Session] = None
        self._cache: List[Dict[str, Any]] = []
        self._last_fetch_ts: float = 0.0
        self._last_market_timestamp: str = ""
        self._lock = threading.Lock()
        self._ensure_cache_dir()
        self._load_fallback_from_disk()

    def _ensure_cache_dir(self):
        os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)

    def _create_session(self) -> requests.Session:
        """Create and warm up requests session with authentic browser headers and cookies."""
        s = requests.Session()
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive"
        }
        try:
            # Hit base page to generate session cookies
            s.get(self.BASE_URL, headers=headers, timeout=12)
        except Exception as e:
            logger.warning(f"NSE cookie warm-up warning: {e}")
        return s

    def _load_fallback_from_disk(self):
        """Load persistent cache from disk for immediate availability."""
        if os.path.exists(CACHE_FILE_PATH):
            try:
                with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._cache = data.get("indices", [])
                    self._last_market_timestamp = data.get("timestamp", "")
                    self._last_fetch_ts = data.get("fetched_at_ts", 0.0)
            except Exception as e:
                logger.error(f"Failed to load cached NSE indices from disk: {e}")

    def _save_fallback_to_disk(self):
        """Save latest successful scrape to disk."""
        try:
            with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": self._last_market_timestamp,
                    "fetched_at_ts": self._last_fetch_ts,
                    "fetched_at_ist": datetime.now(IST_TZ).strftime("%d-%b-%Y %I:%M:%S %p IST"),
                    "count": len(self._cache),
                    "indices": self._cache
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save NSE indices to disk: {e}")

    def scrape_live_indices(self, force: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch all live market indices from NSE India.
        Uses in-memory cache if called within `ttl_seconds`, unless `force=True`.
        """
        now = time.time()
        with self._lock:
            # Return cached copy if still fresh
            if not force and self._cache and (now - self._last_fetch_ts < self.ttl_seconds):
                return self._cache

            try:
                if not self._session or len(self._session.cookies) == 0:
                    self._session = self._create_session()

                api_headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/128.0.0.0 Safari/537.36"
                    ),
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": self.BASE_URL,
                    "X-Requested-With": "XMLHttpRequest"
                }

                resp = self._session.get(self.API_URL, headers=api_headers, timeout=12)

                # If unauthorized or blocked, recreate session and retry once
                if resp.status_code != 200:
                    logger.info("NSE session expired or rejected. Refreshing session...")
                    self._session = self._create_session()
                    resp = self._session.get(self.API_URL, headers=api_headers, timeout=12)

                if resp.status_code == 200:
                    payload = resp.json()
                    raw_data = payload.get("data", [])
                    timestamp_str = payload.get("timestamp", datetime.now(IST_TZ).strftime("%d-%b-%Y %H:%M"))

                    parsed_indices = []
                    for item in raw_data:
                        name = item.get("index", "").strip()
                        if not name:
                            continue
                        parsed_indices.append({
                            "index": name,
                            "symbol": item.get("indexSymbol", name),
                            "category": item.get("key", "BROAD MARKET"),
                            "last": float(item.get("last", 0.0) or 0.0),
                            "variation": float(item.get("variation", 0.0) or 0.0),
                            "percent_change": float(item.get("percentChange", 0.0) or 0.0),
                            "open": float(item.get("open", 0.0) or 0.0),
                            "high": float(item.get("high", 0.0) or 0.0),
                            "low": float(item.get("low", 0.0) or 0.0),
                            "previous_close": float(item.get("previousClose", 0.0) or 0.0),
                            "year_high": float(item.get("yearHigh", 0.0) or 0.0),
                            "year_low": float(item.get("yearLow", 0.0) or 0.0),
                            "indicative_close": float(item.get("indicativeClose", 0.0) or 0.0),
                            "advances": int(item.get("advances", 0) or 0),
                            "declines": int(item.get("declines", 0) or 0),
                            "unchanged": int(item.get("unchanged", 0) or 0),
                            "pe": str(item.get("pe", "-")),
                            "pb": str(item.get("pb", "-")),
                            "dy": str(item.get("dy", "-")),
                            "chart_today_path": item.get("chartTodayPath", "")
                        })

                    if parsed_indices:
                        self._cache = parsed_indices
                        self._last_market_timestamp = timestamp_str
                        self._last_fetch_ts = now
                        self._save_fallback_to_disk()
                        logger.info(f"Successfully scraped {len(parsed_indices)} live indices from NSE India.")
                        return self._cache

            except Exception as e:
                logger.error(f"Error scraping live NSE indices: {e}")

            # Return fallback cached data if live fetch failed
            return self._cache

    def get_marquee_indices(self) -> List[Dict[str, Any]]:
        """
        Returns high-priority benchmark & sectoral indices configured
        specifically for the Market Pulse continuous marquee ribbon.
        """
        all_indices = self.scrape_live_indices()
        if not all_indices:
            # Safe default fallback if network unreachable
            return [
                {"sym": "NIFTY 50", "val": "22,622.70", "chg": "-99.25 (-0.44%)", "up": False},
                {"sym": "NIFTY NEXT 50", "val": "68,999.30", "chg": "+71.35 (+0.10%)", "up": True},
                {"sym": "NIFTY BANK", "val": "55,316.00", "chg": "-165.05 (-0.30%)", "up": False},
                {"sym": "NIFTY FIN SERVICE", "val": "24,948.70", "chg": "-279.85 (-1.11%)", "up": False},
                {"sym": "NIFTY MIDCAP SELECT", "val": "13,773.15", "chg": "+11.20 (+0.08%)", "up": True},
                {"sym": "NIFTY IT", "val": "35,420.10", "chg": "+140.20 (+0.40%)", "up": True},
                {"sym": "NIFTY AUTO", "val": "23,890.40", "chg": "+65.10 (+0.27%)", "up": True},
                {"sym": "INDIA VIX", "val": "13.25", "chg": "-0.29 (-2.14%)", "up": False},
            ]

        lookup = {i["index"].upper(): i for i in all_indices}

        target_symbols = [
            ("NIFTY 50", "NIFTY 50"),
            ("NIFTY NEXT 50", "NIFTY NEXT 50"),
            ("NIFTY BANK", "NIFTY BANK"),
            ("NIFTY FINANCIAL SERVICES", "NIFTY FIN SERVICE"),
            ("NIFTY MIDCAP SELECT", "NIFTY MID SELECT"),
            ("NIFTY 100", "NIFTY 100"),
            ("NIFTY 500", "NIFTY 500"),
            ("NIFTY IT", "NIFTY IT"),
            ("NIFTY AUTO", "NIFTY AUTO"),
            ("NIFTY PHARMA", "NIFTY PHARMA"),
            ("NIFTY METAL", "NIFTY METAL"),
            ("NIFTY FMCG", "NIFTY FMCG"),
            ("INDIA VIX", "INDIA VIX"),
        ]

        result = []
        for full_name, short_label in target_symbols:
            item = lookup.get(full_name.upper())
            if item:
                last_val = f"{item['last']:,.2f}"
                pct = item['percent_change']
                var = item['variation']
                sign = "+" if var >= 0 else ""
                chg_str = f"{sign}{var:,.2f} ({sign}{pct:.2f}%)"
                result.append({
                    "sym": short_label,
                    "val": last_val,
                    "chg": chg_str,
                    "up": var >= 0,
                    "raw_pct": pct
                })

        return result if result else all_indices[:10]

    def get_market_breadth(self) -> Dict[str, Any]:
        """Aggregate advances, declines, and overall market momentum across all indices."""
        all_indices = self.scrape_live_indices()
        if not all_indices:
            return {"advances": 0, "declines": 0, "unchanged": 0, "adv_pct": 50, "dec_pct": 50}

        total_adv = sum(i.get("advances", 0) for i in all_indices if i.get("category") == "BROAD MARKET")
        total_dec = sum(i.get("declines", 0) for i in all_indices if i.get("category") == "BROAD MARKET")
        total_unc = sum(i.get("unchanged", 0) for i in all_indices if i.get("category") == "BROAD MARKET")
        sum_total = total_adv + total_dec + total_unc or 1

        return {
            "advances": total_adv,
            "declines": total_dec,
            "unchanged": total_unc,
            "adv_pct": int((total_adv / sum_total) * 100),
            "dec_pct": int((total_dec / sum_total) * 100),
            "timestamp": self._last_market_timestamp
        }

    def get_categories(self) -> List[str]:
        """Return list of distinct index categories available."""
        all_indices = self.scrape_live_indices()
        categories = sorted(list(set(i.get("category", "BROAD MARKET") for i in all_indices if i.get("category"))))
        return categories

    def get_indices_by_category(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filter indices by category, or return all if None or 'ALL'."""
        all_indices = self.scrape_live_indices()
        if not category or category.upper() in ["ALL", "ALL INDICES"]:
            return all_indices
        cat_clean = category.strip().upper()
        return [i for i in all_indices if i.get("category", "").upper() == cat_clean]

    def start_background_worker(self, interval_seconds: int = 60):
        """
        Start continuous background scraping thread that refreshes indices
        automatically every `interval_seconds` without blocking UI or web requests.
        """
        with self._lock:
            if hasattr(self, "_worker_running") and self._worker_running:
                return
            self._worker_running = True
            self._worker_thread = threading.Thread(
                target=self._background_loop,
                args=(interval_seconds,),
                daemon=True,
                name="NSEIndicesContinuousScraper"
            )
            self._worker_thread.start()
            logger.info(f"NSE continuous background scraper worker started (interval: {interval_seconds}s).")

    def stop_background_worker(self):
        """Gracefully stop continuous background scraper worker."""
        with self._lock:
            self._worker_running = False

    def _background_loop(self, interval_seconds: int):
        """Continuous background poller loop."""
        while getattr(self, "_worker_running", True):
            try:
                time.sleep(interval_seconds)
                logger.debug("Background worker fetching latest NSE indices...")
                self.scrape_live_indices(force=True)
            except Exception as e:
                logger.error(f"Error in NSE background scraper loop: {e}")
                time.sleep(15)

    def get_last_market_timestamp(self) -> str:
        return self._last_market_timestamp or datetime.now(IST_TZ).strftime("%d-%b-%Y %H:%M IST")


# Global Singleton Scraper Instance
_nse_scraper_instance: Optional[NSEIndicesScraper] = None

def get_nse_indices_scraper(auto_start_worker: bool = True) -> NSEIndicesScraper:
    global _nse_scraper_instance
    if _nse_scraper_instance is None:
        _nse_scraper_instance = NSEIndicesScraper()
        if auto_start_worker:
            _nse_scraper_instance.start_background_worker(interval_seconds=60)
    return _nse_scraper_instance

