from typing import List, Dict, Any
import streamlit as st
import pandas as pd


def render_news_feed(articles: List[Dict[str, Any]]):
    """
    Renders filterable, searchable data table of ingested articles with their analyzed sentiment.

    Args:
        articles (List[Dict[str, Any]]): Articles retrieved from DuckDB storage.
    """
    st.markdown("### 📰 Ingested News & Sentiment Stream")

    if not articles:
        st.info("No news articles in database. Click **'🚀 Scan & Analyze Live News'** above to fetch and analyze fresh feeds.")
        return

    # Search filter
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input("🔍 Filter news by headline, ticker, or source...", "")
    with col2:
        sentiment_filter = st.selectbox("Filter Sentiment", options=["All", "BULLISH", "BEARISH", "NEUTRAL"])

    filtered = articles
    if search_query:
        q = search_query.lower()
        filtered = [
            a for a in filtered
            if q in a.get("title", "").lower()
            or q in a.get("source", "").lower()
            or q in a.get("symbol", "").lower()
        ]

    if sentiment_filter != "All":
        filtered = [a for a in filtered if a.get("sentiment", "NEUTRAL").upper() == sentiment_filter]

    st.caption(f"Showing {len(filtered)} of {len(articles)} analyzed news articles")

    sentiment_icons = {
        "BULLISH": "🟢 Bullish",
        "BEARISH": "🔴 Bearish",
        "NEUTRAL": "🟡 Neutral"
    }

    display_rows = []
    for a in filtered:
        sent = a.get("sentiment", "NEUTRAL").upper()
        sent_label = sentiment_icons.get(sent, "🟡 Neutral")
        display_rows.append({
            "Published (UTC)": a.get("published_at", "")[:19].replace("T", " "),
            "Stock": a.get("symbol", "MARKET"),
            "Sentiment": sent_label,
            "Source": a.get("source", "RSS"),
            "Headline": a.get("title", ""),
            "URL": a.get("url", "")
        })

    df = pd.DataFrame(display_rows)
    st.dataframe(
        df,
        column_config={
            "URL": st.column_config.LinkColumn("Source Link", display_text="Read ↗"),
            "Headline": st.column_config.TextColumn("Headline", width="large"),
            "Stock": st.column_config.TextColumn("Stock", width="small"),
            "Sentiment": st.column_config.TextColumn("Sentiment", width="small")
        },
        hide_index=True,
        use_container_width=True
    )
