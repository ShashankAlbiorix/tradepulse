from typing import List, Dict, Any
import html
import re
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
import streamlit as st


# Indian Standard Time (UTC+5:30)
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def clean_html(raw_html: str) -> str:
    """
    Strips leading and trailing whitespace from every line to ensure
    Streamlit markdown never interprets indented lines as markdown code blocks.
    """
    return "\n".join(line.strip() for line in raw_html.strip().splitlines() if line.strip())


def format_to_ist(date_str: str) -> str:
    """
    Convert UTC ISO date strings to user-friendly Indian Standard Time (IST).
    Example: '2026-10-07T12:50:41+00:00' -> '07 Oct 2026, 06:20 PM IST'
    """
    if not date_str:
        return ""
    try:
        dt = date_parser.parse(date_str)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(IST_TZ)
        return ist_dt.strftime("%d %b %Y, %I:%M %p IST")
    except Exception:
        return date_str[:19].replace("T", " ") + " IST"


from dashboard.components.nse_indices_view import render_market_ticker


def get_source_badge_class(source_name: str) -> str:
    """Returns publisher-specific branded badge class."""
    s = (source_name or "").lower()
    if "livemint" in s or "mint" in s:
        return "source-badge source-livemint"
    elif "economic times" in s or "et " in s or s.startswith("et"):
        return "source-badge source-et"
    elif "moneycontrol" in s:
        return "source-badge source-moneycontrol"
    elif "business standard" in s:
        return "source-badge source-bs"
    elif "ndtv" in s:
        return "source-badge source-ndtv"
    return "source-badge"


