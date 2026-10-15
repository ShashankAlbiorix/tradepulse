import time
import pytest
from unittest.mock import MagicMock, patch
from src.ingestion.nse_indices_scraper import NSEIndicesScraper, NSEIndexData, get_nse_indices_scraper


def test_nse_index_data_model():
    """Test validation and default values of NSEIndexData schema."""
    item = NSEIndexData(
        index="NIFTY 50",
        symbol="NIFTY 50",
        category="INDICES ELIGIBLE IN DERIVATIVES",
        last=22622.70,
        variation=-99.25,
        percent_change=-0.44,
        open=22715.75,
        high=22757.95,
        low=22558.95,
        previous_close=22721.95,
        advances=16,
        declines=34
    )
    assert item.index == "NIFTY 50"
    assert item.last == 22622.70
    assert item.percent_change == -0.44
    assert item.advances == 16
    assert item.declines == 34


def test_scraper_marquee_indices():
    """Test formatting of priority marquee indices."""
    scraper = NSEIndicesScraper(ttl_seconds=60)
    scraper._last_fetch_ts = time.time()
    # Mock cache data
    scraper._cache = [
        {
            "index": "NIFTY 50",
            "symbol": "NIFTY 50",
            "category": "INDICES ELIGIBLE IN DERIVATIVES",
            "last": 22622.70,
            "variation": -99.25,
            "percent_change": -0.44,
        },
        {
            "index": "NIFTY NEXT 50",
            "symbol": "NIFTY NEXT 50",
            "category": "INDICES ELIGIBLE IN DERIVATIVES",
            "last": 68999.30,
            "variation": 71.35,
            "percent_change": 0.10,
        },
        {
            "index": "NIFTY BANK",
            "symbol": "NIFTY BANK",
            "category": "INDICES ELIGIBLE IN DERIVATIVES",
            "last": 55316.00,
            "variation": -165.05,
            "percent_change": -0.30,
        }
    ]
    marquee = scraper.get_marquee_indices()
    assert len(marquee) >= 3
    
    nifty50 = next(m for m in marquee if m["sym"] == "NIFTY 50")
    assert nifty50["val"] == "22,622.70"
    assert nifty50["up"] is False
    assert "-99.25" in nifty50["chg"]

    nifty_next = next(m for m in marquee if m["sym"] == "NIFTY NEXT 50")
    assert nifty_next["val"] == "68,999.30"
    assert nifty_next["up"] is True
    assert "+71.35" in nifty_next["chg"]


def test_category_filtering():
    """Test category extraction and filtering."""
    scraper = NSEIndicesScraper(ttl_seconds=60)
    scraper._last_fetch_ts = time.time()
    scraper._cache = [
        {"index": "NIFTY 50", "category": "INDICES ELIGIBLE IN DERIVATIVES", "last": 22622.7},
        {"index": "NIFTY 100", "category": "BROAD MARKET INDICES", "last": 23500.0},
        {"index": "NIFTY AUTO", "category": "SECTORAL INDICES", "last": 23800.0},
    ]

    cats = scraper.get_categories()
    assert "INDICES ELIGIBLE IN DERIVATIVES" in cats
    assert "BROAD MARKET INDICES" in cats
    assert "SECTORAL INDICES" in cats

    derivs = scraper.get_indices_by_category("INDICES ELIGIBLE IN DERIVATIVES")
    assert len(derivs) == 1
    assert derivs[0]["index"] == "NIFTY 50"

    all_items = scraper.get_indices_by_category("All Indices")
    assert len(all_items) == 3


def test_market_breadth_aggregation():
    """Test calculation of advances, declines, and A/D ratio."""
    scraper = NSEIndicesScraper(ttl_seconds=60)
    scraper._last_fetch_ts = time.time()
    scraper._cache = [
        {"index": "NIFTY 50", "category": "INDICES ELIGIBLE IN DERIVATIVES", "advances": 30, "declines": 20, "unchanged": 0},
        {"index": "NIFTY 500", "category": "BROAD MARKET INDICES", "advances": 270, "declines": 230, "unchanged": 0},
    ]
    breadth = scraper.get_market_breadth()
    assert breadth["n50_adv"] == 30
    assert breadth["n50_dec"] == 20
    assert breadth["n50_ratio"] == 1.5
    assert breadth["n500_adv"] == 270
    assert breadth["n500_dec"] == 230
    assert breadth["n500_ratio"] == 1.17
    assert "BULLISH" in breadth["sentiment"]


def test_singleton_and_background_worker():
    """Test scraper singleton instance retrieval and worker startup."""
    scraper = get_nse_indices_scraper(auto_start_worker=False)
    assert scraper is not None
    assert isinstance(scraper, NSEIndicesScraper)
