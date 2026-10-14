import os
import sys
import time
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict
import streamlit as st

IST_TZ = timezone(timedelta(hours=5, minutes=30))
AUTO_FETCH_INTERVAL_SECONDS = 60  # 1 minute


# Ensure repository root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import importlib
import src.ingestion.web_scraper as web_scraper_mod
import src.ingestion.rss_fetcher as rss_fetcher_mod
import src.agent.workflow as workflow_mod
import dashboard.components.news_terminal as news_terminal_module
import dashboard.components.url_analyzer as url_analyzer_module
import dashboard.components.article_scraper_view as article_scraper_module
import dashboard.components.nse_indices_view as nse_indices_view_module

importlib.reload(web_scraper_mod)
importlib.reload(rss_fetcher_mod)
importlib.reload(workflow_mod)
importlib.reload(news_terminal_module)
importlib.reload(url_analyzer_module)
importlib.reload(article_scraper_module)
importlib.reload(nse_indices_view_module)

NewsAnalysisWorkflow = workflow_mod.NewsAnalysisWorkflow
from src.storage.database import DatabaseManager
render_news_terminal = news_terminal_module.render_news_terminal
render_url_analyzer = url_analyzer_module.render_url_analyzer
render_article_scraper_view = article_scraper_module.render_article_scraper_view



