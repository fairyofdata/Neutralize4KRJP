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
    BlindspotVerdict,
    Cluster,
    ClusterAnalysis,
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


def render_blindspots(
    verdicts: Sequence[BlindspotVerdict],
    clusters: Mapping[str, Cluster],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> list[str]:
    hits = [v for v in verdicts if v.is_blindspot]
    uncertain = [
        v for v in verdicts
        if not v.is_blindspot and any(p.decision == "uncertain" for p in v.probes.values())
    ]
    lines = ["## 보도 공백", ""]
    if not hits:
        lines += ["해당 없음.", ""]
    for n, v in enumerate(sorted(hits, key=lambda x: -x.spread_score), 1):
        cluster = clusters.get(v.cluster_id)
        lines.append(f"{n}. **{v.event_label}**")
        if cluster is not None:
            lines.append(f"   - 해외 보도: {_coverage_line(cluster, articles, sources)}"
                         f" · 독립 보도 {cluster.wire_groups}건 · 블록 {len(cluster.blocs)}개")
        for country, probe in sorted(v.probes.items()):
            lines.append(
                f"   - {flag(country)} 판정: {probe.decision} (최고점 {probe.best_score:.3f})"
            )
        lines.append("")
    if uncertain:
        lines += [
            f"> 판정 불확실 {len(uncertain)}건은 위 목록에서 제외했습니다. "
            "교차언어 매칭이 애매한 경우를 공백으로 세면 거짓 공백이 생깁니다 (ADR 0002).",
            "",
        ]
    return lines


def render_cluster(
    cluster: Cluster,
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
    analysis: ClusterAnalysis | None = None,
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

    if analysis is None:
        lines += ["_주장 추출은 Phase 2 입니다._", ""]
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
    verdicts: Sequence[BlindspotVerdict],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
    analyses: Mapping[str, ClusterAnalysis] | None = None,
    *,
    calibrated: bool = False,
) -> str:
    analyses = analyses or {}
    by_id = {c.id: c for c in clusters}
    lines = [f"# {day.isoformat()} 보도 지형 브리핑", ""]
    lines += render_blindspots(verdicts, by_id, articles, sources)
    lines += ["## 주요 사건", ""]
    for cluster in clusters:
        lines += render_cluster(cluster, articles, sources, analyses.get(cluster.id))

    lines += [
        "---",
        "",
        "**이 문서는 AI 가 생성한 분석입니다.** 어느 보도가 옳은지에 대한 판정을 담지 "
        "않으며, 각 주장은 출처 매체에 귀속되어 있습니다. 원문을 직접 확인하십시오.",
        "",
    ]
    if not calibrated:
        lines += [
            "**⚠ 공백 판정 임계값이 보정되지 않았습니다.** 위 공백 건수는 측정된 "
            "수치가 아닙니다. 보정 절차는 `eval/gap_calibration.py` 를 참조하십시오.",
            "",
        ]
    return "\n".join(lines)
