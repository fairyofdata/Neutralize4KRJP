#!/usr/bin/env python3
"""Wikidata 에서 별칭 사전을 생성한다 — `aliases.generated.yaml`.

왜 생성하는가 (ADR 0003)
------------------------
손으로 쓴 다국어 별칭 사전은 두 가지로 무너진다. 규모(세계 뉴스에 등장하는
고유명사는 수천 개다)와 부패(인물은 선거로, 국명은 개칭으로 바뀐다).
Wikidata 는 바로 이 데이터 — 다국어 레이블과 별칭 — 를 이미 갖고 있고,
새 지도자가 취임하면 며칠 안에 반영된다.

그래서 `aliases.yaml` 은 **시드/오버라이드 층**으로 작게 유지하고,
대량은 이 스크립트로 생성한다. 로더가 둘을 합쳐 읽는다.

    load_aliases("aliases.generated.yaml", "aliases.yaml")

실행 요건: `query.wikidata.org` 로의 네트워크 접근. 차단되어 있으면
환경의 허용 도메인에 추가해야 한다 (재시도·우회하지 말 것).

    python scripts/build_aliases_from_wikidata.py --out aliases.generated.yaml

주의: Wikidata 는 공개 위키이므로 레이블이 훼손될 수 있다. 생성본은
입력 데이터이지 지시가 아니다. 로더의 검증(최소 길이, 모호 표기 거부)이
1차 방어선이고, 시드 파일이 오버라이드 수단이다.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict

import httpx
import yaml

ENDPOINT = "https://query.wikidata.org/sparql"
UA = "Blindspot4KRJP-alias-builder/0.1 (+https://github.com/fairyofdata/blindspot4krjp)"
LANGS = ["en", "ko", "ja", "zh", "zh-hant", "fr", "de", "ru", "es"]

# kind → SPARQL. 각 쿼리는 ?item ?kind 를 돌려주고, 레이블·별칭은 별도로 받는다.
QUERIES: dict[str, str] = {
    "country": """
        SELECT DISTINCT ?item WHERE {
          ?item wdt:P31 wd:Q3624078 .          # 주권국가
          FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
        }
    """,
    "org": """
        SELECT DISTINCT ?item WHERE {
          VALUES ?cls { wd:Q484652 wd:Q1335818 wd:Q7210356 }
          ?item wdt:P31/wdt:P279* ?cls .
          ?item wikibase:sitelinks ?links .
          FILTER (?links > 40)                 # 주변부 조직 제외
        }
    """,
    "person": """
        SELECT DISTINCT ?item WHERE {
          ?country wdt:P31 wd:Q3624078 .
          { ?country wdt:P35 ?item } UNION { ?country wdt:P6 ?item }
        }
    """,
}

LABEL_QUERY = """
SELECT ?item ?label ?alt WHERE {
  VALUES ?item { %(items)s }
  OPTIONAL { ?item rdfs:label ?label     FILTER (lang(?label) IN (%(langs)s)) }
  OPTIONAL { ?item skos:altLabel ?alt    FILTER (lang(?alt)   IN (%(langs)s)) }
}
"""


def sparql(client: httpx.Client, query: str) -> list[dict]:
    r = client.post(
        ENDPOINT,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json", "User-Agent": UA},
        timeout=120.0,
    )
    r.raise_for_status()
    return r.json()["results"]["bindings"]


def qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def fetch_kind(client: httpx.Client, kind: str, query: str, chunk: int = 150) -> dict[str, dict]:
    items = [qid(row["item"]["value"]) for row in sparql(client, query)]
    print(f"  {kind}: {len(items)} 개체", file=sys.stderr)

    out: dict[str, dict] = {}
    langs = ", ".join(f'"{x}"' for x in LANGS)
    for i in range(0, len(items), chunk):
        batch = items[i : i + chunk]
        q = LABEL_QUERY % {
            "items": " ".join(f"wd:{x}" for x in batch),
            "langs": langs,
        }
        surfaces: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for row in sparql(client, q):
            item = qid(row["item"]["value"])
            for key in ("label", "alt"):
                if key in row:
                    lang = row[key].get("xml:lang", "und")
                    surfaces[item][lang].add(row[key]["value"])
        for item, by_lang in surfaces.items():
            out[item] = {
                "id": f"wd_{item}",
                "kind": kind,
                "surfaces": {k: sorted(v) for k, v in sorted(by_lang.items())},
                "volatile": kind == "person",
                "as_of": time.strftime("%Y-%m"),
                "notes": f"Wikidata {item} 에서 생성",
            }
        print(f"    레이블 {i + len(batch)}/{len(items)}", file=sys.stderr)
        time.sleep(1.0)  # 공개 엔드포인트에 대한 예의
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Wikidata 별칭 사전 생성")
    p.add_argument("--out", default="aliases.generated.yaml")
    p.add_argument("--kinds", default="country,org,person")
    args = p.parse_args()

    entities: list[dict] = []
    with httpx.Client(follow_redirects=True) as client:
        for kind in args.kinds.split(","):
            kind = kind.strip()
            if kind not in QUERIES:
                print(f"알 수 없는 kind: {kind}", file=sys.stderr)
                return 2
            try:
                entities.extend(fetch_kind(client, kind, QUERIES[kind]).values())
            except httpx.HTTPError as exc:
                print(f"\n{kind} 조회 실패: {type(exc).__name__}: {exc}", file=sys.stderr)
                print(
                    "query.wikidata.org 가 네트워크 정책으로 막혀 있을 수 있습니다. "
                    "허용 도메인에 추가해야 하며, 재시도·우회하지 마십시오.",
                    file=sys.stderr,
                )
                return 1

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(
            "# 자동 생성 파일 — 직접 수정하지 마십시오.\n"
            "# scripts/build_aliases_from_wikidata.py 가 만듭니다.\n"
            "# 손으로 고칠 것은 aliases.yaml (시드/오버라이드) 에 적습니다.\n"
            f"# 생성: {time.strftime('%Y-%m-%d')}\n\n"
        )
        yaml.safe_dump({"entities": entities}, f, allow_unicode=True, sort_keys=False)

    print(f"\n{len(entities)} 개체를 {args.out} 에 기록했습니다.", file=sys.stderr)
    print(
        "검증: python -c \"from blindspot.aliases import load_aliases; "
        "i=load_aliases('aliases.generated.yaml','aliases.yaml'); "
        "print(len(i.entities), i.surface_count)\"",
        file=sys.stderr,
    )
    print(
        "로더가 너무 짧은 표기와 모호한 표기를 거부합니다. 거부되면 "
        "해당 표기를 생성본에서 빼거나 시드에서 오버라이드하십시오.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
