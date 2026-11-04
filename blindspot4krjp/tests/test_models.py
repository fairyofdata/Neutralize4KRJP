"""스키마가 설계 원칙을 실제로 강제하는지."""

import pytest
from pydantic import ValidationError

from blindspot.models import Article, Claim, ClusterAnalysis, SourceProfile

BASE = dict(
    id="x", name="X", country="US", bloc="anglo", language="en",
    ownership="private", editorial_independence="independent", role="source",
    feed={"kind": "rss", "url": "https://example.test/x.xml"},
)


def test_p5_lean_without_basis_is_rejected():
    """P5: 근거 없는 정치성향 라벨은 만들 수 없다."""
    with pytest.raises(ValidationError, match="lean_basis"):
        SourceProfile(**BASE, political_lean="right", lean_basis="")


def test_p5_unclassified_needs_no_basis():
    """근거를 못 찾았을 때의 정답은 unclassified 이고, 그건 허용된다."""
    s = SourceProfile(**BASE, political_lean="unclassified", lean_basis="")
    assert s.political_lean == "unclassified"


def test_p5_lean_with_basis_is_accepted():
    s = SourceProfile(**BASE, political_lean="center_left", lean_basis="AllSides media bias chart")
    assert s.lean_basis


def test_state_control_requires_basis():
    """편집권 라벨도 사실 기술이어야 한다 (§8)."""
    bad = {**BASE, "editorial_independence": "state_controlled"}
    with pytest.raises(ValidationError, match="lean_basis"):
        SourceProfile(**bad, political_lean="unclassified", lean_basis="")


def test_p8_article_has_no_body_field():
    """P8: 본문 필드가 없는 것이 설계다. 추가되면 이 테스트가 깨진다."""
    forbidden = {"body", "full_text", "content", "article_body", "text"}
    assert forbidden.isdisjoint(Article.model_fields.keys())


def test_p2_claim_requires_at_least_one_source(articles):
    """P2: 출처 없는 주장은 생성 자체가 불가능하다."""
    with pytest.raises(ValidationError):
        Claim(text_en="something happened", claim_type="fact", article_ids=[])


def test_p1_cluster_analysis_has_no_verdict_fields():
    """P1: 종합 의견을 담을 자리가 타입에 없다."""
    forbidden = {
        "conclusion", "verdict", "assessment", "neutral_summary",
        "opinion", "synthesis", "neutral_article", "recommendation",
    }
    assert forbidden.isdisjoint(ClusterAnalysis.model_fields.keys())
