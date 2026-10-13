---
title: TradePulse Financial Terminal
emoji: 📈
colorFrom: green
colorTo: blue
sdk: streamlit
app_file: dashboard/app.py
pinned: false
---

# 📈 TradePulse - Real-Time Financial Market News & Sentiment Intelligence

An autonomous Agentic AI pipeline that continuously ingests financial news feeds, performs entity resolution and multi-class sentiment analysis, and synthesizes actionable short-term market verdicts via an interactive Streamlit terminal.


---

## 🏗️ Architecture: 4-Layer Pipeline

```text
┌─────────────────────────────────────────────────────────────┐
│                    1. DATA INGESTION                        │
│  RSS Feeds (ET, Moneycontrol, Mint, NDTV) + Portal Scrapers │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   2. ANALYSIS & REASONING                   │
│   Named Entity Extraction + LLM / FinBERT Sentiment Engine  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│               3. VERDICT & CONFIDENCE SYNTHESIS             │
│   Bullish / Bearish / Neutral Signal + Catalyst Summary     │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 4. PRESENTATION & DASHBOARD                 │
│         Streamlit Real-Time Visual Intelligence UI          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Directory Structure

```text
tradepulse/
├── config/
│   ├── settings.py           # Configuration & environment settings
│   ├── tickers.py            # Tracked symbols, entities, and keyword queries
│   └── prompts.py            # Centralized prompt engineering registry
├── src/
│   ├── ingestion/            # RSS fetchers, News API clients, web scrapers
│   ├── analysis/             # LLM factories, NER, sentiment scoring, impact analyzers
│   ├── verdict/              # Short-term verdict synthesis, confidence scoring, summaries
│   ├── agent/                # LangGraph state machine, workflow DAG, scheduler
│   ├── storage/              # Deduplication cache & historical DuckDB store
│   ├── models/               # Pydantic data schemas
│   └── utils/                # Logging and market calendar utilities
├── dashboard/
│   ├── app.py                # Main Streamlit dashboard application
│   ├── components/           # Header, Ticker View, Verdict Card, News Feed UI widgets
│   └── styles.css            # Dark mode styling
└── tests/
    ├── test_ingestion.py     # Ingestion & scraper unit tests
    ├── test_sentiment.py     # Sentiment parsing & schema validation
    └── test_verdict.py       # Confidence math & signal aggregation tests
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Set your API keys in `.env`:
```env
OPENAI_API_KEY="your-openai-key"
ANTHROPIC_API_KEY="your-anthropic-key"
NEWS_API_KEY="your-news-api-key"
```

### 3. Launch Streamlit Dashboard
```bash
streamlit run dashboard/app.py
```
