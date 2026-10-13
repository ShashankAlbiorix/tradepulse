from abc import ABC, abstractmethod
from typing import List
from src.models.schemas import NewsArticle


class BaseNewsFetcher(ABC):
    """
    Abstract Base Class defining the contract for all news ingestion sources.
    Every fetcher implementation must convert raw input streams into standardized NewsArticle schemas.
    """

    @abstractmethod
    async def fetch_articles(self, limit: int = 20) -> List[NewsArticle]:
        """
        Fetch latest articles from the data source.

        Args:
            limit (int): Maximum number of articles to retrieve.

        Returns:
            List[NewsArticle]: List of standardized article objects.
        """
        pass
