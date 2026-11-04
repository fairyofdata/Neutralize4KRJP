# Blindspot4KRJP — 프로젝트 헌장 및 Phase 0 작업 지시

이 저장소에는 **Phase 1 골격이 이미 들어 있습니다** (테스트 126건 통과, 네트워크·API 키·비용 0). 합성 데이터로 브리핑 한 부가 끝까지 생성됩니다:

```bash
python scripts/demo_briefing.py
```

비어 있는 것은 **실제 피드 결합**(Phase 0 이 끝나야 가능), 실제 임베딩 모델 결합, LLM 주장 추출(Phase 2), 발행 자동화(Phase 4) 입니다.

> **이번 세션의 범위: Phase 0 (소스 접근성 검증) 만.**
> 파이프라인·LLM·UI 코드를 쓰지 마십시오. §7 의 산출물만 만들고 끝냅니다.
> 소스가 실제로 무엇을 주는지 모르는 상태에서 쓴 수집 코드는 전부 버려집니다.

---

## 1. 제품 정의

**한 줄:** 전 세계 주요 언론의 당일 보도를 수집해, ① 같은 사건을 각국이 **어떻게 다르게** 서술하는지의 대조표와, ② 세계가 크게 다루는데 **한국·일본 언론은 다루지 않은** 이슈 목록(보도 공백)을 매일 발행한다.

**사용자:** 한국어·일본어 언론만 소비해서 국제 정세에 대한 시야가 좁아지는 사람. (제작자 본인이 1차 사용자.)

**AI 가 하는 일:** 사건을 묶고, 주장을 출처와 함께 추출하고, 어휘 선택의 차이를 드러낸다.
**AI 가 하지 않는 일:** 어느 쪽이 맞는지 판정하거나, 종합 의견·중립 결론·요약 논평을 쓰는 것.

### 목표 산출물의 모양

```
━━ 2026-11-03 브리핑 ━━

▣ 보도 공백 (세계 3개 블록 이상 보도 / 한국 보도 없음)
  1. [사건명]  — 보도: 🇺🇸3 🇬🇧2 🇫🇷1 🇩🇪1 🇮🇳2  |  🇰🇷0 🇯🇵1
     └ 판정 근거: 매칭 최고점 0.21 (기준 0.34 미만)
  2. ...
  ※ 판정 불확실 4건은 위 목록에서 제외됨

▣ 주요 사건: [사건명]   보도 12건 / 6개국 / 4개 블록
  ├ 공통 사실 (서로 다른 2개 이상 블록이 함께 보도한 것만)
  │   · ○○이 ○○했다.                      [AP, LeMonde, Xinhua]
  ├ 한 블록만 보도한 사실
  │   · ○○ (앵글로권만)                     [NYT, Guardian]
  ├ 서술의 차이 (같은 대상, 다른 단어)
  │   · 🇺🇸🇬🇧 "crackdown"                  [WaPo]
  │   · 🇨🇳   "依法处置 / handled according to law"  [GlobalTimes · 국가통제]
  │   · 🇷🇺   "спецоперация / special operation"    [TASS · 국영]
  └ 각 매체가 밝힌 입장 (귀속 + 소스 라벨)
```

이 출력에 **"따라서 ○○이 타당하다"류의 문장은 등장하지 않습니다.** 판단은 독자가 합니다.

---

## 2. 설계 원칙 (불가침 — 변경하려면 ADR 에 올려 사용자에게 물어볼 것)

**P1. AI 는 결론을 내리지 않는다.**
스키마에 `conclusion`, `assessment`, `verdict`, `neutral_summary`, `opinion` 필드를 만들지 않는다. 금지가 프롬프트에만 있으면 지켜지지 않으므로 타입 수준에서 불가능하게 만든다. `tests/test_p1_no_conclusion_fields.py` 가 `src/` 전체를 스캔해 이를 기계적으로 검사한다.

**P2. 모든 주장은 출처 ID 를 갖는다.**
`Claim.article_ids` 는 `min_length=1`. 클러스터에 없는 article_id 를 참조하는 주장은 `provenance.validate()` 가 버리고 비율을 집계한다. 그 비율이 지표 M1 이다.

**P3. 원어 어휘를 보존한다 — 프레이밍이 데이터다.**
서술 차이 항목은 원문 표현을 원어 그대로 + 영어 주석으로 보존한다 (`QuotedTerm`). 번역은 보조이며, 분석 대상 어휘를 번역으로 대체하지 않는다.

