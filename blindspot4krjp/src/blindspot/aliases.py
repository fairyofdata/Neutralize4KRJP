"""개체 별칭 사전 — 로드와 교차언어 매칭.

매칭 규칙이 왜 이렇게 복잡한가
------------------------------
단순 부분 문자열 일치는 짧은 라틴 표기에서 무너진다.

  "US"  → 영어 대명사 "us", "thus", "crust" 에 걸린다
  "UN"  → 프랑스어 관사 "un", "under" 에 걸린다
  "WHO" → 의문사 "who" 에 걸린다
  "EU"  → 로마자 "eu", "Europe" 에 걸린다

오탐은 "이 두 기사는 같은 개체를 다룬다"는 신호를 망가뜨리고, 그 신호는
공백 판정 점수로 바로 들어간다. 그래서 표기의 문자 체계와 길이에 따라
매칭 방식을 달리한다.

  비라틴 (한글·가나·한자·키릴 …)  부분 문자열, 소문자화. 최소 2자.
  라틴 5자 이상                   라틴 단어 경계, 대소문자 무시
  라틴 4자 이하                   라틴 단어 경계, **대소문자 구분**

단어 경계는 `\\b` 대신 라틴 문자·숫자에 대한 lookaround 를 쓴다. `\\b` 는
"U.S." 처럼 구두점으로 끝나는 표기에서 어긋나고, `\\w` 는 가나·한자를
포함해서 일본어 문장 속 라틴 단어를 놓친다.

키릴 표기에 부분 문자열 일치를 쓰는 것은 부작용이 아니라 이득이다 —
러시아어 굴절형("Путина", "Путину")이 자동으로 잡힌다.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# 라틴 문자·숫자. 단어 경계 판정에 쓴다. 라틴 확장-A/B 까지 포함해
# Türkiye, Erdoğan, Israël 같은 표기를 올바로 다룬다.
_LATIN = r"[0-9A-Za-zÀ-ɏ]"
_SHORT_LATIN_MAX = 4
_MIN_SURFACE_CHARS = 2


class AliasEntity(BaseModel):
    id: str
    kind: str = Field(description="country | org | place | person")
    surfaces: dict[str, list[str]] = Field(description="언어코드 → 표기 목록")
    volatile: bool = Field(default=False, description="선거·정변으로 무효화되는 항목")
    as_of: str | None = Field(default=None, description="volatile 항목의 기준 시점")
    notes: str = ""

    def all_surfaces(self) -> list[str]:
        return [s for forms in self.surfaces.values() for s in forms]


class AliasError(ValueError):
    pass


def _is_latin(surface: str) -> bool:
    """알파벳 문자가 전부 라틴 계열인지. 한글·가나·한자·키릴이 하나라도 있으면 False."""
    return not any(ch.isalpha() and ord(ch) > 0x024F for ch in surface)


def _significant_len(surface: str) -> int:
    return sum(1 for ch in surface if ch.isalnum())


class AliasIndex:
    """표기 → 개체 id 매칭기.

    같은 결과를 주는 세 경로를 미리 컴파일해 둔다. 라틴 표기는 하나의
    합성 정규식으로 묶어서, 표기 수가 늘어도 텍스트를 한 번만 훑는다.
    """

    def __init__(self, entities: Iterable[AliasEntity]) -> None:
        self.entities: dict[str, AliasEntity] = {}
        owner: dict[str, str] = {}          # 정규화된 표기 → entity id
        nonlatin: list[tuple[str, str]] = []  # (소문자 표기, entity id)
        long_latin: dict[str, str] = {}
        short_latin: dict[str, str] = {}

        for ent in entities:
            if ent.id in self.entities:
                raise AliasError(f"개체 id 중복: {ent.id}")
            self.entities[ent.id] = ent
            for surface in ent.all_surfaces():
                s = surface.strip()
                if _significant_len(s) < _MIN_SURFACE_CHARS:
                    raise AliasError(
                        f"{ent.id}: 표기 {surface!r} 가 너무 짧다 "
                        f"(유효문자 {_MIN_SURFACE_CHARS}자 이상 필요). 오탐을 막기 위한 제약이다."
                    )
                key = s if (_is_latin(s) and _significant_len(s) <= _SHORT_LATIN_MAX) else s.lower()
                prev = owner.get(key)
                if prev is not None and prev != ent.id:
                    raise AliasError(
                        f"표기 {surface!r} 가 {prev} 와 {ent.id} 양쪽에 있다. "
                        f"모호한 표기는 어느 쪽에서든 제거해야 한다."
                    )
                owner[key] = ent.id

                if not _is_latin(s):
                    nonlatin.append((s.lower(), ent.id))
                elif _significant_len(s) <= _SHORT_LATIN_MAX:
                    short_latin[s] = ent.id          # 대소문자 구분
                else:
                    long_latin[s.lower()] = ent.id   # 대소문자 무시

        self._nonlatin = nonlatin
        self._long_latin = long_latin
        self._short_latin = short_latin
        self._re_long = self._compile(long_latin.keys(), re.IGNORECASE)
        self._re_short = self._compile(short_latin.keys(), 0)

    @staticmethod
    def _compile(surfaces: Iterable[str], flags: int) -> re.Pattern | None:
        forms = sorted(surfaces, key=len, reverse=True)
        if not forms:
            return None
        body = "|".join(re.escape(f) for f in forms)
        return re.compile(rf"(?<!{_LATIN})(?:{body})(?!{_LATIN})", flags)

    def extract(self, text: str) -> set[str]:
        """텍스트에 등장하는 개체 id 집합."""
        if not text:
            return set()
        low = text.lower()
        found = {eid for surface, eid in self._nonlatin if surface in low}
        if self._re_long is not None:
            for m in self._re_long.finditer(text):
                eid = self._long_latin.get(m.group(0).lower())
                if eid:
                    found.add(eid)
        if self._re_short is not None:
            for m in self._re_short.finditer(text):
                eid = self._short_latin.get(m.group(0))
                if eid:
                    found.add(eid)
        return found

    # --- 점검용 -------------------------------------------------------

    @property
    def surface_count(self) -> int:
        return len(self._nonlatin) + len(self._long_latin) + len(self._short_latin)

    def volatile_entities(self) -> list[AliasEntity]:
        """검토가 필요한 항목. 인물은 선거로 무효화된다."""
        return [e for e in self.entities.values() if e.volatile]

    def language_coverage(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for ent in self.entities.values():
            for lang in ent.surfaces:
                out[lang] = out.get(lang, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def load_aliases(*paths: str | Path) -> AliasIndex:
    """여러 파일을 합쳐 로드한다. 뒤 파일이 같은 id 를 가지면 거부한다.

    의도한 사용법: `load_aliases("aliases.generated.yaml", "aliases.yaml")`
    처럼 생성본과 손으로 쓴 시드를 함께 쓴다. id 충돌은 조용히 덮어쓰는
    대신 오류로 드러낸다 — 어느 쪽이 이겼는지 모르는 상태가 더 나쁘다.
    """
    entities: list[AliasEntity] = []
    seen: set[str] = set()
    for path in paths:
        p = Path(path)
        if not p.exists():
            continue
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for item in raw.get("entities", []):
            ent = AliasEntity.model_validate(item)
            if ent.id in seen:
                raise AliasError(f"{p}: 개체 id {ent.id} 가 앞선 파일에 이미 있다")
            seen.add(ent.id)
            entities.append(ent)
    return AliasIndex(entities)
