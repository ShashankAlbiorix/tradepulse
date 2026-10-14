from typing import List, Dict, Optional
import streamlit as st
from config.tickers import TRACKED_ENTITIES, TrackedEntity
from src.models.schemas import ShortTermVerdict, VerdictSignal


def render_stock_matrix(verdicts_by_symbol: Dict[str, ShortTermVerdict]):
    """
    Renders an overview grid showing sentiment analysis and short-term verdicts
    across ALL tracked stocks simultaneously on the dashboard.

    Args:
        verdicts_by_symbol: Dictionary mapping ticker symbols to their ShortTermVerdict.
    """
    st.markdown("### 📊 Market-Wide Stock Sentiment & Trading Verdicts")
    st.caption("AI-computed sentiment consensus and short-term verdicts synthesized from breaking news across all monitored equities.")

    # Render in 3 responsive columns
    cols = st.columns(3)

    signal_map = {
        VerdictSignal.STRONG_BUY: ("STRONG BUY", "badge-strong-buy", "🟢"),
        VerdictSignal.BUY: ("BUY", "badge-buy", "🟢"),
        VerdictSignal.NEUTRAL: ("NEUTRAL / HOLD", "badge-neutral", "🟡"),
        VerdictSignal.SELL: ("SELL", "badge-sell", "🔴"),
        VerdictSignal.STRONG_SELL: ("STRONG SELL", "badge-strong-sell", "🔴"),
    }

    for idx, entity in enumerate(TRACKED_ENTITIES):
        col = cols[idx % 3]
        verdict = verdicts_by_symbol.get(entity.symbol.upper())

        if verdict:
            label, badge_class, icon = signal_map.get(
                verdict.verdict,
                (verdict.verdict.value, "badge-neutral", "⚪")
            )
            confidence = int(verdict.confidence * 100)
            dist = verdict.sentiment_distribution
            bullish = dist.get("BULLISH", 0.0)
            bearish = dist.get("BEARISH", 0.0)
            neutral = dist.get("NEUTRAL", 0.0)
            driver = verdict.key_drivers[0] if verdict.key_drivers else "Awaiting market catalysts"
            article_count = verdict.analyzed_articles_count
        else:
            label, badge_class, icon = ("NEUTRAL / HOLD", "badge-neutral", "🟡")
            confidence = 50
            bullish, neutral, bearish = 33.3, 33.4, 33.3
            driver = "No breaking news detected"
            article_count = 0

        with col:
            st.markdown(
                f"""
                <div style="background: rgba(18, 26, 44, 0.75); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px); border: 1px solid rgba(255, 255, 255, 0.09); border-radius: 12px; padding: 18px 20px; margin-bottom: 16px; box-shadow: 0 4px 18px rgba(0,0,0,0.35);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div style="font-family: 'Space Grotesk', sans-serif; font-size: 1.10rem; font-weight: 700; color: #FFFFFF;">{entity.name}</div>
                            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.76rem; color: #94A3B8; margin-top: 2px;">{entity.symbol} • {entity.sector}</div>
                        </div>
                        <div>
                            <span class="{badge_class}" style="font-size: 0.76rem; padding: 4px 10px; border-radius: 6px;">{icon} {label}</span>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 14px; font-size: 0.82rem; color: #CBD5E1; font-family: 'JetBrains Mono', monospace;">
                        <span>Confidence: <b style="color: #FFFFFF;">{confidence}%</b></span>
                        <span>News Stories: <b style="color: #38BDF8;">{article_count}</b></span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.80rem; color: #CBD5E1; font-weight: 600; font-family: 'JetBrains Mono', monospace;">
                        <span style="color: #10B981;">🟢 {bullish:.0f}%</span> &nbsp;|&nbsp; <span style="color: #38BDF8;">🟡 {neutral:.0f}%</span> &nbsp;|&nbsp; <span style="color: #EF4444;">🔴 {bearish:.0f}%</span>
                    </div>
                    <div style="margin-top: 12px; font-size: 0.84rem; color: #E2E8F0; border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 10px; line-height: 1.45;">
                        ⚡ <strong style="color: #FFFFFF;">Key Driver:</strong> {driver}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
