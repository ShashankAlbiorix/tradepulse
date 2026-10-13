import os
import sys
import html
import textwrap
import streamlit as st

# Ensure repository root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.ingestion.article_reader import ArticleReader
from src.analysis.qwen_sentiment_engine import QwenFinancialSentimentEngine
from src.analysis.finbert_engine import FinBERTEngine


# Configure Streamlit page layout
st.set_page_config(
    page_title="TradePulse — Article Web Scraper & Reader",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load global CSS
css_path = os.path.join(os.path.dirname(__file__), "..", "styles.css")
if os.path.exists(css_path):
    with open(css_path, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Custom Scraper Page Styles
st.markdown("""
<style>
/* Scraper Header Hero */
.scraper-hero-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #0B101E;
    border: 1px solid #1E293B;
    border-radius: 12px;
    padding: 16px 24px;
    margin-bottom: 20px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.scraper-hero-title {
    display: flex;
    align-items: center;
    gap: 12px;
}

.scraper-hero-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 700;
    color: #10B981;
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 3px 8px;
    border-radius: 5px;
    letter-spacing: 0.8px;
}

/* Preset Chips */
.preset-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
    margin-bottom: 14px;
    flex-wrap: wrap;
}

.preset-chip {
    font-size: 0.76rem;
    font-family: 'JetBrains Mono', monospace;
    color: #94A3B8;
    background: #0D1322;
    border: 1px solid #1E293B;
    border-radius: 6px;
    padding: 4px 10px;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s ease;
}

/* Telemetry Ribbon */
.telemetry-ribbon {
    display: flex;
    align-items: center;
    gap: 16px;
    background: #0D1322;
    border: 1px solid #162035;
    border-radius: 8px;
    padding: 10px 18px;
    margin-bottom: 20px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #94A3B8;
    flex-wrap: wrap;
}

.telemetry-dot {
    width: 8px;
    height: 8px;
    background: #10B981;
    border-radius: 50%;
    display: inline-block;
    box-shadow: 0 0 8px #10B981;
}

/* Article Reader Card (Left Column) */
.article-reader-container {
    background: #0B101E;
    border: 1px solid #162035;
    border-radius: 12px;
    padding: 28px 32px;
    box-shadow: 0 6px 25px rgba(0, 0, 0, 0.45);
    margin-bottom: 24px;
}

.article-byline-strip {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}

.article-headline-display {
    font-family: 'Space Grotesk', 'Plus Jakarta Sans', sans-serif;
    font-size: 1.75rem;
    font-weight: 800;
    line-height: 1.3;
    color: #F8FAFC;
    letter-spacing: -0.02em;
    margin-bottom: 16px;
}

.article-lead-box {
    background: rgba(16, 185, 129, 0.06);
    border-left: 3px solid #10B981;
    border-radius: 6px;
    padding: 14px 18px;
    margin-bottom: 22px;
    font-size: 0.95rem;
    line-height: 1.6;
    color: #E2E8F0;
    font-weight: 500;
}

.article-body-paragraph {
    font-size: 0.96rem;
    line-height: 1.75;
    color: #CBD5E1;
    margin-bottom: 16px;
    text-align: justify;
}

.article-lead-image {
    width: 100%;
    max-height: 380px;
    object-fit: cover;
    border-radius: 10px;
    border: 1px solid #1E293B;
    margin-bottom: 22px;
}

/* Intelligence Panel (Right Column) */
.intel-card {
    background: #0B101E;
    border: 1px solid #162035;
    border-radius: 12px;
    padding: 22px 24px;
    margin-bottom: 18px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}

.intel-header-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.70rem;
    font-weight: 700;
    color: #64748B;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_reader() -> ArticleReader:
    return ArticleReader()


@st.cache_resource
def get_qwen_engine() -> QwenFinancialSentimentEngine:
    return QwenFinancialSentimentEngine()


@st.cache_resource
def get_finbert_engine() -> FinBERTEngine:
    return FinBERTEngine()


def main():
    # Sidebar Navigation
    st.sidebar.markdown("### 🧭 Terminal Navigation")
    st.sidebar.page_link("app.py", label="Live Breaking News Stream", icon="📡")
    st.sidebar.page_link("pages/1_URL_Article_Scraper.py", label="Full Article Scraper & Reader", icon="📰")
    st.sidebar.markdown("---")
    st.sidebar.info("💡 **Deep DOM Scraper** extracts true publisher timestamps (IST), full editorial paragraphs, and runs FinBERT / Qwen-0.6B neural sentiment inference.")

    # 1. Page Header & Back Navigation
    st.markdown("""
    <div class="scraper-hero-bar">
        <div class="scraper-hero-title">
            <span style="font-size: 1.5rem;">🌐</span>
            <div>
                <h2 style="margin: 0; font-size: 1.35rem; font-weight: 800; color: #F8FAFC;">
                    ARTICLE SCRAPER & READER
                </h2>
                <div style="font-size: 0.80rem; color: #94A3B8;">
                    Scrape full webpage data, true publisher dates, lead copy, and neural sentiment intelligence
                </div>
            </div>
        </div>
        <div>
            <span class="scraper-hero-badge">PRODUCTION ENGINE</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Controls HUD: URL Input, Engine Selector, Action Button
    col_model, col_url, col_btn = st.columns([1.8, 4.2, 1.2], gap="small")

    with col_model:
        model_choice = st.selectbox(
            "Neural Engine",
            options=["NOSIBLE/financial-sentiment-v1.1-base", "ProsusAI/finbert"],
            index=0,
            label_visibility="collapsed"
        )

    with col_url:
        target_url = st.text_input(
            "Article URL",
            value="",
            placeholder="Paste news article link (LiveMint, Moneycontrol, Economic Times, Bloomberg, Reuters)...",
            label_visibility="collapsed"
        )

    with col_btn:
        run_scrape = st.button("⚡ Scrape & Read", type="primary", use_container_width=True)

    clean_target = target_url.strip() if target_url else ""
    if not clean_target or not clean_target.startswith(("http://", "https://")):
        st.info("💡 Paste any financial news article URL above and click **'⚡ Scrape & Read'** to extract the full article and neural sentiment.")
        return

    # Execute scrape and display
    reader = get_reader()

    if clean_target:

        with st.spinner("🤖 Scraping full webpage data and computing neural sentiment..."):
            data = reader.scrape_url(target_url.strip())

            if data.get("status") != "success":
                st.error(f"❌ Failed to scrape article: {data.get('message')}")
                return

            # Run sentiment analysis on scraped full text
            full_text = data.get("full_text", "")
            title = data.get("title", "Financial Article")
            snippet_for_ai = (title + ". " + full_text)[:2500]

            if "NOSIBLE" in model_choice:
                engine = get_qwen_engine()
                sentiment_data = engine.predict_sentiment(snippet_for_ai)
            else:
                engine = get_finbert_engine()
                sentiment_data = engine.analyze_text(snippet_for_ai)

        # 3. Telemetry Ribbon
        st.markdown(f"""
        <div class="telemetry-ribbon">
            <span><span class="telemetry-dot"></span> <strong>SCRAPE ACTIVE & VERIFIED</strong></span>
            <span>PUBLISHER: <strong style="color: #F8FAFC;">{data.get('source')}</strong></span>
            <span>PUBLISHED (IST): <strong style="color: #38BDF8;">{data.get('published_at_formatted')}</strong></span>
            <span>WORDS: <strong style="color: #F8FAFC;">{data.get('word_count')}</strong></span>
            <span>READ TIME: <strong style="color: #F8FAFC;">~{data.get('reading_time_min')} min</strong></span>
            <span>DOMAIN: <strong style="color: #94A3B8;">{data.get('domain')}</strong></span>
        </div>
        """, unsafe_allow_html=True)

        # 4. Dual-Column Stage (Left: Editorial Reader, Right: Neural Terminal)
        col_left, col_right = st.columns([6.2, 3.8], gap="medium")

        # LEFT COLUMN: Editorial Article Reader
        with col_left:
            st.markdown('<div class="article-reader-container">', unsafe_allow_html=True)

            # Metadata Strip
            source_badge = f'<span class="source-badge">📰 {data.get("source")}</span>'
            author_badge = f'<span class="source-badge">✍️ By {data.get("author")}</span>' if data.get("author") else ""
            date_badge = f'<span class="datetime-badge">🕒 {data.get("published_at_formatted")}</span>'

            st.markdown(f"""
            <div class="article-byline-strip">
                {source_badge}
                {author_badge}
                {date_badge}
            </div>
            """, unsafe_allow_html=True)

            # Headline
            st.markdown(f'<h1 class="article-headline-display">{html.escape(title)}</h1>', unsafe_allow_html=True)

            # Lead Image (if present)
            if data.get("lead_image") and data.get("lead_image").startswith("http"):
                st.markdown(f'<img src="{data["lead_image"]}" class="article-lead-image" alt="Article Lead Image">', unsafe_allow_html=True)

            # Executive Subhead / Lead Description
            if data.get("description"):
                st.markdown(f"""
                <div class="article-lead-box">
                    <strong>EXECUTIVE SUMMARY</strong><br>
                    {html.escape(data.get("description"))}
                </div>
                """, unsafe_allow_html=True)

            # Formatted Paragraphs
            paragraphs = data.get("paragraphs", [])
            if paragraphs:
                st.markdown("<div style='margin-top: 18px;'>", unsafe_allow_html=True)
                for p in paragraphs:
                    st.markdown(f'<p class="article-body-paragraph">{html.escape(p)}</p>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.write(data.get("full_text", "No readable body paragraphs extracted."))

            st.markdown('</div>', unsafe_allow_html=True)

        # RIGHT COLUMN: Neural Intelligence Console
        with col_right:
            # Verdict Card
            sentiment = sentiment_data.get("sentiment", "NEUTRAL").upper()
            confidence = int(sentiment_data.get("confidence", 0.5) * 100)
            reasoning = html.escape(sentiment_data.get("reasoning", ""))
            probs = sentiment_data.get("probabilities", {})
            bull_pct = int(probs.get("bullish", 0) * 100)
            bear_pct = int(probs.get("bearish", 0) * 100)
            neut_pct = int(probs.get("neutral", 0) * 100)

            if sentiment == "BULLISH":
                verdict_color = "#10B981"
                verdict_icon = "▲ BULLISH"
                verdict_class = "sentiment-bullish"
            elif sentiment == "BEARISH":
                verdict_color = "#EF4444"
                verdict_icon = "▼ BEARISH"
                verdict_class = "sentiment-bearish"
            else:
                verdict_color = "#38BDF8"
                verdict_icon = "■ NEUTRAL"
                verdict_class = "sentiment-neutral"

            engine_label = "Qwen-0.6B Base" if "NOSIBLE" in model_choice else "FinBERT"

            st.markdown(f"""
            <div class="intel-card">
                <div class="intel-header-tag">SYNTHESIZED MARKET VERDICT</div>
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <div>
                        <span class="{verdict_class}" style="font-size: 1.05rem; padding: 6px 14px; height: 32px;">
                            {verdict_icon} · {confidence}%
                        </span>
                    </div>
                    <div style="font-family: monospace; font-size: 0.74rem; color: #64748B;">
                        {engine_label}
                    </div>
                </div>

                <div class="intel-header-tag" style="margin-top: 14px;">SOFTMAX CONVICTION SPREAD</div>
                <div style="display: flex; justify-content: space-between; font-family: monospace; font-size: 0.74rem; margin-bottom: 6px;">
                    <span style="color: #10B981;">BULLISH: {bull_pct}%</span>
                    <span style="color: #38BDF8;">NEUTRAL: {neut_pct}%</span>
                    <span style="color: #EF4444;">BEARISH: {bear_pct}%</span>
                </div>
                <div style="display: flex; height: 8px; border-radius: 999px; overflow: hidden; background: #162035; margin-bottom: 16px;">
                    <div style="width: {bull_pct}%; background: #10B981;"></div>
                    <div style="width: {neut_pct}%; background: #38BDF8;"></div>
                    <div style="width: {bear_pct}%; background: #EF4444;"></div>
                </div>

                <div class="intel-header-tag">AI REASONING INSIGHT</div>
                <div class="reasoning-box" style="margin-top: 4px; font-size: 0.85rem;">
                    <span class="reasoning-tag">AI ANALYSIS</span> {reasoning}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Source Verification Card
            st.markdown(f"""
            <div class="intel-card">
                <div class="intel-header-tag">SOURCE VERIFICATION</div>
                <div style="display: flex; flex-direction: column; gap: 8px; font-size: 0.82rem; font-family: monospace; color: #CBD5E1;">
                    <div><strong>Original Link:</strong> <a href="{data.get('url')}" target="_blank" style="color: #38BDF8; text-decoration: none;">Open Source Article ↗</a></div>
                    <div><strong>Published:</strong> <span style="color: #F8FAFC;">{data.get('published_at_formatted')}</span></div>
                    <div><strong>Domain:</strong> <span style="color: #F8FAFC;">{data.get('domain')}</span></div>
                    <div><strong>Extraction:</strong> <span style="color: #10B981;">Direct DOM Parser</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # 5. Raw Scraped Data & Meta Inspector (Expandable)
        with st.expander("🔍 **Inspect Raw Scraped Meta Tags & OpenGraph Telemetry**", expanded=False):
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


main()

