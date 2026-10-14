import html
import streamlit as st
from typing import List, Dict, Any
from src.ingestion.nse_indices_scraper import get_nse_indices_scraper


def clean_html(raw_html: str) -> str:
    """Strips leading whitespace from lines to prevent Streamlit codeblock interpretation."""
    return "\n".join(line.strip() for line in raw_html.strip().splitlines() if line.strip())


def render_market_ticker():
    """
    Renders an institutional trading terminal header consisting of:
    1. Top Advance / Decline Ratio Strip (NIFTY 500 & NIFTY 50 breadth metrics, ratios, and micro-meters).
    2. Continuous Marquee Ticker Ribbon displaying ALL 139 live NSE market indices.
    """
    scraper = get_nse_indices_scraper()
    try:
        indices = scraper.get_marquee_indices(include_all=True)
    except TypeError:
        indices = scraper.get_marquee_indices()
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

    # 2. Continuous Marquee Ticker Ribbon with ALL 139 Indices (Bottom)
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
ALL {len(indices)} INDICES · LIVE
</div>
<div class="ticker-items-container">
{duplicated_items}
</div>
</div>
"""
    st.markdown(clean_html(ticker_ribbon_html), unsafe_allow_html=True)
