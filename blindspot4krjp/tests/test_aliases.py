"""별칭 매칭 규칙 — 오탐 방지가 핵심이다.

오탐은 "이 두 기사는 같은 개체를 다룬다"는 신호를 망가뜨리고,
그 신호는 공백 판정 점수로 바로 들어간다.
"""

from __future__ import annotations

import pytest

from blindspot.aliases import AliasEntity, AliasError, AliasIndex, load_aliases


def idx_of(**spec) -> AliasIndex:
    return AliasIndex(
        AliasEntity(id=k, kind="test", surfaces={"und": v}) for k, v in spec.items()
    )


# ---------------------------------------------------------------- 오탐

@pytest.mark.parametrize(
    ("surface_set", "text"),
    [
        ({"usa": ["US"]}, "It gave us hope."),
        ({"usa": ["US"]}, "The crust of the earth."),
        ({"usa": ["US"]}, "He said thus."),
        ({"united_nations": ["UN"]}, "Un homme est mort."),
        ({"united_nations": ["UN"]}, "It happened under pressure."),
        ({"who": ["WHO"]}, "Who knows what happened?"),
        ({"european_union": ["EU"]}, "eu is a romanization."),
        ({"usa": ["America"]}, "An American citizen."),
    ],
)
def test_short_latin_forms_do_not_false_match(surface_set, text):
    assert idx_of(**surface_set).extract(text) == set()


# ---------------------------------------------------------------- 정탐

@pytest.mark.parametrize(
    ("surface_set", "text", "expected"),
    [
        ({"usa": ["US"]}, "The US agreed.", {"usa"}),
        ({"usa": ["U.S."]}, "U.S. officials said so.", {"usa"}),
        ({"usa": ["US"]}, "Worth US$5bn.", {"usa"}),
        ({"united_nations": ["UN"]}, "The UN voted.", {"united_nations"}),
        ({"who": ["WHO"]}, "WHO issued a warning.", {"who"}),
        ({"usa": ["America"]}, "America responded.", {"usa"}),
        ({"turkey": ["Türkiye"]}, "Türkiye objected.", {"turkey"}),
    ],
)
def test_expected_matches(surface_set, text, expected):
    assert idx_of(**surface_set).extract(text) == expected


def test_long_latin_is_case_insensitive():
    i = idx_of(ukraine=["Ukraine"])
    assert i.extract("ukraine said") == {"ukraine"}
    assert i.extract("UKRAINE SAID") == {"ukraine"}


def test_nonlatin_uses_substring_matching():
    """CJK 는 공백으로 단어가 나뉘지 않으므로 부분 문자열 일치가 맞다."""
    i = idx_of(taiwan=["台湾"])
    assert i.extract("台湾海峡の緊張") == {"taiwan"}


def test_cyrillic_substring_catches_inflections():
    """부작용이 아니라 이득이다 — 러시아어 굴절형이 자동으로 잡힌다."""
    i = idx_of(putin=["Путин"])
    assert i.extract("Путина спросили") == {"putin"}
    assert i.extract("Путину сказали") == {"putin"}


# ---------------------------------------------------------------- 로드 검증

def test_too_short_surface_is_rejected():
    with pytest.raises(AliasError, match="너무 짧다"):
        idx_of(x=["A"])


def test_ambiguous_surface_shared_by_two_entities_is_rejected():
    with pytest.raises(AliasError, match="모호한"):
        idx_of(korea_north=["Korea"], korea_south=["Korea"])


def test_duplicate_entity_id_is_rejected():
    with pytest.raises(AliasError, match="중복"):
        AliasIndex([
            AliasEntity(id="a", kind="test", surfaces={"en": ["Alpha"]}),
            AliasEntity(id="a", kind="test", surfaces={"en": ["Beta"]}),
        ])


# ---------------------------------------------------------------- 실제 사전

@pytest.fixture(scope="module")
def seed() -> AliasIndex:
    return load_aliases("aliases.yaml")


def test_seed_dictionary_loads(seed):
    assert len(seed.entities) >= 100
    assert seed.surface_count >= 500


def test_seed_covers_the_core_languages(seed):
    cov = seed.language_coverage()
    for lang in ("en", "ko", "ja", "zh"):
        assert cov.get(lang, 0) >= 100, f"{lang} 표기가 부족하다"


def test_same_event_matches_across_four_languages(seed):
    """사전의 존재 이유. 임베딩이 약해도 이 신호는 확실하다."""
    texts = [
        "Trump met Xi Jinping to discuss the Taiwan Strait.",
        "트럼프 대통령이 시진핑 주석과 대만해협 문제를 논의했다.",
        "トランプ氏と習近平氏が台湾海峡について協議した。",
        "特朗普与习近平就台湾海峡问题进行了磋商。",
    ]
    extracted = [seed.extract(t) for t in texts]
    common = set.intersection(*extracted)
    assert {"donald_trump", "xi_jinping", "taiwan_strait"} <= common


def test_person_entries_are_flagged_volatile(seed):
    """선거·정변으로 무효화되는 항목은 표시되어야 한다."""
    persons = [e for e in seed.entities.values() if e.kind == "person"]
    assert persons
    assert all(e.volatile and e.as_of for e in persons)


def test_seed_has_no_generic_topic_words(seed):
    """일반 주제어가 들어오면 모든 관세 기사가 서로 매칭되어 신호가 죽는다."""
    banned = {
        "tariff", "ceasefire", "election", "earthquake", "sanctions",
        "관세", "휴전", "선거", "지진", "제재",
    }
    surfaces = {s.lower() for e in seed.entities.values() for s in e.all_surfaces()}
    assert banned.isdisjoint(surfaces)
