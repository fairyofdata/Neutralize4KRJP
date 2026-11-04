"""파생 집계 — '공통 사실'은 LLM 출력이 아니라 계산 결과다.

이것이 이 프로젝트의 중심 설계다.

이전 접근(기존 저장소 Neutralize4KRJP)에서는 LLM 이 shared_facts 필드를
직접 채웠다. 그래서 무엇이 '공통 사실'인지가 모델의 판단에 달려 있었고,
재현도 반증도 불가능했다. 그것이 "중립성을 측정하지 않았다"의 근원이었다.

여기서는 LLM 이 "이 주장은 이 기사들에 나온다"만 말하고, 무엇이 공통
사실인지는 아래 함수들이 집합 연산으로 정한다. 정의가 코드에 적혀 있으므로
재현 가능하고, 정의가 틀렸다고 반박할 수도 있다.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from .models import Article, Claim, SourceProfile


def blocs_of(
    article_ids: Sequence[str],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> set[str]:
    out: set[str] = set()
    for aid in article_ids:
        art = articles.get(aid)
        if art is None:
            continue
        src = sources.get(art.source_id)
        if src is not None:
            out.add(src.bloc)
    return out


def shared_facts(
    claims: Sequence[Claim],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
    min_blocs: int = 2,
) -> list[Claim]:
    """공통 사실 = 서로 다른 블록 min_blocs개 이상이 보도한 fact 주장.

    '여러 매체가 보도' 가 아니라 '여러 블록이 보도' 인 이유: 앵글로권 매체
    다섯 곳이 같은 통신사 기사를 전재한 것은 교차 확인이 아니다.
    """
    return [
        c
        for c in claims
        if c.claim_type == "fact"
        and len(blocs_of(c.article_ids, articles, sources)) >= min_blocs
    ]


def solo_facts(
    claims: Sequence[Claim],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> list[Claim]:
    """한 블록만 보도한 사실 주장. 틀렸다는 뜻이 아니라 교차 확인이 없다는 뜻이다."""
    return [
        c
        for c in claims
        if c.claim_type == "fact"
        and len(blocs_of(c.article_ids, articles, sources)) == 1
    ]


def framing_contrast(
    claims: Sequence[Claim],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> dict[str, list[Claim]]:
    """블록별 서술 어휘. P3 의 출력 지점.

    같은 대상에 각 블록이 어떤 단어를 붙였는지를 나란히 놓는다.
    "crackdown" / "依法处置" / "спецоперация" 를 병치하는 것 자체가 산출물이며,
    어느 쪽이 맞다는 판정은 하지 않는다 (P1).
    """
    out: dict[str, list[Claim]] = defaultdict(list)
    for c in claims:
        if c.claim_type != "characterization":
            continue
        for bloc in blocs_of(c.article_ids, articles, sources):
            out[bloc].append(c)
    return dict(out)


def attributed_positions(claims: Sequence[Claim]) -> list[Claim]:
    """귀속된 입장. 출력에서는 반드시 소스 라벨(소유구조·편집권)과 함께 표시한다 (P4)."""
    return [c for c in claims if c.claim_type == "attributed_position"]


def anglo_amplification(
    claims: Sequence[Claim],
    article_ids_in_cluster: Sequence[str],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> float:
    """지표 M2.

    (주장이 인용한 기사 중 앵글로권 비율) − (클러스터 입력 중 앵글로권 비율).

    양수면 모델이 영미권 소스를 입력 비중 이상으로 인용하고 있다는 뜻이다.
    영어권 웹으로 학습된 모델을 중립 심판으로 쓰는 데서 오는 편향을
    문서에 적어두는 대신 숫자로 감시한다.
    """

    def anglo_share(ids: Sequence[str]) -> float:
        total = 0
        anglo = 0
        for aid in ids:
            art = articles.get(aid)
            if art is None:
                continue
            src = sources.get(art.source_id)
            if src is None:
                continue
            total += 1
            if src.bloc == "anglo":
                anglo += 1
        return anglo / total if total else 0.0

    cited = [aid for c in claims for aid in c.article_ids]
    if not cited:
        return 0.0
    return anglo_share(cited) - anglo_share(article_ids_in_cluster)
