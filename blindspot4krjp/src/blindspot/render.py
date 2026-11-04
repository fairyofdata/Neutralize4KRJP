"""브리핑 렌더링 — Markdown.

여기에 '종합 의견' 절이 없는 것이 설계다 (P1). 렌더러는 계산된 집합을
나란히 놓을 뿐이고, 어느 쪽이 맞는지 쓰지 않는다. 판단은 독자가 한다.

소스 라벨(소유구조·편집권)을 인용마다 붙인다 (P4). 국가통제 매체를 라벨
없이 인용하면 선전을 관점으로 승격시키는 구조가 된다.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from . import derive
from .models import (
    Article,
    Cluster,
    ClusterAnalysis,
    ExposureVerdict,
    SourceProfile,
)

_INDEPENDENCE_LABEL = {
    "independent": "",
    "partly_constrained": " · 편집권 제약",
    "state_controlled": " · 국가통제",
}
_OWNERSHIP_LABEL = {
    "state_owned": "국영",
    "party_organ": "당 기관지",
    "public_broadcaster": "공영",
    "private": "",
    "nonprofit": "",
}


def flag(country: str) -> str:
    """ISO 3166-1 alpha-2 → 지역 표시 기호. 결정론적이다."""
    if len(country) != 2 or not country.isalpha():
        return country
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in country.upper())


def source_label(profile: SourceProfile) -> str:
    """P4: 인용마다 소유구조·편집권을 함께 표시한다."""
    bits = [profile.name]
    owner = _OWNERSHIP_LABEL.get(profile.ownership, "")
    indep = _INDEPENDENCE_LABEL.get(profile.editorial_independence, "")
    if owner:
        bits.append(f"({owner})")
    return "".join([" ".join(bits), indep])


def _cite(article_ids: Sequence[str], articles: Mapping[str, Article],
          sources: Mapping[str, SourceProfile]) -> str:
    names = []
    for aid in article_ids:
        art = articles.get(aid)
        if art is None:
            continue
        profile = sources.get(art.source_id)
        names.append(source_label(profile) if profile else art.source_id)
    return ", ".join(dict.fromkeys(names))


def _coverage_line(cluster: Cluster, articles: Mapping[str, Article],
                   sources: Mapping[str, SourceProfile]) -> str:
    per_country: dict[str, int] = {}
    for aid in cluster.article_ids:
        art = articles.get(aid)
        profile = sources.get(art.source_id) if art else None
        if profile:
            per_country[profile.country] = per_country.get(profile.country, 0) + 1
    parts = [f"{flag(c)}{n}" for c, n in sorted(per_country.items())]
    return " ".join(parts)


_TIER_KO = {
    "absent": "안쪽 보도 없음",
    "underreported": "안쪽 과소 보도",
    "comparable": "안쪽에서도 충분히 보도",
    "undecided": "판정 불가",
    "insufficient_spread": "바깥에서도 널리 다뤄지지 않음",
}


def _home_line(verdict: ExposureVerdict) -> str:
    home = verdict.home
    if home.has_coverage:
        detail = ", ".join(f"{flag(c)}{n}" for c, n in sorted(home.by_country.items()))
        return f"안쪽 {home.article_count}건 ({detail}) · 노출 격차 {verdict.exposure_gap:.2f}"
    if home.undecided:
        return "안쪽 판정 불가 — " + ", ".join(
            f"{flag(c)} {r}" for c, r in sorted(home.undecided.items())
        )
    return f"안쪽 보도 없음 · 노출 격차 {verdict.exposure_gap:.2f}"


def render_exposure_gaps(
    verdicts: Sequence[ExposureVerdict],
    clusters: Mapping[str, Cluster],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> list[str]:
    """노출 격차 순으로 보여준다 (ADR 0006).

    '아예 안 다뤄진 것'과 '적게 다뤄진 것'을 같은 축에 두고, 격차가 큰
    순서로 정렬한다. 이진 목록이 아니라 정도의 문제로 다룬다.
    """
    def key(v: ExposureVerdict):
        return (-v.exposure_gap, -v.spread_score, v.cluster_id)

    absent = sorted((v for v in verdicts if v.tier == "absent"), key=key)
    under = sorted((v for v in verdicts if v.tier == "underreported"), key=key)
    undecided = [v for v in verdicts if v.tier == "undecided"]

    def entry(n: int, v: ExposureVerdict) -> list[str]:
        out = [f"{n}. **{v.event_label}**"]
        cluster = clusters.get(v.cluster_id)
        if cluster is not None:
            out.append(
                f"   - 바깥 보도: {_coverage_line(cluster, articles, sources)}"
                f" · 독립 보도 {cluster.wire_groups}건 · 블록 {len(cluster.blocs)}개"
            )
        out.append(f"   - {_home_line(v)}")
        return out

    lines = ["## 내가 접하기 어려웠던 사건", ""]

    lines += ["### 안쪽 보도 없음", "", "_접할 기회가 아예 없었던 사건._", ""]
    if absent:
        for n, v in enumerate(absent, 1):
            lines += entry(n, v)
            lines.append("")
    else:
        lines += ["해당 없음.", ""]

    if under:
        lines += ["### 안쪽 과소 보도", "",
                  "_안쪽에서도 다뤘지만 바깥에 비해 현저히 적게 다뤄진 사건._", ""]
        for n, v in enumerate(under, 1):
            lines += entry(n, v)
            lines.append("")

    if undecided:
        reasons = sorted({r for v in undecided for r in v.home.undecided.values()})
        lines += [
            f"> 판정 불가 {len(undecided)}건은 제외했습니다 — " + "; ".join(reasons)
            + ". 모르는 것을 '안 다뤄졌다'로 세면 거짓 신호가 됩니다 (ADR 0002·0005).",
            "",
        ]
    return lines


def render_outside_view(
    verdicts: Sequence[ExposureVerdict],
    clusters: Mapping[str, Cluster],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
    home_entities: Sequence[str],
) -> list[str]:
    """★ 외부에서 본 안쪽 이슈 (ADR 0006).

    노출 격차의 역방향이다. 내가 놓친 것을 찾는 게 아니라, **내 나라 이슈를
    제3자가 어떻게 쓰는지** 본다. 안쪽에서 보는 것보다 객관적이라는 보장은
    없지만, 이해관계가 다른 복수의 시선이라는 점은 보장된다.

    별칭 사전이 한국·일본 관련 개체를 추출하므로 새 기계가 필요 없다.
    """
    wanted = set(home_entities)
    picked = [
        v for v in verdicts
        if (c := clusters.get(v.cluster_id)) is not None and (c.entities & wanted)
    ]
    if not picked:
        return []

    lines = ["## 외부에서 본 안쪽 이슈", "",
             "_한국·일본 관련 사안을 바깥 언론이 어떻게 다루는지._", ""]
    for n, v in enumerate(
        sorted(picked, key=lambda x: (-x.spread_score, x.cluster_id)), 1
    ):
        cluster = clusters[v.cluster_id]
        hit = ", ".join(sorted(cluster.entities & wanted))
        lines.append(f"{n}. **{v.event_label}**  _({hit})_")
        lines.append(
            f"   - 바깥 보도: {_coverage_line(cluster, articles, sources)}"
            f" · 블록 {len(cluster.blocs)}개"
        )
        lines.append(f"   - {_home_line(v)}")
        lines.append("")
    return lines


def render_home_framing(
    verdict: ExposureVerdict | None,
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> list[str]:
    """안쪽 언론이 쓴 틀을 비교표의 한 행으로 보여준다 (ADR 0006).

    설계 초기에는 안쪽 매체를 브리핑 본문에서 의도적으로 뺐다. 누락 탐지에는
    맞았지만, **굴절 탐지에서는 안쪽 프레이밍이 바로 관찰 대상**이다.
    다른 블록과 나란히 놓고 "당신이 본 틀은 이것이었다"로 보여준다.

    LLM 주장 추출(Phase 2)을 거치지 않고 원문 제목을 그대로 인용한다 —
    안쪽 프레이밍은 요약하면 안 되는 대상이다.
    """
    if verdict is None or not verdict.home.matched_article_ids:
        return []
    lines = ["**안쪽 언론이 쓴 틀** — 당신이 접한 서술", ""]
    for aid in verdict.home.matched_article_ids:
        art = articles.get(aid)
        if art is None:
            continue
        profile = sources.get(art.source_id)
        name = profile.name if profile else art.source_id
        country = flag(profile.country) if profile else ""
        lines.append(f"- {country} 「{art.title_orig}」  ·  _{name}_  ·  [원문]({art.url})")
    lines.append("")
    return lines


def render_cluster(
    cluster: Cluster,
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
    analysis: ClusterAnalysis | None = None,
    verdict: ExposureVerdict | None = None,
) -> list[str]:
    lines = [
        f"### {cluster.event_label}",
        "",
        f"보도 {len(cluster.article_ids)}건 · 독립 보도 {cluster.wire_groups}건 · "
        f"{len(cluster.countries)}개국 · 블록 {len(cluster.blocs)}개",
        "",
        f"{_coverage_line(cluster, articles, sources)}",
        "",
    ]
    if cluster.blocs_with_pickups - cluster.blocs:
        extra = ", ".join(sorted(cluster.blocs_with_pickups - cluster.blocs))
        lines += [f"> 전재로만 보도된 블록: {extra} (블록 집계에서 제외, ADR 0004)", ""]

    lines += render_home_framing(verdict, articles, sources)

    if analysis is None:
        lines += ["_바깥 언론의 주장 추출은 Phase 2 입니다._", ""]
        return lines

    shared = derive.shared_facts(analysis.claims, articles, sources)
    solo = derive.solo_facts(analysis.claims, articles, sources)
    framing = derive.framing_contrast(analysis.claims, articles, sources)
    positions = derive.attributed_positions(analysis.claims)

    lines += ["**공통 사실** — 서로 다른 2개 이상 블록이 함께 보도", ""]
    lines += [f"- {c.text_en}  ·  _{_cite(c.article_ids, articles, sources)}_" for c in shared] or ["- 없음"]
    lines.append("")

    if solo:
        lines += ["**한 블록만 보도한 사실** — 틀렸다는 뜻이 아니라 교차 확인이 없다는 뜻", ""]
        lines += [f"- {c.text_en}  ·  _{_cite(c.article_ids, articles, sources)}_" for c in solo]
        lines.append("")

    if framing:
        lines += ["**서술의 차이** — 같은 대상, 다른 단어", ""]
        for bloc in sorted(framing):
            for claim in framing[bloc]:
                terms = " / ".join(
                    f"`{t.term_orig}`" + (f" ({t.gloss_en})" if t.gloss_en != t.term_orig else "")
                    for t in claim.quoted_terms
                ) or claim.text_en
                lines.append(f"- **{bloc}** {terms}  ·  _{_cite(claim.article_ids, articles, sources)}_")
        lines.append("")

    if positions:
        lines += ["**각 매체가 밝힌 입장** — 귀속 표기", ""]
        lines += [f"- {c.text_en}  ·  _{_cite(c.article_ids, articles, sources)}_" for c in positions]
        lines.append("")
    return lines


def render_briefing(
    day: date,
    clusters: Sequence[Cluster],
    verdicts: Sequence[ExposureVerdict],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
    analyses: Mapping[str, ClusterAnalysis] | None = None,
    *,
    home_entities: Sequence[str] = (),
    calibrated: bool = False,
) -> str:
    analyses = analyses or {}
    by_id = {c.id: c for c in clusters}
    by_cluster = {v.cluster_id: v for v in verdicts}

    lines = [f"# {day.isoformat()} 보도 지형 브리핑", ""]
    lines += render_exposure_gaps(verdicts, by_id, articles, sources)
    if home_entities:
        lines += render_outside_view(verdicts, by_id, articles, sources, home_entities)

    lines += ["## 사건별 보도 지형", ""]
    for cluster in clusters:
        lines += render_cluster(
            cluster, articles, sources, analyses.get(cluster.id), by_cluster.get(cluster.id)
        )

    lines += [
        "---",
        "",
        "**이 문서는 AI 가 생성한 분석입니다.** 어느 보도가 옳은지에 대한 판정을 담지 "
        "않으며, 각 주장은 출처 매체에 귀속되어 있습니다. 원문을 직접 확인하십시오.",
        "",
    ]
    if not calibrated:
        lines += [
            "**⚠ 임계값이 보정되지 않았습니다.** 위 노출 격차 수치는 측정된 값이 "
            "아닙니다. 보정 절차는 `eval/gap_calibration.py` 를 참조하십시오.",
            "",
        ]
    return "\n".join(lines)
