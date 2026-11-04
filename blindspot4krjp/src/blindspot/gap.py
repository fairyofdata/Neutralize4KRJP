"""보도 공백 판정 — 비대칭 검색 방식.

왜 클러스터링이 아니라 검색인가
--------------------------------
처음 설계는 "한국 기사가 해외 클러스터에 같이 묶이면 보도된 것"이었다.
이 방식은 실패 방향이 한쪽으로 쏠린다. 교차언어 임베딩에서 매칭에 실패할
가능성이 가장 높은 것이 바로 한국어 기사이므로, 클러스터링이 실패할 때마다
"한국 언론이 다루지 않았다"는 거짓 공백이 계통적으로 과다 생성된다.
제품의 핵심 지표가 가장 흔한 실패 모드에 의해 한 방향으로 부풀려지는 구조다.

그래서 판정을 뒤집는다:
  1. 클러스터는 해외 소스만으로 만든다 (baseline 기사는 클러스터링에 참여하지 않는다).
  2. 각 해외 클러스터의 대표 문장을 **질의**로 삼아 baseline 코퍼스를 검색한다.
  3. baseline 쪽은 임계값과 시간 윈도우를 **따로, 더 느슨하게** 둔다.
  4. 판정은 3분기다. 애매한 구간(uncertain)은 공백으로 집계하지 않고 따로 센다.

결과적으로 틀리는 방향이 보수적으로 뒤집힌다 — 공백을 과다 보고하는 대신
과소 보고한다. 지표로서는 이쪽이 정직하다.

임베딩만으로는 짧은 텍스트의 사건 동일성이 불안정하므로 신호를 섞는다.
숫자·연도는 언어 독립 신호라서 사전 없이도 작동하고, 개체명은 작은 별칭
사전을 거쳐 정규화한다.

이 모듈의 모든 임계값과 가중치는 **미보정**이다. eval/gap_calibration.py 로
손 라벨을 받아 보정하기 전까지 여기서 나온 수치를 공개 지표로 쓰지 말 것 (P9).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import timedelta

from .models import Article, BaselineProbe, BlindspotVerdict, Cluster, MatchSignals, SourceProfile

# 질의 1건 vs 후보 N건의 코사인 유사도를 돌려주는 함수. 주입해서 쓴다.
# 실제 구현은 다국어 문장 임베딩 모델, 테스트에서는 가짜 함수.
EmbedSim = Callable[[str, Sequence[str]], Sequence[float]]

_NUM_RE = re.compile(r"\d[\d,._]*")


def numeric_tokens(text: str) -> set[str]:
    """숫자·연도 토큰. 구분자를 벗기고 2자리 이상만 남긴다.

    언어에 거의 의존하지 않는 신호다. 한국어·일본어·중국어·러시아어 기사 모두
    아라비아 숫자로 사망자 수, 연도, 금액, 의석 수를 쓴다. 사전이 필요 없다.
    1자리 숫자는 노이즈가 커서 버린다.
    """
    out: set[str] = set()
    for raw in _NUM_RE.findall(text):
        digits = re.sub(r"[,._]", "", raw)
        if len(digits) >= 2:
            out.add(digits)
    return out


def build_alias_index(aliases: Mapping[str, Iterable[str]]) -> dict[str, str]:
    """{canonical_id: [표면형, ...]} → {표면형(소문자): canonical_id}.

    표면형은 언어별 표기를 모두 담는다. 예:
      us_president_trump: ["Trump", "트럼프", "トランプ", "特朗普", "Трамп"]
    전면 다국어 NER 대신 반복 등장하는 수백 개 개체만 손으로 관리한다.
    유지보수 항목이지만 투입 대비 효과가 크다.
    """
    index: dict[str, str] = {}
    for canonical, surfaces in aliases.items():
        for s in surfaces:
            s = s.strip().lower()
            if s:
                index[s] = canonical
    return index


def entity_tokens(text: str, alias_index: Mapping[str, str]) -> set[str]:
    """별칭 사전을 거쳐 정규화된 개체 집합. 부분 문자열 일치로 찾는다.

    CJK 는 공백으로 단어가 나뉘지 않으므로 토큰화 대신 부분 문자열 일치가 맞다.
    """
    low = text.lower()
    return {canon for surface, canon in alias_index.items() if surface in low}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def build_cluster_query(
    cluster: Cluster,
    articles: Mapping[str, Article],
    top_k: int = 3,
) -> str:
    """클러스터의 대표 질의 문장.

    현재는 앞쪽 k개 기사의 match_text 를 이어붙인다. 임베딩 중심점에서 가장
    가까운 k개를 쓰는 편이 낫지만, 그건 클러스터링 구현이 들어온 뒤의 일이다
    (Phase 1). 여기서는 호출 계약만 고정한다.
    """
    texts: list[str] = []
    for aid in cluster.article_ids[:top_k]:
        art = articles.get(aid)
        if art is not None:
            texts.append(art.match_text())
    return "\n\n".join(texts)


def compute_signals(
    query_text: str,
    candidate: Article,
    embedding_sim: float,
    cluster_time,
    alias_index: Mapping[str, str],
) -> MatchSignals:
    q_nums, c_nums = numeric_tokens(query_text), numeric_tokens(candidate.match_text())
    q_ents = entity_tokens(query_text, alias_index)
    c_ents = entity_tokens(candidate.match_text(), alias_index)
    delta = abs((candidate.published_at - cluster_time).total_seconds()) / 3600.0
    return MatchSignals(
        embedding_max=embedding_sim,
        entity_overlap=jaccard(q_ents, c_ents),
        numeric_overlap=jaccard(q_nums, c_nums),
        time_delta_hours=delta,
    )


def blend(signals: MatchSignals, weights: Mapping[str, float]) -> float:
    """선형 결합. 설명 가능하고, 손 라벨로 가중치를 맞출 수 있다.

    복잡한 학습 모델을 쓰지 않는 이유: 라벨이 수십 건 규모라 과적합하고,
    왜 그렇게 판정했는지 사용자에게 보여줄 수 없게 된다.
    """
    return (
        weights.get("embedding", 0.6) * max(signals.embedding_max, 0.0)
        + weights.get("entity", 0.25) * signals.entity_overlap
        + weights.get("numeric", 0.15) * signals.numeric_overlap
    )


def decide(score: float, tau_low: float, tau_high: float) -> str:
    """3분기 판정. 사이 구간을 covered 로도 not_covered 로도 밀지 않는다."""
    if score >= tau_high:
        return "covered"
    if score < tau_low:
        return "not_covered"
    return "uncertain"


def probe_baseline(
    cluster: Cluster,
    cluster_articles: Mapping[str, Article],
    baseline_articles: Sequence[Article],
    baseline_country: str,
    embed_sim: EmbedSim,
    cfg: Mapping,
    alias_index: Mapping[str, str] | None = None,
) -> BaselineProbe:
    """해외 클러스터 하나에 대해 특정 baseline 국가의 보도 여부를 판정한다."""
    alias_index = alias_index or {}
    bcfg = cfg["baseline"]
    query = build_cluster_query(cluster, cluster_articles, top_k=bcfg.get("query_top_k", 3))

    # 클러스터 기준 시각 = 소속 기사 발행 시각의 중앙값 근처(여기서는 최초 기사)
    times = sorted(
        cluster_articles[aid].published_at
        for aid in cluster.article_ids
        if aid in cluster_articles
    )
    if not times or not query.strip():
        return BaselineProbe(
            cluster_id=cluster.id,
            baseline_country=baseline_country,
            decision="uncertain",
            best_score=0.0,
        )
    cluster_time = times[len(times) // 2]

    # ★ 비대칭 1: baseline 쪽 시간 윈도우를 더 넓게 둔다.
    #    한국 언론은 해외 사건을 하루 이상 늦게 다루는 경우가 흔하다.
    window = timedelta(hours=bcfg.get("window_hours", 72))
    pool = [
        a
        for a in baseline_articles
        if a.source_id and abs(a.published_at - cluster_time) <= window
    ]
    if not pool:
        return BaselineProbe(
            cluster_id=cluster.id,
            baseline_country=baseline_country,
            decision="not_covered",
            best_score=0.0,
        )

    sims = list(embed_sim(query, [a.match_text() for a in pool]))
    best_score = -1.0
    best: tuple[Article, MatchSignals] | None = None
    for art, sim in zip(pool, sims, strict=True):
        sig = compute_signals(query, art, sim, cluster_time, alias_index)
        score = blend(sig, bcfg.get("weights", {}))
        if score > best_score:
            best_score, best = score, (art, sig)

    assert best is not None
    art, sig = best
    # ★ 비대칭 2: 클러스터링 임계값과 별개의, 더 느슨한 임계값을 쓴다.
    decision = decide(best_score, bcfg["tau_low"], bcfg["tau_high"])
    return BaselineProbe(
        cluster_id=cluster.id,
        baseline_country=baseline_country,
        decision=decision,
        best_score=best_score,
        matched_article_ids=[art.id] if decision == "covered" else [],
        signals=sig,
    )


def verdict(
    cluster: Cluster,
    probes: Mapping[str, BaselineProbe],
    cfg: Mapping,
) -> BlindspotVerdict:
    """공백 판정.

    규칙: 서로 다른 블록 N개 이상이 보도했고(P7), KR 이 not_covered 일 때만 공백.
    KR 이 uncertain 이면 공백으로 세지 않는다 — 과다 보고를 막기 위한 보수적 선택이며,
    그 대신 note 에 이유를 남겨 집계할 수 있게 한다.
    """
    min_blocs = cfg["blindspot"]["min_blocs"]
    kr = probes.get("KR")
    enough_spread = len(cluster.blocs) >= min_blocs

    if not enough_spread:
        note = f"블록 {len(cluster.blocs)}개 < 기준 {min_blocs}개"
        is_bs = False
    elif kr is None:
        note = "KR baseline probe 없음"
        is_bs = False
    elif kr.decision == "uncertain":
        note = f"KR 매칭 불확실 (score={kr.best_score:.3f}) — 공백 집계에서 제외"
        is_bs = False
    elif kr.decision == "covered":
        note = "KR 보도 있음"
        is_bs = False
    else:
        note = "블록 기준 충족 + KR 보도 없음"
        is_bs = True

    return BlindspotVerdict(
        cluster_id=cluster.id,
        event_label=cluster.event_label,
        blocs=set(cluster.blocs),
        spread_score=cluster.spread_score,
        probes=dict(probes),
        is_blindspot=is_bs,
        note=note,
    )


def spread_score(blocs: Iterable[str], countries: Iterable[str]) -> float:
    """P7: 기사 수를 쓰지 않는다.

    앵글로권은 영문 매체가 압도적으로 많아서, 기사 수로 랭킹하면 미·영 의제가
    세계 의제로 둔갑한다. 블록 수를 주 신호로, 국가 수를 보조로 쓴다.
    """
    b, c = len(set(blocs)), len(set(countries))
    return b + 0.1 * c
