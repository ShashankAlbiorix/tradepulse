import streamlit as st
from config.tickers import TICKER_MAP, TrackedEntity


def render_ticker_view(symbol: str):
    """
    Renders deep-dive company profile, sector information, and tracked keywords.

    Args:
        symbol (str): Target stock symbol.
    """
    entity: TrackedEntity = TICKER_MAP.get(symbol.upper())

    if not entity:
        st.info(f"Ticker {symbol} profile not found in configuration.")
        return

    st.markdown(f"### 🏢 {entity.name} (`{entity.symbol}`)")
    st.markdown(f"**Sector:** {entity.sector}")

    with st.expander("🔍 Tracked Company Aliases & Catalyst Keywords", expanded=False):
        st.markdown(f"**Aliases:** {', '.join(entity.aliases)}")
        st.markdown(f"**Search Keywords:** {', '.join(entity.keywords)}")
