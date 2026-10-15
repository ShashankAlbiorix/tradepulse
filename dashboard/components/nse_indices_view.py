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
    Renders an institutional trading terminal header consisting of:
    1. Top Advance / Decline Ratio Strip (NIFTY 500 & NIFTY 50 breadth metrics, ratios, and micro-meters).
    2. Continuous Marquee Ticker Ribbon displaying SECTORAL INDICES (23) · LIVE real-time from NSE.
    3. Collapsible / Toggleable Sectoral Indices Heatmap Card Matrix.
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

    breadth = scraper.get_market_breadth()
    market_ts = scraper.get_last_market_timestamp()

    # 1. Advance / Decline Ratio Header Strip (Top)
    n500_adv = breadth.get("n500_adv", 240)
    n500_dec = breadth.get("n500_dec", 260)
    n500_ratio = breadth.get("n500_ratio", 0.92)
    n500_adv_pct = breadth.get("n500_adv_pct", 48.0)
    n500_dec_pct = breadth.get("n500_dec_pct", 52.0)

    n50_adv = breadth.get("n50_adv", 16)
    n50_dec = breadth.get("n50_dec", 34)
    n50_ratio = breadth.get("n50_ratio", 0.47)
    n50_adv_pct = breadth.get("n50_adv_pct", 32.0)
    n50_dec_pct = breadth.get("n50_dec_pct", 68.0)

    sentiment = breadth.get("sentiment", "BALANCED / NEUTRAL")
    sentiment_color = "#34D399" if "BULLISH" in sentiment else ("#F87171" if "BEARISH" in sentiment else "#38BDF8")

    breadth_header_html = f"""
<div class="market-breadth-container">
<div class="breadth-left-block">
<span class="breadth-badge-beacon"></span>
<span>NSE MARKET BREADTH</span>
<span style="color: {sentiment_color}; font-size: 0.70rem; font-weight: 700; background: rgba(255,255,255,0.06); padding: 2px 7px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.08);">{sentiment}</span>
</div>
<div class="breadth-stats-row">
<div class="breadth-chip">
<span class="chip-title">NIFTY 500 A/D:</span>
<span class="chip-adv">▲ {n500_adv}</span>
<span class="chip-dec">▼ {n500_dec}</span>
<span class="chip-ratio">Ratio: {n500_ratio:.2f}</span>
<div class="breadth-micro-bar">
<div class="fill-adv" style="width: {n500_adv_pct}%;"></div>
<div class="fill-dec" style="width: {n500_dec_pct}%;"></div>
</div>
</div>
<div class="breadth-chip">
<span class="chip-title">NIFTY 50 A/D:</span>
<span class="chip-adv">▲ {n50_adv}</span>
<span class="chip-dec">▼ {n50_dec}</span>
<span class="chip-ratio">Ratio: {n50_ratio:.2f}</span>
<div class="breadth-micro-bar">
<div class="fill-adv" style="width: {n50_adv_pct}%;"></div>
<div class="fill-dec" style="width: {n50_dec_pct}%;"></div>
</div>
</div>
<span class="breadth-time-pill">⏱️ As on {html.escape(market_ts)} IST</span>
</div>
</div>
"""

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
{breadth_header_html}
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

