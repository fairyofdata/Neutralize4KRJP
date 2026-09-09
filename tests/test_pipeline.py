"""Unit tests for NAKOJA pipeline components with mocked OpenAI calls."""

from unittest.mock import MagicMock
import pytest
from nakoja.pipeline.classifier import classify_titles
from nakoja.pipeline.selector import select_article_pair
from nakoja.pipeline.summarizer import summarize_to_intermediate_english
from nakoja.pipeline.neutralizer import generate_neutral_article
from nakoja.schemas import (
    TopicClassificationBatch,
    TitleClassificationItem,
    PairSelectionResult,
    ArticleSummary,
    NeutralArticle,
    PerspectiveComparison,
)


def test_classify_titles_structured_mock():
    mock_client = MagicMock()
    mock_batch = TopicClassificationBatch(
        classifications=[
            TitleClassificationItem(index=1, category="Diplomacy"),
            TitleClassificationItem(index=2, category="Economy"),
        ]
    )
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(parsed=mock_batch))]
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    titles = ["한일 외교장관 회담", "한일 반도체 공급망 협력"]
    results = classify_titles(titles, mock_client)

    assert results == ["Diplomacy", "Economy"]
    mock_client.beta.chat.completions.parse.assert_called_once()


def test_classify_titles_fallback():
    mock_client = MagicMock()
    mock_client.beta.chat.completions.parse.side_effect = Exception("API error")

    mock_chat_completion = MagicMock()
    mock_chat_completion.choices = [
        MagicMock(message=MagicMock(content="1. Politics\n2. Security"))
    ]
    mock_client.chat.completions.create.return_value = mock_chat_completion

    titles = ["Title A", "Title B"]
    results = classify_titles(titles, mock_client)
    assert len(results) == 2
    assert results[0] == "Politics"
    assert results[1] == "Security"


def test_select_article_pair_mock():
    mock_client = MagicMock()
    mock_result = PairSelectionResult(
        korean_index=1,
        japanese_index=2,
        common_topic="Bilateral Summit",
        selection_reason="Identical event dates and agenda",
    )
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(parsed=mock_result))]
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    k_idx, j_idx, meta = select_article_pair(
        korean_titles=["한일 정상회담"],
        japanese_titles=["日韓経済協議", "日韓首脳会談"],
        client=mock_client,
    )
    assert k_idx == 0
    assert j_idx == 1
    assert meta.common_topic == "Bilateral Summit"


def test_summarizer_mock():
    mock_client = MagicMock()
    mock_summary = ArticleSummary(
        outlet="JoongAng Ilbo",
        country="Korea",
        key_facts=["Summit held in Seoul"],
        stated_positions=["Korea emphasized history resolution"],
        english_summary="The two leaders held talks in Seoul discussing historical reconciliation.",
    )
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(parsed=mock_summary))]
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    res = summarize_to_intermediate_english(
        content="기사 본문 내용...",
        outlet="JoongAng Ilbo",
        country="Korea",
        client=mock_client,
    )
    assert res.english_summary.startswith("The two leaders")
    assert len(res.key_facts) == 1


def test_neutralizer_mock():
    mock_client = MagicMock()
    mock_neutral = NeutralArticle(
        topic_summary="Summary",
        comparison=PerspectiveComparison(
            shared_facts=["Fact 1"],
            korean_emphasis=["KR point"],
            japanese_emphasis=["JP point"],
            framing_divergence="Framing difference",
        ),
        headline_kr="한일 보도 종합",
        headline_jp="日韓報道の総合",
        content_kr="중앙일보는 A라 보도한 반면 요미우리는 B라 보도했다.",
        content_jp="中央日報はAと報じた一方、読売はBと報じた。",
    )
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=MagicMock(parsed=mock_neutral))]
    mock_client.beta.chat.completions.parse.return_value = mock_completion

    k_s = ArticleSummary(
        outlet="JoongAng", country="Korea", key_facts=["Fact 1"], stated_positions=["KR"], english_summary="KR Eng"
    )
    j_s = ArticleSummary(
        outlet="Yomiuri", country="Japan", key_facts=["Fact 1"], stated_positions=["JP"], english_summary="JP Eng"
    )

    neutral = generate_neutral_article(k_s, j_s, mock_client)
    assert "중앙일보" in neutral.content_kr
    assert "読売" in neutral.content_jp
