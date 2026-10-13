from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    """
    Central application settings and environment variables.
    Loads configurations from .env file or system environment.
    """
    # LLM Provider Configuration
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: str = "openai"
    DEFAULT_LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.1

    # Ingestion & Scraping Settings
    NEWS_API_KEY: Optional[str] = None
    FINNHUB_API_KEY: Optional[str] = None
    FETCH_INTERVAL_SECONDS: int = 300
    MAX_ARTICLES_PER_FETCH: int = 20

    # Storage Settings
    DATABASE_PATH: str = "data/news_agent.duckdb"
    DEDUPLICATION_CACHE_TTL_HOURS: int = 48

    # Application Settings
    ENVIRONMENT: str = "DEVELOPMENT"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
