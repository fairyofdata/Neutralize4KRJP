"""P2 의 집행자 — claim-level provenance 검증.

LLM 에게 "출처 없는 주장을 쓰지 마라"고 지시하는 것으로는 부족하다.
지시는 확률적으로 지켜지고, 지켜졌는지 알 방법이 없다. 그래서 코드가 검사한다.

이 모듈은 LLM 을 호출하지 않는 순수 함수다. 단위 테스트로 동작을 고정한다.
반환되는 ProvenanceReport 가 지표 M1(unsupported_claim_rate)의 산출물이다.
"""

from __future__ import annotations

from .models import Claim, Cluster, ClusterAnalysis, ProvenanceReport


def validate(analysis: ClusterAnalysis, cluster: Cluster) -> tuple[ClusterAnalysis, ProvenanceReport]:
    """클러스터에 없는 article_id 를 참조하는 주장을 제거하고 그 비율을 보고한다.

    규칙:
      - article_ids 중 cluster.article_ids 에 없는 것은 제거 (repaired)
      - 제거 후 article_ids 가 비면 Claim 자체를 폐기 (dropped)
      - quoted_terms 도 같은 규칙으로 검사한다. 원어 인용이 엉뚱한 기사에
        귀속되면 P3 의 의미가 사라지기 때문이다.
      - dropped / total = unsupported_claim_rate (지표 M1)

    폐기된 주장의 원문은 dropped_texts 에 남긴다. 무엇이 환각이었는지
    눈으로 확인할 수 없으면 비율만 있어도 쓸모가 없다.
    """
    valid_ids = set(cluster.article_ids)

    kept: list[Claim] = []
    dropped = 0
    repaired = 0
    dropped_texts: list[str] = []
    total_terms = 0
    dropped_terms = 0

    for claim in analysis.claims:
        good_ids = [aid for aid in claim.article_ids if aid in valid_ids]
        if len(good_ids) != len(claim.article_ids):
            if not good_ids:
                dropped += 1
                dropped_texts.append(claim.text_en)
                total_terms += len(claim.quoted_terms)
                dropped_terms += len(claim.quoted_terms)
                continue
            repaired += 1

        good_terms = []
        for term in claim.quoted_terms:
            total_terms += 1
            if term.article_id in valid_ids:
                good_terms.append(term)
            else:
                dropped_terms += 1

        kept.append(
            claim.model_copy(update={"article_ids": good_ids, "quoted_terms": good_terms})
        )

    report = ProvenanceReport(
        total_claims=len(analysis.claims),
        dropped_claims=dropped,
        repaired_claims=repaired,
        total_quoted_terms=total_terms,
        dropped_quoted_terms=dropped_terms,
        dropped_texts=dropped_texts,
    )
    return analysis.model_copy(update={"claims": kept}), report