**P4. 거짓 대칭 금지.**
"좌/우 양쪽"은 편집권이 독립된 언론 사이에서만 유효한 축이다. 국가통제 매체는 배제하지 않고 **라벨을 붙여 포함**한다 — 그 정부가 밀고 있는 프레임의 1차 사료로서 가치가 있다. 출력에는 항상 소유구조·편집권 라벨이 함께 표시된다.

**P5. 편향 라벨을 LLM 이 만들지 않는다.**
`political_lean` 은 외부 공개 레퍼런스(AllSides, Media Bias/Fact Check, Reuters Institute, RSF 등)를 `lean_basis` 에 인용한다. 근거를 못 찾으면 `unclassified`. `SourceProfile` 의 validator 가 근거 없는 라벨을 거부한다.

**P6. 한국·일본 매체는 소스가 아니라 측정 기준선이다.**
브리핑 본문에 절대 투입하지 않는다 (`role: baseline`). 보도 공백 계산을 위해서만 수집한다.

**P7. 공백 판정은 비대칭 검색으로 한다. ★**
한국어 기사가 해외 클러스터에 "묶이기"를 요구하지 **않는다.** 교차언어 매칭에서 실패 가능성이 가장 높은 것이 한국어 기사이므로, 그 방식은 클러스터링 실패를 그대로 거짓 공백으로 바꿔 지표를 한 방향으로 부풀린다. 대신 해외 클러스터의 대표 문장으로 baseline 코퍼스를 **질의**하고, baseline 쪽 시간 윈도우와 임계값을 따로·더 느슨하게 둔다. 판정은 3분기이며 **애매한 구간은 공백으로 세지 않는다.** 근거: `docs/decisions/0002`.

**P8. 중요도는 기사 수가 아니라 블록 수로 매긴다.**
앵글로권은 영문 매체가 압도적으로 많아서, 기사 수로 랭킹하면 미·영 의제가 세계 의제로 둔갑한다. `spread_score` 는 서로 다른 블록 개수를 기준으로 한다.

**P9. RSS/API 만. Selenium 금지. 전문 저장 금지.**
저장하는 것은 제목 + 리드 + URL + 시각 + 언어뿐이다. `Article` 에 본문 필드를 만들지 않는다. 유료장벽 우회·본문 스크레이핑을 하지 않는다.

**P10. 측정하지 않은 것은 주장하지 않는다.**
"중립적", "객관적", "편향 없는" 같은 표현을 제품 설명에 쓰지 않는다. 지표가 있으면 숫자를, 없으면 "측정하지 않음"을 쓴다. 실측 전 필드는 `None` 으로 둔다.

**P11. 비용 상한을 코드로 강제한다.**
일일 LLM 호출·토큰 상한을 `config.yaml` 에 두고, 초과 시 파이프라인이 중단되며 부분 결과를 저장한다.

---

## 3. 아키텍처

```
  [RSS/API 어댑터]                      sources.yaml 선언. 코드 수정 없이 소스 추가.
        │                               role=source (해외) / role=baseline (KR·JP)
        ▼
  [정규화 → Article]                    제목 + 리드 + URL + 시각 + 언어. 본문 없음 (P9).
        │
        ├──────────────────────────┬──────────────────────────┐
        ▼                          ▼                          │
  role=source 만                role=baseline 만               │
        │                       (클러스터링에 불참)              │
        ▼                          │                          │
  [다국어 임베딩]  ★ LLM 0회       │                          │
        ▼                          │                          │
  [클러스터링 → Cluster]            │                          │
   당일 ±36h, 코사인 임계값          │                          │
        │                          │                          │
        ├──────────────────────────┘                          │
        ▼                                                     │
  ★ [비대칭 baseline 검색]  (P7)                                │
   클러스터 대표문 → baseline 코퍼스 질의                         │
   · 윈도우 ±72h  (해외 36h 보다 넓게 — 한국 보도는 지연된다)      │
   · 임계값 tau_low / tau_high  (클러스터링과 별개, 더 느슨하게)   │
   · 신호: 임베딩 + 숫자·연도(언어 독립) + 개체 별칭               │
   · 판정: covered / uncertain / not_covered                   │
        ▼                                                     │
  [공백 판정 → BlindspotVerdict]                                │
   blocs ≥ 3 AND KR = not_covered  → 공백                      │
   KR = uncertain                  → 집계 제외 + 따로 센다       │
        │                                                     │
        │          ┌──────────────────────────────────────────┘
        ▼          ▼
  [클러스터 랭킹]  spread_score = 블록 수 기반 (P8). 상위 N 개만 다음 단계로.
        ▼
  [주장 추출 (LLM, 클러스터 단위)]
   Claim{text_en, claim_type, article_ids, quoted_terms}
        ▼
  [provenance validator (순수 함수, LLM 아님)]
   존재하지 않는 article_id 참조 주장 → 폐기 + 집계 (지표 M1)
        ▼
  [파생 집계 (코드, LLM 아님)]
   공통 사실 = claim_type=fact AND 참조 블록 ≥ 2
   단독 보도 = claim_type=fact AND 참조 블록 = 1
   서술 차이 = claim_type=characterization, 블록별 묶음
        ▼
  [렌더링]  Jinja2 → Markdown + 정적 HTML
        ▼
  [평가 하네스]  M1~M4
```

