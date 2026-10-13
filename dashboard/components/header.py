from datetime import datetime, timezone
import streamlit as st
from src.utils.market_calendar import MarketCalendar


def render_header(total_articles: int = 0, avg_bullish_pct: float = 60.0, providers_count: int = 5):
    """
    Renders top navigation banner with market session indicator and live news telemetry.
    """
    session_details = MarketCalendar.get_session_details()
    session_name = session_details.get("session", "REGULAR")
    is_open = session_details.get("is_trading_open", True)
    
    st.markdown("## 🌐 Global & Indian Markets News Intelligence")
    st.caption("Real-time automated news ingestion across major financial media with AI sentiment & catalyst extraction.")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Market Session",
            value=session_name.replace("_", " "),
            delta="Market Open" if is_open else "Closed"
        )
    with col2:
        st.metric(
            label="Latest News Ingested",
            value=f"{total_articles} Articles",
            delta="Live Stream" if total_articles > 0 else "0"
        )
    with col3:
        st.metric(
            label="News Sentiment Bias",
            value=f"{avg_bullish_pct:.0f}% Bullish",
            delta="Positive" if avg_bullish_pct >= 50 else "Bearish / Cautious"
        )
    with col4:
        st.metric(
            label="Active News Providers",
            value=f"{providers_count} Providers",
            delta="9 Live Feeds"
        )

    st.divider()
