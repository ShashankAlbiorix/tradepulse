import streamlit as st
from src.models.schemas import ShortTermVerdict, VerdictSignal


def render_verdict_card(verdict: ShortTermVerdict):
    """
    Renders high-visibility trading verdict badge with confidence metric and horizon.

    Args:
        verdict (ShortTermVerdict): Computed short-term verdict object.
    """
    st.markdown("### 🎯 Short-Term Trading Verdict")

    # Map badge class to signal
    signal_map = {
        VerdictSignal.STRONG_BUY: ("STRONG BUY", "badge-strong-buy", "🟢"),
        VerdictSignal.BUY: ("BUY", "badge-buy", "🟢"),
        VerdictSignal.NEUTRAL: ("NEUTRAL / HOLD", "badge-neutral", "🟡"),
        VerdictSignal.SELL: ("SELL", "badge-sell", "🔴"),
        VerdictSignal.STRONG_SELL: ("STRONG SELL", "badge-strong-sell", "🔴"),
    }

    label, badge_class, icon = signal_map.get(
        verdict.verdict,
        (verdict.verdict.value, "badge-neutral", "⚪")
    )

    conf_pct = int(verdict.confidence * 100)

    st.markdown(
        f"""
        <div class="verdict-box">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <div>
                    <span class="{badge_class}">{icon} {label}</span>
                    <span style="color: #90a4ae; margin-left: 10px; font-size: 0.9rem;">Timeframe: {verdict.timeframe}</span>
                </div>
                <div style="text-align: right;">
                    <span style="font-size: 1.4rem; font-weight: 700; color: #f0f2f6;">{conf_pct}%</span>
                    <div style="font-size: 0.75rem; color: #90a4ae;">AI Confidence</div>
                </div>
            </div>
            <p style="color: #cfd8dc; font-size: 1rem; line-height: 1.5; margin-top: 10px;">
                {verdict.executive_summary}
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Sentiment Distribution Progress Bars
    dist = verdict.sentiment_distribution
    bullish = dist.get("BULLISH", 0.0)
    bearish = dist.get("BEARISH", 0.0)
    neutral = dist.get("NEUTRAL", 0.0)

    st.markdown("**Sentiment Consensus Breakdown:**")
    c1, c2, c3 = st.columns(3)
    c1.metric("🟢 Bullish", f"{bullish:.0f}%")
    c2.metric("🟡 Neutral", f"{neutral:.0f}%")
    c3.metric("🔴 Bearish", f"{bearish:.0f}%")

    if verdict.key_drivers:
        st.markdown("**Identified Catalyst Drivers:**")
        tags_html = "".join([f'<span class="catalyst-tag">⚡ {driver}</span>' for driver in verdict.key_drivers])
        st.markdown(tags_html, unsafe_allow_html=True)
