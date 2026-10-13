import json
import re
from typing import Optional, Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models.chat_models import BaseChatModel

from config.prompts import SENTIMENT_CLASSIFICATION_PROMPT
from src.analysis.llm_factory import LLMFactory
from src.analysis.finbert_engine import FinBERTEngine
from src.models.schemas import NewsArticle, SentimentResult, SentimentLabel
from src.utils.logger import logger


class SentimentEngine:
    """
    Evaluates financial news tone and market impact using FinBERT neural classification
    with seamless fallback to LangChain LLMs.
    """

    def __init__(self, use_finbert: bool = True, llm: Optional[BaseChatModel] = None):
        """
        Initialize sentiment analysis engine with FinBERT or configured LLM.
        """
        self.use_finbert = use_finbert
        self.finbert = FinBERTEngine() if use_finbert else None
        self.llm = llm if not use_finbert else None

    def _parse_llm_json_response(self, raw_text: str) -> Dict[str, Any]:
        """
        Robustly extract and parse JSON object from LLM response strings.
        """
        try:
            return json.loads(raw_text)
        except Exception:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    pass

        return {
            "sentiment": "NEUTRAL",
            "confidence": 0.5,
            "reasoning": "Failed to parse structured LLM response.",
            "key_catalysts": []
        }

    async def analyze_sentiment(self, article: NewsArticle, symbol: str = "MARKET") -> SentimentResult:
        """
        Perform structured sentiment classification for an article using FinBERT.

        Args:
            article (NewsArticle): Ingested article text and metadata.
            symbol (str): Target stock ticker or MARKET.

        Returns:
            SentimentResult: Structured sentiment label, confidence, and reasoning.
        """
        # 1. FinBERT Neural Engine (Primary Fast Path)
        if self.use_finbert and self.finbert:
            try:
                # Combine title and body text for comprehensive context
                analysis_text = f"{article.title}. {article.summary or article.content or ''}".strip()
                res = self.finbert.predict_sentiment(analysis_text[:2000])

                raw_sent = res.get("sentiment", "NEUTRAL").upper()
                if raw_sent == "BULLISH":
                    label = SentimentLabel.BULLISH
                elif raw_sent == "BEARISH":
                    label = SentimentLabel.BEARISH
                else:
                    label = SentimentLabel.NEUTRAL

                confidence = float(res.get("confidence", 0.60))
                reasoning = res.get("reasoning", "FinBERT financial neural classification.")
                probs = res.get("probabilities", {})

                # Generate informative catalysts summary from probabilities
                catalysts = [
                    f"FinBERT Bullish: {int(probs.get('bullish', 0)*100)}%",
                    f"FinBERT Bearish: {int(probs.get('bearish', 0)*100)}%",
                    f"FinBERT Neutral: {int(probs.get('neutral', 0)*100)}%"
                ]

                return SentimentResult(
                    article_id=article.article_id,
                    symbol=symbol,
                    sentiment=label,
                    confidence=confidence,
                    reasoning=reasoning,
                    key_catalysts=catalysts
                )
            except Exception as e:
                logger.warning(f"FinBERT inference failed for {article.article_id}, falling back to LLM: {e}")

    async def analyze_sentiment_batch(self, articles: List[NewsArticle], symbol: str = "MARKET") -> List[SentimentResult]:
        """
        Batch sentiment classification across multiple articles.
        """
        if not articles:
            return []

        if self.use_finbert and self.finbert:
            texts = [f"{a.title}. {a.summary or a.content or ''}".strip() for a in articles]
            batch_res = self.finbert.predict_sentiment_batch(texts, batch_size=32)

            results: List[SentimentResult] = []
            for article, res in zip(articles, batch_res):
                raw_sent = res.get("sentiment", "NEUTRAL").upper()
                if raw_sent == "BULLISH":
                    label = SentimentLabel.BULLISH
                elif raw_sent == "BEARISH":
                    label = SentimentLabel.BEARISH
                else:
                    label = SentimentLabel.NEUTRAL

                confidence = float(res.get("confidence", 0.60))
                reasoning = res.get("reasoning", "FinBERT financial neural classification.")
                probs = res.get("probabilities", {})

                catalysts = [
                    f"FinBERT Bullish: {int(probs.get('bullish', 0)*100)}%",
                    f"FinBERT Bearish: {int(probs.get('bearish', 0)*100)}%",
                    f"FinBERT Neutral: {int(probs.get('neutral', 0)*100)}%"
                ]

                results.append(SentimentResult(
                    article_id=article.article_id,
                    symbol=symbol,
                    sentiment=label,
                    confidence=confidence,
                    reasoning=reasoning,
                    key_catalysts=catalysts
                ))
            return results

        # Fallback to single loop
        results = []
        for article in articles:
            results.append(await self.analyze_sentiment(article, symbol=symbol))
        return results

        # 2. LLM Fallback
        if not self.llm:
            self.llm = LLMFactory.get_chat_model()

        prompt = SENTIMENT_CLASSIFICATION_PROMPT.format(
            title=article.title,
            summary=article.summary or "N/A",
            content=(article.content or article.summary or "")[:1500]
        )

        messages = [
            SystemMessage(content="You are a senior quantitative equity research analyst. Return ONLY valid JSON."),
            HumanMessage(content=prompt)
        ]

        try:
            response = await self.llm.ainvoke(messages)
            content_str = response.content if isinstance(response.content, str) else str(response.content)
            parsed_data = self._parse_llm_json_response(content_str)

            raw_sentiment = str(parsed_data.get("sentiment", "NEUTRAL")).upper().strip()
            if raw_sentiment in ["BULLISH", "POSITIVE", "BUY"]:
                label = SentimentLabel.BULLISH
            elif raw_sentiment in ["BEARISH", "NEGATIVE", "SELL"]:
                label = SentimentLabel.BEARISH
            else:
                label = SentimentLabel.NEUTRAL

            confidence = float(parsed_data.get("confidence", 0.6))
            confidence = max(0.0, min(1.0, confidence))
            reasoning = str(parsed_data.get("reasoning", "Standard catalyst analysis."))
            catalysts = list(parsed_data.get("key_catalysts", []))

            return SentimentResult(
                article_id=article.article_id,
                symbol=symbol,
                sentiment=label,
                confidence=confidence,
                reasoning=reasoning,
                key_catalysts=catalysts
            )

        except Exception as e:
            logger.error(f"SentimentEngine analysis error on {article.article_id}: {str(e)}")
            return SentimentResult(
                article_id=article.article_id,
                symbol=symbol,
                sentiment=SentimentLabel.NEUTRAL,
                confidence=0.5,
                reasoning=f"Error occurred during analysis: {str(e)}",
                key_catalysts=[]
            )
