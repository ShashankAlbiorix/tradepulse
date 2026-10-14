import html
import streamlit as st
from typing import List, Dict, Any
from src.ingestion.nse_indices_scraper import get_nse_indices_scraper


def clean_html(raw_html: str) -> str:
    """Strips leading whitespace from lines to prevent Streamlit codeblock interpretation."""
    return "\n".join(line.strip() for line in raw_html.strip().splitlines() if line.strip())


def render_market_ticker():
    """
    Renders an institutional stock market ticker ribbon with live Indian benchmarks
    scraped continuously from NSE India (nseindia.com/market-data/live-market-indices).
    """
    scraper = get_nse_indices_scraper()
    indices = scraper.get_marquee_indices()
    market_ts = scraper.get_last_market_timestamp()

    items_html = ""
    for idx in indices:
        is_up = idx.get("up", True)
        chg_class = "ticker-up" if is_up else "ticker-down"
        arrow = "▲" if is_up else "▼"
        sym = html.escape(str(idx.get("sym", "")))
        val = html.escape(str(idx.get("val", "")))
        chg = html.escape(str(idx.get("chg", "")))
        items_html += f'<div class="ticker-item"><span class="ticker-sym">{sym}</span><span class="ticker-val">{val}</span><span class="{chg_class}">{arrow} {chg}</span></div>'

    # Duplicate items for continuous seamless horizontal CSS marquee loop
    duplicated_items = items_html + items_html

    ticker_ribbon_html = f"""
<div class="market-ticker-ribbon">
<div class="ticker-status-pill">
<span class="ticker-beacon"></span>
LIVE NSE · {html.escape(market_ts)}
</div>
<div class="ticker-items-container">
{duplicated_items}
</div>
</div>
"""
    st.markdown(clean_html(ticker_ribbon_html), unsafe_allow_html=True)


