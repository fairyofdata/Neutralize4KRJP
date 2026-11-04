"""종단 테스트 — 수집 이후 전 단계가 연결되어 돌아가는지.

의도적으로 네 가지 경우를 구성한 합성 세계(eval/demo_world.py)를 쓴다.
각 경우가 올바르게 갈라지는지가 ADR 0002·0004 의 회귀 테스트다.
네트워크·LLM·비용 0.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT)]

from scripts.demo_briefing import run  # noqa: E402


@pytest.fixture(scope="module")
def result():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    return run(cfg)


@pytest.fixture(scope="module")
def text(result):
    return result[0]


@pytest.fixture(scope="module")
def stats(result):
    return result[1]


def _ids_with_tier(stats, tier: str) -> list[str]:
    return sorted(cid for cid, t in stats["tiers"].items() if t == tier)


def _note_for(stats, keyword: str) -> str:
    for note in stats["verdict_notes"].values():
        if keyword in note:
            return note
    return ""


# ---------------------------------------------------------------- 분류

def test_six_clusters_are_formed(stats):
    assert stats["clusters"] == 6


def test_every_cluster_gets_a_tier(stats):
    assert len(stats["tiers"]) == 6
    assert set(stats["tiers"].values()) <= {
        "absent", "underreported", "comparable", "undecided", "insufficient_spread",
    }


def test_sahel_is_absent_from_home_media(stats):
    """안쪽 보도 0건 — 접할 기회가 아예 없었던 사건."""
    assert len(_ids_with_tier(stats, "absent")) == 1
    assert _note_for(stats, "안쪽 보도 없음")


def test_sparsely_covered_events_are_underreported(stats):
    """'아예 안 다뤄진 것'과 '적게 다뤄진 것'이 같은 축에 들어온다 (ADR 0006)."""
    assert _ids_with_tier(stats, "underreported")
    assert _note_for(stats, "격차")


def test_wire_only_cluster_is_filtered_by_spread(stats):
    """★ ADR 0004 회귀. 전재 3건은 블록 1개로 축약되어 대상에서 빠진다."""
    assert _note_for(stats, "블록 1개 < 기준")
    assert _ids_with_tier(stats, "insufficient_spread")


def test_exposure_gap_is_a_continuous_value(stats):
    gaps = list(stats["gaps"].values())
    assert all(isinstance(g, float) for g in gaps)
    assert max(gaps) > min(gaps), "이진 판정이 아니라 정도의 문제여야 한다"


def test_gap_is_largest_where_home_coverage_is_absent(stats):
    absent = _ids_with_tier(stats, "absent")[0]
    others = [cid for cid in stats["gaps"] if cid != absent]
    assert all(stats["gaps"][absent] >= stats["gaps"][c] for c in others)


# ---------------------------------------------------------------- 외부 시선

def test_outside_view_section_picks_up_home_related_issues(stats):
    """★ ADR 0006. 한국·일본 관련 사안을 바깥 언론이 어떻게 쓰는지."""
    assert stats["outside_view"], "일본 방위비 클러스터가 잡혀야 한다"


def test_outside_view_is_rendered(text):
    assert "## 외부에서 본 안쪽 이슈" in text
    head = text.split("## 사건별 보도 지형")[0]
    assert "Japan" in head.split("## 외부에서 본 안쪽 이슈")[1]


def test_outside_view_includes_well_covered_events(stats):
    """내가 이미 본 사건도 외부 시선 섹션에는 들어간다 — 굴절이 관심사이므로."""
    cid = stats["outside_view"][0]
    assert stats["tiers"][cid] == "comparable"


# ---------------------------------------------------------------- 안쪽 프레이밍

def test_home_framing_is_shown_as_a_row(text):
    """★ ADR 0006. 안쪽 프레이밍이 관찰 대상이 된다. 설계 초기 원칙을 뒤집은 지점."""
    assert "**안쪽 언론이 쓴 틀**" in text
    assert "당신이 접한 서술" in text


def test_home_framing_quotes_the_original_headline(text):
    """안쪽 프레이밍은 요약하면 안 되는 대상이다 — 원문 제목을 그대로 인용한다."""
    assert "防衛費" in text or "방위비" in text
    assert "[원문](" in text


def test_home_sources_are_labelled_in_the_framing_row(text):
    block = text.split("**안쪽 언론이 쓴 틀**")[1]
    assert any(name in block for name in ("朝日新聞", "연합뉴스", "The Japan Times"))


def test_home_sources_are_not_counted_as_world_coverage(text):
    """안쪽 매체는 바깥 보도 집계에 들어가지 않는다 (P6 의 남은 부분)."""
    for line in text.splitlines():
        if line.strip().startswith("바깥 보도:"):
            assert "🇰🇷" not in line and "🇯🇵" not in line


# ---------------------------------------------------------------- 지표

def test_hallucinated_claim_is_dropped(stats):
    """출처가 클러스터에 없는 주장은 코드가 버린다 (P2 / M1)."""
    assert stats["m1_dropped"] == 1
    assert stats["m1_total"] == 8


def test_dropped_claim_does_not_reach_the_briefing(text):
    assert "minister resigned" not in text


def test_anglo_amplification_is_reported(stats):
    assert stats["m2"]
    assert all(isinstance(v, float) for v in stats["m2"].values())


# ---------------------------------------------------------------- 산출물 성질

def test_framing_contrast_preserves_each_blocs_wording(text):
    """P3. 같은 경찰 행동에 붙은 세 단어가 나란히 놓인다."""
    for term in ("crackdown", "handled according to law", "special policing operation"):
        assert term in text


def test_state_controlled_sources_are_labelled(text):
    """P4. 국가통제 매체를 라벨 없이 인용하면 선전을 관점으로 승격시킨다."""
    assert "국가통제" in text
    assert "당 기관지" in text


def test_shared_facts_require_two_blocs(text):
    """공통 사실은 LLM 판단이 아니라 집합 연산 결과다."""
    shared = text.split("**공통 사실**")[1].split("**한 블록만")[0]
    assert "4,500 people" in shared
    assert "Police dispersed the crowd" not in shared


def test_briefing_carries_no_synthesised_verdict(text):
    """P1. 어느 쪽이 맞는지 쓰지 않는다."""
    for banned in ("결론", "종합 의견", "따라서", "타당", "중립적으로 보면"):
        assert banned not in text


def test_briefing_states_that_thresholds_are_uncalibrated(text):
    """P10. 측정하지 않은 수치를 측정된 것처럼 내보내지 않는다."""
    assert "보정되지 않았습니다" in text


def test_briefing_declares_ai_authorship(text):
    assert "AI 가 생성한 분석" in text


def test_undecided_cases_are_reported_not_hidden(text):
    head = text.split("## 사건별 보도 지형")[0]
    assert "판정 불가" in head or "undecided" not in str(head)
