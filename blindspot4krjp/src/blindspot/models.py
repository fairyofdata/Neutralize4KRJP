"""도메인 스키마.

설계 원칙과의 대응 (헌장 §2):
  P1  ClusterAnalysis 에 conclusion / verdict / neutral_summary 필드가 **없다**.
      금지를 프롬프트에 적는 대신 타입에서 표현 불가능하게 만든다.
      tests/test_p1_no_conclusion_fields.py 가 소스를 스캔해 이를 기계적으로 검사한다.
  P2  Claim.article_ids 는 min_length=1. 출처 없는 주장은 생성 자체가 불가능하다.
  P3  QuotedTerm 이 원어 표현을 보존한다. 프레이밍은 번역으로 대체되지 않는다.
  P4  SourceProfile 이 소유구조·편집권 독립성을 명시한다.
  P5  political_lean 에는 외부 근거(lean_basis)가 필요하다 — model_validator 가 강제.
  P6  SourceProfile.role 이 source(해외) 와 baseline(KR/JP) 를 분리한다.
  P7  Cluster.spread_score 는 기사 수가 아니라 블록 수에서 파생된다.
  P8  Article 에 본문 필드가 없다. 추가하지 말 것.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

Bloc = Literal[
    "anglo", "eu", "sinosphere", "russia", "sea",
    "southasia", "mena", "latam", "africa", "other",
]

Lean = Literal[
    "left", "center_left", "center", "center_right", "right",
    "state_line", "unclassified",
]


class FeedConfig(BaseModel):
    """소스를 어떻게 읽는지. Phase 0 의 조사 결과가 여기로 들어온다."""

    kind: Literal["rss", "atom", "json_api"] = "rss"
    url: str
    # Phase 0 에서 실측한 값. 추측으로 채우지 않는다 (P9).
    lead_coverage: float | None = Field(
        default=None, description="리드(description)를 가진 item 비율 0..1. 미측정이면 None"
    )
    lead_median_chars: int | None = Field(default=None, description="리드 중위 길이")
    items_per_day: float | None = Field(default=None, description="추정 일일 생산량")
    robots_allowed: bool | None = Field(default=None, description="robots.txt 가 이 경로를 허용하는지")
    requires_key: bool = False


class SourceProfile(BaseModel):
    """P4·P5·P6 의 구현체. 소스 메타데이터는 숨기지 않고 출력에 함께 표시된다."""

    id: str
    name: str
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")
    bloc: Bloc
    language: str = Field(min_length=2, max_length=2, description="ISO 639-1")
    ownership: Literal["private", "public_broadcaster", "state_owned", "party_organ", "nonprofit"]
    editorial_independence: Literal["independent", "partly_constrained", "state_controlled"]
    political_lean: Lean
    lean_basis: str = Field(
        default="",
        description="P5: political_lean 의 외부 근거. 비우면 lean 은 unclassified 여야 한다.",
    )
    role: Literal["source", "baseline"]
    feed: FeedConfig
    tos_note: str = Field(default="미확인", description="이용약관/법적고지 확인 결과")

    @model_validator(mode="after")
    def _p5_lean_needs_basis(self) -> SourceProfile:
        """P5: 모델의 인상으로 좌/우를 매기지 못하게 한다."""
        if self.political_lean != "unclassified" and not self.lean_basis.strip():
            raise ValueError(
                f"{self.id}: political_lean={self.political_lean!r} 에는 lean_basis 근거가 필요하다 "
                f"(P5). 근거를 못 찾았으면 political_lean 을 'unclassified' 로 두라."
            )
        return self

    @model_validator(mode="after")
    def _state_control_needs_basis(self) -> SourceProfile:
        """'state_controlled' 같은 라벨도 사실 기술이어야 한다 (§8)."""
        if self.editorial_independence != "independent" and not self.lean_basis.strip():
            raise ValueError(
                f"{self.id}: editorial_independence={self.editorial_independence!r} 는 "
                f"외부 근거를 lean_basis 에 적어야 한다 (§8)."
            )
        return self


class Article(BaseModel):
    """P8 의 구현체.

    body / full_text / content 필드가 없는 것이 설계다. 추가하지 말 것.
    저장하는 것은 피드가 준 제목·리드까지이며, 그 이상은 수집하지 않는다.
    """

    id: str
    source_id: str
    url: HttpUrl
    title_orig: str
    lead_orig: str | None = None
    lang: str
    published_at: datetime
    fetched_at: datetime

    def match_text(self) -> str:
        """클러스터링·검색에 쓰는 텍스트. 제목 + 리드까지."""
        return self.title_orig if not self.lead_orig else f"{self.title_orig}\n{self.lead_orig}"


class Cluster(BaseModel):
    """해외 소스(role=source)만으로 구성된다. baseline 기사는 들어오지 않는다 (P6)."""

    id: str
    day: date
    article_ids: list[str] = Field(min_length=1)
    event_label: str = Field(description="사람이 읽을 사건명. 사실 주장이 아니다.")
    countries: set[str] = Field(default_factory=set)
    blocs: set[Bloc] = Field(default_factory=set)
    spread_score: float = Field(default=0.0, description="P7: 블록 수 기반")


# ---------------------------------------------------------------- 보도 공백

class MatchSignals(BaseModel):
    """baseline 매칭의 하이브리드 신호. 임베딩만으로는 교차언어 사건 동일성이 불안정하다."""

    embedding_max: float = Field(ge=-1.0, le=1.0)
    entity_overlap: float = Field(ge=0.0, le=1.0, description="별칭 사전 경유 개체 Jaccard")
    numeric_overlap: float = Field(ge=0.0, le=1.0, description="숫자·연도 일치. 언어 독립 신호")
    time_delta_hours: float


class BaselineProbe(BaseModel):
    """한 클러스터에 대한 baseline(KR 또는 JP) 보도 여부 판정.

    ★ 3분기 판정이다. 'uncertain' 이 존재하는 것이 핵심이다.
    교차언어 매칭이 실패하면 거짓 공백이 계통적으로 과다 생성되므로,
    애매한 구간은 공백으로 집계하지 않고 따로 센다.
    """

    cluster_id: str
    baseline_country: str
    decision: Literal["covered", "not_covered", "uncertain"]
    best_score: float
    matched_article_ids: list[str] = Field(default_factory=list)
    signals: MatchSignals | None = None


class BlindspotVerdict(BaseModel):
    cluster_id: str
    event_label: str
    blocs: set[Bloc]
    spread_score: float
    probes: dict[str, BaselineProbe] = Field(default_factory=dict)
    is_blindspot: bool
    note: str = ""


# ---------------------------------------------------------------- 주장

class QuotedTerm(BaseModel):
    """P3: 원어 보존. 같은 대상에 각국이 붙인 단어가 분석 대상이다."""

    term_orig: str
    lang: str
    gloss_en: str
    article_id: str


class Claim(BaseModel):
    """P2: article_ids 를 비울 수 없다."""

    text_en: str
    claim_type: Literal[
        "fact",                 # 검증 가능한 사실 서술
        "attributed_position",  # "X 정부는 ~라고 주장" — 귀속된 입장
        "characterization",     # 평가적 어휘 선택 ← 프레이밍 데이터
    ]
    article_ids: list[str] = Field(min_length=1)
    quoted_terms: list[QuotedTerm] = Field(default_factory=list)


class ClusterAnalysis(BaseModel):
    """P1: 종합 의견 필드가 없다.

    공통 사실 / 단독 보도 / 서술 차이는 이 모델의 필드가 아니라
    derive.py 가 claims 에서 집합 연산으로 **계산**한다.
    그래서 '공통'의 정의가 재현 가능하고 반증 가능하다.
    """

    cluster_id: str
    claims: list[Claim] = Field(default_factory=list)


class ProvenanceReport(BaseModel):
    """P2 의 측정값. 지표 M1 의 산출물."""

    total_claims: int
    dropped_claims: int
    repaired_claims: int
    total_quoted_terms: int
    dropped_quoted_terms: int
    dropped_texts: list[str] = Field(default_factory=list)

    @property
    def unsupported_claim_rate(self) -> float:
        if self.total_claims == 0:
            return 0.0
        return self.dropped_claims / self.total_claims