**이 설계의 중심 두 가지:**

1. **"공통 사실"은 LLM 출력 필드가 아니라 계산 결과다.** LLM 은 "이 주장은 이 기사들에 나온다"만 말하고, 무엇이 공통 사실인지는 `derive.py` 가 집합 연산으로 정한다. 그래서 '공통'의 정의가 재현 가능하고 반증 가능하다. 이전 프로젝트(`Neutralize4KRJP`)에서 LLM 이 `shared_facts` 를 직접 채웠던 것이 "중립성을 측정하지 않았다"의 근원이었다.
2. **보도 공백은 LLM 호출 0회로 나온다.** 가장 가치 있고 가장 독창적인 기능이 가장 싸다. 그래서 Phase 1 이 이것만으로 끝난다.

---

## 4. 이미 구현된 것 / 비어 있는 것

**구현됨** — `pytest -q` → 126 passed. 외부 호출은 전부 주입된 가짜와 동결 fixture 로 대체되므로 테스트가 네트워크도 돈도 쓰지 않습니다.

| 파일 | 내용 |
|---|---|
| `src/blindspot/models.py` | 전체 스키마. 원칙을 타입과 validator 로 강제 |
| `src/blindspot/ingest/rss.py` | 범용 RSS/Atom 어댑터. ★ 리드를 600자로 잘라 P9 를 집행 |
| `src/blindspot/dedupe.py` | ★ 통신사 전재 축약 (ADR 0004) |
| `src/blindspot/cluster.py` | 평균 연결 클러스터링. 임베딩 주입. baseline 유입 시 예외 (P6) |
| `src/blindspot/gap.py` | ★ 비대칭 공백 판정 (ADR 0002) |
| `src/blindspot/aliases.py` + `aliases.yaml` | 개체 별칭 사전 112개. 문자 체계별 매칭 (ADR 0003) |
| `src/blindspot/provenance.py` | P2 집행 validator + M1 |
| `src/blindspot/derive.py` | 공통 사실·단독 보도·서술 차이 집합 연산 + M2 |
| `src/blindspot/render.py` | Markdown 브리핑 |
| `src/blindspot/sources.py` | `sources.yaml` 로더 + Phase 0 DoD 자동 점검 |
| `spikes/probe_sources.py` | ★ 피드 조사. 정책 차단과 사이트 장애를 구분 보고 |
| `scripts/build_aliases_from_wikidata.py` | 별칭 사전 생성기 (네트워크 필요, 미실행) |
| `scripts/demo_briefing.py` + `eval/demo_world.py` | 합성 데이터 종단 데모 |
| `eval/gap_calibration.py` | 임계값 보정 하네스 |

**비어 있음:** 실제 임베딩 모델 결합(`cluster.Embedder` 주입만 하면 됨), `analyze.py`(LLM 주장 추출), 발행 자동화, M3, 소스별 health check.

**실측값 없음:** `config.yaml` 의 모든 임계값(클러스터링·공백 판정·전재 축약), `sources.yaml`(템플릿만), `docs/source-audit.md`(틀만).

### 설계 결정 기록

- `docs/decisions/0001` — Phase 0 소스 선정 (진행 중, **사용자 판단 필요한 질문 4개**)
- `docs/decisions/0002` — ★ 공백 판정을 비대칭 검색으로
- `docs/decisions/0003` — 별칭 사전은 시드 + Wikidata 생성본
- `docs/decisions/0004` — ★ 통신사 전재는 블록 집계 전에 축약

