#!/usr/bin/env python3
"""보도 공백 판정의 임계값 보정 — 지표를 주장에서 숫자로 바꾸는 도구.

왜 필요한가
-----------
공백 판정은 교차언어 매칭에 의존하고, 그 정확도는 측정 전까지 알 수 없다.
측정하지 않은 수치를 공개하면 헌장 P9 위반이다. 그래서 하루치를 손으로
라벨링하고 임계값을 맞춘다. 50개 클러스터면 두 시간 정도 걸리고,
그 뒤로는 "보도 공백 N건"이 측정된 숫자가 된다.

절차
----
1. Phase 1 파이프라인으로 하루치 클러스터와 baseline 점수를 뽑는다.
2. 사람이 각 클러스터에 대해 "한국 언론이 이 사건을 보도했는가"를 직접 라벨링한다.
   (연합뉴스·네이버 뉴스 검색으로 확인. 애매하면 2 로 표시하고 분석에서 제외.)
3. 이 스크립트로 임계값을 스윕해서 운영점을 고른다.

읽는 방법
---------
- precision 이 중요하다. 거짓 공백은 "한국 언론이 안 다뤘다"는 틀린 주장이고,
  그게 이 제품의 신뢰를 직접 깎는다.
- recall 은 덜 중요하다. 공백을 몇 건 놓치는 것은 조용한 실패다.
- 따라서 precision 을 먼저 만족시키고 그 안에서 recall 을 최대화한다.
- uncertain_rate 가 높으면 임계값 간격이 너무 넓은 것이다. 다만 좁히기보다
  신호(개체 별칭 사전)를 보강하는 쪽이 낫다.

입력 형식
---------
scores.csv : cluster_id,score        파이프라인이 낸 baseline 매칭 점수
labels.csv : cluster_id,kr_covered   사람 라벨. 1=보도함 0=안 함 2=애매(제외)
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

TARGET_PRECISION = 0.90


def read_scores(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as f:
        return {r["cluster_id"]: float(r["score"]) for r in csv.DictReader(f)}


def read_labels(path: Path) -> dict[str, int]:
    with path.open(encoding="utf-8") as f:
        return {r["cluster_id"]: int(r["kr_covered"]) for r in csv.DictReader(f)}


def evaluate(scores: dict[str, float], labels: dict[str, int], tau_low: float, tau_high: float) -> dict:
    """공백 목록의 정밀도·재현율.

    양성(positive) = 공백으로 판정한 것 = not_covered = score < tau_low.
    정답 양성 = 사람이 kr_covered=0 으로 라벨한 것.
    uncertain 구간은 공백으로 세지 않으므로 음성으로 취급되고, 재현율을 깎는다.
    이것이 의도된 보수성이다.
    """
    tp = fp = fn = unc = 0
    for cid, label in labels.items():
        if label == 2 or cid not in scores:
            continue
        s = scores[cid]
        called_blindspot = s < tau_low
        if tau_low <= s < tau_high:
            unc += 1
        if called_blindspot and label == 0:
            tp += 1
        elif called_blindspot and label == 1:
            fp += 1
        elif not called_blindspot and label == 0:
            fn += 1

    n = sum(1 for cid, l in labels.items() if l != 2 and cid in scores)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall and (precision + recall)
        else None
    )
    return {
        "tau_low": tau_low, "tau_high": tau_high, "n": n,
        "tp": tp, "fp": fp, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "uncertain_rate": unc / n if n else None,
    }


def sweep(scores, labels, lows, highs) -> list[dict]:
    return [
        evaluate(scores, labels, lo, hi)
        for lo in lows for hi in highs if hi > lo
    ]


def fmt(v) -> str:
    return "  -  " if v is None else f"{v:5.3f}"


def main() -> int:
    p = argparse.ArgumentParser(description="보도 공백 임계값 보정")
    p.add_argument("--scores", required=True)
    p.add_argument("--labels", required=True)
    p.add_argument("--target-precision", type=float, default=TARGET_PRECISION)
    args = p.parse_args()

    scores = read_scores(Path(args.scores))
    labels = read_labels(Path(args.labels))
    usable = sum(1 for cid, l in labels.items() if l != 2 and cid in scores)
    if usable < 30:
        print(f"⚠ 분석 가능한 라벨이 {usable}건입니다. 30건 미만이면 추정이 불안정합니다.")

    lows = [round(x / 100, 2) for x in range(20, 61, 4)]
    highs = [round(x / 100, 2) for x in range(40, 86, 5)]
    rows = sweep(scores, labels, lows, highs)

    print(f"\n라벨 {usable}건 (애매 제외) 기준 임계값 스윕\n")
    print(f"{'tau_low':>8}{'tau_high':>9}{'prec':>7}{'recall':>8}{'f1':>7}{'unc':>7}{'tp':>5}{'fp':>5}{'fn':>5}")
    print("-" * 68)
    for r in rows:
        print(
            f"{r['tau_low']:>8.2f}{r['tau_high']:>9.2f}{fmt(r['precision']):>7}"
            f"{fmt(r['recall']):>8}{fmt(r['f1']):>7}{fmt(r['uncertain_rate']):>7}"
            f"{r['tp']:>5}{r['fp']:>5}{r['fn']:>5}"
        )

    ok = [r for r in rows if r["precision"] is not None and r["precision"] >= args.target_precision]
    print()
    if not ok:
        best = max((r for r in rows if r["precision"] is not None),
                   key=lambda r: r["precision"], default=None)
        print(f"✗ precision {args.target_precision} 를 만족하는 임계값이 없습니다.")
        if best:
            print(f"  최고 precision = {best['precision']:.3f} (tau_low={best['tau_low']})")
        print("  임계값을 조이는 대신 신호를 보강하십시오 — 개체 별칭 사전 확장이 가장 효과가 큽니다.")
        print("  보정 전까지 공백 건수를 공개 지표로 쓰지 마십시오 (P9).")
        return 1

    pick = max(ok, key=lambda r: (r["recall"] or 0))
    print(f"✓ 권장 운영점: tau_low={pick['tau_low']} tau_high={pick['tau_high']}")
    print(f"  precision={fmt(pick['precision'])} recall={fmt(pick['recall'])} uncertain={fmt(pick['uncertain_rate'])}")
    print("  config.yaml 의 baseline.tau_low / tau_high 에 반영하고, 측정일과 라벨 수를 README 에 적으십시오.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
