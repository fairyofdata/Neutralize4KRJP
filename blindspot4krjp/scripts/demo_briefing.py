#!/usr/bin/env python3
"""합성 데이터로 브리핑을 한 부 생성한다 — 네트워크·LLM·비용 0.

    python scripts/demo_briefing.py [--out out/demo-briefing.md]

파이프라인 전체(클러스터링 → 전재 축약 → 비대칭 공백 판정 → 주장 검증 →
파생 집계 → 렌더링)가 연결되어 돌아가는지 확인하고, 산출물의 모양을 눈으로
보기 위한 것이다. 데이터는 eval/demo_world.py 의 창작물이다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

import yaml  # noqa: E402

from blindspot import gap, provenance, render  # noqa: E402
from blindspot.aliases import load_aliases  # noqa: E402
from blindspot.cluster import build_clusters  # noqa: E402
from blindspot.derive import anglo_amplification  # noqa: E402
from eval import demo_world as world  # noqa: E402


def run(cfg: dict) -> tuple[str, dict]:
    sources = world.sources()
    overseas = world.overseas_articles()
    baseline = world.baseline_articles()
    articles = {a.id: a for a in overseas + baseline}
    aliases = load_aliases(ROOT / "aliases.yaml")

    clusters = build_clusters(
        overseas, sources, world.embedder, cfg, day=world.DAY, aliases=aliases
    )

    verdicts = []
    for cluster in clusters:
        probes = {}
        for country in cfg["blindspot"]["home_media"]:
            pool = [
                a for a in baseline
                if sources[a.source_id].country == country
            ]
            probes[country] = gap.probe_baseline(
                cluster, articles, pool, country, world.baseline_sim, cfg, aliases
            )
        verdicts.append(gap.exposure(cluster, gap.home_coverage(probes), cfg))

    analyses: dict[str, object] = {}
    stats = {"m1_dropped": 0, "m1_total": 0, "m2": {}}
    for cluster in clusters:
        key = "A" if "pension" in cluster.event_label.lower() else cluster.id
        raw = world.analysis_for(key, cluster.article_ids)
        if not raw.claims:
            continue
        clean, report = provenance.validate(raw, cluster)
        analyses[cluster.id] = clean
        stats["m1_total"] += report.total_claims
        stats["m1_dropped"] += report.dropped_claims
        stats["m2"][cluster.id] = round(
            anglo_amplification(clean.claims, cluster.article_ids, articles, sources), 3
        )

    home_entities = cfg["blindspot"].get("home_entities", [])
    text = render.render_briefing(
        world.DAY, clusters, verdicts, articles, sources, analyses,
        home_entities=home_entities, calibrated=False,
    )
    stats["clusters"] = len(clusters)
    stats["tiers"] = {v.cluster_id: v.tier for v in verdicts}
    stats["gaps"] = {v.cluster_id: v.exposure_gap for v in verdicts}
    stats["outside_view"] = sorted(
        c.id for c in clusters if c.entities & set(home_entities)
    )
    stats["verdict_notes"] = {v.cluster_id: v.note for v in verdicts}
    return text, stats


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(ROOT / "out" / "demo-briefing.md"))
    args = p.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    text, stats = run(cfg)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")

    print(text)
    print("\n" + "=" * 60, file=sys.stderr)
    print(f"클러스터 {stats['clusters']}개", file=sys.stderr)
    print(f"분류: {stats['tiers']}", file=sys.stderr)
    print(f"노출 격차: {stats['gaps']}", file=sys.stderr)
    print(f"외부에서 본 안쪽 이슈: {stats['outside_view']}", file=sys.stderr)
    print(f"M1 환각률: {stats['m1_dropped']}/{stats['m1_total']}", file=sys.stderr)
    print(f"M2 앵글로권 과대인용: {stats['m2']}", file=sys.stderr)
    for cid, note in stats["verdict_notes"].items():
        print(f"  {cid}: {note}", file=sys.stderr)
    print(f"\n저장: {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