def render_nse_indices_explorer():
    """
    Interactive Live NSE Indices Explorer matching the exact layout and data
    from https://www.nseindia.com/market-data/live-market-indices.
    Features:
    - Real-time continuous scraping of all 139+ NSE indices
    - Category filtering (Derivatives Eligible, Broad Market, Sectoral, Thematic, etc.)
    - Instant live text search filter
    - Market breadth (advances/declines) statistics
    - Manual force refresh button
    """
    scraper = get_nse_indices_scraper()
    all_indices = scraper.scrape_live_indices()
    market_ts = scraper.get_last_market_timestamp()
    breadth = scraper.get_market_breadth()
    categories = scraper.get_categories()

    # Prepend 'All Indices' and ensure 'INDICES ELIGIBLE IN DERIVATIVES' is prominent
    cat_options = ["All Indices"] + categories
    default_cat_idx = 0
    if "INDICES ELIGIBLE IN DERIVATIVES" in cat_options:
        default_cat_idx = cat_options.index("INDICES ELIGIBLE IN DERIVATIVES")

    with st.expander(f"📊 Live NSE Market Indices Explorer ({len(all_indices)} Indices • As on {market_ts})", expanded=False):
        # 1. Header Action & Controls Bar
        col_cat, col_search, col_ref = st.columns([4.2, 4.0, 1.8], gap="small")

        with col_cat:
            selected_cat = st.selectbox(
                "Category",
                options=cat_options,
                index=default_cat_idx,
                label_visibility="collapsed",
                key="nse_category_select"
            )

        with col_search:
            search_term = st.text_input(
                "Search",
                placeholder="Search index (e.g. NIFTY 50, BANK, IT, AUTO)...",
                label_visibility="collapsed",
                key="nse_index_search"
            )

        with col_ref:
            if st.button("🔄 Refresh Live", use_container_width=True, key="nse_force_refresh_btn", help="Fetch fresh real-time data from nseindia.com"):
                with st.spinner("Fetching latest live indices from NSE..."):
                    scraper.scrape_live_indices(force=True)
                st.toast("✅ Scraped latest live indices from NSE India!", icon="📈")
                st.rerun()

        # 2. Filter Indices
        filtered = all_indices
        if selected_cat and selected_cat != "All Indices":
            filtered = [i for i in filtered if i.get("category") == selected_cat]

        if search_term and search_term.strip():
            q = search_term.strip().lower()
            filtered = [i for i in filtered if q in i.get("index", "").lower() or q in i.get("symbol", "").lower()]

        # 3. Market Breadth & Meta Strip
        adv_val = breadth.get("advances", 0)
        dec_val = breadth.get("declines", 0)
        unc_val = breadth.get("unchanged", 0)

        meta_html = f"""
<div class="nse-meta-bar">
<div class="nse-meta-title">
<span style="color:#10B981; font-size:1.1rem;">●</span>
<span>NSE LIVE MARKET INDICES</span>
<span style="color: #64748B; font-size: 0.76rem; font-weight: normal;">• Source: nseindia.com • Showing {len(filtered)} of {len(all_indices)} indices</span>
</div>
<div class="nse-meta-stats">
<span style="color: #34D399;">▲ Adv: <strong>{adv_val}</strong></span>
<span style="color: #F87171;">▼ Dec: <strong>{dec_val}</strong></span>
<span style="color: #94A3B8;">— Unch: <strong>{unc_val}</strong></span>
<span class="live-time">As on {html.escape(market_ts)} IST</span>
</div>
</div>
"""
        st.markdown(clean_html(meta_html), unsafe_allow_html=True)

        if not filtered:
            st.info(f"No indices found matching '{search_term}'. Try clearing your search query.")
            return

        # 4. Institutional Cyber-Glass Data Table
        table_rows_html = ""
        for item in filtered:
            name = html.escape(item.get("index", ""))
            last = f"{item.get('last', 0.0):,.2f}"
            pct = item.get("percent_change", 0.0)
            var = item.get("variation", 0.0)
            sign = "+" if var >= 0 else ""
            var_str = f"{sign}{var:,.2f}"
            pct_str = f"{sign}{pct:.2f}%"

            is_up = var >= 0
            val_cls = "val-up" if is_up else "val-down"
            badge_cls = "badge-up" if is_up else "badge-down"

            open_val = f"{item.get('open', 0.0):,.2f}" if item.get('open') else "-"
            high_val = f"{item.get('high', 0.0):,.2f}" if item.get('high') else "-"
            low_val = f"{item.get('low', 0.0):,.2f}" if item.get('low') else "-"
            prev_val = f"{item.get('previous_close', 0.0):,.2f}" if item.get('previous_close') else "-"
            y_high = f"{item.get('year_high', 0.0):,.2f}" if item.get('year_high') else "-"
            y_low = f"{item.get('year_low', 0.0):,.2f}" if item.get('year_low') else "-"
            pe_val = html.escape(str(item.get('pe', '-')))
            adv = item.get('advances', 0)
            dec = item.get('declines', 0)

            table_rows_html += f"""
<tr>
<td><span style="color: #F8FAFC; font-weight:700;">{name}</span></td>
<td class="{val_cls}">{last}</td>
<td><span class="{badge_cls}">{pct_str}</span></td>
<td class="{val_cls}">{var_str}</td>
<td>{open_val}</td>
<td style="color:#34D399;">{high_val}</td>
<td style="color:#F87171;">{low_val}</td>
<td>{prev_val}</td>
<td>{y_high}</td>
<td>{y_low}</td>
<td><span style="color:#34D399;">{adv}</span> / <span style="color:#F87171;">{dec}</span></td>
<td>{pe_val}</td>
</tr>
"""

        table_container_html = f"""
<div class="nse-table-wrapper">
<table class="nse-indices-table">
<thead>
<tr>
<th>INDEX</th>
<th>CURRENT</th>
<th>% CHANGE</th>
<th>CHANGE (PTS)</th>
<th>OPEN</th>
<th>HIGH</th>
<th>LOW</th>
<th>PREV. CLOSE</th>
<th>52W HIGH</th>
<th>52W LOW</th>
<th>ADV / DEC</th>
<th>P/E</th>
</tr>
</thead>
<tbody>
{table_rows_html}
</tbody>
</table>
</div>
"""
        st.markdown(clean_html(table_container_html), unsafe_allow_html=True)
