"""
Centralized prompt template registry for news processing, sentiment classification, and verdict generation.
"""

SENTIMENT_CLASSIFICATION_PROMPT = """
You are a senior financial analyst. Classify the financial sentiment and expected market impact of the following news story.
Headline: {title}
Summary: {summary}
Content: {content}

Evaluate whether the overall impact is BULLISH, BEARISH, or NEUTRAL for the short-term (1-5 trading days).
Provide confidence score (0.0 - 1.0) and reasoning.
"""

VERDICT_SYNTHESIS_PROMPT = """
Synthesize the aggregate sentiment and recent market news flow:
Recent Analyzed News Items:
{news_items}

Generate a concise short-term verdict:
- Overall Signal: STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
- Confidence: 0.0 - 1.0
- Catalyst Factors: Top 3 drivers
- Executive Summary: 2-3 sentences explaining the verdict.
"""
