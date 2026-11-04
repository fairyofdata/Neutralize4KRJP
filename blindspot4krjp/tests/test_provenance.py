"""P2 집행 — validator 의 동작을 고정한다."""

from __future__ import annotations

from blindspot.models import Claim, ClusterAnalysis, QuotedTerm
from blindspot.provenance import validate


def _analysis(*claims: Claim) -> ClusterAnalysis:
    return ClusterAnalysis(cluster_id="c1", claims=list(claims))


def test_valid_claims_pass_through(cluster):
    a = _analysis(Claim(text_en="x", claim_type="fact", article_ids=["a1", "a2"]))
    out, rep = validate(a, cluster)
    assert len(out.claims) == 1
    assert rep.dropped_claims == 0
    assert rep.unsupported_claim_rate == 0.0


def test_claim_citing_unknown_article_is_dropped(cluster):
    a = _analysis(Claim(text_en="hallucinated", claim_type="fact", article_ids=["ghost"]))
    out, rep = validate(a, cluster)
    assert out.claims == []
    assert rep.dropped_claims == 1
    assert rep.unsupported_claim_rate == 1.0
    assert "hallucinated" in rep.dropped_texts


def test_partially_valid_claim_is_repaired_not_dropped(cluster):
    a = _analysis(Claim(text_en="x", claim_type="fact", article_ids=["a1", "ghost"]))
    out, rep = validate(a, cluster)
    assert out.claims[0].article_ids == ["a1"]
    assert rep.repaired_claims == 1
    assert rep.dropped_claims == 0


def test_quoted_term_with_bad_attribution_is_dropped(cluster):
    """P3 의 의미는 인용이 올바른 기사에 귀속될 때만 성립한다."""
    a = _analysis(
        Claim(
            text_en="framing",
            claim_type="characterization",
            article_ids=["a1"],
            quoted_terms=[
                QuotedTerm(term_orig="crackdown", lang="en", gloss_en="crackdown", article_id="a1"),
                QuotedTerm(term_orig="ghosted", lang="en", gloss_en="x", article_id="ghost"),
            ],
        )
    )
    out, rep = validate(a, cluster)
    assert [t.term_orig for t in out.claims[0].quoted_terms] == ["crackdown"]
    assert rep.dropped_quoted_terms == 1
    assert rep.total_quoted_terms == 2


def test_rate_is_the_m1_metric(cluster):
    a = _analysis(
        Claim(text_en="ok1", claim_type="fact", article_ids=["a1"]),
        Claim(text_en="ok2", claim_type="fact", article_ids=["a2"]),
        Claim(text_en="bad", claim_type="fact", article_ids=["nope"]),
    )
    _, rep = validate(a, cluster)
    assert rep.total_claims == 3
    assert abs(rep.unsupported_claim_rate - 1 / 3) < 1e-9


def test_validator_is_pure(cluster):
    """입력 객체를 변형하지 않는다."""
    a = _analysis(Claim(text_en="x", claim_type="fact", article_ids=["a1", "ghost"]))
    before = a.model_dump_json()
    validate(a, cluster)
    assert a.model_dump_json() == before
