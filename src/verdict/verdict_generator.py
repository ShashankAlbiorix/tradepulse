from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from src.models.schemas import SentimentResult, SentimentLabel, ShortTermVerdict, VerdictSignal
from src.verdict.confidence_scorer import ConfidenceScorer
from src.verdict.summarizer import VerdictSummarizer
from src.utils.logger import logger


class VerdictGenerator:
    """
    Synthesizes aggregated sentiments, catalyst weights, and news flow into an actionable trading verdict.
    """

    def __init__(self, confidence_scorer: Optional[ConfidenceScorer] = None, summarizer: Optional[VerdictSummarizer] = None):
        """
        Initialize verdict generator with scoring and summarizer components.
        """
        self.scorer = confidence_scorer or ConfidenceScorer()
        self.summarizer = summarizer or VerdictSummarizer()

    def _compute_sentiment_distribution(self, sentiments: List[SentimentResult]) -> Dict[str, float]:
        """
        Calculate percentage distribution of Bullish, Bearish, and Neutral sentiments.
        """
        if not sentiments:
            return {"BULLISH": 0.0, "BEARISH": 0.0, "NEUTRAL": 100.0}

        total = len(sentiments)
        bullish = sum(1 for s in sentiments if s.sentiment == SentimentLabel.BULLISH)
        bearish = sum(1 for s in sentiments if s.sentiment == SentimentLabel.BEARISH)
        neutral = sum(1 for s in sentiments if s.sentiment == SentimentLabel.NEUTRAL)

        return {
            "BULLISH": round((bullish / total) * 100, 1),
            "BEARISH": round((bearish / total) * 100, 1),
            "NEUTRAL": round((neutral / total) * 100, 1)
        }

    def _compute_net_score(self, sentiments: List[SentimentResult]) -> float:
        """
        Calculate confidence-weighted directional score between -1.0 (strongly bearish) and +1.0 (strongly bullish).
        """
        if not sentiments:
            return 0.0

        weighted_sum = 0.0
        total_weight = 0.0

        for item in sentiments:
            weight = item.confidence
            if item.sentiment == SentimentLabel.BULLISH:
                weighted_sum += (1.0 * weight)
            elif item.sentiment == SentimentLabel.BEARISH:
                weighted_sum += (-1.0 * weight)
            else:
                weighted_sum += (0.0 * weight)
            total_weight += weight

        if total_weight == 0.0:
            return 0.0

        return weighted_sum / total_weight

    async def generate_verdict(self, symbol: str, sentiments: List[SentimentResult]) -> ShortTermVerdict:
        """
        Aggregate multiple sentiment items and produce a unified short-term signal.

        Args:
            symbol (str): Stock ticker symbol.
            sentiments (List[SentimentResult]): Recent sentiment outputs for this symbol.

        Returns:
            ShortTermVerdict: Final verdict signal, confidence, distribution, and catalyst rationale.
        """
        distribution = self._compute_sentiment_distribution(sentiments)
        confidence = self.scorer.calculate_confidence(sentiments)
        net_score = self._compute_net_score(sentiments)

        # Signal Mapping Logic
        if net_score >= 0.60 and confidence >= 0.70:
            verdict_signal = VerdictSignal.STRONG_BUY
        elif net_score >= 0.20:
            verdict_signal = VerdictSignal.BUY
        elif net_score <= -0.60 and confidence >= 0.70:
            verdict_signal = VerdictSignal.STRONG_SELL
        elif net_score <= -0.20:
            verdict_signal = VerdictSignal.SELL
        else:
            verdict_signal = VerdictSignal.NEUTRAL

        # Extract top catalysts
        top_catalysts = self.summarizer.extract_top_catalysts(sentiments, max_catalysts=3)

        # Generate narrative executive summary
        summary = await self.summarizer.generate_summary(
            symbol=symbol,
            verdict=verdict_signal,
            confidence=confidence,
            sentiments=sentiments
        )

        return ShortTermVerdict(
            symbol=symbol.upper(),
            verdict=verdict_signal,
            confidence=confidence,
            sentiment_distribution=distribution,
            timeframe="1-5 Trading Days",
            executive_summary=summary,
            key_drivers=top_catalysts,
            analyzed_articles_count=len(sentiments),
            generated_at=datetime.now(timezone.utc)
        )
