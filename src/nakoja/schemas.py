"""Domain schemas and Pydantic models for LLM-NAKOJA."""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class Article(BaseModel):
    """Normalized news article schema."""
    title: str = Field(description="Article headline")
    content: str = Field(description="Full text or body of the article")
    outlet: str = Field(description="News outlet name (e.g. JoongAng Ilbo, Yomiuri Shimbun)")
    country: Literal["Korea", "Japan"] = Field(description="Country of the outlet")
    url: Optional[str] = Field(default=None, description="Source article URL")
    date: Optional[str] = Field(default=None, description="Publication date string")
    category: Optional[str] = Field(default=None, description="Assigned topic category")


class TitleItem(BaseModel):
    """Title with its unique identifier/index."""
    index: int = Field(description="1-based index of the article")
    title: str = Field(description="Article title")
    country: Optional[str] = Field(default=None, description="Korea or Japan if known")


class TitleClassificationItem(BaseModel):
    """Classification for a single title."""
    index: int = Field(description="1-based index corresponding to input list")
    category: str = Field(
        description="Assigned category: Economy, Politics, Culture, Sports, Diplomacy, Security, History, or Other"
    )


class TopicClassificationBatch(BaseModel):
    """Batch classification of multiple article titles."""
    classifications: List[TitleClassificationItem] = Field(
        description="List of classified titles with category"
    )


class PairSelectionResult(BaseModel):
    """Result of identifying the best matching Korean and Japanese article pair."""
    korean_index: int = Field(description="1-based index of the selected Korean article")
    japanese_index: int = Field(description="1-based index of the selected Japanese article")
    common_topic: str = Field(description="Specific shared event or subject both articles cover")
    selection_reason: str = Field(
        description="Reason why this pair is the most directly comparable"
    )


class ArticleSummary(BaseModel):
    """Intermediate English summary designed to eliminate L1 linguistic framing bias."""
    outlet: str = Field(description="Outlet name")
    country: str = Field(description="Country of origin")
    key_facts: List[str] = Field(description="List of concrete factual points reported")
    stated_positions: List[str] = Field(description="Subjective or country-specific claims and positions")
    english_summary: str = Field(
        description="Concise neutral intermediate summary written in English"
    )


class PerspectiveComparison(BaseModel):
    """Contrast matrix of reporting differences between the two outlets."""
    shared_facts: List[str] = Field(
        description="Facts mutually acknowledged and reported by both sides"
    )
    korean_emphasis: List[str] = Field(
        description="Key aspects, historical context, or angles emphasized primarily by Korean media"
    )
    japanese_emphasis: List[str] = Field(
        description="Key aspects, policy stances, or angles emphasized primarily by Japanese media"
    )
    framing_divergence: str = Field(
        description="Analysis of how the underlying framing or terminology diverges between the two narratives"
    )


class NeutralArticle(BaseModel):
    """Final synthesized bilingual neutral article with explicit attribution."""
    topic_summary: str = Field(description="One-line summary of the issue")
    comparison: PerspectiveComparison = Field(
        description="Structured comparative analysis of perspectives"
    )
    headline_kr: str = Field(description="Balanced headline in Korean")
    headline_jp: str = Field(description="Balanced headline in Japanese")
    content_kr: str = Field(
        description="Full neutral article in Korean explicitly attributing viewpoints (e.g. '중앙일보는... 반면 요미우리신문은...')"
    )
    content_jp: str = Field(
        description="Full neutral article in Japanese explicitly attributing viewpoints (e.g. '中央日報は…と報じた一方、読売新聞は…')"
    )
