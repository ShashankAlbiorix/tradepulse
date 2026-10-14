import os
import html
import streamlit as st

from src.ingestion.article_reader import ArticleReader
from src.analysis.qwen_sentiment_engine import QwenFinancialSentimentEngine
from src.analysis.finbert_engine import FinBERTEngine


@st.cache_resource
def get_article_reader() -> ArticleReader:
    return ArticleReader()


@st.cache_resource
def get_qwen_sentiment_engine() -> QwenFinancialSentimentEngine:
    return QwenFinancialSentimentEngine()


@st.cache_resource
def get_finbert_sentiment_engine() -> FinBERTEngine:
    return FinBERTEngine()


def render_article_scraper_view():
    """
    Renders the dedicated, production-grade Article Web Scraper & Reader view:
    Extracts true publisher dates in IST, full editorial paragraphs, author byline,
    lead image, and executes neural financial sentiment analysis.
    """
    # Scraper Header Hero
    st.markdown("""
    <div style="background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; box-shadow: 0 4px 20px -2px rgba(0,0,0,0.45); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 1.6rem;">🌐</span>
            <div>
                <h2 style="margin: 0; font-size: 1.35rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.02em;">
                    LIVE ARTICLE WEB SCRAPER & READER
                </h2>
                <div style="font-size: 0.85rem; color: #CBD5E1; margin-top: 2px;">
                    Deep DOM extraction: True publisher dates in IST, full editorial body, lead summaries, and neural sentiment
                </div>
            </div>
        </div>
        <div>
            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; color: #34D399; background: rgba(16, 185, 129, 0.14); border: 1px solid rgba(16, 185, 129, 0.40); padding: 5px 12px; border-radius: 6px; letter-spacing: 0.8px;">
                ● DEEP EXTRACTION ENGINE
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # URL input in session state
    if "scraper_url_input_val" not in st.session_state:
        st.session_state["scraper_url_input_val"] = ""

    col_model, col_url, col_btn = st.columns([1.8, 4.4, 1.2], gap="small")

    with col_model:
        selected_model = st.selectbox(
            "Neural Engine",
            options=["NOSIBLE/financial-sentiment-v1.1-base", "ProsusAI/finbert"],
            index=0,
            key="article_scraper_engine_select"
        )

    with col_url:
        input_url = st.text_input(
            "Article URL to Scrape",
            value=st.session_state.get("scraper_url_input_val", ""),
            placeholder="Paste news article URL (LiveMint, Moneycontrol, Economic Times, Bloomberg, Reuters)...",
            label_visibility="collapsed",
            key="scraper_page_url_input"
        )

    with col_btn:
        run_scrape = st.button("⚡ Scrape & Read", type="primary", use_container_width=True, key="btn_run_article_scrape")

    active_url = input_url.strip() if input_url else ""
    if run_scrape and active_url:
        st.session_state["scraper_url_input_val"] = active_url

    if not active_url or not active_url.startswith(("http://", "https://")):
        st.info("💡 Paste any financial news article URL above and click **'⚡ Scrape & Read'** to extract the full article and neural sentiment.")
        return


    reader = get_article_reader()

    spinner_text = (
        "🤖 Scraping article DOM and computing Qwen3-0.6B neural sentiment..."
        if "NOSIBLE" in selected_model
        else "🤖 Scraping article DOM and computing FinBERT neural sentiment..."
    )

    with st.spinner(spinner_text):
        data = reader.scrape_url(active_url)

        if data.get("status") != "success":
            st.error(f"❌ Failed to scrape webpage: {data.get('message', 'Unreachable link')}")
            return

        # Run AI sentiment classification on the scraped article text
        full_text = data.get("full_text", "")
        title = data.get("title", "Financial Article")
        ai_input_text = (title + ". " + full_text)[:2500]

        if "NOSIBLE" in selected_model:
            engine = get_qwen_sentiment_engine()
            sentiment_data = engine.predict_sentiment(ai_input_text)
        else:
            engine = get_finbert_sentiment_engine()
            sentiment_data = engine.analyze_text(ai_input_text)

    # 1. Telemetry Ribbon Bar
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 16px; background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 9px; padding: 10px 18px; margin-bottom: 22px; font-family: 'JetBrains Mono', monospace; font-size: 0.80rem; color: #CBD5E1; flex-wrap: wrap;">
        <span style="color: #34D399; font-weight: 700;">● EXTRACTION VERIFIED</span>
        <span>PUBLISHER: <strong style="color: #FFFFFF;">{data.get('source')}</strong></span>
        <span>PUBLISHED (IST): <strong style="color: #38BDF8;">{data.get('published_at_formatted')}</strong></span>
        <span>WORDS: <strong style="color: #FFFFFF;">{data.get('word_count')}</strong></span>
        <span>READ TIME: <strong style="color: #FFFFFF;">~{data.get('reading_time_min')} min</strong></span>
        <span>DOMAIN: <strong style="color: #94A3B8;">{data.get('domain')}</strong></span>
    </div>
    """, unsafe_allow_html=True)

    # 2. Dual-Column Reader & Intelligence Stage
    col_reader, col_intel = st.columns([6.2, 3.8], gap="medium")

    # LEFT: Editorial Article Reader
    with col_reader:
        source_badge = f'<span class="source-badge">📰 {data.get("source")}</span>'
        author_badge = f'<span class="source-badge">✍️ {data.get("author")}</span>' if data.get("author") else ""
        date_badge = f'<span class="datetime-badge">🕒 {data.get("published_at_formatted")}</span>'

        lead_image_html = (
            f'<img src="{data.get("lead_image")}" style="width: 100%; max-height: 360px; object-fit: cover; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.12); margin-bottom: 20px;" alt="Article Image">'
            if data.get("lead_image") and data.get("lead_image").startswith("http")
            else ""
        )

        desc_html = (
            f'<div style="background: rgba(16, 185, 129, 0.10); border-left: 3.5px solid #10B981; border-radius: 7px; padding: 14px 18px; margin-bottom: 22px; font-size: 0.96rem; line-height: 1.6; color: #E2E8F0; font-weight: 500;"><strong>EXECUTIVE SUMMARY</strong><br>{html.escape(data.get("description"))}</div>'
            if data.get("description")
            else ""
        )

        paragraphs_html = ""
        for p in data.get("paragraphs", []):
            paragraphs_html += f'<p style="font-size: 0.98rem; line-height: 1.8; color: #CBD5E1; margin-bottom: 16px;">{html.escape(p)}</p>'

        if not paragraphs_html:
            paragraphs_html = f'<p style="font-size: 0.98rem; line-height: 1.8; color: #CBD5E1;">{html.escape(data.get("full_text", ""))}</p>'

        card_html = f"""
        <div style="background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 12px; padding: 28px 32px; box-shadow: 0 6px 25px rgba(0,0,0,0.45); margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;">
                {source_badge}
                {author_badge}
                {date_badge}
            </div>
            <h1 style="font-family: 'Space Grotesk', sans-serif; font-size: 1.80rem; font-weight: 800; line-height: 1.35; color: #FFFFFF; letter-spacing: -0.02em; margin-bottom: 20px;">
                {html.escape(title)}
            </h1>
            {lead_image_html}
            {desc_html}
            <div style="margin-top: 18px;">
                {paragraphs_html}
            </div>
        </div>
        """
        st.markdown(card_html, unsafe_allow_html=True)

    # RIGHT: Neural Intelligence Console
    with col_intel:
        sentiment = sentiment_data.get("sentiment", "NEUTRAL").upper()
        confidence = int(sentiment_data.get("confidence", 0.5) * 100)
        reasoning = html.escape(sentiment_data.get("reasoning", ""))
        probs = sentiment_data.get("probabilities", {})
        bull_pct = int(probs.get("bullish", 0) * 100)
        bear_pct = int(probs.get("bearish", 0) * 100)
        neut_pct = int(probs.get("neutral", 0) * 100)

        if sentiment == "BULLISH":
            verdict_icon = "▲ BULLISH"
            sent_class = "sentiment-bullish"
        elif sentiment == "BEARISH":
            verdict_icon = "▼ BEARISH"
            sent_class = "sentiment-bearish"
        else:
            verdict_icon = "■ NEUTRAL"
            sent_class = "sentiment-neutral"

        engine_name = "Qwen-0.6B Base" if "NOSIBLE" in selected_model else "FinBERT"

        st.markdown(f"""
        <div style="background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 12px; padding: 22px 24px; margin-bottom: 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px;">
                SYNTHESIZED MARKET VERDICT
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <span class="{sent_class}" style="font-size: 1.05rem; padding: 6px 14px; height: 32px;">
                    {verdict_icon} · {confidence}%
                </span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: #CBD5E1;">
                    {engine_name}
                </span>
            </div>

            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; margin-top: 14px; margin-bottom: 6px;">
                SOFTMAX CONVICTION SPREAD
            </div>
            <div style="display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; margin-bottom: 6px;">
                <span style="color: #10B981;">BULLISH: {bull_pct}%</span>
                <span style="color: #38BDF8;">NEUTRAL: {neut_pct}%</span>
                <span style="color: #EF4444;">BEARISH: {bear_pct}%</span>
            </div>
            <div style="display: flex; height: 8px; border-radius: 999px; overflow: hidden; background: rgba(255, 255, 255, 0.08); margin-bottom: 18px;">
                <div style="width: {bull_pct}%; background: linear-gradient(90deg, #059669, #10B981);"></div>
                <div style="width: {neut_pct}%; background: linear-gradient(90deg, #0284C7, #38BDF8);"></div>
                <div style="width: {bear_pct}%; background: linear-gradient(90deg, #DC2626, #EF4444);"></div>
            </div>

            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px;">
                AI REASONING INSIGHT
            </div>
            <div class="reasoning-box" style="margin-top: 4px; font-size: 0.88rem; line-height: 1.55;">
                <span class="reasoning-tag">⚡ FINBERT SIGNAL</span> {reasoning}
            </div>
        </div>

        <div style="background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 12px; padding: 20px 22px; margin-bottom: 18px; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px;">
                SOURCE VERIFICATION AUDIT
            </div>
            <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.84rem; font-family: 'JetBrains Mono', monospace; color: #CBD5E1;">
                <div><strong>Original Article:</strong> <a href="{data.get('url')}" target="_blank" rel="noopener noreferrer" style="color: #38BDF8; text-decoration: none;">Open Source Article ↗</a></div>
                <div><strong>Published (IST):</strong> <span style="color: #FFFFFF;">{data.get('published_at_formatted')}</span></div>
                <div><strong>Publisher:</strong> <span style="color: #FFFFFF;">{data.get('source')}</span></div>
                <div><strong>Domain:</strong> <span style="color: #FFFFFF;">{data.get('domain')}</span></div>
                <div><strong>Scrape Method:</strong> <span style="color: #10B981;">Direct DOM Parser</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 3. Expandable Inspector for Metadata and Telemetry
    with st.expander("🔍 **Inspect Raw Discovered Meta Tags & OpenGraph Telemetry**", expanded=False):
        st.json({
            "title": data.get("title"),
            "publisher": data.get("source"),
            "author": data.get("author"),
            "published_at_formatted": data.get("published_at_formatted"),
            "published_at_raw": data.get("published_at_raw"),
            "word_count": data.get("word_count"),
            "reading_time_minutes": data.get("reading_time_min"),
            "url": data.get("url"),
            "meta_tags_count": len(data.get("meta_tags", {})),
            "discovered_meta_tags": data.get("meta_tags", {})
        })
