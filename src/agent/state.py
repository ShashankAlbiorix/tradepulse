from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from src.models.schemas import NewsArticle, EntityMention, SentimentResult, ShortTermVerdict


class AgentState(TypedDict, total=False):
    """
    Shared mutable state dictionary passed between nodes in the LangGraph workflow.
    """
    raw_articles: List[NewsArticle]
    new_articles: List[NewsArticle]
    extracted_entities: Dict[str, List[EntityMention]]  # article_id -> List[EntityMention]
    sentiment_results: List[SentimentResult]
    verdicts: Dict[str, ShortTermVerdict]               # symbol -> ShortTermVerdict
    errors: List[str]
    current_step: str
