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

from .aliases import AliasEntity, AliasIndex
from .models import Article, BaselineProbe, BlindspotVerdict, Cluster, MatchSignals

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


def build_alias_index(aliases: Mapping[str, Iterable[str]] | AliasIndex | None) -> AliasIndex:
    """{개체 id: [표면형, ...]} → AliasIndex. 테스트·간단한 호출용 편의 함수.

    실제 운영에서는 `aliases.load_aliases("aliases.yaml")` 로 만든 AliasIndex 를
    직접 넘긴다. 매칭 규칙(문자 체계별 처리, 짧은 라틴 표기의 대소문자 구분)은
    aliases.AliasIndex 가 담당한다 — 단순 부분 문자열 일치는 "US"/"UN"/"WHO" 에서
    오탐을 내고, 그 오탐이 공백 판정 점수로 바로 들어간다.
    """
    if isinstance(aliases, AliasIndex):
        return aliases
    if not aliases:
        return AliasIndex([])
    return AliasIndex(
        AliasEntity(id=canonical, kind="unknown", surfaces={"und": list(surfaces)})
        for canonical, surfaces in aliases.items()
    )


def entity_tokens(text: str, alias_index: AliasIndex | Mapping | None) -> set[str]:
    """별칭 사전을 거쳐 정규화된 개체 집합."""
    return build_alias_index(alias_index).extract(text)


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
    alias_index: AliasIndex | Mapping | None,
) -> MatchSignals:
    q_nums, c_nums = numeric_tokens(query_text), numeric_tokens(candidate.match_text())
    idx = build_alias_index(alias_index)
    q_ents = idx.extract(query_text)
    c_ents = idx.extract(candidate.match_text())
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
    alias_index: AliasIndex | Mapping | None = None,
) -> BaselineProbe:
    """해외 클러스터 하나에 대해 특정 baseline 국가의 보도 여부를 판정한다."""
    idx = build_alias_index(alias_index)
    bcfg = cfg["baseline"]
    query = build_cluster_query(cluster, cluster_articles, top_k=bcfg.get("query_top_k", 3))

    # 클러스터 기준 시각 = 소속 기사 발행 시각의 중앙값 근처(여기서는 최초 기사)
    times = sorted(
        cluster_articles[aid].published_at
        for aid in cluster.article_ids
        if aid in cluster_articles
    )
    if not baseline_articles:
        # ★ ADR 0005: 그 나라 기사를 그날 하나도 못 받았다.
        # "안 다뤘다"가 아니라 "모른다" 다. 피드가 고장난 날 모든 사건이
        # 공백으로 집계되는 것을 막는 구분이다.
        return BaselineProbe(
            cluster_id=cluster.id,
            baseline_country=baseline_country,
            decision="no_data",
            best_score=0.0,
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
        # 그 나라는 그날 기사를 냈지만 이 사건의 시간대에는 없었다.
        # 위의 no_data 와 다르다 — 이쪽은 진짜 미보도에 가깝다.
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
        sig = compute_signals(query, art, sim, cluster_time, idx)
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
    """공백 판정 (ADR 0005).

    ★ 한국과 일본을 **하나의 언론 환경**으로 본다. 두 독자가 아니라, 두
    언론을 모두 소비하는 한 독자를 가정한다. 목적은 "내가 접하는 언론의
    바깥"을 찾는 것이므로, 한국이 놓쳤어도 일본이 다룬 사건은 그 독자가
    이미 본 것이고 공백이 아니다.

    조건 (전부 충족해야 공백):
      1. 서로 다른 블록 N개 이상이 **독립적으로** 보도했다 (P8, ADR 0004)
      2. baseline 국가가 하나 이상 판정되었다
      3. 판정된 모든 국가가 not_covered 다 (AND)
      4. 판정하지 못한 국가가 없다

    4번이 필요한 이유: 한쪽이 uncertain 이거나 no_data 면 "내가 이미 봤는지"
    를 알 수 없다. 모르는 것을 공백으로 세면 거짓 공백이 된다. 이 설계가
    일관되게 택하는 방향 — 과다 보고보다 과소 보고 — 과 같다.
    """
    min_blocs = cfg["blindspot"]["min_blocs"]
    enough_spread = len(cluster.blocs) >= min_blocs

    missed: set[str] = set()
    covered: set[str] = set()
    undecided: dict[str, str] = {}

    for country, probe in sorted(probes.items()):
        if probe.decision == "not_covered":
            missed.add(country)
        elif probe.decision == "covered":
            covered.add(country)
        elif probe.decision == "uncertain":
            undecided[country] = f"매칭 불확실 (score={probe.best_score:.3f})"
        else:  # no_data
            undecided[country] = "해당 국가 기사 없음 — 판정 불가"

    is_bs = bool(
        enough_spread and missed and not covered and not undecided
    )

    if not enough_spread:
        note = f"독립 보도 블록 {len(cluster.blocs)}개 < 기준 {min_blocs}개"
    elif not probes:
        note = "baseline 판정 없음"
    elif is_bs:
        note = "공백 — " + ", ".join(sorted(missed)) + " 모두 미보도"
    elif covered and missed:
        note = (
            "공백 아님 (이미 접함) — 보도: " + ", ".join(sorted(covered))
            + " / 미보도: " + ", ".join(sorted(missed))
        )
    elif covered:
        note = "공백 아님 — 보도: " + ", ".join(sorted(covered))
    else:
        note = "판정 불가 — " + ", ".join(f"{c}: {r}" for c, r in sorted(undecided.items()))

    return BlindspotVerdict(
        cluster_id=cluster.id,
        event_label=cluster.event_label,
        blocs=set(cluster.blocs),
        spread_score=cluster.spread_score,
        probes=dict(probes),
        is_blindspot=is_bs,
        missed_by=missed,
        covered_by=covered,
        undecided=undecided,
        note=note,
    )


def spread_score(blocs: Iterable[str], countries: Iterable[str]) -> float:
    """P8. 구현은 cluster.spread_from 에 있다 — 클러스터 구성과 같은 자리에 둔다."""
    from .cluster import spread_from

    return spread_from(blocs, countries)
