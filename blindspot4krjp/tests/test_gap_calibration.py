"""보정 하네스가 정밀도·재현율을 올바르게 계산하는지."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.gap_calibration import evaluate  # noqa: E402


def test_perfect_separation():
    scores = {"c1": 0.1, "c2": 0.2, "c3": 0.9, "c4": 0.8}
    labels = {"c1": 0, "c2": 0, "c3": 1, "c4": 1}
    r = evaluate(scores, labels, tau_low=0.5, tau_high=0.6)
    assert r["precision"] == 1.0 and r["recall"] == 1.0
    assert r["fp"] == 0 and r["fn"] == 0


def test_false_blindspot_lowers_precision():
    """한국이 보도했는데 공백으로 판정한 경우 — 가장 피해야 할 오류."""
    scores = {"c1": 0.1, "c2": 0.1}
    labels = {"c1": 0, "c2": 1}
    r = evaluate(scores, labels, tau_low=0.5, tau_high=0.6)
    assert r["fp"] == 1
    assert r["precision"] == 0.5


def test_uncertain_band_costs_recall_not_precision():
    """★ 설계 의도의 검증.

    애매한 구간은 공백으로 세지 않으므로 재현율은 떨어지지만,
    정밀도는 보호된다. 조용히 놓치는 쪽이 틀리게 주장하는 쪽보다 낫다.
    """
    scores = {"c1": 0.45, "c2": 0.1}
    labels = {"c1": 0, "c2": 0}
    r = evaluate(scores, labels, tau_low=0.4, tau_high=0.6)
    assert r["precision"] == 1.0
    assert r["recall"] == 0.5
    assert r["uncertain_rate"] == 0.5


def test_ambiguous_labels_are_excluded():
    scores = {"c1": 0.1, "c2": 0.1}
    labels = {"c1": 0, "c2": 2}
    r = evaluate(scores, labels, tau_low=0.5, tau_high=0.6)
    assert r["n"] == 1
