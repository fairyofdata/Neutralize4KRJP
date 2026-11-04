"""클러스터링 — 가짜 임베딩으로 전부 테스트한다 (네트워크·비용 0)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from blindspot.cluster import BaselineLeakError, build_clusters, cosine, spread_from
from blindspot.models import Article

T0 = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def art(aid, source_id, title, lead="", hours=0.0, lang="en"):
    return Article(
        id=aid, source_id=source_id, url=f"https://x.test/{aid}",
        title_orig=title, lead_orig=lead or None, lang=lang,
        published_at=T0 + timedelta(hours=hours), fetched_at=T0,
    )


def topic_embedder(topic_of: dict[str, list[float]]):
    """기사 텍스트의 첫 단어를 주제 키로 보고 미리 정한 벡터를 돌려준다."""
    def _embed(texts):
        return [topic_of[t.split()[0]] for t in texts]
    return _embed


PROTEST = [1.0, 0.0, 0.0]
TARIFF = [0.0, 1.0, 0.0]
VEC = {"PROTEST": PROTEST, "TARIFF": TARIFF}


def test_cosine_basics():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([0, 0], [1, 0]) == 0.0


def test_two_topics_form_two_clusters(sources, cfg):
    arts = [
        art("a", "guardian", "PROTEST one", hours=0),
        art("b", "lemonde", "PROTEST two", hours=1),
        art("c", "globaltimes", "TARIFF one", hours=2),
        art("d", "tass", "TARIFF two", hours=3),
    ]
    clusters = build_clusters(arts, sources, topic_embedder(VEC), cfg)
    assert len(clusters) == 2
    assert all(len(c.article_ids) == 2 for c in clusters)


def test_singletons_are_dropped(sources, cfg):
    arts = [
        art("a", "guardian", "PROTEST one", hours=0),
        art("b", "lemonde", "PROTEST two", hours=1),
        art("c", "globaltimes", "TARIFF alone", hours=2),
    ]
    clusters = build_clusters(arts, sources, topic_embedder(VEC), cfg)
    assert len(clusters) == 1


def test_time_window_prevents_cross_day_merges(sources, cfg):
    """윈도우 밖의 쌍은 유사도를 0으로 둬서 다른 날의 비슷한 사건이 합쳐지지 않게 한다."""
    far = cfg["cluster"]["window_hours"] + 10
    arts = [
        art("a", "guardian", "PROTEST one", hours=0),
        art("b", "lemonde", "PROTEST two", hours=far),
    ]
    assert build_clusters(arts, sources, topic_embedder(VEC), cfg) == []


def test_baseline_article_in_clustering_raises(sources, cfg):
    """★ P6 집행. 방침이 아니라 구조로 막는다."""
    arts = [
        art("a", "guardian", "PROTEST one", hours=0),
        art("kr", "yonhap", "PROTEST two", hours=1),
    ]
    with pytest.raises(BaselineLeakError, match="baseline"):
        build_clusters(arts, sources, topic_embedder(VEC), cfg)


def test_unknown_source_raises(sources, cfg):
    with pytest.raises(BaselineLeakError, match="알 수 없는"):
        build_clusters([art("a", "ghost", "PROTEST one")], sources, topic_embedder(VEC), cfg)


# ---------------------------------------------------------------- 전재 반영

WIRE = (
    "Police dispersed some 4,500 demonstrators in the capital on Tuesday, "
    "officials said, after a march turned confrontational."
)


def test_wire_copy_does_not_inflate_bloc_count(sources, cfg):
    """★ ADR 0004. 한 통신사 기사가 3개 블록에 실려도 블록 수는 1이다."""
    arts = [
        art("a", "guardian", "PROTEST a", WIRE, hours=0),
        art("b", "lemonde", "PROTEST b", WIRE, hours=1),
        art("c", "globaltimes", "PROTEST c", WIRE, hours=2),
    ]
    c = build_clusters(arts, sources, topic_embedder(VEC), cfg)[0]
    assert c.wire_groups == 1
    assert c.blocs == {"anglo"}
    assert c.blocs_with_pickups == {"anglo", "eu", "sinosphere"}
    assert c.spread_score < 2.0


def test_independent_reports_do_raise_bloc_count(sources, cfg):
    arts = [
        art("a", "guardian", "PROTEST first account of the march and the police response", hours=0),
        art("b", "lemonde", "PROTEST entirely separate wording about pension anger", hours=1),
        art("c", "globaltimes", "PROTEST third distinct framing of lawful handling", hours=2),
    ]
    c = build_clusters(arts, sources, topic_embedder(VEC), cfg)[0]
    assert c.wire_groups == 3
    assert c.blocs == {"anglo", "eu", "sinosphere"}


def test_clusters_are_ranked_by_spread_not_volume(sources, cfg):
    """P8: 앵글로권 기사가 많아도 블록이 적으면 뒤로 간다."""
    arts = [
        art("a1", "guardian", "TARIFF alpha distinct wording one", hours=0),
        art("a2", "wapo", "TARIFF alpha distinct wording two", hours=1),
        art("b1", "lemonde", "PROTEST beta distinct wording one", hours=0),
        art("b2", "globaltimes", "PROTEST beta distinct wording two", hours=1),
        art("b3", "tass", "PROTEST beta distinct wording three", hours=2),
    ]
    clusters = build_clusters(arts, sources, topic_embedder(VEC), cfg)
    assert len(clusters) == 2
    assert len(clusters[0].blocs) > len(clusters[1].blocs)
    assert clusters[0].spread_score > clusters[1].spread_score


def test_spread_from_prefers_blocs():
    assert spread_from({"anglo", "eu", "russia"}, {"US", "FR", "RU"}) > spread_from(
        {"anglo"}, {"US", "GB", "CA", "AU"}
    )
