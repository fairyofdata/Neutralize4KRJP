"""비대칭 공백 판정의 동작을 고정한다.

여기서 검증하는 것은 '정확도'가 아니라 '실패 방향'이다.
교차언어 매칭이 애매할 때 거짓 공백을 만들지 않는지가 핵심이다.
"""

from __future__ import annotations

import pytest

from blindspot import gap
from blindspot.models import Cluster


def fake_embed(score_by_text: dict[str, float], default: float = 0.05):
    """후보 텍스트에 미리 정한 유사도를 돌려주는 가짜 임베딩."""
    def _sim(query: str, candidates):
        return [
            next((v for k, v in score_by_text.items() if k in c), default)
            for c in candidates
        ]
    return _sim


# ---------------------------------------------------------------- 신호

def test_numeric_tokens_are_language_independent():
    ko = gap.numeric_tokens("3일 시위 참가자 4,500명")
    fr = gap.numeric_tokens("4500 manifestants le 3 novembre")
    assert "4500" in ko and "4500" in fr
    assert "3" not in ko, "1자리 숫자는 노이즈라 버린다"


def test_entity_tokens_match_across_scripts():
    idx = gap.build_alias_index({"capital_city": ["Capital City", "수도", "首都", "capitale"]})
    assert gap.entity_tokens("수도에서 시위", idx) == {"capital_city"}
    assert gap.entity_tokens("Manifestations dans la capitale", idx) == {"capital_city"}


def test_blend_uses_configured_weights():
    sig = gap.MatchSignals(embedding_max=0.5, entity_overlap=1.0, numeric_overlap=1.0, time_delta_hours=0)
    s = gap.blend(sig, {"embedding": 0.6, "entity": 0.25, "numeric": 0.15})
    assert abs(s - (0.3 + 0.25 + 0.15)) < 1e-9


def test_blend_ignores_negative_embedding():
    sig = gap.MatchSignals(embedding_max=-0.4, entity_overlap=0.0, numeric_overlap=0.0, time_delta_hours=0)
    assert gap.blend(sig, {"embedding": 0.6}) == 0.0


def test_decide_has_three_outcomes():
    assert gap.decide(0.9, 0.34, 0.58) == "covered"
    assert gap.decide(0.1, 0.34, 0.58) == "not_covered"
    assert gap.decide(0.45, 0.34, 0.58) == "uncertain"


# ---------------------------------------------------------------- 비대칭

def test_baseline_window_is_wider_than_cluster_window(cluster, articles, cfg, kr_article_factory):
    """★ 비대칭 1: 한국 보도는 흔히 지연되므로 baseline 쪽 윈도우가 더 넓다.

    클러스터 윈도우(36h) 밖, baseline 윈도우(72h) 안에 있는 기사가
    후보 풀에 들어와야 한다.
    """
    assert cfg["baseline"]["window_hours"] > cfg["cluster"]["window_hours"]
    late = kr_article_factory("수도 시위 진압", "경찰이 시위대 4500명을 해산시켰다.", 60.0)
    probe = gap.probe_baseline(
        cluster, articles, [late], "KR",
        fake_embed({"수도 시위": 0.95}), cfg,
    )
    assert probe.decision == "covered", "72h 윈도우 안의 지연 보도는 잡혀야 한다"
    assert probe.matched_article_ids == [late.id]


def test_article_beyond_baseline_window_is_excluded(cluster, articles, cfg, kr_article_factory):
    far = kr_article_factory("수도 시위 진압", "경찰이 시위대 4500명을 해산시켰다.", 200.0)
    probe = gap.probe_baseline(
        cluster, articles, [far], "KR", fake_embed({"수도 시위": 0.95}), cfg
    )
    assert probe.decision == "not_covered"


def test_hybrid_signals_rescue_a_weak_embedding(cluster, articles, cfg, kr_article_factory):
    """숫자·개체 신호가 약한 임베딩을 임계값 위로 끌어올릴 수 있어야 한다.

    짧은 교차언어 텍스트에서 임베딩만 믿으면 재현율이 떨어진다.
    """
    idx = gap.build_alias_index({"capital_city": ["Capital City", "수도"]})
    kr = kr_article_factory("수도 집회 4500명 참가", "3일 수도에서 4500명이 모였다.", 6.0)
    sim = fake_embed({"수도": 0.45})  # 애매한 구간

    weak = gap.probe_baseline(cluster, articles, [kr], "KR", sim, cfg, alias_index={})
    strong = gap.probe_baseline(cluster, articles, [kr], "KR", sim, cfg, alias_index=idx)

    assert strong.best_score > weak.best_score
    assert strong.signals.numeric_overlap > 0, "4500 이 양쪽에 있으므로 숫자 신호가 켜져야 한다"
    assert strong.signals.entity_overlap > 0


def test_no_articles_at_all_is_no_data_not_not_covered(cluster, articles, cfg):
    """★ ADR 0005.

    그 나라 기사를 하나도 못 받은 것은 "안 다뤘다"가 아니라 "모른다"다.
    이걸 구분하지 않으면 피드가 고장난 날 모든 사건이 공백으로 집계된다.
    """
    probe = gap.probe_baseline(cluster, articles, [], "KR", fake_embed({}), cfg)
    assert probe.decision == "no_data"
    assert probe.matched_article_ids == []


def test_articles_exist_but_none_in_window_is_not_covered(cluster, articles, cfg, kr_article_factory):
    """그 나라는 그날 기사를 냈지만 이 사건 시간대에는 없었다 — 진짜 미보도에 가깝다."""
    far = kr_article_factory("무관한 기사", "전혀 다른 내용이다.", 500.0)
    probe = gap.probe_baseline(cluster, articles, [far], "KR", fake_embed({}), cfg)
    assert probe.decision == "not_covered"


