"""수집 어댑터 — 동결 fixture 로만 테스트한다 (네트워크·비용 0).

fixture 는 전부 창작물이다. tests/fixtures/README.md 참조.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from blindspot.ingest.rss import (
    MAX_LEAD_CHARS,
    article_id,
    canonical_url,
    parse_feed,
    strip_html,
)
from blindspot.models import SourceProfile

FIX = Path(__file__).resolve().parent / "fixtures"
NOW = datetime(2026, 11, 3, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def source() -> SourceProfile:
    return SourceProfile(
        id="fixture", name="Fixture", country="US", bloc="anglo", language="en",
        ownership="private", editorial_independence="independent",
        political_lean="unclassified", role="source",
        feed={"kind": "rss", "url": "https://fixture.test/feed.xml"},
    )


def load(name: str, source: SourceProfile, **kw):
    return parse_feed((FIX / name).read_bytes(), source, fetched_at=NOW, **kw)


# ---------------------------------------------------------------- 정상 경로

def test_well_formed_feed_yields_articles(source):
    arts, rep = load("well_formed.xml", source)
    assert rep.seen == 2 and rep.accepted == 2
    assert arts[0].title_orig == "Capital City protests met with police response"
    assert "4,500 demonstrators" in arts[0].lead_orig
    assert arts[0].lang == "en"
    assert rep.lead_coverage == 1.0


def test_html_is_stripped_from_lead(source):
    arts, _ = load("well_formed.xml", source)
    assert "<p>" not in arts[0].lead_orig
    assert "&amp;" not in arts[0].lead_orig


def test_atom_summary_and_content_both_work(source):
    arts, rep = load("atom.xml", source)
    assert rep.accepted == 2
    assert "maritime security" in arts[0].lead_orig
    assert "12 paragraphs" in arts[1].lead_orig


# ---------------------------------------------------------------- P9 집행

def test_full_text_feed_is_clamped_not_rejected(source):
    """★ P9 집행 지점.

    피드가 전문을 실어도 저장은 리드 길이까지다. 방침으로 적어두면
    '이 소스는 예외로' 가 생기지만, 수집 경로에서 자르면 예외가 없다.
    """
    arts, rep = load("full_body.xml", source)
    assert rep.accepted == 1
    assert rep.lead_truncated == 1
    assert len(arts[0].lead_orig) <= MAX_LEAD_CHARS


def test_article_model_cannot_hold_a_body(source):
    arts, _ = load("full_body.xml", source)
    assert not hasattr(arts[0], "body")
    assert "body" not in arts[0].model_dump()


# ---------------------------------------------------------------- 결함 처리

def test_degraded_feed_skips_and_counts(source):
    arts, rep = load("degraded.xml", source)
    assert rep.skipped_no_date == 1
    assert rep.skipped_no_title == 1
    assert rep.skipped_no_url == 1
    assert rep.skipped_too_old == 1
    assert rep.skipped_duplicate_url == 1
    assert rep.lead_echoed_title == 1
    assert rep.accepted == 2
    assert len(arts) == 2


def test_undated_items_are_dropped_not_backfilled(source):
    """날짜 없는 항목을 수집 시각으로 채우면 시간 윈도우가 오염되고,
    그 윈도우가 공백 판정에 직접 쓰인다."""
    arts, _ = load("degraded.xml", source)
    assert all(a.published_at != NOW for a in arts)


def test_age_window_is_configurable(source):
    _, rep = load("degraded.xml", source, max_age_hours=24)
    assert rep.skipped_too_old >= 1


# ---------------------------------------------------------------- URL 정규화

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://a.test/x?utm_source=rss", "https://a.test/x"),
        ("https://a.test/x?fbclid=z&id=7", "https://a.test/x?id=7"),
        ("https://A.TEST/x/#frag", "https://a.test/x"),
        ("https://a.test/x/", "https://a.test/x"),
        ("https://a.test/?spm=abc", "https://a.test/"),
    ],
)
def test_canonical_url(raw, expected):
    assert canonical_url(raw) == expected


def test_id_is_stable_and_source_scoped():
    u = "https://a.test/x"
    assert article_id("s1", u) == article_id("s1", u)
    assert article_id("s1", u) != article_id("s2", u)


def test_strip_html_handles_none():
    assert strip_html(None) == ""
