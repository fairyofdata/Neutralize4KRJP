"""통신사 전재 축약 — 공백 판정 기준의 분모를 정직하게 만드는 장치."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from blindspot.dedupe import (
    group_wire_duplicates,
    origin_blocs,
    shingles,
    similarity,
)
from blindspot.models import Article

T0 = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)

WIRE_LEAD = (
    "Police dispersed some 4,500 demonstrators in the capital on Tuesday, "
    "officials said, after a march over pension reform turned confrontational."
)


def art(aid: str, source_id: str, title: str, lead: str, lang: str = "en", hours: float = 0.0):
    return Article(
        id=aid, source_id=source_id, url=f"https://x.test/{aid}",
        title_orig=title, lead_orig=lead, lang=lang,
        published_at=T0 + timedelta(hours=hours), fetched_at=T0,
    )


def test_identical_wire_lead_groups_across_sources(sources):
    """★ 핵심 사례. 한 통신사 기사가 3개 블록에 실린 상황."""
    arts = [
        art("w1", "guardian", "Thousands march in capital", WIRE_LEAD, hours=0),
        art("w2", "lemonde", "Marchers fill the capital", WIRE_LEAD, hours=1),
        art("w3", "globaltimes", "Capital sees large march", WIRE_LEAD, hours=2),
    ]
    groups = group_wire_duplicates(arts, sources)
    assert len(groups) == 1
    assert groups[0].pickup_count == 2
    assert origin_blocs(groups) == {"anglo"}, "가장 먼저 발행된 기사의 블록에만 귀속"


def test_distinct_reporting_is_not_collapsed(sources):
    arts = [
        art("a", "guardian", "Thousands march in capital", WIRE_LEAD, hours=0),
        art("b", "lemonde", "Pension reform passes committee",
            "Lawmakers advanced the pension bill in committee by a narrow margin "
            "after three days of procedural wrangling in the lower house.", hours=1),
    ]
    groups = group_wire_duplicates(arts, sources)
    assert len(groups) == 2
    assert origin_blocs(groups) == {"anglo", "eu"}


def test_origin_is_the_earliest_published(sources):
    arts = [
        art("late", "guardian", "Pickup", WIRE_LEAD, hours=5),
        art("early", "lemonde", "Original", WIRE_LEAD, hours=0),
    ]
    groups = group_wire_duplicates(arts, sources)
    assert groups[0].representative_id == "early"
    assert groups[0].origin_bloc == "eu"


def test_different_languages_are_never_compared(sources):
    """교차언어 근접 중복 판정은 오탐이 커서 서로 다른 사건을 합칠 위험이 있다."""
    arts = [
        art("en", "guardian", "Same story", WIRE_LEAD, lang="en"),
        art("fr", "lemonde", "Same story", WIRE_LEAD, lang="fr"),
    ]
    groups = group_wire_duplicates(arts, sources)
    assert len(groups) == 2


def test_grouping_is_transitive(sources):
    near = WIRE_LEAD.replace("officials said", "officials have said")
    arts = [
        art("a", "guardian", "t", WIRE_LEAD, hours=0),
        art("b", "lemonde", "t", near, hours=1),
        art("c", "globaltimes", "t", near, hours=2),
    ]
    assert len(group_wire_duplicates(arts, sources)) == 1


def test_title_is_used_when_lead_is_missing(sources):
    arts = [
        art("a", "guardian", "Exactly the same headline text here", "", hours=0),
        art("b", "lemonde", "Exactly the same headline text here", "", hours=1),
    ]
    arts = [a.model_copy(update={"lead_orig": None}) for a in arts]
    assert len(group_wire_duplicates(arts, sources)) == 1


# ---------------------------------------------------------------- 유사도

def test_cjk_uses_character_ngrams():
    """CJK 는 공백으로 단어가 나뉘지 않으므로 문자 n-gram 이어야 한다."""
    a = "警察は首都で約4500人のデモ参加者を解散させた"
    assert len(shingles(a)) > 5
    assert similarity(a, a) == 1.0


def test_similarity_bounds():
    assert similarity("", "anything") == 0.0
    assert similarity("the quick brown fox jumps", "the quick brown fox jumps") == 1.0
    assert 0.0 <= similarity("completely different words here now",
                             "the quick brown fox jumps") < 0.3


@pytest.mark.parametrize("threshold", [0.3, 0.6, 0.9])
def test_threshold_is_configurable(sources, threshold):
    arts = [
        art("a", "guardian", "t", WIRE_LEAD, hours=0),
        art("b", "lemonde", "t", WIRE_LEAD[:80] + " and other unrelated wording entirely", hours=1),
    ]
    groups = group_wire_duplicates(arts, sources, threshold=threshold)
    assert 1 <= len(groups) <= 2