### 핵심 스키마 (`models.py` 참조)

```python
class Article(BaseModel):
    id, source_id, url, title_orig, lead_orig, lang, published_at, fetched_at
    # body / full_text / content 필드는 의도적으로 없음 (P9). 추가하지 말 것.

class Cluster(BaseModel):
    blocs                # 판정용. 전재 축약 후, origin 귀속 (ADR 0004)
    blocs_with_pickups   # 표시용. 전재 포함
    wire_groups          # 독립적인 편집 판단의 수
    spread_score         # P8: 블록 수 기반

class BaselineProbe(BaseModel):
    decision: Literal["covered", "not_covered", "uncertain"]   # ★ 3분기
    best_score, matched_article_ids, signals

class Claim(BaseModel):
    text_en
    claim_type: Literal["fact", "attributed_position", "characterization"]
    article_ids: list[str] = Field(min_length=1)   # P2
    quoted_terms: list[QuotedTerm]                 # P3

class ClusterAnalysis(BaseModel):
    cluster_id, claims
    # P1: 종합 의견 필드 없음. 공통 사실은 derive.py 가 계산한다.
```

## 5. 단계 계획

| Phase | 내용 | LLM 호출 | 완료 조건 |
|---|---|---|---|
| **0** | **소스 접근성 검증** | 0 | `sources.yaml` 확정 + `docs/source-audit.md` 실측 |
| 1 | ingest → 임베딩 → 클러스터링 → 비대칭 공백 판정 → 리포트 | **0** | **골격 완료.** 남은 것은 실제 피드·임베딩 결합 |
| 1.5 | **공백 판정 보정** | 0 | 50건 손 라벨 → 정밀도·재현율 숫자 확보 |
| 2 | 주장 추출 + validator + 파생 집계 + 서술 차이 대조표 | 클러스터당 1 | 상위 5 클러스터 대조표 생성 |
| 3 | 평가 하네스 완성 (M3) + 동결 fixture 결정론적 테스트 | 평가용 | README 에 숫자를 쓸 수 있다 |
| 4 | 발행 자동화 (GH Actions 일일 cron + 정적 사이트 + 소스 health check) | — | 매일 자동 갱신 |

**Phase 1 이 LLM 0회**인 것이 이 계획의 핵심입니다. 가장 독창적인 기능을 비용 0·환각 위험 0으로 먼저 완성해서, 1단계만 끝나도 프로젝트가 쓸모 있는 상태가 되게 합니다.

**Phase 1.5 를 건너뛰지 마십시오.** 보정 전의 공백 건수는 측정되지 않은 수치이고, 그것을 발행하면 이 프로젝트의 존재 이유(P10)가 무너집니다.

### 평가 지표

- **M1 `unsupported_claim_rate`** — validator 가 폐기한 주장 비율. 표본에 대해 entailment 판정(리드가 주장을 실제로 함의하는가)을 추가.
- **M2 `anglo_amplification`** — (주장이 인용한 기사 중 앵글로권 비율) − (클러스터 입력 중 앵글로권 비율). 양수면 영미권 과대 인용. 영어권 웹으로 학습된 모델을 쓰는 데서 오는 편향을 숫자로 감시한다.
- **M3 `reproducibility`** — 동일 입력 3회 실행 후 fact 주장 집합의 Jaccard.
- **M4 공백 정밀도·재현율** — 손 라벨 대조. **정밀도 우선.** 거짓 공백은 "한국 언론이 안 다뤘다"는 틀린 주장이고 제품 신뢰를 직접 깎지만, 놓친 공백은 조용한 실패다.

M1·M2·M4 는 로직이 구현돼 있고 실측만 남았습니다.

---

## 6. 기술 스택

- **Python 3.12**, **uv** 권장
- **httpx** + **feedparser** (수집), **Pydantic v2** (스키마·구조화 출력), **PyYAML**
- **임베딩: 로컬 다국어 모델.** 비용 0이고, **언어를 넘어 바로 묶이므로 클러스터링 전 번역이 불필요**하다. 품질이 부족하면 상용 임베딩으로 교체 — `gap.EmbedSim` 타입 뒤에 숨겨져 있어 주입만 바꾸면 된다.
- **클러스터링**: 당일 윈도우 + 코사인 agglomerative (임계값 `config.yaml`). 통신사 전재 중복 제거를 별도 단계로 둘 것 — 여러 매체가 같은 로이터 기사를 실으면 `spread_score` 가 오염된다.
- **저장소**: SQLite 1개 파일. 커밋하지 않는다.
- **LLM**: `LLMClient` 프로토콜 뒤에 어댑터 1개. 구조화 출력 지원 공급자를 쓴다.
- **테스트**: pytest. 외부 네트워크·LLM 은 전부 주입된 가짜와 동결 fixture. **테스트가 돈을 쓰거나 네트워크를 타면 안 된다.**

