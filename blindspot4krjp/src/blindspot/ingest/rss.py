"""범용 RSS/Atom 어댑터.

소스별 어댑터를 쓰지 않는 이유: 피드 형식의 차이는 대부분 '어느 필드에
리드가 들어있는가'와 '날짜 형식'뿐이고, feedparser 가 그 둘을 흡수한다.
소스마다 클래스를 만들면 소스 추가가 코드 수정이 되어 확장이 멈춘다.
형식이 정말 다른 소스(공식 JSON API)만 별도 어댑터를 둔다.

★ 이 모듈이 P9(본문 저장 금지)를 집행한다.
피드가 전문을 싣고 있어도 리드를 MAX_LEAD_CHARS 로 자른다. 금지를 방침으로
적어두면 '이 소스는 예외로' 가 생기지만, 수집 경로에서 자르면 예외가 없다.
잘라낸 건수는 IngestReport 에 남아서 어떤 소스가 전문을 싣는지 드러난다.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import feedparser
from pydantic import BaseModel

from ..models import Article, SourceProfile

# 리드 저장 상한. 프레이밍 비교에는 2~3문장이면 충분하고,
# 이 상한이 전문 수집을 구조적으로 불가능하게 만든다.
MAX_LEAD_CHARS = 600

# 피드 역사(backfill)를 긁어오지 않도록 하는 기본 상한
DEFAULT_MAX_AGE_HOURS = 96

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# 추적 파라미터. URL 정규화에서 제거해 같은 기사가 둘로 세어지는 것을 막는다.
_TRACKING_PREFIXES = ("utm_", "pk_", "mc_", "at_")
_TRACKING_KEYS = {
    "fbclid", "gclid", "igshid", "ref", "ref_src", "s", "smid", "sref",
    "cmpid", "ocid", "ito", "CMP", "spm",
}

_LEAD_KEYS = ("summary", "description", "subtitle", "content")


class IngestReport(BaseModel):
    """무엇이 들어오고 무엇이 버려졌는지. 소스 품질 진단의 1차 자료."""

    source_id: str
    seen: int = 0
    accepted: int = 0
    skipped_no_title: int = 0
    skipped_no_url: int = 0
    skipped_no_date: int = 0
    skipped_too_old: int = 0
    skipped_duplicate_url: int = 0
    lead_missing: int = 0
    lead_truncated: int = 0
    lead_echoed_title: int = 0

    @property
    def lead_coverage(self) -> float:
        """리드를 가진 기사 비율. 0.8 미만이면 프레이밍 비교에 쓰기 어렵다."""
        if self.accepted == 0:
            return 0.0
        return (self.accepted - self.lead_missing) / self.accepted


def strip_html(raw: str | None) -> str:
    """피드 리드에 섞인 태그와 엔티티를 벗긴다."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = unicodedata.normalize("NFC", text)
    return _WS_RE.sub(" ", text).strip()


def canonical_url(raw: str) -> str:
    """추적 파라미터와 프래그먼트를 제거한 정규 URL."""
    parts = urlsplit(raw.strip())
    kept = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not (k.startswith(_TRACKING_PREFIXES) or k in _TRACKING_KEYS)
    ]
    query = "&".join(f"{k}={v}" for k, v in kept)
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def article_id(source_id: str, url: str) -> str:
    return hashlib.sha1(f"{source_id}\n{url}".encode()).hexdigest()[:16]


def _entry_lead(entry) -> str:
    for key in _LEAD_KEYS:
        value = entry.get(key)
        if isinstance(value, list):              # Atom content 는 리스트로 온다
            value = value[0].get("value") if value and isinstance(value[0], dict) else None
        text = strip_html(value if isinstance(value, str) else None)
        if text:
            return text
    return ""


def _entry_time(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def parse_feed(
    body: bytes | str,
    source: SourceProfile,
    *,
    fetched_at: datetime | None = None,
    max_age_hours: int = DEFAULT_MAX_AGE_HOURS,
) -> tuple[list[Article], IngestReport]:
    """피드 본문 → Article 목록 + 보고서.

    네트워크를 타지 않는다. 호출자가 받아온 바이트를 넘긴다. 그래서 동결
    fixture 로 완전히 테스트할 수 있고, 테스트가 돈이나 네트워크를 쓰지 않는다.

    날짜가 없는 항목은 버린다. `fetched_at` 으로 대체하면 모든 무날짜 항목이
    수집 시각에 몰려서 시간 윈도우를 오염시키고, 그 윈도우가 공백 판정에
    직접 쓰인다. 버린 건수는 보고서에 남는다.
    """
    now = fetched_at or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    parsed = feedparser.parse(body)
    report = IngestReport(source_id=source.id)
    seen_urls: set[str] = set()
    out: list[Article] = []

    for entry in parsed.entries or []:
        report.seen += 1

        title = strip_html(entry.get("title"))
        if not title:
            report.skipped_no_title += 1
            continue

        link = (entry.get("link") or "").strip()
        if not link.startswith(("http://", "https://")):
            report.skipped_no_url += 1
            continue
        url = canonical_url(link)
        if url in seen_urls:
            report.skipped_duplicate_url += 1
            continue

        published = _entry_time(entry)
        if published is None:
            report.skipped_no_date += 1
            continue
        if published < cutoff:
            report.skipped_too_old += 1
            continue

        lead = _entry_lead(entry)
        if not lead:
            report.lead_missing += 1
        else:
            if len(lead) > MAX_LEAD_CHARS:
                # ★ P9 집행 지점
                lead = lead[:MAX_LEAD_CHARS].rstrip()
                report.lead_truncated += 1
            if lead[:60] == title[:60]:
                report.lead_echoed_title += 1

        seen_urls.add(url)
        out.append(
            Article(
                id=article_id(source.id, url),
                source_id=source.id,
                url=url,
                title_orig=title,
                lead_orig=lead or None,
                lang=source.language,
                published_at=published,
                fetched_at=now,
            )
        )
        report.accepted += 1

    return out, report
