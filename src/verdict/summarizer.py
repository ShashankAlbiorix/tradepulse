from typing import List, Set, Optional, Any
from src.models.schemas import SentimentResult, SentimentLabel, VerdictSignal
from src.utils.logger import logger


class VerdictSummarizer:
    """
    Generates actionable executive summaries and distinct catalyst driver bullet points
    from multi-article sentiment results.
    """

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Args:
            llm_client: Optional LangChain chat model for natural language synthesis.
        """
        self.llm = llm_client

    def extract_top_catalysts(self, sentiments: List[SentimentResult], max_catalysts: int = 5) -> List[str]:
        """
        Deduplicate and rank top catalyst drivers across news items.
        """
        seen: Set[str] = set()
        top_catalysts: List[str] = []

        for item in sentiments:
            for catalyst in item.key_catalysts:
                cleaned = catalyst.strip().capitalize()
                if cleaned and cleaned.lower() not in seen:
                    seen.add(cleaned.lower())
                    top_catalysts.append(cleaned)
                    if len(top_catalysts) >= max_catalysts:
                        break
            if len(top_catalysts) >= max_catalysts:
                break

        return top_catalysts

    async def generate_summary(
        self,
        symbol: str,
        verdict: VerdictSignal,
        confidence: float,
        sentiments: List[SentimentResult]
    ) -> str:
        """
        Synthesizes directional bias, news volume, and primary catalysts into an executive summary.

        Args:
            symbol (str): Ticker symbol.
            verdict (VerdictSignal): Final computed verdict.
            confidence (float): Aggregate confidence score.
            sentiments (List[SentimentResult]): Analyzed news sentiment items.

        Returns:
            str: 2-3 sentence executive summary paragraph.
        """
        total = len(sentiments)
        if total == 0:
            return f"No recent news articles ingested for {symbol}. Short-term outlook remains NEUTRAL."

        bullish_count = sum(1 for s in sentiments if s.sentiment == SentimentLabel.BULLISH)
        bearish_count = sum(1 for s in sentiments if s.sentiment == SentimentLabel.BEARISH)
        neutral_count = sum(1 for s in sentiments if s.sentiment == SentimentLabel.NEUTRAL)

        catalysts = self.extract_top_catalysts(sentiments, max_catalysts=3)
        catalyst_str = f" Key drivers include: {', '.join(catalysts)}." if catalysts else ""

        if verdict in [VerdictSignal.STRONG_BUY, VerdictSignal.BUY]:
            bias_text = (
                f"{symbol} exhibits strong positive news sentiment across {total} recent news items "
                f"({bullish_count} Bullish, {neutral_count} Neutral). "
                f"Short-term momentum is supportive of upside continuation with {confidence * 100:.0f}% confidence."
            )
        elif verdict in [VerdictSignal.STRONG_SELL, VerdictSignal.SELL]:
            bias_text = (
                f"{symbol} faces negative news headwinds across {total} recent articles "
                f"({bearish_count} Bearish, {neutral_count} Neutral). "
                f"Elevated risk suggests caution or downside pressure with {confidence * 100:.0f}% confidence."
            )
        else:
            bias_text = (
                f"{symbol} exhibits balanced or neutral news flow across {total} articles. "
                f"No dominant catalyst detected to support a directional breakout in the 1-5 day horizon."
            )

        return f"{bias_text}{catalyst_str}"
