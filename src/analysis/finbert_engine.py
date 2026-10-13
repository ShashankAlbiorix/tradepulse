import os
import re
from typing import Dict, Any, Optional, List

# Prevent Windows libiomp5 duplicate initialization error
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import requests
from bs4 import BeautifulSoup
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from src.utils.logger import logger


class FinBERTEngine:
    """
    Financial sentiment analysis engine powered by ProsusAI/finbert.
    Supports full article body extraction from news URLs and direct neural inference.
    """
    _instance: Optional["FinBERTEngine"] = None
    MODEL_NAME = "ProsusAI/finbert"

    def __new__(cls, *args, **kwargs):
        """Singleton implementation to ensure model and tokenizer are loaded only once."""
        if cls._instance is None:
            cls._instance = super(FinBERTEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return

        self.model_name = model_name or self.MODEL_NAME
        logger.info(f"Loading FinBERT model & tokenizer from '{self.model_name}'...")
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self.model.eval()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            logger.info(f"FinBERT loaded successfully on device: {self.device.upper()}")
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            raise e

        # FinBERT canonical label order: 0: positive, 1: negative, 2: neutral
        self.label_mapping = {
            0: "BULLISH",
            1: "BEARISH",
            2: "NEUTRAL"
        }
        self._initialized = True

    def fetch_article_from_url(self, url: str, timeout: int = 10) -> Dict[str, str]:
        """
        Fetch full article text and title from a financial news URL.

        Args:
            url (str): Target web page link.
            timeout (int): HTTP request timeout in seconds.

        Returns:
            Dict[str, str]: Extracted title and sanitized text body (truncated to 3,000 chars).
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract headline/title
            title = ""
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"].strip()
            elif soup.title and soup.title.string:
                title = soup.title.string.strip()
            elif soup.find("h1"):
                title = soup.find("h1").get_text().strip()

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            # Extract all paragraph texts
            paragraphs = [
                p.get_text().strip()
                for p in soup.find_all("p")
                if len(p.get_text().strip()) > 30
            ]
            article_text = " ".join(paragraphs)

            # Fallback to general text if few paragraphs were found
            if not article_text:
                article_text = soup.get_text(separator=" ", strip=True)

            # Sanitize extra whitespace
            article_text = re.sub(r"\s+", " ", article_text).strip()

            return {
                "title": title or "Financial News Article",
                "text": article_text[:3000],
                "url": url,
                "status": "success"
            }

        except Exception as e:
            logger.warning(f"Failed to fetch article body from {url}: {e}")
            return {
                "title": "News Story",
                "text": "",
                "url": url,
                "status": f"error: {str(e)}"
            }

    def predict_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Classify text sentiment using FinBERT sequence classification.

        Args:
            text (str): News headline or full article text.

        Returns:
            Dict[str, Any]: Sentiment verdict, confidence score, and probability distribution.
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return {
                "sentiment": "NEUTRAL",
                "confidence": 0.50,
                "probabilities": {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34},
                "reasoning": "Insufficient article text for neural classification."
            }

        try:
            inputs = self.tokenizer(
                clean_text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            ).to(self.device)

            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

            best_idx = int(torch.argmax(probs))
            predicted_label = self.label_mapping.get(best_idx, "NEUTRAL")
            confidence = float(probs[best_idx])

            prob_dist = {
                "bullish": round(float(probs[0]), 3),
                "bearish": round(float(probs[1]), 3),
                "neutral": round(float(probs[2]), 3)
            }

            conf_pct = int(confidence * 100)
            reasoning = f"FinBERT financial neural analysis indicates {predicted_label.lower()} momentum ({conf_pct}% confidence)."

            return {
                "sentiment": predicted_label,
                "confidence": round(confidence, 2),
                "probabilities": prob_dist,
                "reasoning": reasoning
            }

        except Exception as e:
            logger.error(f"Error during FinBERT sentiment inference: {e}")
            return {
                "sentiment": "NEUTRAL",
                "confidence": 0.50,
                "probabilities": {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34},
                "reasoning": f"Inference exception: {str(e)}"
            }

    def predict_sentiment_batch(self, texts: List[str], batch_size: int = 32) -> List[Dict[str, Any]]:
        """
        Perform high-throughput batched FinBERT classification across a list of texts.

        Args:
            texts (List[str]): List of article texts or headlines.
            batch_size (int): Mini-batch size for tensor forward passes.

        Returns:
            List[Dict[str, Any]]: Sentiment results matching input order.
        """
        results: List[Dict[str, Any]] = []
        if not texts:
            return results

        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            clean_chunk = [t[:1000] if t and t.strip() else "Market news" for t in chunk]

            try:
                inputs = self.tokenizer(
                    clean_chunk,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probs_matrix = torch.nn.functional.softmax(outputs.logits, dim=-1)

                for row in probs_matrix:
                    best_idx = int(torch.argmax(row))
                    predicted_label = self.label_mapping.get(best_idx, "NEUTRAL")
                    confidence = float(row[best_idx])
                    conf_pct = int(confidence * 100)

                    prob_dist = {
                        "bullish": round(float(row[0]), 3),
                        "bearish": round(float(row[1]), 3),
                        "neutral": round(float(row[2]), 3)
                    }

                    results.append({
                        "sentiment": predicted_label,
                        "confidence": round(confidence, 2),
                        "probabilities": prob_dist,
                        "reasoning": f"FinBERT financial neural analysis indicates {predicted_label.lower()} momentum ({conf_pct}% confidence)."
                    })

            except Exception as e:
                logger.error(f"Error in predict_sentiment_batch: {e}")
                for _ in chunk:
                    results.append({
                        "sentiment": "NEUTRAL",
                        "confidence": 0.50,
                        "probabilities": {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34},
                        "reasoning": f"Batch inference error: {str(e)}"
                    })

        return results

    def analyze_url(self, url: str) -> Dict[str, Any]:
        """
        High-level pipeline: Scrapes URL, analyzes article body, and returns full verdict metadata.

        Args:
            url (str): Financial news article URL.

        Returns:
            Dict[str, Any]: Complete analysis result including title, text snippet, and sentiment.
        """
        article_data = self.fetch_article_from_url(url)
        content_to_analyze = article_data.get("text") or article_data.get("title") or ""
        sentiment_result = self.predict_sentiment(content_to_analyze)

        return {
            "url": url,
            "title": article_data.get("title", ""),
            "text_snippet": (article_data.get("text", "")[:300] + "...") if len(article_data.get("text", "")) > 300 else article_data.get("text", ""),
            "status": article_data.get("status", ""),
            "sentiment": sentiment_result.get("sentiment", "NEUTRAL"),
            "confidence": sentiment_result.get("confidence", 0.5),
            "probabilities": sentiment_result.get("probabilities", {}),
            "reasoning": sentiment_result.get("reasoning", "")
        }
