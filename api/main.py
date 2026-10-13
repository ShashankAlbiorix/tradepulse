import os
import sys
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure repo root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Windows OpenMP fix
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import torch
from src.analysis.qwen_sentiment_engine import QwenFinancialSentimentEngine
from src.utils.logger import logger

app = FastAPI(
    title="TradePulse Financial Sentiment API",
    description="High-throughput API serving NOSIBLE/financial-sentiment-v1.1-base for market news sentiment intelligence",
    version="1.1.0"
)

# Enable CORS for all frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-loaded engine singleton
_engine: Optional[QwenFinancialSentimentEngine] = None

def get_engine() -> QwenFinancialSentimentEngine:
    global _engine
    if _engine is None:
        logger.info("Instantiating QwenFinancialSentimentEngine in FastAPI...")
        _engine = QwenFinancialSentimentEngine()
    return _engine


class TextSentimentRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=5000, description="Financial news headline or article body text")

class URLSentimentRequest(BaseModel):
    url: str = Field(..., description="Valid HTTP/HTTPS financial news article URL")


@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    cuda_avail = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if cuda_avail else "CPU"
    return {
        "status": "healthy",
        "model": "NOSIBLE/financial-sentiment-v1.1-base",
        "device": "CUDA" if cuda_avail else "CPU",
        "device_name": device_name,
        "engine_loaded": _engine is not None
    }


@app.post("/api/sentiment/text")
def analyze_text(payload: TextSentimentRequest) -> Dict[str, Any]:
    try:
        engine = get_engine()
        result = engine.predict_sentiment(payload.text)
        return {
            "status": "success",
            "text": payload.text,
            "sentiment": result["sentiment"],
            "confidence": result["confidence"],
            "probabilities": result["probabilities"],
            "raw_response": result.get("raw_response", ""),
            "reasoning": result["reasoning"],
            "latency_ms": result.get("latency_ms", 0.0),
            "model": result.get("model", "NOSIBLE/financial-sentiment-v1.1-base")
        }
    except Exception as e:
        logger.error(f"Error in /api/sentiment/text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sentiment/url")
def analyze_url(payload: URLSentimentRequest) -> Dict[str, Any]:
    if not payload.url.strip().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL. Must begin with http:// or https://")
    
    try:
        engine = get_engine()
        result = engine.analyze_url(payload.url.strip())
        if result.get("status") != "success" and not result.get("text_snippet"):
            raise HTTPException(status_code=422, detail=result.get("reasoning", "Failed to scrape article from URL"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /api/sentiment/url: {e}")
        raise HTTPException(status_code=500, detail=str(e))


from src.ingestion.article_reader import ArticleReader
_article_reader: Optional[ArticleReader] = None

def get_article_reader() -> ArticleReader:
    global _article_reader
    if _article_reader is None:
        _article_reader = ArticleReader()
    return _article_reader


@app.post("/api/scraper/article")
def scrape_full_article(payload: URLSentimentRequest) -> Dict[str, Any]:
    """Scrape complete webpage data (headline, byline, date in IST, clean paragraphs, word count) and analyze sentiment."""
    if not payload.url.strip().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL. Must begin with http:// or https://")

    try:
        reader = get_article_reader()
        article_data = reader.scrape_url(payload.url.strip())
        if article_data.get("status") != "success":
            raise HTTPException(status_code=422, detail=article_data.get("message", "Failed to scrape article from URL"))

        engine = get_engine()
        snippet = (article_data.get("title", "") + ". " + article_data.get("full_text", ""))[:2500]
        sentiment_data = engine.predict_sentiment(snippet)
        article_data["sentiment"] = sentiment_data
        return article_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /api/scraper/article: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mount static directory for frontend
web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
if os.path.isdir(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.get("/")
    def serve_frontend():
        index_file = os.path.join(web_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "TradePulse API active. Static frontend not yet compiled."}

    @app.get("/scraper")
    def serve_scraper_frontend():
        scraper_file = os.path.join(web_dir, "scraper.html")
        if os.path.exists(scraper_file):
            return FileResponse(scraper_file)
        return FileResponse(os.path.join(web_dir, "index.html"))
