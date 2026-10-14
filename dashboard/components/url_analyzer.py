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

            # Render custom verdict card (Cyber-Institutional Glass Theme)
            engine_name = "Qwen-0.6B" if "NOSIBLE" in selected_model else "FinBERT"
            card_html = textwrap.dedent(f"""
<div style="background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.10); border-radius: 12px; padding: 20px 22px; margin-top: 16px; box-shadow: 0 4px 20px -2px rgba(0,0,0,0.45), inset 0 1px 0 0 rgba(255,255,255,0.06);">
    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; flex-wrap: wrap; margin-bottom: 14px;">
        <div style="flex: 1; min-width: 250px;">
            <span style="font-size: 0.70rem; font-weight: 700; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.8px; font-family: 'JetBrains Mono', monospace;">SCRAPED HEADLINE</span>
            <h4 style="margin: 4px 0 0 0; color: #FFFFFF; font-size: 1.15rem; line-height: 1.45; font-weight: 700;">
                <a href="{url}" target="_blank" rel="noopener noreferrer" style="color: #FFFFFF; text-decoration: none;">{title} ↗</a>
            </h4>
        </div>
        <div>
            <span class="{sent_class}" style="font-size: 0.82rem; padding: 5px 14px; height: 30px;">{sent_label}</span>
        </div>
    </div>

    <div style="margin: 16px 0 12px 0;">
        <div style="display: flex; justify-content: space-between; font-size: 0.76rem; font-weight: 700; font-family: 'JetBrains Mono', monospace; margin-bottom: 6px;">
            <span style="color: #10B981;">BULLISH: {bull_pct}%</span>
            <span style="color: #38BDF8;">NEUTRAL: {neut_pct}%</span>
            <span style="color: #EF4444;">BEARISH: {bear_pct}%</span>
        </div>
        <div style="display: flex; height: 8px; border-radius: 999px; overflow: hidden; background: rgba(255, 255, 255, 0.08);">
            <div style="width: {bull_pct}%; background: linear-gradient(90deg, #059669, #10B981);"></div>
            <div style="width: {neut_pct}%; background: linear-gradient(90deg, #0284C7, #38BDF8);"></div>
            <div style="width: {bear_pct}%; background: linear-gradient(90deg, #DC2626, #EF4444);"></div>
        </div>
    </div>

    <div style="background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(255, 255, 255, 0.08); border-left: 3.5px solid #10B981; padding: 12px 16px; border-radius: 7px; font-size: 0.88rem; color: #E2E8F0; margin-top: 14px; line-height: 1.55;">
        💡 <strong style="color: #FFFFFF;">{engine_name} Verdict Reasoning:</strong> {reasoning}
    </div>
</div>
""")
            st.markdown(card_html, unsafe_allow_html=True)

            with st.expander("📄 View Scraped Article Body Snippet", expanded=False):
                st.write(result.get("text_snippet", "No body text extracted."))
