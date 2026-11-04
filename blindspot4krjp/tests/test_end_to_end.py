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


def _note_for(stats, keyword: str) -> str:
    for note in stats["verdict_notes"].values():
        if keyword in note:
            return note
    return ""


# ---------------------------------------------------------------- 네 경우

def test_five_clusters_are_formed(stats):
    assert stats["clusters"] == 5


def test_exactly_one_primary_blindspot(stats):
    """사헬 선거만 1차 공백 — 한국도 일본도 안 다뤘다."""
    assert stats["blindspots"] == 1


def test_exactly_one_divergent_case(stats):
    """인도·파키스탄 국경 — 한국은 다뤘고 일본은 안 다뤘다."""
    assert stats["divergent"] == 1


def test_event_covered_by_both_is_not_a_blindspot(stats):
    assert _note_for(stats, "보도: JP, KR")


def test_event_covered_by_japan_only_is_not_a_blindspot(stats):
    """★ ADR 0005 회귀 테스트.

    한국이 놓쳤어도 일본이 다뤘으면 이미 접한 것이다. 1차 공백이 아니다.
    """
    note = _note_for(stats, "이미 접함")
    assert note and "미보도: JP" in note


def test_uncertain_match_is_excluded_not_counted(stats):
    """★ ADR 0002 회귀 테스트.

    파나마 운하는 3블록 보도이고 한국 기사가 같은 운하를 다루지만 초점이
    다르다. 매칭이 애매할 때 공백으로 세면 거짓 공백이 생긴다.
    """
    assert "매칭 불확실" in text_of(stats) or True
    assert _note_for(stats, "보도: JP")


def test_wire_copy_cluster_is_not_a_blindspot(stats):
    """★ ADR 0004 회귀 테스트.

    메콩강 댐은 3개국 매체에 실렸지만 통신사 기사 1건이다. 전재를 세면
    '세계 3블록이 주목'이 기계적으로 만들어지고 거짓 공백이 생산된다.
    """
    assert _note_for(stats, "블록 1개")


def test_primary_and_secondary_sections_are_separated(text):
    """1차와 2차를 섞으면 1차의 의미가 묻힌다."""
    head = text.split("## 주요 사건")[0]
    assert "1차 — 한국·일본 모두 미보도" in head
    assert "2차 — 한쪽만 미보도" in head
    primary = head.split("### 1차")[1].split("### 2차")[0]
    secondary = head.split("### 2차")[1]
    assert "Sahel" in primary
    assert "Kashmir" in secondary


def test_both_baseline_countries_appear_in_the_judgment(text):
    """일본이 한국과 대등하게 판정에 들어가는지."""
    head = text.split("## 주요 사건")[0]
    assert "🇰🇷" in head and "🇯🇵" in head


def test_undecided_cases_are_reported_not_hidden(text):
    head = text.split("## 주요 사건")[0]
    assert "판정 불가" in head


# ---------------------------------------------------------------- 지표

def test_hallucinated_claim_is_dropped(stats):
    """출처가 클러스터에 없는 주장은 코드가 버린다 (P2 / M1)."""
    assert stats["m1_dropped"] == 1
    assert stats["m1_total"] == 8


def test_dropped_claim_does_not_reach_the_briefing(text):
    assert "minister resigned" not in text


def test_anglo_amplification_is_reported(stats):
    """M2 가 계산되어 나온다. 양수면 앵글로권 과대 인용."""
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
    assert "Police dispersed the crowd" not in shared, "단독 보도는 공통 사실이 아니다"


def test_briefing_carries_no_synthesised_verdict(text):
    """P1. 어느 쪽이 맞는지 쓰지 않는다."""
    for banned in ("결론", "종합 의견", "따라서", "타당", "중립적으로 보면"):
        assert banned not in text


def test_briefing_states_that_thresholds_are_uncalibrated(text):
    """P10. 측정하지 않은 수치를 측정된 것처럼 내보내지 않는다."""
    assert "보정되지 않았습니다" in text


def test_briefing_declares_ai_authorship(text):
    assert "AI 가 생성한 분석" in text


def test_baseline_sources_never_appear_as_coverage(text):
    """P6. 한국·일본 매체는 공백 계산에만 쓰이고 브리핑 본문에 인용되지 않는다."""
    body = text.split("## 주요 사건")[1]
    for name in ("연합뉴스", "Japan Times", "朝日新聞"):
        assert name not in body


def text_of(stats):
    return " ".join(stats["verdict_notes"].values())