def render_news_terminal(articles: List[Dict[str, Any]], search_query: str = "", sort_order: str = "Newest First", last_sync_time: str = None):
    """
    Renders an interactive, real-time financial news stream terminal
    designed for stock market traders with market indicators, sentiment barometer,
    quick filter chips, and high-contrast readable typography.
    """
    if not articles:
        st.info("💡 No news articles in database. Click **'⚡ Fetch Now'** at the top right to fetch and analyze live feeds across all news providers.")
        return

    # 1. Market Breadth Advance/Decline Strip & Live Ticker Marquee (All 139 Indices)
    render_market_ticker()

    # 2. Boilerplate / Junk headline filter
    junk_headers = [
        "from the house of hindustan times", "trending stories", "top stories",
        "live events", "market dashboard", "quick reads", "most popular",
        "latest news", "web stories", "mint epaper", "subscribe to mint",
        "view all stories", "stock market live", "todays top news"
    ]
    def is_junk_story(title_text: str) -> bool:
        t_clean = re.sub(r'[^a-z0-9 ]', '', (title_text or "").lower()).strip()
        if len(t_clean) < 18:
            return True
        for junk in junk_headers:
            if junk in t_clean and len(t_clean) < 45:
                return True
        if "income plus arbitrage" in t_clean or "copycat passive mutual" in t_clean or "fpis retreat retail shifts" in t_clean:
            return True
        return False

    filtered = [a for a in articles if not is_junk_story(a.get("title", ""))]

    # 3. Deduplicate identical headlines (e.g. stories syndicated across multiple sections)
    deduped = []
    seen_titles = set()
    for a in filtered:
        norm_title = re.sub(r'[^a-z0-9]', '', a.get("title", "").lower().strip())
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            deduped.append(a)
    filtered = deduped

    # 4. Compute Sentiment Metrics for the Barometer
    total_active = len(filtered)
    bull_count = sum(1 for a in filtered if a.get("sentiment", "").upper() == "BULLISH")
    bear_count = sum(1 for a in filtered if a.get("sentiment", "").upper() == "BEARISH")
    neut_count = sum(1 for a in filtered if a.get("sentiment", "").upper() not in ["BULLISH", "BEARISH"])

    bull_pct = int((bull_count / total_active) * 100) if total_active > 0 else 0
    bear_pct = int((bear_count / total_active) * 100) if total_active > 0 else 0
    neut_pct = max(0, 100 - bull_pct - bear_pct) if total_active > 0 else 0

    if bull_pct >= 40:
        stance_text = "🟢 MODERATE BULLISH BIAS"
        stance_color = "#10B981"
    elif bear_pct >= 30:
        stance_text = "🔴 BEARISH CAUTION"
        stance_color = "#EF4444"
    else:
        stance_text = "🟡 BALANCED / NEUTRAL"
        stance_color = "#38BDF8"

    # 5. Render Market Sentiment Barometer & KPI Dashboard
    kpi_html = f"""
<div class="market-pulse-kpi-grid">
<div class="kpi-tile">
<div class="kpi-header">
<span>ACTIVE STORIES</span>
<span>📰 FEEDS</span>
</div>
<div class="kpi-main-stat">{total_active}</div>
<div class="kpi-sub-stat" style="color: #94A3B8;">Across 5 Tier-1 Providers</div>
</div>

<div class="kpi-tile">
<div class="kpi-header">
<span>BULLISH CATALYSTS</span>
<span style="color: #10B981;">▲ {bull_pct}%</span>
</div>
<div class="kpi-main-stat" style="color: #10B981;">{bull_count} <span style="font-size: 0.9rem; color: #34D399;">STORIES</span></div>
<div class="kpi-sub-stat" style="color: #34D399;">Upside Momentum Detected</div>
</div>

<div class="kpi-tile">
<div class="kpi-header">
<span>BEARISH HEADWINDS</span>
<span style="color: #EF4444;">▼ {bear_pct}%</span>
</div>
<div class="kpi-main-stat" style="color: #EF4444;">{bear_count} <span style="font-size: 0.9rem; color: #F87171;">STORIES</span></div>
<div class="kpi-sub-stat" style="color: #F87171;">Downside Risk / Macro Drag</div>
</div>

<div class="kpi-tile">
<div class="kpi-header">
<span>MARKET PULSE STANCE</span>
<span style="color: {stance_color};">● CONSENSUS</span>
</div>
<div class="kpi-main-stat" style="font-size: 1.12rem; color: {stance_color}; line-height: 1.3;">
{stance_text}
</div>
<div class="sentiment-barometer-track">
<div class="barometer-seg-bull" style="width: {bull_pct}%;"></div>
<div class="barometer-seg-neut" style="width: {neut_pct}%;"></div>
<div class="barometer-seg-bear" style="width: {bear_pct}%;"></div>
</div>
</div>
</div>
"""
    st.markdown(clean_html(kpi_html), unsafe_allow_html=True)

    # 6. Active Trader Filter Chips (Sentiment & Sources)
    col_filter_sent, col_filter_src = st.columns([1.1, 1.3], gap="small")

    with col_filter_sent:
        sentiment_filter = st.pills(
            "Sentiment Filter",
            options=["All Stories", "🟢 Bullish Only", "🔴 Bearish Only", "🟡 Neutral Only"],
            default="All Stories",
            label_visibility="collapsed",
            key="terminal_sentiment_filter"
        )

    with col_filter_src:
        source_filter = st.pills(
            "Source Filter",
            options=["All Sources", "LiveMint", "Economic Times", "Moneycontrol", "NDTV Profit", "Business Standard"],
            default="All Sources",
            label_visibility="collapsed",
            key="terminal_source_filter"
        )

    # 7. Apply Sentiment & Source Filters
    if sentiment_filter == "🟢 Bullish Only":
        filtered = [a for a in filtered if a.get("sentiment", "").upper() == "BULLISH"]
    elif sentiment_filter == "🔴 Bearish Only":
        filtered = [a for a in filtered if a.get("sentiment", "").upper() == "BEARISH"]
    elif sentiment_filter == "🟡 Neutral Only":
        filtered = [a for a in filtered if a.get("sentiment", "").upper() not in ["BULLISH", "BEARISH"]]

    if source_filter and source_filter != "All Sources":
        s_target = source_filter.lower()
        filtered = [a for a in filtered if s_target in a.get("source", "").lower()]

    # 8. Apply Search Filter
    if search_query:
        q = search_query.lower().strip()
        filtered = [
            a for a in filtered
            if q in a.get("title", "").lower()
            or q in a.get("summary", "").lower()
            or q in a.get("source", "").lower()
            or q in a.get("symbol", "").lower()
            or q in a.get("sentiment", "").lower()
            or q in a.get("reasoning", "").lower()
        ]

    # 9. Apply Sort Order (Newest First vs Oldest First)
    is_reverse = (sort_order == "Newest First")
    filtered = sorted(filtered, key=lambda x: str(x.get("published_at", "")), reverse=is_reverse)

    if not filtered:
        st.warning(f"No news articles matching current filters. Try resetting search or filter pills.")
        return

    # 10. Live Auto-Fetch Status Bar
    current_ist_time = last_sync_time or datetime.now(IST_TZ).strftime("%I:%M:%S %p IST")
    status_bar_html = f"""
<div class="live-status-bar">
<div class="live-status-left">
<span class="live-pulse-dot"></span>
<span class="live-status-text"><strong>LIVE NEWS STREAM</strong> &bull; Auto-fetch: <strong style="color: #10B981;">Every 1 min</strong> &bull; Last sync: <span class="live-time">{current_ist_time}</span></span>
</div>
<div class="live-status-right">
<span class="live-count-badge">{len(filtered)} FILTERED STORIES</span>
</div>
</div>
"""
    st.markdown(clean_html(status_bar_html), unsafe_allow_html=True)

    # 11. Render High-Density Article Cards
    for a in filtered:
        title = html.escape(a.get("title", "No Title"))
        url = a.get("url", "#")
        source = html.escape(a.get("source", "Financial News"))
        source_class = get_source_badge_class(a.get("source", ""))
        raw_published_at = a.get("published_at", "")
        formatted_ist_time = format_to_ist(raw_published_at)
        summary_raw = a.get("summary", "").strip()
        symbol = a.get("symbol", "MARKET")
        sentiment = a.get("sentiment", "NEUTRAL").upper()
        confidence = int(a.get("confidence", 0.6) * 100)
        reasoning = html.escape(a.get("reasoning", ""))
        impact_category = html.escape(a.get("impact_category", ""))

        # Check if summary is meaningful and not a duplicate of headline
        clean_summary = ""
        if summary_raw and summary_raw.lower() != a.get("title", "").strip().lower() and len(summary_raw) > 12:
            clean_summary = html.escape(summary_raw)

        # Style by Sentiment
        if sentiment == "BULLISH":
            card_class = "news-article-card card-bullish"
            sent_class = "sentiment-bullish"
            sent_label = f"▲ BULLISH · {confidence}%"
            reasoning_box_class = "reasoning-box reasoning-bullish"
            reasoning_tag = '<span class="reasoning-tag">⚡ FINBERT CATALYST</span>'
        elif sentiment == "BEARISH":
            card_class = "news-article-card card-bearish"
            sent_class = "sentiment-bearish"
            sent_label = f"▼ BEARISH · {confidence}%"
            reasoning_box_class = "reasoning-box reasoning-bearish"
            reasoning_tag = '<span class="reasoning-tag tag-bearish">⚠️ FINBERT RISK SIGNAL</span>'
        else:
            card_class = "news-article-card card-neutral"
            sent_class = "sentiment-neutral"
            sent_label = f"■ NEUTRAL · {confidence}%"
            reasoning_box_class = "reasoning-box reasoning-neutral"
            reasoning_tag = '<span class="reasoning-tag tag-neutral">ℹ️ NEURAL ANALYSIS</span>'

        symbol_badge_html = f'<span class="ticker-tag-badge">📌 {html.escape(symbol)}</span>' if symbol and symbol != "MARKET" else ""
        impact_badge_html = f'<span class="source-badge">{impact_category}</span>' if impact_category else ""
        datetime_badge_html = f'<span class="datetime-badge">🕒 {formatted_ist_time}</span>'

        summary_html = f'<div class="news-summary">{clean_summary}</div>' if clean_summary else ""

        reasoning_html = (
            f'<div class="{reasoning_box_class}">'
            f'{reasoning_tag} {reasoning}'
            f'</div>'
        ) if reasoning else ""

        card_html = f"""
<div class="{card_class}">
<div class="news-card-meta-row">
<div class="news-card-badges-left">
<span class="{source_class}">{source}</span>
<span class="{sent_class}">{sent_label}</span>
{symbol_badge_html}
{impact_badge_html}
</div>
<div class="news-card-time-right">
{datetime_badge_html}
</div>
</div>
<div class="news-card-headline-row">
<a class="news-headline" href="{url}" target="_blank" rel="noopener noreferrer">{title} ↗</a>
</div>
{summary_html}
{reasoning_html}
</div>
"""
        st.markdown(clean_html(card_html), unsafe_allow_html=True)
