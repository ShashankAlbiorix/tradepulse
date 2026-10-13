import re
from typing import List, Set, Dict, Optional
from config.tickers import TRACKED_ENTITIES, TrackedEntity, TICKER_MAP
from src.models.schemas import NewsArticle, EntityMention
from src.utils.logger import logger


class EntityExtractor:
    """
    Extracts and links mentioned corporate entities and stock ticker symbols
    from raw financial news headlines and article body text.
    """

    def __init__(self, tracked_entities: Optional[List[TrackedEntity]] = None):
        """
        Initialize entity extractor with target watchlist entities and regex patterns.
        """
        self.entities = tracked_entities or TRACKED_ENTITIES
        self._regex_cache: Dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _compile_patterns(self):
        """
        Pre-compile regex word-boundary matchers for all symbols, names, and aliases.
        """
        for entity in self.entities:
            terms = [re.escape(entity.symbol), re.escape(entity.name)] + [
                re.escape(alias) for alias in entity.aliases
            ]
            # Match whole words only to prevent false substrings
            pattern_str = r"\b(" + "|".join(terms) + r")\b"
            self._regex_cache[entity.symbol] = re.compile(pattern_str, re.IGNORECASE)

    async def extract_entities(self, article: NewsArticle) -> List[EntityMention]:
        """
        Scan headline, summary, and content for mentions of tracked entities.

        Args:
            article: NewsArticle to inspect.

        Returns:
            List[EntityMention]: Extracted unique entity mentions with relevance scores.
        """
        combined_text = f"{article.title} {article.summary or ''} {article.content or ''}"
        matched_mentions: Dict[str, EntityMention] = {}

        for entity in self.entities:
            pattern = self._regex_cache.get(entity.symbol)
            if not pattern:
                continue

            matches = pattern.findall(combined_text)
            if matches:
                # Higher relevance if found in title vs body
                title_matches = pattern.findall(article.title)
                relevance = 1.0 if title_matches else 0.75

                matched_mentions[entity.symbol] = EntityMention(
                    symbol=entity.symbol,
                    company_name=entity.name,
                    relevance_score=relevance
                )

        return list(matched_mentions.values())
