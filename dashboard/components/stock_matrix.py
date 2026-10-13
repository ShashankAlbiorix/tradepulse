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
                <div class="stock-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div class="stock-card-title">{entity.name}</div>
                            <div class="stock-card-subtitle">{entity.symbol} • {entity.sector}</div>
                        </div>
                        <div>
                            <span class="{badge_class}">{icon} {label}</span>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 12px; font-size: 0.88rem; color: #1e293b;">
                        <span>Confidence: <b>{confidence}%</b></span>
                        <span>News Articles: <b>{article_count}</b></span>
                    </div>
                    <div style="margin-top: 8px; font-size: 0.85rem; color: #475569; font-weight: 600;">
                        🟢 {bullish:.0f}% Bullish &nbsp;|&nbsp; 🟡 {neutral:.0f}% Neutral &nbsp;|&nbsp; 🔴 {bearish:.0f}% Bearish
                    </div>
                    <div style="margin-top: 10px; font-size: 0.85rem; color: #334155; border-top: 1px solid #e2e8f0; padding-top: 8px; line-height: 1.4;">
                        ⚡ <b>Key Driver:</b> {driver}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
