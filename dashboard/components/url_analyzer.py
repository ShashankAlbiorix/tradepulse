import html
import streamlit as st
from src.analysis.finbert_engine import FinBERTEngine
from src.analysis.qwen_sentiment_engine import QwenFinancialSentimentEngine


def render_url_analyzer():
    """
    Renders an interactive widget in Streamlit for users to paste any
    financial news article link, scrape its full text, and run neural sentiment analysis.
    Supports both ProsusAI/finbert and NOSIBLE/financial-sentiment-v1.1-base.
    """
    with st.expander("🔗 **Analyze Any Custom News Article URL (FinBERT & Qwen-0.6B)**", expanded=False):
        col_info, col_jump = st.columns([7.2, 2.8], gap="small")
        with col_info:
            st.markdown("""
            Paste any financial news link (*LiveMint, Economic Times, Moneycontrol, Bloomberg, Reuters, etc.*) to scrape article body and compute **neural sentiment**.
            """)
        with col_jump:
            if st.button("🌐 Full Reader Page ↗", use_container_width=True, key="btn_jump_to_deep_reader"):
                st.session_state["current_view"] = "scraper"
                st.rerun()


        col_model, col_url, col_btn = st.columns([2.0, 3.5, 1.2], gap="small")
        with col_model:
            selected_model = st.selectbox(
                "Neural Engine",
                options=["NOSIBLE/financial-sentiment-v1.1-base", "ProsusAI/finbert"],
                index=0,
                key="url_analyzer_model_select"
            )

        with col_url:
            user_url = st.text_input(
                "News Article URL",
                placeholder="https://www.livemint.com/market/...",
                label_visibility="collapsed",
                key="custom_url_input"
            )

        with col_btn:
            analyze_clicked = st.button("⚡ Analyze URL", type="primary", use_container_width=True)

        if analyze_clicked:
            if not user_url or not user_url.strip().startswith("http"):
                st.warning("⚠️ Please enter a valid URL starting with `http://` or `https://`.")
                return

            spinner_msg = (
                "🤖 Fetching article text from URL and computing Qwen3-0.6B neural sentiment..."
                if "NOSIBLE" in selected_model
                else "🤖 Fetching article text from URL and computing FinBERT neural sentiment..."
            )

            with st.spinner(spinner_msg):
                if "NOSIBLE" in selected_model:
                    engine = QwenFinancialSentimentEngine()
                else:
                    engine = FinBERTEngine()
                result = engine.analyze_url(user_url.strip())

            if not result.get("text_snippet") and "error" in result.get("status", ""):
                st.error(f"❌ Failed to extract article body from URL: {result.get('status')}")
                return

            # Format result card
            title = html.escape(result.get("title", "News Article"))
            url = result.get("url", "#")
            sentiment = result.get("sentiment", "NEUTRAL").upper()
            confidence = int(result.get("confidence", 0.5) * 100)
            reasoning = html.escape(result.get("reasoning", ""))
            probs = result.get("probabilities", {})

            bull_pct = int(probs.get("bullish", 0) * 100)
            bear_pct = int(probs.get("bearish", 0) * 100)
            neut_pct = int(probs.get("neutral", 0) * 100)

            if sentiment == "BULLISH":
                sent_class = "sentiment-bullish"
                sent_label = f"🟢 BULLISH ({confidence}%)"
            elif sentiment == "BEARISH":
                sent_class = "sentiment-bearish"
                sent_label = f"🔴 BEARISH ({confidence}%)"
            else:
                sent_class = "sentiment-neutral"
                sent_label = f"🟡 NEUTRAL ({confidence}%)"

            import textwrap

            # Render custom verdict card (Dark Terminal Theme)
            engine_name = "Qwen-0.6B" if "NOSIBLE" in selected_model else "FinBERT"
            card_html = textwrap.dedent(f"""
<div style="background: #0B101E; border: 1px solid #162035; border-radius: 10px; padding: 18px 20px; margin-top: 14px; box-shadow: 0 4px 14px rgba(0,0,0,0.35);">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 12px;">
        <div style="flex: 1; min-width: 250px;">
            <span style="font-size: 0.68rem; font-weight: 700; color: #64748B; text-transform: uppercase; letter-spacing: 0.8px; font-family: monospace;">SCRAPED HEADLINE</span>
            <h4 style="margin: 4px 0 0 0; color: #F8FAFC; font-size: 1.12rem; line-height: 1.4; font-weight: 700;">
                <a href="{url}" target="_blank" rel="noopener noreferrer" style="color: #F8FAFC; text-decoration: none;">{title} ↗</a>
            </h4>
        </div>
        <div>
            <span class="{sent_class}" style="font-size: 0.85rem; padding: 4px 12px; height: 28px;">{sent_label}</span>
        </div>
    </div>

    <div style="margin: 14px 0 10px 0;">
        <div style="display: flex; justify-content: space-between; font-size: 0.74rem; font-weight: 700; font-family: monospace; margin-bottom: 6px; color: #94A3B8;">
            <span style="color: #10B981;">BULLISH: {bull_pct}%</span>
            <span style="color: #38BDF8;">NEUTRAL: {neut_pct}%</span>
            <span style="color: #EF4444;">BEARISH: {bear_pct}%</span>
        </div>
        <div style="display: flex; height: 8px; border-radius: 999px; overflow: hidden; background: #162035;">
            <div style="width: {bull_pct}%; background: #10B981;"></div>
            <div style="width: {neut_pct}%; background: #38BDF8;"></div>
            <div style="width: {bear_pct}%; background: #EF4444;"></div>
        </div>
    </div>

    <div style="background: rgba(15, 23, 42, 0.8); border-left: 3px solid #10B981; padding: 10px 14px; border-radius: 4px; font-size: 0.84rem; color: #CBD5E1; margin-top: 12px; line-height: 1.5;">
        💡 <strong style="color: #F1F5F9;">{engine_name} Verdict Reasoning:</strong> {reasoning}
    </div>
</div>
""")
            st.markdown(card_html, unsafe_allow_html=True)

            with st.expander("📄 View Scraped Article Body Snippet", expanded=False):
                st.write(result.get("text_snippet", "No body text extracted."))
