"""Base crawler class and web scraping utilities."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..schemas import Article


class BaseCrawler(ABC):
    """Abstract base class for news scrapers."""

    def __init__(self, outlet_name: str, country: str, max_articles: int = 15):
        self.outlet_name = outlet_name
        self.country = country
        self.max_articles = max_articles

    @abstractmethod
    def scrape(self, keyword: Optional[str] = None) -> List[Article]:
        """Scrape articles matching the given keyword and return normalized Article instances."""
        pass
