"""비대칭 공백 판정의 동작을 고정한다.

여기서 검증하는 것은 '정확도'가 아니라 '실패 방향'이다.
교차언어 매칭이 애매할 때 거짓 공백을 만들지 않는지가 핵심이다.
"""

from __future__ import annotations

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


def test_empty_baseline_pool_is_not_covered(cluster, articles, cfg):
    probe = gap.probe_baseline(cluster, articles, [], "KR", fake_embed({}), cfg)
    assert probe.decision == "not_covered"
    assert probe.matched_article_ids == []


# ---------------------------------------------------------------- 판정

def _probe(decision: str, score: float = 0.5):
    return gap.BaselineProbe(
        cluster_id="c1", baseline_country="KR", decision=decision, best_score=score
    )


def test_blindspot_requires_enough_bloc_spread(cluster, cfg):
    narrow = cluster.model_copy(update={"blocs": {"anglo"}})
    v = gap.verdict(narrow, {"KR": _probe("not_covered")}, cfg)
    assert not v.is_blindspot
    assert "블록" in v.note


def test_blindspot_when_spread_and_no_kr_coverage(cluster, cfg):
    v = gap.verdict(cluster, {"KR": _probe("not_covered")}, cfg)
    assert v.is_blindspot


def test_covered_is_not_a_blindspot(cluster, cfg):
    v = gap.verdict(cluster, {"KR": _probe("covered", 0.8)}, cfg)
    assert not v.is_blindspot


def test_uncertain_is_never_counted_as_blindspot(cluster, cfg):
    """★ 이 테스트가 설계의 핵심이다.

    애매한 매칭을 공백으로 세면, 교차언어 매칭 실패가 그대로 거짓 공백이
    되어 지표가 한 방향으로 부풀려진다. 그래서 uncertain 은 제외하고 센다.
    """
    v = gap.verdict(cluster, {"KR": _probe("uncertain", 0.45)}, cfg)
    assert not v.is_blindspot
    assert "불확실" in v.note


def test_missing_kr_probe_is_not_a_blindspot(cluster, cfg):
    v = gap.verdict(cluster, {}, cfg)
    assert not v.is_blindspot


def test_spread_score_prefers_blocs_over_article_count():
    """P7: 앵글로권 기사 수가 많아도 블록이 적으면 점수가 낮아야 한다."""
    many_anglo = gap.spread_score(["anglo"], ["US", "GB", "CA", "AU"])
    few_diverse = gap.spread_score(["anglo", "eu", "sinosphere"], ["US", "FR", "CN"])
    assert few_diverse > many_anglo
