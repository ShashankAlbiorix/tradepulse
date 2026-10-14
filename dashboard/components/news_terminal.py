from typing import List, Dict, Any
import html
import textwrap
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
import streamlit as st


# Indian Standard Time (UTC+5:30)
IST_TZ = timezone(timedelta(hours=5, minutes=30))


def format_to_ist(date_str: str) -> str:
    """
    Convert UTC ISO date strings to user-friendly Indian Standard Time (IST).
    Example: '2026-10-07T12:50:41+00:00' -> '07 Oct, 06:20 PM IST'
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


def render_news_terminal(articles: List[Dict[str, Any]], search_query: str = "", sort_order: str = "Newest First", last_sync_time: str = None):
    """
    Renders an interactive, real-time financial news stream terminal
    displaying stories fetched from news providers with all badge boxes
    (Source, Sentiment, Stock, DateTime in IST) aligned at the right side top.
    """
    if not articles:
        st.info("💡 No news articles in database. Click **'⚡ Scan'** at the top right to fetch and analyze live feeds across all news providers.")
        return

    # 1. Boilerplate / Junk headline filter
    import re
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
        # Filter out stale archival stories from past months
        if "income plus arbitrage" in t_clean or "copycat passive mutual" in t_clean or "fpis retreat retail shifts" in t_clean:
            return True
        return False

    filtered = [a for a in articles if not is_junk_story(a.get("title", ""))]

    # 2. Apply Search Filter
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

    # 3. Apply Sort Order (Newest First vs Oldest First)
    is_reverse = (sort_order == "Newest First")
    filtered = sorted(filtered, key=lambda x: str(x.get("published_at", "")), reverse=is_reverse)

    # 4. Deduplicate identical headlines (e.g. stories syndicated across ET Markets and ET Stocks)
    import re
    deduped = []
    seen_titles = set()
    for a in filtered:
        norm_title = re.sub(r'[^a-z0-9]', '', a.get("title", "").lower().strip())
        if norm_title not in seen_titles:
            seen_titles.add(norm_title)
            deduped.append(a)
    filtered = deduped

    if not filtered:
        st.warning(f"No news articles matching '{search_query}'. Try searching for another keyword or clear the search bar.")
        return

    # 5. Live Auto-Fetch Status Bar
    current_ist_time = last_sync_time or datetime.now(IST_TZ).strftime("%I:%M:%S %p IST")
    status_bar_html = textwrap.dedent(f"""
    <div class="live-status-bar">
        <div class="live-status-left">
            <span class="live-pulse-dot"></span>
            <span class="live-status-text"><strong>LIVE NEWS STREAM</strong> &bull; Auto-fetch: <strong style="color: #10B981;">Every 1 min</strong> &bull; Last sync: <span class="live-time">{current_ist_time}</span></span>
        </div>
        <div class="live-status-right">
            <span class="live-count-badge">{len(filtered)} BREAKING STORIES</span>
        </div>
    </div>
    """)
    st.markdown(status_bar_html, unsafe_allow_html=True)


    # 6. Render High-Density Article Cards
    for a in filtered:
        title = html.escape(a.get("title", "No Title"))
        url = a.get("url", "#")
        source = html.escape(a.get("source", "RSS Feed"))
        raw_published_at = a.get("published_at", "")
        formatted_ist_time = format_to_ist(raw_published_at)
        summary = html.escape(a.get("summary", ""))
        symbol = a.get("symbol", "MARKET")
        sentiment = a.get("sentiment", "NEUTRAL").upper()
        confidence = int(a.get("confidence", 0.6) * 100)
        reasoning = html.escape(a.get("reasoning", ""))
        impact_category = html.escape(a.get("impact_category", ""))

        # Institutional Terminal Badges (TradingView / Linear style)
        if sentiment == "BULLISH":
            sent_class = "sentiment-bullish"
            sent_label = f"▲ BULLISH · {confidence}%"
        elif sentiment == "BEARISH":
            sent_class = "sentiment-bearish"
            sent_label = f"▼ BEARISH · {confidence}%"
        else:
            sent_class = "sentiment-neutral"
            sent_label = f"■ NEUTRAL · {confidence}%"

        impact_badge_html = f'<span class="source-badge">{impact_category}</span>' if impact_category else ""
        datetime_badge_html = f'<span class="datetime-badge">{formatted_ist_time}</span>'

        reasoning_html = (
            f'<div class="reasoning-box">'
            f'<span class="reasoning-tag">AI ANALYSIS</span> {reasoning}'
            f'</div>'
        ) if reasoning else ""

        card_html = textwrap.dedent(f"""
<div class="news-article-card">
<div class="news-card-meta-row">
<div class="news-card-badges-left">
<span class="source-badge">{source}</span>
<span class="{sent_class}">{sent_label}</span>
{impact_badge_html}
</div>
<div class="news-card-time-right">
{datetime_badge_html}
</div>
</div>
<div class="news-card-headline-row">
<a class="news-headline" href="{url}" target="_blank" rel="noopener noreferrer">{title} ↗</a>
</div>
<div class="news-summary">{summary}</div>
{reasoning_html}
</div>
""")
        st.markdown(card_html, unsafe_allow_html=True)
