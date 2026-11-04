#!/usr/bin/env python3
"""Phase 0 — 후보 피드 접근성 조사.

측정하는 것:
  - HTTP 상태, 최종 URL(리다이렉트), content-type, 크기, 응답 시간
  - feedparser 파싱 성공 여부와 bozo 이유
  - item 개수
  - ★ 필드 가용성: title / lead / link / published 가 각각 몇 %의 item 에 있는지
  - ★ 리드 중위 길이 — 제목을 반복하기만 하는 피드를 걸러내기 위함
  - 전문 포함 의심 플래그 (리드가 비정상적으로 길면 저장해선 안 되므로)
  - 최신 item 시각 → 피드 생존 여부, 갱신 빈도 추정
  - robots.txt 가 해당 경로를 허용하는지

측정하지 않는 것: 이용약관. 사람이 각 매체의 법적고지를 직접 읽고
docs/source-audit.md 에 적는다. 추측으로 채우지 않는다 (P9).

사용법:
    python spikes/probe_sources.py                      # 전체
    python spikes/probe_sources.py --only bbc_world,dw_en
    python spikes/probe_sources.py --candidates spikes/candidates.tsv

결과는 spikes/out/probe_<timestamp>.json 에 누적 저장된다.
일일 생산량을 추정하려면 6시간 이상 간격으로 두 번 이상 돌려야 한다.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import feedparser
import httpx

UA = "Blindspot4KRJP-probe/0.1 (+https://github.com/fairyofdata/blindspot4krjp)"
CONCURRENCY = 4
TIMEOUT = 20.0
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "spikes" / "out"

# 리드가 이보다 길면 피드가 전문을 싣고 있을 가능성이 높다 → 저장 금지 대상 (P8)
FULL_BODY_SUSPECT_CHARS = 1200


def classify_failure(exc: Exception) -> tuple[str, str]:
    """실패를 '정책 차단'과 '사이트 문제'로 구분한다.

    정책 차단은 재시도·우회 대상이 아니라 보고 대상이다. 둘을 섞으면
    소스가 죽은 것인지 내 환경이 막힌 것인지 알 수 없게 된다.
    """
    msg = f"{type(exc).__name__}: {exc}"
    low = msg.lower()
    policy_markers = (
        "403 forbidden",
        "connect tunnel failed",
        "proxyerror",
        "getaddrinfo",
        "name or service not known",
        "nodename nor servname",
        "temporary failure in name resolution",
    )
    if any(m in low for m in policy_markers):
        return "blocked_or_unresolved", msg
    return "error", msg


async def fetch(client: httpx.AsyncClient, url: str) -> dict:
    t0 = time.monotonic()
    try:
        r = await client.get(url, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 — 실패 종류를 기록하는 것이 목적
        kind, msg = classify_failure(exc)
        return {"ok": False, "outcome": kind, "detail": msg,
                "elapsed_ms": round((time.monotonic() - t0) * 1000)}
    return {
        "ok": r.status_code == 200,
        "outcome": "http",
        "status": r.status_code,
        "final_url": str(r.url),
        "content_type": r.headers.get("content-type", ""),
        "bytes": len(r.content),
        "elapsed_ms": round((time.monotonic() - t0) * 1000),
        "_body": r.content,
    }


async def check_robots(client: httpx.AsyncClient, url: str) -> dict:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        r = await client.get(robots_url, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        kind, msg = classify_failure(exc)
        return {"robots_status": kind, "robots_allowed": None, "detail": msg}
    if r.status_code != 200:
        # robots.txt 가 없으면 허용으로 간주하는 것이 관례다.
        return {"robots_status": f"http_{r.status_code}", "robots_allowed": True}
    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    return {
        "robots_status": "ok",
        "robots_allowed": rp.can_fetch(UA, url),
        "robots_allowed_generic": rp.can_fetch("*", url),
    }


def analyze_feed(body: bytes) -> dict:
    parsed = feedparser.parse(body)
    entries = parsed.entries or []
    n = len(entries)

    def has(key: str, e) -> bool:
        v = e.get(key)
        return bool(v and str(v).strip())

    def lead_of(e) -> str:
        for key in ("summary", "description", "subtitle"):
            v = e.get(key)
            if v and str(v).strip():
                return str(v)
        return ""

    leads = [lead_of(e) for e in entries]
    lead_lens = [len(x) for x in leads if x]
    titles = [str(e.get("title", "")) for e in entries]

    # 리드가 제목과 거의 같은 비율 — 사실상 리드가 없는 피드를 잡아낸다
    echo = sum(
        1
        for t, ld in zip(titles, leads, strict=False)
        if ld and t and (ld.strip()[:60] == t.strip()[:60])
    )

    times = []
    for e in entries:
        st = e.get("published_parsed") or e.get("updated_parsed")
        if st:
            try:
                times.append(datetime(*st[:6], tzinfo=timezone.utc))
            except Exception:  # noqa: BLE001, S110
                pass

    pct = lambda k: round(sum(1 for e in entries if has(k, e)) / n, 3) if n else 0.0  # noqa: E731

    return {
        "bozo": bool(parsed.get("bozo")),
        "bozo_reason": str(parsed.get("bozo_exception", ""))[:200],
        "feed_title": str(parsed.feed.get("title", ""))[:120] if parsed.get("feed") else "",
        "items": n,
        "pct_title": pct("title"),
        "pct_link": pct("link"),
        "pct_published": round(len(times) / n, 3) if n else 0.0,
        "pct_lead": round(len([x for x in leads if x]) / n, 3) if n else 0.0,
        "lead_median_chars": int(statistics.median(lead_lens)) if lead_lens else 0,
        "lead_max_chars": max(lead_lens) if lead_lens else 0,
        "lead_echoes_title_pct": round(echo / n, 3) if n else 0.0,
        "full_body_suspect": bool(lead_lens and statistics.median(lead_lens) > FULL_BODY_SUSPECT_CHARS),
        "newest_item_utc": max(times).isoformat() if times else None,
        "oldest_item_utc": min(times).isoformat() if times else None,
        "span_hours": round((max(times) - min(times)).total_seconds() / 3600, 1) if len(times) > 1 else None,
    }


async def probe_one(sem: asyncio.Semaphore, client: httpx.AsyncClient, cand: dict) -> dict:
    async with sem:
        rec: dict = {**cand, "probed_at": datetime.now(timezone.utc).isoformat()}
        res = await fetch(client, cand["url"])
        body = res.pop("_body", None)
        rec.update(res)
        if body and res.get("ok"):
            rec.update(analyze_feed(body))
        rec.update(await check_robots(client, cand["url"]))
        return rec


def read_candidates(path: Path) -> list[dict]:
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cols = [c.strip() for c in line.split("\t") if c.strip() != ""]
        if len(cols) < 4:
            continue
        out.append({
            "bloc": cols[0], "country": cols[1], "source_id": cols[2],
            "url": cols[3],
            "priority": cols[4] if len(cols) > 4 else "",
            "note": cols[5] if len(cols) > 5 else "",
        })
    return out


def print_table(rows: list[dict]) -> None:
    hdr = (f"{'source_id':<22}{'prio':<9}{'res':<10}{'items':>6}{'lead%':>7}"
           f"{'leadMed':>8}{'echo%':>7}{'robots':>8}  feed")
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(rows, key=lambda x: (x.get("bloc", ""), x.get("source_id", ""))):
        if r.get("outcome") == "http":
            res = str(r.get("status"))
        else:
            res = r.get("outcome", "?")[:9]
        robots = r.get("robots_allowed")
        robots_s = "-" if robots is None else ("allow" if robots else "DENY")
        print(
            f"{r.get('source_id',''):<22}{r.get('priority','')[:8]:<9}{res:<10}{r.get('items',0):>6}"
            f"{r.get('pct_lead',0):>7.2f}{r.get('lead_median_chars',0):>8}"
            f"{r.get('lead_echoes_title_pct',0):>7.2f}{robots_s:>8}  "
            f"{(r.get('feed_title') or r.get('detail',''))[:44]}"
        )


async def main_async(args) -> int:
    cands = read_candidates(Path(args.candidates))
    if args.only:
        wanted = {s.strip() for s in args.only.split(",")}
        cands = [c for c in cands if c["source_id"] in wanted]
    if not cands:
        print("후보가 없습니다.", file=sys.stderr)
        return 2

    print(f"{len(cands)}개 후보 조사 시작 (동시 {CONCURRENCY}, 타임아웃 {TIMEOUT}s)\n")
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        headers={"User-Agent": UA, "Accept": "application/rss+xml, application/xml, */*"},
        timeout=TIMEOUT,
    ) as client:
        rows = await asyncio.gather(*(probe_one(sem, client, c) for c in cands))

    print_table(rows)

    blocked = [r for r in rows if r.get("outcome") == "blocked_or_unresolved"]
    if blocked:
        print(
            f"\n⚠ {len(blocked)}/{len(rows)} 건이 차단 또는 미해석입니다. "
            "사이트 문제가 아니라 실행 환경의 네트워크 정책일 수 있습니다.\n"
            "  해당 호스트를 세션/환경의 허용 도메인에 추가해야 합니다. 재시도·우회하지 마십시오.\n"
            "  호스트: " + ", ".join(sorted({urlsplit(r["url"]).netloc for r in blocked}))
        )

    usable = [
        r for r in rows
        if r.get("ok") and r.get("items", 0) > 0
        and r.get("pct_lead", 0) >= 0.8 and r.get("lead_echoes_title_pct", 1) < 0.5
    ]
    print(f"\n리드를 쓸만하게 제공하는 소스: {len(usable)}/{len(rows)}")
    print("  " + ", ".join(sorted(r["source_id"] for r in usable)) if usable else "  (없음)")

    # ★ ADR 0006: 자국어판이 전제를 지킨다. 영문판 비중을 드러낸다.
    by_prio: dict[str, int] = {}
    for r in usable:
        by_prio[r.get("priority", "")] = by_prio.get(r.get("priority", ""), 0) + 1
    if by_prio:
        print(f"\n우선순위별 사용 가능: {by_prio}")
        native, export = by_prio.get("native", 0), by_prio.get("export", 0)
        if export > native:
            print(
                "  ⚠ 영문판(export)이 자국어판(native)보다 많습니다. 그대로 채택하면 "
                "국내 필터를 수출용 필터로 바꾸는 것일 뿐입니다 (ADR 0006).\n"
                "    자국어판 URL 을 더 찾아보고, 그래도 안 되면 audit 에 그 사실을 적으십시오."
            )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_DIR / f"probe_{stamp}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out}")
    print("일일 생산량 추정에는 6시간 이상 간격의 2회차 실행이 필요합니다.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Phase 0 피드 접근성 조사")
    p.add_argument("--candidates", default=str(ROOT / "spikes" / "candidates.tsv"))
    p.add_argument("--only", default="", help="쉼표로 구분한 source_id 목록")
    return asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