---

## 7. ★ 이번 세션의 작업: Phase 0

**왜 이걸 먼저 하는가:** 후보 소스 중 상당수는 (a) RSS 를 폐지했거나 (b) 리드 없이 제목만 주거나 (c) 봇을 차단하거나 (d) 약관이 자동 수집을 금지한다. 이게 확정되기 전의 모든 설계는 추측이다.

### ⚠ 먼저 확인: 네트워크

이 스캐폴드는 외부 호스트가 전부 차단된 환경에서 작성되었습니다. **후보 30개 중 단 한 건도 실측되지 않았습니다.** 당신의 환경에서도 막혀 있을 수 있습니다.

```bash
python spikes/probe_sources.py --only bbc_world,dw_en,yonhap
```

`blocked_or_unresolved` 가 나오면:
- **정책 차단이므로 재시도하거나 우회하지 마십시오.** 스크립트가 차단된 호스트명을 출력합니다.
- 사용자에게 해당 호스트를 환경의 허용 도메인에 추가해야 한다고 알리십시오.
- 그동안 네트워크가 필요 없는 작업(§7 산출물 4의 ADR 질문 정리, 별칭 사전 초안)을 진행하십시오.
- **조사 결과를 추측으로 채우지 마십시오.** 측정 못 한 칸은 "미확인"입니다 (P10).

### 산출물

**(1) 실측 데이터** — `spikes/probe_sources.py` 를 전체 후보(`spikes/candidates.tsv`, 30건)에 대해 실행. 일일 생산량 추정을 위해 **6시간 이상 간격으로 2회** 실행. 결과는 `spikes/out/*.json` 에 누적된다.

끊긴 피드는 각 매체의 RSS 안내 페이지에서 현행 주소를 찾아 교체하고, 못 찾으면 탈락시키고 사유를 적는다. 블록 균형을 위해 **latam·africa 소스를 새로 찾는 것은 권장된다** — 현재 후보에 비어 있고, "세계가 어떻게 돌아가는지"의 공백은 오히려 그쪽일 가능성이 크다.

**(2) `docs/source-audit.md`** — 틀이 이미 있다. 실측값으로 채운다. 요구사항:
- 후보 **전부**를 채택/탈락 사유와 함께 기록한다. **탈락 기록이 이 문서의 주된 가치다.**
- 이용약관은 각 매체의 Terms/법적고지를 **직접 읽고** 적는다. 스크립트가 채우지 않는다. 못 읽었으면 "미확인".
- 블록 균형 집계와 앵글로권 비중을 적는다 (`SourceRegistry.phase0_report()` 가 계산해 준다). 절반을 넘으면 그 사실을 명시하고 P8 과 연결해 적는다.
- 리드 제공률 0.8 미만, 제목반복률 0.5 이상인 피드는 프레이밍 비교에 쓸 수 없다. 탈락 또는 보완 경로 검토.

**(3) `sources.yaml`** — `sources.example.yaml` 을 본뜨되 실측값으로. `SourceProfile` 로 파싱되어야 한다.
- `political_lean` 은 P5 를 지킨다. 외부 근거를 `lean_basis` 에 인용하고, 못 찾으면 `unclassified`. **모델의 인상으로 좌/우를 매기지 말 것.**
- `feed` 의 `lead_coverage` / `lead_median_chars` / `items_per_day` / `robots_allowed` 는 **실측값만.** 미측정은 `null`.
- 목표: **해외 소스 8~14개, 블록 4개 이상, baseline 2개 이상.** 20개를 채우려 무리하지 말 것. 리드를 제대로 주는 소스 10개가 제목만 주는 소스 20개보다 낫다.
- `SourceRegistry.phase0_report()` 가 통과하는지 확인하고 출력을 audit 문서에 붙인다.

**(4) `docs/decisions/0001-phase0-source-selection.md` 갱신** — 틀과 미해결 질문 4개가 이미 있다. 조사 결과로 「결과」 절을 채우고, 질문에 대한 조사 사실을 덧붙여 **사용자에게 판단을 요청한다.** 혼자 원칙을 바꾸지 말 것.

