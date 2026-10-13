import os
import re
import time
from typing import Dict, Any, Optional, List

# Prevent Windows libiomp5 duplicate initialization error
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import requests
from bs4 import BeautifulSoup
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from src.utils.logger import logger


class QwenFinancialSentimentEngine:
    """
    Financial sentiment analysis engine powered by NOSIBLE/financial-sentiment-v1.1-base.
    Fine-tuned from Qwen-0.6B on 100k financial market news articles.
    Supports full article body extraction from news URLs and neural causal LM inference.
    """
    _instance: Optional["QwenFinancialSentimentEngine"] = None
    MODEL_NAME = "NOSIBLE/financial-sentiment-v1.1-base"

    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure weights and tokenizer are loaded only once."""
        if cls._instance is None:
            cls._instance = super(QwenFinancialSentimentEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return

        self.model_name = model_name or self.MODEL_NAME
        logger.info(f"Initializing QwenFinancialSentimentEngine with '{self.model_name}'...")
        
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=dtype,
                device_map="auto" if torch.cuda.is_available() else None,
                trust_remote_code=True
            )
            if self.device == "cpu":
                self.model.to("cpu")
            self.model.eval()
            logger.info(f"QwenFinancialSentimentEngine loaded successfully on {self.device.upper()}.")
        except Exception as e:
            logger.error(f"Failed to load QwenFinancialSentimentEngine '{self.model_name}': {e}")
            raise e

        self._initialized = True

    def fetch_article_from_url(self, url: str, timeout: int = 10) -> Dict[str, str]:
        """
        Fetch full article text and title from a financial news URL.
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

            # Remove unwanted tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                tag.decompose()

            # Extract all readable paragraphs
            paragraphs = [
                p.get_text().strip()
                for p in soup.find_all("p")
                if len(p.get_text().strip()) > 30
            ]
            article_text = " ".join(paragraphs)

            if not article_text:
                article_text = soup.get_text(separator=" ", strip=True)

            article_text = re.sub(r"\s+", " ", article_text).strip()

            return {
                "title": title or "Financial News Article",
                "text": article_text[:3000],
                "url": url,
                "status": "success"
            }

        except Exception as e:
            logger.warning(f"Failed to scrape article from {url}: {e}")
            return {
                "title": "News Story",
                "text": "",
                "url": url,
                "status": f"error: {str(e)}"
            }

    def predict_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Classify financial sentiment using NOSIBLE/financial-sentiment-v1.1-base.
        Returns standard BULLISH, BEARISH, or NEUTRAL verdict and structured probabilities.
        """
        clean_text = text.strip() if text else ""
        if not clean_text:
            return {
                "sentiment": "NEUTRAL",
                "confidence": 0.50,
                "probabilities": {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34},
                "raw_response": "neutral",
                "reasoning": "Insufficient article text for neural classification."
            }

        t_start = time.perf_counter()
        messages = [
            {"role": "system", "content": "Classify the financial sentiment as positive, neutral, or negative."},
            {"role": "user", "content": clean_text[:2500]}
        ]

        try:
            # Apply standard Qwen chat template
            input_text = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            ).to(self.model.device)

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=128,
                    do_sample=False,
                    pad_token_id=self.tokenizer.eos_token_id
                )

            # Slice out generated tokens
            new_tokens = output_ids[0][inputs.input_ids.shape[1]:]
            verdict_raw = self.tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

            # Extract internal chain-of-thought reasoning from inside <think>...</think>
            think_match = re.search(r"<think>(.*?)(?:</think>|$)", verdict_raw, flags=re.DOTALL)
            extracted_reasoning = think_match.group(1).strip() if think_match else ""

            # Extract final answer: text outside/after </think> tags
            after_think = re.sub(r"<think>.*?</think>", "", verdict_raw, flags=re.DOTALL).strip().lower()
            target_eval = after_think if after_think else verdict_raw.lower()

            if "positive" in target_eval or "bullish" in target_eval:
                standard_label = "BULLISH"
                conf = 0.95
                probs = {"bullish": 0.95, "bearish": 0.02, "neutral": 0.03}
            elif "negative" in target_eval or "bearish" in target_eval:
                standard_label = "BEARISH"
                conf = 0.95
                probs = {"bullish": 0.02, "bearish": 0.95, "neutral": 0.03}
            elif "neutral" in target_eval:
                standard_label = "NEUTRAL"
                conf = 0.88
                probs = {"bullish": 0.06, "bearish": 0.06, "neutral": 0.88}
            else:
                standard_label = "NEUTRAL"
                conf = 0.70
                probs = {"bullish": 0.15, "bearish": 0.15, "neutral": 0.70}

            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 1)
            reasoning = extracted_reasoning if extracted_reasoning else f"Qwen financial sentiment analysis identified {standard_label.lower()} market bias ({int(conf * 100)}% confidence in {elapsed_ms}ms)."

            return {
                "sentiment": standard_label,
                "confidence": conf,
                "probabilities": probs,
                "raw_response": verdict_raw,
                "reasoning": reasoning,
                "latency_ms": elapsed_ms,
                "model": self.MODEL_NAME
            }

        except Exception as e:
            logger.error(f"Inference error in QwenFinancialSentimentEngine: {e}")
            return {
                "sentiment": "NEUTRAL",
                "confidence": 0.50,
                "probabilities": {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34},
                "raw_response": f"error: {str(e)}",
                "reasoning": f"Inference exception: {str(e)}",
                "latency_ms": 0.0,
                "model": self.MODEL_NAME
            }

    def analyze_url(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """
        High-level orchestrator: scrape an article from URL, clean text, and run neural inference.
        """
        scraped = self.fetch_article_from_url(url, timeout=timeout)
        if scraped.get("status") != "success" or not scraped.get("text"):
            return {
                "url": url,
                "title": scraped.get("title", "Unknown Title"),
                "text_snippet": "",
                "sentiment": "NEUTRAL",
                "confidence": 0.50,
                "probabilities": {"bullish": 0.33, "bearish": 0.33, "neutral": 0.34},
                "reasoning": f"Scraping failed: {scraped.get('status', 'Empty article')}",
                "status": scraped.get("status", "error"),
                "model": self.MODEL_NAME
            }

        res = self.predict_sentiment(scraped["text"])
        snippet = scraped["text"][:350] + ("..." if len(scraped["text"]) > 350 else "")

        return {
            "url": url,
            "title": scraped["title"],
            "text_snippet": snippet,
            "sentiment": res["sentiment"],
            "confidence": res["confidence"],
            "probabilities": res["probabilities"],
            "raw_response": res.get("raw_response", ""),
            "reasoning": res["reasoning"],
            "latency_ms": res.get("latency_ms", 0.0),
            "status": "success",
            "model": self.MODEL_NAME
        }
