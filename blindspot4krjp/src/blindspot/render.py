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


_DECISION_KO = {
    "covered": "보도",
    "not_covered": "미보도",
    "uncertain": "판정 불가(매칭 애매)",
    "no_data": "판정 불가(기사 없음)",
}


def _probe_line(verdict: BlindspotVerdict) -> str:
    bits = []
    for country, probe in sorted(verdict.probes.items()):
        label = _DECISION_KO.get(probe.decision, probe.decision)
        bits.append(f"{flag(country)} {label} ({probe.best_score:.3f})")
    return " · ".join(bits)


def render_blindspots(
    verdicts: Sequence[BlindspotVerdict],
    clusters: Mapping[str, Cluster],
    articles: Mapping[str, Article],
    sources: Mapping[str, SourceProfile],
) -> list[str]:
    """두 단계로 보여준다 (ADR 0005).

    1차는 한국·일본 모두 미보도 — 접할 기회가 아예 없었던 사건.
    2차는 한쪽만 미보도 — 기회는 있었지만 놓쳤을 수 있는 약한 신호.
    둘을 섞으면 1차의 의미가 묻히므로 분리한다.
    """
    primary = sorted(
        (v for v in verdicts if v.is_blindspot), key=lambda x: -x.spread_score
    )
    secondary = sorted(
        (v for v in verdicts if v.is_divergent), key=lambda x: -x.spread_score
    )
    undecided = [
        v for v in verdicts
        if v.undecided and not v.is_blindspot and not v.is_divergent
    ]

    def entry(n: int, v: BlindspotVerdict, *, with_coverage: bool) -> list[str]:
        out = [f"{n}. **{v.event_label}**"]
        cluster = clusters.get(v.cluster_id)
        if with_coverage and cluster is not None:
            out.append(
                f"   - 해외 보도: {_coverage_line(cluster, articles, sources)}"
                f" · 독립 보도 {cluster.wire_groups}건 · 블록 {len(cluster.blocs)}개"
            )
        out.append(f"   - {_probe_line(v)}")
        return out

    lines = ["## 보도 공백", ""]

    lines += ["### 1차 — 한국·일본 모두 미보도", "",
              "_접할 기회가 아예 없었던 사건._", ""]
    if primary:
        for n, v in enumerate(primary, 1):
            lines += entry(n, v, with_coverage=True)
            lines.append("")
    else:
        lines += ["해당 없음.", ""]

    if secondary:
        lines += ["### 2차 — 한쪽만 미보도 (약한 신호)", "",
                  "_한쪽 언론이 다뤘으므로 접할 기회는 있었지만, 놓쳤을 수 있는 사건._", ""]
        for n, v in enumerate(secondary, 1):
            lines += entry(n, v, with_coverage=True)
            lines.append("")

    if undecided:
        reasons = sorted({r for v in undecided for r in v.undecided.values()})
        lines += [
            f"> 판정 불가 {len(undecided)}건은 두 목록에서 제외했습니다 — "
            + "; ".join(reasons)
            + ". 모르는 것을 공백으로 세면 거짓 공백이 됩니다 (ADR 0002·0005).",
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
