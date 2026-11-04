from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
import yaml

from blindspot.models import Article, Cluster, SourceProfile

T0 = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def _src(sid: str, country: str, bloc: str, lang: str, role: str = "source", **kw) -> SourceProfile:
    base = dict(
        id=sid, name=sid, country=country, bloc=bloc, language=lang,
        ownership="private", editorial_independence="independent",
        political_lean="unclassified", role=role,
        feed={"kind": "rss", "url": f"https://example.test/{sid}.xml"},
        tos_note="미확인",
    )
    base.update(kw)
    return SourceProfile(**base)


@pytest.fixture
def sources() -> dict[str, SourceProfile]:
    profiles = [
        _src("wapo", "US", "anglo", "en"),
        _src("guardian", "GB", "anglo", "en"),
        _src("lemonde", "FR", "eu", "fr"),
        _src("globaltimes", "CN", "sinosphere", "zh",
             ownership="party_organ", editorial_independence="state_controlled",
             political_lean="state_line", lean_basis="RSF Press Freedom Index; 중국 당 기관지 계열"),
        _src("tass", "RU", "russia", "ru",
             ownership="state_owned", editorial_independence="state_controlled",
             political_lean="state_line", lean_basis="RSF Press Freedom Index; 러시아 국영통신"),
        _src("yonhap", "KR", "other", "ko", role="baseline"),
        _src("japantimes", "JP", "other", "ja", role="baseline"),
    ]
    return {p.id: p for p in profiles}


def _art(aid: str, source_id: str, title: str, lead: str, lang: str, hours: float = 0.0) -> Article:
    return Article(
        id=aid, source_id=source_id, url=f"https://example.test/{aid}",
        title_orig=title, lead_orig=lead, lang=lang,
        published_at=T0 + timedelta(hours=hours), fetched_at=T0 + timedelta(hours=hours + 1),
    )


@pytest.fixture
def articles() -> dict[str, Article]:
    arts = [
        _art("a1", "wapo", "Protests in Capital City met with crackdown",
             "Police dispersed some 4500 demonstrators on November 3.", "en", 0),
        _art("a2", "guardian", "Thousands protest as police move in",
             "About 4500 people gathered before officers intervened.", "en", 1),
        _art("a3", "lemonde", "Manifestations reprimees dans la capitale",
             "Quelque 4500 manifestants se sont rassembles le 3 novembre.", "fr", 2),
        _art("a4", "globaltimes", "Authorities handle unrest according to law",
             "Local authorities said 4500 participants were managed lawfully.", "en", 3),
        _art("a5", "tass", "Special operation restores order in capital",
             "Officials reported 4500 participants.", "en", 4),
    ]
    return {a.id: a for a in arts}


@pytest.fixture
def cluster(articles) -> Cluster:
    return Cluster(
        id="c1", day=date(2026, 11, 3),
        article_ids=["a1", "a2", "a3", "a4", "a5"],
        event_label="Capital city protests and police response",
        countries={"US", "GB", "FR", "CN", "RU"},
        blocs={"anglo", "eu", "sinosphere", "russia"},
        spread_score=4.5,
    )


@pytest.fixture
def cfg() -> dict:
    return yaml.safe_load(open("config.yaml", encoding="utf-8"))


@pytest.fixture
def kr_article_factory():
    def make(title: str, lead: str, hours: float) -> Article:
        return _art(f"kr{int(hours)}", "yonhap", title, lead, "ko", hours)
    return make
