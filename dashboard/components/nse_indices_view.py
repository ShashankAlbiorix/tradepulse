import html
import streamlit as st
from typing import List, Dict, Any, Optional
from src.ingestion.nse_indices_scraper import get_nse_indices_scraper


def clean_html(raw_html: str) -> str:
    """Strips leading whitespace from lines to prevent Streamlit codeblock interpretation."""
    return "\n".join(line.strip() for line in raw_html.strip().splitlines() if line.strip())


def render_sectoral_indices_heatmap():
    """
    Renders an institutional Sectoral Indices Heatmap Card Matrix (23 indices)
    matching the exact NSE website layout (https://www.nseindia.com/market-data/live-market-indices/heatmap).
    """
    scraper = get_nse_indices_scraper()
    sectoral_indices = scraper.get_sectoral_indices()
    market_ts = scraper.get_last_market_timestamp()

    if not sectoral_indices:
        return

    # Generate 23 Sectoral Cards
    cards_html = ""
    for item in sectoral_indices:
        sym = html.escape(str(item.get("sym", "")))
        val = html.escape(str(item.get("val", "")))
        pct = item.get("pct", 0.0)
        tier = item.get("tier", "tier-p1")
        sign = "+" if pct >= 0 else ""
        pct_display = f"{sign}{pct:.2f}%"

        cards_html += f"""
<div class="sector-card sector-{tier}">
    <div class="sector-card-name" title="{html.escape(item.get('full_name', sym))}">{sym}</div>
    <div class="sector-card-bottom">
        <span class="sector-card-val">{val}</span>
        <span class="sector-card-pct">{pct_display}</span>
    </div>
</div>
"""

    heatmap_html = f"""
<div class="sectoral-heatmap-wrapper">
    <div class="sectoral-heatmap-header">
        <div class="sectoral-title-box">
            <span class="sectoral-title-text">Sectoral Indices</span>
            <span class="sectoral-count-badge">23 Live</span>
            <span class="ticker-beacon"></span>
            <span style="font-size: 0.72rem; color: #94A3B8; font-family: 'JetBrains Mono', monospace;">Real-time from NSE India · As on {html.escape(market_ts)} IST</span>
        </div>
        <div class="sectoral-legend">
            <span class="legend-pill legend-p5">5</span>
            <span class="legend-pill legend-p3">3</span>
            <span class="legend-pill legend-p1">1</span>
            <span class="legend-pill legend-zero">0%</span>
            <span class="legend-pill legend-n1">-1</span>
            <span class="legend-pill legend-n3">-3</span>
            <span class="legend-pill legend-n5">-5</span>
        </div>
    </div>
    <div class="sectoral-grid">
        {cards_html}
    </div>
</div>
"""
    st.markdown(clean_html(heatmap_html), unsafe_allow_html=True)


def render_market_ticker(category: str = "SECTORAL"):
    """
    Renders continuous Marquee Ticker Ribbon displaying SECTORAL INDICES (23) · LIVE real-time from NSE.
    """
    scraper = get_nse_indices_scraper()
    
    if category and category.upper() in ["SECTORAL", "SECTORAL INDICES"]:
        indices = scraper.get_sectoral_indices()
        status_label = f"SECTORAL INDICES ({len(indices)}) · LIVE"
        marquee_class = "ticker-items-container-sectoral"
    else:
        indices = scraper.get_marquee_indices(include_all=True)
        status_label = f"ALL {len(indices)} INDICES · LIVE"
        marquee_class = "ticker-items-container"


    # 2. Continuous Marquee Ticker Ribbon with Live Sectoral Indices (Bottom)
    items_html = ""
    for idx in indices:
        is_up = idx.get("up", True)
        chg_class = "ticker-up" if is_up else "ticker-down"
        arrow = "▲" if is_up else "▼"
        sym = html.escape(str(idx.get("sym", "")))
        val = html.escape(str(idx.get("val", "")))
        chg = html.escape(str(idx.get("chg", "")))
        items_html += f'<div class="ticker-item"><span class="ticker-sym">{sym}</span><span class="ticker-val">{val}</span><span class="{chg_class}">{arrow} {chg}</span></div>'

    # Duplicate items for unbroken continuous horizontal CSS marquee loop
    duplicated_items = items_html + items_html

    ticker_ribbon_html = f"""
<div class="market-ticker-ribbon">
<div class="ticker-status-pill">
<span class="ticker-beacon"></span>
{status_label}
</div>
<div class="{marquee_class}">
{duplicated_items}
</div>
</div>
"""
    st.markdown(clean_html(ticker_ribbon_html), unsafe_allow_html=True)

