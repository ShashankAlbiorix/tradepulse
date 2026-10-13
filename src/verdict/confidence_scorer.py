import math
from typing import List
from src.models.schemas import SentimentResult, SentimentLabel


class ConfidenceScorer:
    """
    Computes mathematical confidence scores for aggregate sentiment signals
    based on consensus consistency, average inference confidence, and sample size.
    """

    def __init__(self, min_articles_for_high_confidence: int = 3):
        self.min_articles = min_articles_for_high_confidence

    def calculate_confidence(self, sentiments: List[SentimentResult]) -> float:
        """
        Calculates a confidence coefficient between 0.0 and 1.0.

        Formula:
        Confidence = (Consensus Score * 0.5) + (Average Article Confidence * 0.3) + (Volume Factor * 0.2)

        Args:
            sentiments (List[SentimentResult]): List of sentiment results for a ticker.

        Returns:
            float: Composite confidence metric bounded between [0.0, 1.0].
        """
        if not sentiments:
            return 0.0

        total_count = len(sentiments)

        # 1. Calculate Consensus Agreement (Proportion of dominant sentiment)
        bullish_count = sum(1 for s in sentiments if s.sentiment == SentimentLabel.BULLISH)
        bearish_count = sum(1 for s in sentiments if s.sentiment == SentimentLabel.BEARISH)
        neutral_count = sum(1 for s in sentiments if s.sentiment == SentimentLabel.NEUTRAL)

        max_consensus = max(bullish_count, bearish_count, neutral_count)
        consensus_ratio = max_consensus / total_count  # 0.33 to 1.0

        # Scale consensus ratio from [0.33, 1.0] to [0.0, 1.0]
        consensus_score = max(0.0, (consensus_ratio - 0.33) / 0.67)

        # 2. Average Individual LLM Confidence
        avg_confidence = sum(s.confidence for s in sentiments) / total_count

        # 3. Volume Factor (Sample Size Saturation curve: 1 - e^(-count / min_articles))
        volume_factor = min(1.0, 1.0 - math.exp(-total_count / self.min_articles))

        # Composite Weighted Score
        raw_score = (consensus_score * 0.50) + (avg_confidence * 0.30) + (volume_factor * 0.20)
        return round(max(0.10, min(1.0, raw_score)), 2)
