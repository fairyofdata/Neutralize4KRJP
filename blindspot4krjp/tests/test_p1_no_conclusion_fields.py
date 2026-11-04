"""P1 을 소스 전체에 대해 기계적으로 검사한다.

타입에 필드를 두지 않는 것만으로는 부족하다. 나중에 누군가(사람이든 모델이든)
'중립 요약' 필드를 어딘가에 추가할 수 있기 때문이다. 그래서 금지된 식별자가
src/ 어디에도 등장하지 않는지 테스트가 직접 확인한다.

이 테스트가 깨졌다면 구현을 고치는 것이 아니라, 원칙을 바꿀 것인지
사용자에게 물어야 한다 (헌장 §2).
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# 필드명·변수명으로 등장하면 안 되는 것들. 주석에서의 언급은 허용한다.
FORBIDDEN = [
    "conclusion",
    "verdict_text",
    "assessment",
    "neutral_summary",
    "neutral_article",
    "overall_opinion",
    "our_view",
    "recommendation",
]


def _strip_comments_and_docstrings(text: str) -> str:
    text = re.sub(r'""".*?"""', "", text, flags=re.S)
    text = re.sub(r"'''.*?'''", "", text, flags=re.S)
    return re.sub(r"#.*", "", text)


def test_no_forbidden_identifiers_in_src():
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        code = _strip_comments_and_docstrings(path.read_text(encoding="utf-8"))
        for word in FORBIDDEN:
            if re.search(rf"\b{re.escape(word)}\b", code):
                offenders.append(f"{path.relative_to(SRC)}: {word}")
    assert not offenders, (
        "P1 위반 — 종합 의견을 담는 식별자가 등장했습니다:\n  "
        + "\n  ".join(offenders)
        + "\n원칙을 바꾸려면 ADR 에 올려 사용자에게 물어볼 것."
    )
