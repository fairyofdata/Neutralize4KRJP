"""'공통 사실'이 LLM 판단이 아니라 집합 연산이라는 것을 고정한다."""

from __future__ import annotations

from blindspot import derive
from blindspot.models import Claim, QuotedTerm


def test_shared_fact_needs_two_different_blocs(articles, sources):
    cross = Claim(text_en="4500 attended", claim_type="fact", article_ids=["a1", "a3"])  # anglo+eu
    same = Claim(text_en="police acted", claim_type="fact", article_ids=["a1", "a2"])     # anglo+anglo
    out = derive.shared_facts([cross, same], articles, sources)
    assert [c.text_en for c in out] == ["4500 attended"]


def test_wire_copy_within_one_bloc_is_not_cross_confirmation(articles, sources):
    """앵글로권 매체 둘이 같은 내용을 실은 것은 교차 확인이 아니다."""
    c = Claim(text_en="x", claim_type="fact", article_ids=["a1", "a2"])
    assert derive.shared_facts([c], articles, sources) == []
    assert derive.solo_facts([c], articles, sources) == [c]


def test_characterizations_are_grouped_by_bloc(articles, sources):
    claims = [
        Claim(text_en="described as crackdown", claim_type="characterization", article_ids=["a1"],
              quoted_terms=[QuotedTerm(term_orig="crackdown", lang="en", gloss_en="crackdown", article_id="a1")]),
        Claim(text_en="described as lawful handling", claim_type="characterization", article_ids=["a4"]),
        Claim(text_en="described as special operation", claim_type="characterization", article_ids=["a5"]),
    ]
    out = derive.framing_contrast(claims, articles, sources)
    assert set(out) == {"anglo", "sinosphere", "russia"}
    assert out["anglo"][0].quoted_terms[0].term_orig == "crackdown"


def test_facts_are_not_treated_as_framing(articles, sources):
    f = Claim(text_en="4500 attended", claim_type="fact", article_ids=["a1", "a3"])
    assert derive.framing_contrast([f], articles, sources) == {}


def test_attributed_positions_are_separated(articles, sources):
    p = Claim(text_en="Ministry said order was restored", claim_type="attributed_position", article_ids=["a5"])
    f = Claim(text_en="4500 attended", claim_type="fact", article_ids=["a1"])
    assert derive.attributed_positions([p, f]) == [p]


def test_anglo_amplification_detects_over_citation(articles, sources, cluster):
    """M2: 입력 비중(2/5=0.4)보다 앵글로권을 많이 인용하면 양수."""
    claims = [Claim(text_en="x", claim_type="fact", article_ids=["a1", "a2"])]  # 100% anglo
    score = derive.anglo_amplification(claims, cluster.article_ids, articles, sources)
    assert score > 0
    assert abs(score - (1.0 - 0.4)) < 1e-9


def test_anglo_amplification_is_zero_when_proportional(articles, sources, cluster):
    claims = [Claim(text_en="x", claim_type="fact", article_ids=["a1", "a2", "a3", "a4", "a5"])]
    score = derive.anglo_amplification(claims, cluster.article_ids, articles, sources)
    assert abs(score) < 1e-9


def test_anglo_amplification_negative_when_under_citing(articles, sources, cluster):
    claims = [Claim(text_en="x", claim_type="fact", article_ids=["a3", "a4"])]  # eu+sinosphere
    assert derive.anglo_amplification(claims, cluster.article_ids, articles, sources) < 0