### 비 RSS 경로 2개도 함께 조사

- **Guardian Open Platform** (`content.guardianapis.com`) — 무료 키로 본문까지 제공되는지. 사실이면 P9 과 긴장이 생긴다. 기본 방침은 *제공되더라도 저장하지 않고 리드 길이로 잘라 쓴다* 이지만, ADR 0001 의 미해결 질문 1번이므로 사용자 판단을 받을 것.
- **GDELT 2.0 DOC API** (`api.gdeltproject.org`) — 개별 피드 없이 블록별 커버리지 집계를 얻을 수 있는지. 필드·갱신 지연·쿼리 제한 확인. 리드를 못 얻으면 프레이밍 대조표는 만들 수 없으므로 "보완"인지 "대체"인지 구분해 적을 것.

### 완료 조건

- [ ] 전체 후보에 대해 프로브 2회 실행, 결과 JSON 누적
- [ ] `docs/source-audit.md` 에 후보 전부가 채택/탈락 사유와 함께 기록
- [ ] 모든 소스의 `tos_note` 가 직접 확인 결과이거나 "미확인"
- [ ] `sources.yaml` 이 `phase0_report()["passed"] == True`
- [ ] 비 RSS 경로 2개 조사 결과가 ADR 0001 에 반영
- [ ] 사용자에게 올릴 질문이 정리됨
- [ ] `pytest -q` 가 계속 통과 (126건, 새 소스 추가로 깨지면 안 된다)
- [ ] `python scripts/demo_briefing.py` 가 계속 돌아간다
- [ ] README 의 「현재 상태」가 갱신됨. 성능·중립성을 선전하지 않는다 (P10)

### 이번 세션에서 하지 말 것

- 수집 어댑터·클러스터링·LLM·렌더링 코드 (Phase 1+)
- Selenium / Playwright / 헤드리스 브라우저 (P9)
- 기사 본문 수집·저장 (P9)
- 유료장벽 우회, robots.txt 무시, User-Agent 위장
- 조사 못 한 값을 그럴듯하게 채우기 (P10)
- `config.yaml` 의 임계값 조정 — 보정은 Phase 1.5 에서 라벨을 받고 한다
- 헌장 원칙을 혼자 수정하기 (ADR 에 올려 질문할 것)
- PR 생성 (사용자가 명시적으로 요청할 때만)

---

## 8. 법적·윤리 규칙 (전 단계 공통)

- 저장: 제목 + 리드 + URL + 시각 + 언어. **본문은 저장하지 않는다.**
- 발행물: 기사당 인용은 짧게(25단어 이내 목표), **원문 링크 필수**, **"AI 가 생성한 분석" 표시 필수**.
- 조사·테스트 fixture 는 소량 표본이며 출처와 수집일을 명기하고 재배포하지 않는다.
- 소스 라벨은 사실 기술이어야 한다. `state_controlled` 등에는 외부 근거를 붙인다.
- 공개 서비스 운영 전에는 오보·명예훼손 책임을 검토한다. 당장은 개인용·포트폴리오용.

## 9. 작성자 / 저장소 규약

- 작성자: 백지헌 (Jiheon Baek), GitHub [@fairyofdata](https://github.com/fairyofdata)
- 라이선스: MIT (수집 데이터는 라이선스 범위 밖임을 명기)
- README 는 한국어판을 원본으로 하고 영·일을 번역으로 둔다 (기존 저장소 관행)
- 커밋은 작은 단위로, 무엇을 왜 바꿨는지 쓴다

---

**시작하십시오.** 먼저 `pytest -q` 와 `python scripts/demo_briefing.py` 로 스캐폴드가 온전한지 확인하십시오. 그다음 §7 의 네트워크 점검을 하십시오. 막혀 있으면 사용자에게 호스트 목록을 전달한 뒤, 네트워크가 필요 없는 산출물부터 만드십시오.

Phase 0 이 끝나면 다음 작업은 둘입니다. (a) 실제 임베딩 모델을 `cluster.Embedder` 로 주입하고 `config.yaml` 의 `cosine_threshold` 를 맞추는 것, (b) `scripts/build_aliases_from_wikidata.py` 를 실행해 별칭 사전을 보강하는 것. 둘 다 소스 확정 뒤에 하십시오.