# Configure Streamlit page layout
st.set_page_config(
    page_title="TradePulse",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Inject custom CSS styles
css_path = os.path.join(os.path.dirname(__file__), "styles.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


@st.cache_resource
def get_db():
    """Singleton database manager instance."""
    return DatabaseManager()


@st.cache_resource
def get_workflow():
    """Singleton LangGraph workflow instance."""
    return NewsAnalysisWorkflow(db=get_db())


def run_ingestion_pipeline(workflow):
    """Execute news scraping and LangGraph pipeline, updating database with fresh news stories."""
    with st.spinner("🤖 Fetching live financial feeds and computing neural sentiment..."):
        try:
            final_state = asyncio.run(workflow.run())
            new_count = len(final_state.get("new_articles", []))
            st.session_state["last_auto_fetch_ts"] = time.time()
            st.session_state["last_auto_fetch_time"] = datetime.now(IST_TZ).strftime("%I:%M:%S %p IST")
            if new_count > 0:
                st.toast(f"✅ Ingested & analyzed {new_count} latest breaking news stories via FinBERT!", icon="📰")
            st.rerun()
        except Exception as e:
            st.error(f"Execution failed: {str(e)}")


@st.fragment(run_every=60)
def render_live_news_stream(workflow, db, search_query: str, sort_order: str):
    """
    Live streaming fragment that automatically fetches fresh news data
    from providers every 1 minute without manual refresh.
    """
    now = time.time()
    last_fetch_ts = st.session_state.get("last_auto_fetch_ts", 0)

    # Automatically fetch fresh live news every 1 minute (60 seconds)
    if last_fetch_ts > 0 and (now - last_fetch_ts >= 58):
        try:
            final_state = asyncio.run(workflow.run())
            new_count = len(final_state.get("new_articles", []))
            st.session_state["last_auto_fetch_ts"] = now
            st.session_state["last_auto_fetch_time"] = datetime.now(IST_TZ).strftime("%I:%M:%S %p IST")
            if new_count > 0:
                st.toast(f"⚡ Auto-fetched {new_count} fresh breaking news stories!", icon="📡")
        except Exception as e:
            pass

    last_sync = st.session_state.get("last_auto_fetch_time")
    articles = db.get_recent_articles_with_sentiments(limit=150)
    render_news_terminal(articles, search_query=search_query, sort_order=sort_order, last_sync_time=last_sync)


def main():
    db = get_db()
    workflow = get_workflow()

    # Automatically fetch fresh news only if database is currently empty
    if "dashboard_loaded" not in st.session_state:
        st.session_state["dashboard_loaded"] = True
        st.session_state["last_auto_fetch_ts"] = time.time()
        st.session_state["last_auto_fetch_time"] = datetime.now(IST_TZ).strftime("%I:%M:%S %p IST")
        existing_articles = db.get_recent_articles_with_sentiments(limit=1)
        if not existing_articles:
            run_ingestion_pipeline(workflow)
            return

    # 1. Top Header Bar with Search, Sort Toggle & Action Controls
    col_title, col_search, col_sort, col_scan = st.columns(
        [3.0, 4.0, 1.4, 1.6],
        gap="small"
    )
    
    with col_title:
        st.markdown("""
        <div class="trade-pulse-brand">
            <div class="brand-icon-box">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M3 17L9 11L13 15L21 7" stroke="#ffffff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M16 7H21V12" stroke="#ffffff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="9" cy="11" r="1.5" fill="#34D399"/>
                    <circle cx="13" cy="15" r="1.5" fill="#34D399"/>
                    <circle cx="21" cy="7" r="1.8" fill="#10B981"/>
                </svg>
            </div>
            <div class="brand-title-wrap">
                <span class="brand-text-main">TRADE</span><span class="brand-text-accent">PULSE</span>
            </div>
            <span class="brand-terminal-pill">TERMINAL</span>
        </div>
        """, unsafe_allow_html=True)
    
    with col_search:
        search_query = st.text_input(
            "Search",
            placeholder="Search breaking headlines, tickers, sources...",
            label_visibility="collapsed",
            key="top_news_search"
        )

    with col_sort:
        sort_order = st.selectbox(
            "Sort",
            options=["Newest First", "Oldest First"],
            label_visibility="collapsed",
            key="news_sort_order"
        )
        
    should_scan = False
    with col_scan:
        if st.button("⚡ Fetch Now", type="primary", use_container_width=True, help="Immediately fetch and analyze latest news without waiting for 1-minute auto-fetch"):
            should_scan = True

    # Trigger fresh scan and scraping when requested
    if should_scan:
        run_ingestion_pipeline(workflow)

    # 2. View Routing (Direct URL parameter access: ?view=scraper or ?page=scraper)
    query_view = st.query_params.get("view", "") or st.query_params.get("page", "")
    is_scraper_view = query_view in ["scraper", "reader"]

    if is_scraper_view:
        col_back, col_spacer = st.columns([2.6, 7.4])
        with col_back:
            if st.button("← Back to Live Breaking News", type="secondary", use_container_width=True):
                st.query_params.clear()
                st.rerun()
        # Full Webpage Scraper, DOM extractor, IST timestamps & Neural Intelligence
        render_article_scraper_view()
    else:
        # Interactive Custom News URL Analyzer with FinBERT
        render_url_analyzer()
        # Auto-fetching Live News Feed (every 1 minute)
        render_live_news_stream(workflow, db, search_query=search_query, sort_order=sort_order)



    # Sidebar: Navigation & Providers
    st.sidebar.markdown("### 🧭 Terminal Navigation")
    st.sidebar.page_link("app.py", label="Live Breaking News Stream", icon="📡")
    st.sidebar.page_link("pages/1_URL_Article_Scraper.py", label="Full Article Scraper & Reader", icon="📰")
    st.sidebar.markdown("---")

    st.sidebar.markdown("### 📰 Connected News Providers")
    st.sidebar.markdown("""
    - **Economic Times** (Markets & Corporate)
    - **Moneycontrol** (Latest News & Markets)
    - **LiveMint** (Companies & Economy)
    - **NDTV Profit** (Business & Stocks)
    - **Business Standard** (Companies & Markets)
    """)
    st.sidebar.markdown("---")
    st.sidebar.info("⏱️ Auto-fetch: **Every 1 minute**\n\nAI Sentiment: **FinBERT (ProsusAI/finbert)**\n\nDatabase: **DuckDB Analytical DB**")
    st.sidebar.caption("Financial News Intelligence Terminal • v1.0.0")



if __name__ == "__main__":
    main()