# ---------------------------------------------------------------- 판정

def _probe(country: str, decision: str, matched: int = 0, score: float = 0.5):
    return gap.BaselineProbe(
        cluster_id="c1", baseline_country=country, decision=decision, best_score=score,
        matched_article_ids=[f"{country}{i}" for i in range(matched)],
    )


def test_insufficient_spread_is_not_reported(cluster, cfg):
    """바깥에서도 널리 다뤄지지 않은 사건은 '내가 못 접한 것'이 아니다."""
    narrow = cluster.model_copy(update={"blocs": {"anglo"}})
    probes = {"KR": _probe("KR", "not_covered"), "JP": _probe("JP", "not_covered")}
    v = gap.exposure(narrow, gap.home_coverage(probes), cfg)
    assert v.tier == "insufficient_spread"


def test_no_home_coverage_is_absent(cluster, cfg):
    probes = {"KR": _probe("KR", "not_covered"), "JP": _probe("JP", "not_covered")}
    v = gap.exposure(cluster, gap.home_coverage(probes), cfg)
    assert v.tier == "absent"
    assert v.exposure_gap == pytest.approx(len(cluster.blocs))


def test_country_is_not_distinguished_once_coverage_exists(cluster, cfg):
    """★ ADR 0006 의 핵심.

    한국이 다뤘든 일본이 다뤘든 접할 기회가 있었던 것이다. 안쪽을 하나로
    합치면 AND/OR 를 고민할 필요가 애초에 사라진다.
    """
    kr_only = gap.home_coverage(
        {"KR": _probe("KR", "covered", 1, 0.8), "JP": _probe("JP", "not_covered")}
    )
    jp_only = gap.home_coverage(
        {"KR": _probe("KR", "not_covered"), "JP": _probe("JP", "covered", 1, 0.8)}
    )
    assert kr_only.article_count == jp_only.article_count == 1
    a = gap.exposure(cluster, kr_only, cfg)
    b = gap.exposure(cluster, jp_only, cfg)
    assert a.tier == b.tier
    assert a.exposure_gap == b.exposure_gap


def test_sparse_home_coverage_is_underreported(cluster, cfg):
    """'아예 안 다뤄진 것'과 '적게 다뤄진 것'이 같은 축에 있다."""
    probes = {"KR": _probe("KR", "covered", 1, 0.8), "JP": _probe("JP", "not_covered")}
    v = gap.exposure(cluster, gap.home_coverage(probes), cfg)
    assert v.tier == "underreported"
    assert 0 < v.exposure_gap < len(cluster.blocs)


def test_ample_home_coverage_is_comparable(cluster, cfg):
    probes = {
        "KR": _probe("KR", "covered", 3, 0.8),
        "JP": _probe("JP", "covered", 3, 0.8),
    }
    v = gap.exposure(cluster, gap.home_coverage(probes), cfg)
    assert v.tier == "comparable"
    assert not v.is_outside_view


def test_exposure_gap_falls_as_home_coverage_rises(cluster, cfg):
    gaps = [
        gap.exposure(
            cluster,
            gap.home_coverage({"KR": _probe("KR", "covered", n, 0.8)}),
            cfg,
        ).exposure_gap
        for n in (0, 1, 2, 5)
    ]
    assert gaps == sorted(gaps, reverse=True)


def test_undecided_only_matters_when_nothing_was_found(cluster, cfg):
    """★ 단순화의 이득.

    안쪽 보도를 이미 찾았으면 다른 나라의 판정 불가는 결론을 바꾸지 못한다.
    찾지 못했을 때만 '모른다'가 문제가 된다.
    """
    blocked = gap.home_coverage(
        {"KR": _probe("KR", "uncertain", 0, 0.45), "JP": _probe("JP", "not_covered")}
    )
    assert gap.exposure(cluster, blocked, cfg).tier == "undecided"

    found = gap.home_coverage(
        {"KR": _probe("KR", "uncertain", 0, 0.45), "JP": _probe("JP", "covered", 1, 0.8)}
    )
    assert found.undecided == {}
    assert gap.exposure(cluster, found, cfg).tier != "undecided"


def test_no_data_also_yields_undecided(cluster, cfg):
    """★ ADR 0005. 피드가 고장난 나라를 미보도로 세면 신호가 폭증한다."""
    probes = {"KR": _probe("KR", "no_data", 0, 0.0), "JP": _probe("JP", "no_data", 0, 0.0)}
    v = gap.exposure(cluster, gap.home_coverage(probes), cfg)
    assert v.tier == "undecided"
    assert "기사 없음" in v.note


def test_probe_counts_every_article_above_threshold(cluster, articles, cfg, kr_article_factory):
    """분량 축을 위해 임계값을 넘은 기사를 전부 센다."""
    arts = [
        kr_article_factory("수도 시위 진압 1", "경찰이 시위대 4500명을 해산시켰다.", 2.0),
        kr_article_factory("수도 시위 진압 2", "경찰이 시위대 4500명을 해산시켰다.", 3.0),
    ]
    arts = [a.model_copy(update={"id": f"kr{i}"}) for i, a in enumerate(arts)]
    probe = gap.probe_baseline(
        cluster, articles, arts, "KR", fake_embed({"수도 시위": 0.95}), cfg
    )
    assert probe.decision == "covered"
    assert len(probe.matched_article_ids) == 2


def test_spread_score_prefers_blocs_over_article_count():
    """P8: 앵글로권 기사 수가 많아도 블록이 적으면 점수가 낮아야 한다."""
    many_anglo = gap.spread_score(["anglo"], ["US", "GB", "CA", "AU"])
    few_diverse = gap.spread_score(["anglo", "eu", "sinosphere"], ["US", "FR", "CN"])
    assert few_diverse > many_anglo
