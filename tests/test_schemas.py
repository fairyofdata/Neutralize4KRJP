"""Unit tests for NAKOJA Pydantic schemas."""

import pytest
from pydantic import ValidationError
from nakoja.schemas import (
    Article,
    TitleClassificationItem,
    TopicClassificationBatch,
    PairSelectionResult,
    ArticleSummary,
    PerspectiveComparison,
    NeutralArticle,
)


def test_article_schema_valid():
    art = Article(
        title="한일 정상회담 개최",
        content="서울에서 한일 정상회담이 열렸습니다...",
        outlet="JoongAng Ilbo",
        country="Korea",
        url="https://example.com/news/1",
        date="2026-09-10",
    )
    assert art.title == "한일 정상회담 개최"
    assert art.country == "Korea"


def test_article_schema_invalid_country():
    with pytest.raises(ValidationError):
        Article(
            title="Invalid",
            content="Content",
            outlet="Unknown",
            country="USA",  # Literal["Korea", "Japan"]
        )


def test_topic_classification_batch():
    batch = TopicClassificationBatch(
        classifications=[
            TitleClassificationItem(index=1, category="Diplomacy"),
            TitleClassificationItem(index=2, category="Economy"),
        ]
    )
    assert len(batch.classifications) == 2
    assert batch.classifications[0].category == "Diplomacy"


def test_pair_selection_result():
    res = PairSelectionResult(
        korean_index=1,
        japanese_index=3,
        common_topic="Bilateral Economic Forum",
        selection_reason="Both articles cover the bilateral business meeting in Tokyo.",
    )
    assert res.korean_index == 1
    assert res.japanese_index == 3


def test_neutral_article_schema():
    comp = PerspectiveComparison(
        shared_facts=["The summit occurred on Wednesday"],
        korean_emphasis=["Historical apology context"],
        japanese_emphasis=["Future security cooperation"],
        framing_divergence="Past accountability vs future forward-looking coordination",
    )
    neutral = NeutralArticle(
        topic_summary="2026 Korea-Japan Summit",
        comparison=comp,
        headline_kr="한일 정상회담 보도 대조 및 중립 종합",
        headline_jp="日韓首脳会談報道の対照と中立総合",
        content_kr="중앙일보는... 반면 요미우리신문은...",
        content_jp="中央日報は… 一方読売新聞は…",
    )
    assert neutral.comparison.framing_divergence.startswith("Past accountability")
    assert "중앙일보" in neutral.content_kr
