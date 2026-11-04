"""사건 클러스터링 — 임베딩 함수를 주입받는다.

주입 구조인 이유: 임베딩 모델 선택은 Phase 1 의 열린 문제이고(로컬 다국어
모델 vs 상용 API), 모델을 고르기 전에 클러스터링 로직을 완성하고 테스트할
수 있어야 한다. 테스트는 가짜 임베딩을 넣어 돌아가므로 네트워크도 비용도
쓰지 않는다.

연결 방식은 **평균 연결(average-link)** 이다. 단일 연결(single-link)은
뉴스에서 사슬 효과가 심하다 — A≈B, B≈C 라는 이유로 A 와 C 가 전혀 다른
사건인데도 한 클러스터가 된다. 평균 연결은 그 사슬을 끊는다.

★ P6 집행 지점: baseline(KR·JP) 기사가 들어오면 예외를 던진다.
"브리핑 본문에 투입하지 않는다"를 방침이 아니라 구조로 만든다.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta

from .dedupe import blocs_with_pickups, group_wire_duplicates, origin_blocs
from .models import Article, Cluster, SourceProfile

# 텍스트 목록 → 벡터 목록. sentence-transformers 의 encode 와 같은 모양.
Embedder = Callable[[Sequence[str]], Sequence[Sequence[float]]]


class BaselineLeakError(RuntimeError):
    """P6 위반 — baseline 기사가 클러스터링에 들어왔다."""


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return num / (na * nb)


def _average_link(
    ids: Sequence[str],
    sim: dict[tuple[str, str], float],
    threshold: float,
) -> list[list[str]]:
    """평균 연결 응집 클러스터링. 임계값 아래가 되면 멈춘다."""
    groups: list[list[str]] = [[i] for i in ids]

    def pair_sim(g1: list[str], g2: list[str]) -> float:
        total = 0.0
        for x in g1:
            for y in g2:
                total += sim.get((x, y), sim.get((y, x), 0.0))
        return total / (len(g1) * len(g2))

    while len(groups) > 1:
        best = (-1.0, -1, -1)
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                s = pair_sim(groups[i], groups[j])
                if s > best[0]:
                    best = (s, i, j)
        if best[0] < threshold:
            break
        _, i, j = best
        groups[i] = groups[i] + groups[j]
        groups.pop(j)
    return groups


def build_clusters(
    articles: Sequence[Article],
    sources: Mapping[str, SourceProfile],
    embed: Embedder,
    cfg: Mapping,
    *,
    day: date | None = None,
) -> list[Cluster]:
    """해외 소스 기사 → 클러스터 목록.

    같은 사건 판정은 임베딩 유사도와 시간 근접성을 함께 본다. 윈도우 밖의
    쌍은 유사도를 0으로 둬서 다른 날의 비슷한 사건이 합쳐지지 않게 한다.
    """
    for art in articles:
        profile = sources.get(art.source_id)
        if profile is None:
            raise BaselineLeakError(f"알 수 없는 소스: {art.source_id}")
        if profile.role != "source":
            raise BaselineLeakError(
                f"{art.source_id} 는 role={profile.role} 다. baseline 기사는 "
                f"클러스터링에 들어갈 수 없다 (P6). 공백 판정에만 쓰인다."
            )
    if not articles:
        return []

    ccfg = cfg["cluster"]
    window = timedelta(hours=ccfg["window_hours"])
    threshold = ccfg["cosine_threshold"]
    min_size = ccfg.get("min_cluster_size", 2)

    ordered = sorted(articles, key=lambda a: (a.published_at, a.id))
    vectors = list(embed([a.match_text() for a in ordered]))
    if len(vectors) != len(ordered):
        raise ValueError("임베딩 개수가 기사 수와 다르다")

    by_id = {a.id: a for a in ordered}
    sim: dict[tuple[str, str], float] = {}
    for i, a in enumerate(ordered):
        for j in range(i + 1, len(ordered)):
            b = ordered[j]
            if abs((b.published_at - a.published_at)) > window:
                continue
            sim[(a.id, b.id)] = cosine(vectors[i], vectors[j])

    out: list[Cluster] = []
    for idx, member_ids in enumerate(
        _average_link([a.id for a in ordered], sim, threshold)
    ):
        if len(member_ids) < min_size:
            continue
        members = sorted((by_id[i] for i in member_ids), key=lambda a: (a.published_at, a.id))

        groups = group_wire_duplicates(members, sources)
        blocs = origin_blocs(groups)
        display_blocs = blocs_with_pickups(members, sources)
        countries = {
            sources[a.source_id].country for a in members if a.source_id in sources
        }

        out.append(
            Cluster(
                id=f"c{idx + 1:03d}",
                day=day or members[0].published_at.date(),
                article_ids=[a.id for a in members],
                # Phase 2 에서 LLM 이 사건명을 붙일 때까지는 최초 보도의 제목을 쓴다.
                # 사실 주장이 아니라 식별용 라벨이다.
                event_label=members[0].title_orig,
                countries=countries,
                blocs=blocs,
                blocs_with_pickups=display_blocs,
                wire_groups=len(groups),
                spread_score=spread_from(blocs, countries),
            )
        )

    out.sort(key=lambda c: (-c.spread_score, c.id))
    return out


def spread_from(blocs, countries) -> float:
    """P8: 기사 수를 쓰지 않는다.

    앵글로권은 영문 매체가 압도적으로 많아서, 기사 수로 랭킹하면 미·영 의제가
    세계 의제로 둔갑한다. 블록 수를 주 신호로, 국가 수를 보조로 쓴다.
    """
    return len(set(blocs)) + 0.1 * len(set(countries))
