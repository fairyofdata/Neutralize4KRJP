"""통신사 전재 축약 — spread_score 오염 차단.

문제
----
로이터·AP 기사 하나가 Guardian(anglo), Straits Times(sea), The Hindu(southasia)
에 그대로 실리면, 블록 집계는 "서로 다른 3개 블록이 보도"로 읽는다. 실제로는
**한 편집국의 기사 한 건**이다.

이것이 단순한 수치 부풀림이 아닌 이유: 블록 수는 랭킹(P8)뿐 아니라 공백 판정
기준(`blocs >= 3`)에도 직접 쓰인다. 즉 전재를 세면 "세계가 주목하는 사안"이
기계적으로 만들어지고, 그 결과 **거짓 보도 공백이 생산된다.** 공백 판정을
비대칭으로 고친 것(ADR 0002)과 같은 종류의 문제가 반대편에 있었다.

해결
----
1. 같은 언어 안에서 근접 중복을 찾아 **wire 그룹**으로 묶는다.
2. 각 그룹은 블록 집계에 **한 번만** 기여하고, 기여하는 블록은 그룹에서
   **가장 먼저 발행된** 기사의 블록이다 (원발행지에 가장 가까운 대리값).
3. 전재를 포함한 블록 집합(`blocs_with_pickups`)은 표시용으로 따로 보관한다.
   전재도 "그 지역 편집자가 실을 만하다고 판단했다"는 약한 정보는 되므로
   버리지 않고, 다만 판정 기준에는 쓰지 않는다.

언어를 넘는 비교는 하지 않는다. 전재는 거의 항상 같은 언어에서 일어나고
(영문 통신 → 영문 매체), 번역된 전재는 일반 클러스터링이 잡는다. 교차언어
근접 중복 판정은 오탐이 커서 서로 다른 사건을 합칠 위험이 있다.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, Field

from .models import Article, SourceProfile

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")
DEFAULT_THRESHOLD = 0.60
_SHINGLE_N = 3


class WireGroup(BaseModel):
    """한 편집국의 기사 한 건으로 간주되는 기사 묶음."""

    representative_id: str = Field(description="그룹에서 가장 먼저 발행된 기사")
    article_ids: list[str] = Field(min_length=1)
    origin_bloc: str | None = None
    origin_source_id: str | None = None

    @property
    def pickup_count(self) -> int:
        return len(self.article_ids) - 1


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _is_cjk_heavy(text: str) -> bool:
    """공백으로 단어가 나뉘지 않는 문자가 많으면 문자 n-gram 을 쓴다."""
    if not text:
        return False
    cjk = sum(
        1
        for ch in text
        if "぀" <= ch <= "ヿ" or "㐀" <= ch <= "鿿" or "가" <= ch <= "힯"
    )
    return cjk / len(text) > 0.2


def shingles(text: str, n: int = _SHINGLE_N) -> set[str]:
    norm = normalize(text)
    if not norm:
        return set()
    if _is_cjk_heavy(norm):
        chars = norm.replace(" ", "")
        if len(chars) < n:
            return {chars}
        return {chars[i : i + n] for i in range(len(chars) - n + 1)}
    words = norm.split()
    if len(words) < n:
        return {" ".join(words)}
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


def similarity(a: str, b: str) -> float:
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def _dedupe_text(article: Article) -> str:
    """비교 대상 텍스트. 리드를 우선한다 — 전재 매체는 제목을 다시 쓰지만
    리드는 통신사 문장을 그대로 두는 경우가 많다."""
    return article.lead_orig or article.title_orig


def group_wire_duplicates(
    articles: Sequence[Article],
    sources: Mapping[str, SourceProfile] | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[WireGroup]:
    """근접 중복을 묶는다. 같은 언어끼리만 비교한다.

    union-find 로 전이적으로 묶는다. A≈B, B≈C 면 A,B,C 가 한 그룹이다.
    """
    sources = sources or {}
    parent: dict[str, str] = {a.id: a.id for a in articles}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    by_lang: dict[str, list[Article]] = {}
    for art in articles:
        by_lang.setdefault(art.lang, []).append(art)

    for group in by_lang.values():
        texts = {a.id: _dedupe_text(a) for a in group}
        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if similarity(texts[a.id], texts[b.id]) >= threshold:
                    union(a.id, b.id)

    members: dict[str, list[Article]] = {}
    for art in articles:
        members.setdefault(find(art.id), []).append(art)

    out: list[WireGroup] = []
    for group in members.values():
        group.sort(key=lambda a: (a.published_at, a.id))
        origin = group[0]
        profile = sources.get(origin.source_id)
        out.append(
            WireGroup(
                representative_id=origin.id,
                article_ids=[a.id for a in group],
                origin_bloc=profile.bloc if profile else None,
                origin_source_id=origin.source_id,
            )
        )
    out.sort(key=lambda g: g.representative_id)
    return out


def origin_blocs(groups: Iterable[WireGroup]) -> set[str]:
    """판정에 쓰는 블록 집합. wire 그룹당 한 번만 센다."""
    return {g.origin_bloc for g in groups if g.origin_bloc}


def blocs_with_pickups(
    articles: Sequence[Article],
    sources: Mapping[str, SourceProfile],
) -> set[str]:
    """표시용 블록 집합. 전재도 포함한다."""
    out: set[str] = set()
    for art in articles:
        profile = sources.get(art.source_id)
        if profile:
            out.add(profile.bloc)
    return out
