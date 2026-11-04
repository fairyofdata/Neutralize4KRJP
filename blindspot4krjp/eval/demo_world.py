"""합성 세계 — 파이프라인 전체를 네트워크·LLM 없이 돌리기 위한 가공 데이터.

등장하는 사건·수치·인용은 **전부 창작물**이다. 실제 기사가 아니다.
목적은 두 가지다.
  1. 수집 이후 전 단계(클러스터링 → 전재 축약 → 비대칭 공백 판정 →
     주장 검증 → 파생 집계 → 렌더링)가 연결되어 돌아가는지 확인한다.
  2. ADR 0002(불확실 구간 제외)와 ADR 0004(전재 축약)가 산출물에서
     실제로 어떻게 보이는지 눈으로 확인한다.

클러스터 5개를 의도적으로 서로 다른 경우로 구성했다.
  A 프랑스 연금 시위    — 4블록 독립 · 한국 보도 · 일본 보도    → 공백 아님
  B 사헬 선거 분쟁      — 3블록 독립 · 한국 미보도 · 일본 미보도 → ★ 1차 공백
  C 메콩강 댐 (전재)    — 3블록에 실렸지만 통신사 1건           → 기준 미달 (ADR 0004)
  D 파나마 운하 협상    — 3블록 독립 · 한국 애매 · 일본 보도     → 판정 불가 (ADR 0002)
  E 인도-파키스탄 국경  — 3블록 독립 · 안쪽 1건                 → 과소 보도
  F 일본 방위비 증액    — 3블록 독립 · 안쪽 3건                 → ★ 외부에서 본 안쪽 이슈
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from blindspot.models import Article, Claim, ClusterAnalysis, QuotedTerm, SourceProfile

DAY = date(2026, 11, 3)
T0 = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)


def _src(sid, name, country, bloc, lang, role="source", **kw) -> SourceProfile:
    base = dict(
        id=sid, name=name, country=country, bloc=bloc, language=lang,
        ownership="private", editorial_independence="independent",
        political_lean="unclassified", lean_basis="", role=role,
        feed={"kind": "rss", "url": f"https://{sid}.test/feed.xml"},
        tos_note="합성 데이터 (가공)",
    )
    base.update(kw)
    return SourceProfile(**base)


def sources() -> dict[str, SourceProfile]:
    profiles = [
        _src("wapo", "Washington Post", "US", "anglo", "en"),
        _src("guardian", "The Guardian", "GB", "anglo", "en", ownership="nonprofit"),
        _src("lemonde", "Le Monde", "FR", "eu", "fr"),
        _src("dw", "Deutsche Welle", "DE", "eu", "en", ownership="public_broadcaster"),
        _src("thehindu", "The Hindu", "IN", "southasia", "en"),
        _src("globaltimes", "Global Times", "CN", "sinosphere", "en",
             ownership="party_organ", editorial_independence="state_controlled",
             political_lean="state_line",
             lean_basis="RSF Press Freedom Index (합성 데이터용 예시)"),
        _src("tass", "TASS", "RU", "russia", "en",
             ownership="state_owned", editorial_independence="state_controlled",
             political_lean="state_line",
             lean_basis="RSF Press Freedom Index (합성 데이터용 예시)"),
        # baseline = 내가 실제로 접하는 언론. 한국과 일본을 하나의 환경으로 본다.
        _src("yonhap", "연합뉴스", "KR", "other", "ko", role="baseline"),
        _src("asahi", "朝日新聞", "JP", "other", "ja", role="baseline"),
        _src("japantimes", "The Japan Times", "JP", "other", "en", role="baseline"),
    ]
    return {p.id: p for p in profiles}


def _a(aid, source_id, title, lead, lang, hours) -> Article:
    return Article(
        id=aid, source_id=source_id, url=f"https://{source_id}.test/{aid}",
        title_orig=title, lead_orig=lead, lang=lang,
        published_at=T0 + timedelta(hours=hours), fetched_at=T0 + timedelta(hours=12),
    )


# ── C 클러스터용 통신사 리드. 세 매체가 그대로 싣는다.
WIRE_MEKONG = (
    "Construction on a 1,200 megawatt dam on the lower Mekong will begin in March, "
    "the project consortium said on Tuesday, drawing objections from two downstream states."
)


def overseas_articles() -> list[Article]:
    return [
        # A — 프랑스 연금 시위. 4블록 독립 보도.
        _a("a1", "wapo",
           "France pension protests met with police crackdown",
           "Police in Paris dispersed some 4,500 demonstrators on Tuesday as anger over "
           "Macron's pension overhaul spilled into a third week.", "en", 0),
        _a("a2", "lemonde",
           "Manifestations contre la reforme des retraites a Paris",
           "Quelque 4 500 manifestants se sont rassembles mardi a Paris contre la reforme "
           "des retraites portee par Macron.", "fr", 1),
        _a("a3", "globaltimes",
           "French authorities handle pension unrest according to law",
           "Local authorities in France said 4,500 participants were managed lawfully as "
           "Macron's pension plan advanced.", "en", 2),
        _a("a4", "tass",
           "Order restored in Paris after pension demonstrations",
           "Officials in France reported 4,500 participants in what they described as a "
           "special policing operation around the Macron pension bill.", "en", 3),

        # B — 사헬 선거 분쟁. 3블록 독립 보도. 한국 보도 없음 → 공백.
        _a("b1", "lemonde",
           "Scrutin contesté au Sahel: la commission reporte les résultats",
           "La commission électorale a repoussé de 72 heures l'annonce des résultats au "
           "Sahel, invoquant 31 bureaux de vote non comptabilisés.", "fr", 1),
        _a("b2", "thehindu",
           "Sahel poll results delayed as observers raise concerns",
           "The electoral commission postponed results by 72 hours, citing 31 uncounted "
           "polling stations across the Sahel region.", "en", 2),
        _a("b3", "guardian",
           "Opposition rejects delay to Sahel election count",
           "A 72-hour postponement affecting 31 polling stations has been rejected by "
           "opposition parties in the Sahel.", "en", 4),

        # C — 메콩강 댐. 통신사 전재가 3블록에 실린다 → 블록 집계는 1.
        _a("c1", "guardian", "Mekong dam construction to start in March", WIRE_MEKONG, "en", 0),
        _a("c2", "thehindu", "Consortium confirms Mekong dam timetable", WIRE_MEKONG, "en", 2),
        _a("c3", "dw", "Mekong dam work set for March start", WIRE_MEKONG, "en", 3),

        # D — 파나마 운하 협상. 3블록 독립 보도. 한국 매칭 애매 → 제외.
        _a("d1", "wapo",
           "US and Panama open talks on canal transit fees",
           "Negotiators met in Panama City on Tuesday over a proposed 18 percent increase "
           "in Panama Canal transit fees.", "en", 0),
        _a("d2", "dw",
           "Panama Canal fee talks begin amid shipping concerns",
           "Shipping groups warned that an 18 percent rise in Panama Canal fees would "
           "reshape routing decisions across two oceans.", "en", 2),
        _a("d3", "globaltimes",
           "Panama Canal fee negotiations proceed in orderly fashion",
           "Talks on an 18 percent Panama Canal fee adjustment are proceeding, with "
           "officials describing the process as orderly.", "en", 3),

        # E — 인도·파키스탄 국경 교전. 3블록 독립 보도.
        #     한국은 보도, 일본은 미보도 → 1차 공백은 아니지만 한·일 엇갈림.
        _a("e1", "wapo",
           "Border exchange of fire reported along Kashmir line",
           "Both armies confirmed a border exchange of fire near the Kashmir line of "
           "control, with 7 posts affected, officials said.", "en", 1),
        _a("e2", "lemonde",
           "Échanges de tirs signalés à la frontière au Cachemire",
           "Les deux armées ont confirmé des échanges de tirs à la frontière du "
           "Cachemire, 7 postes étant touchés.", "fr", 2),
        _a("e3", "thehindu",
           "Border firing along LoC leaves posts damaged",
           "Seven posts were damaged in a border exchange of fire along the Line of "
           "Control in Kashmir, army sources said.", "en", 3),

        # F — 일본 방위비. 안쪽에서도 충분히 보도됐지만, 바깥 언론이 어떤
        #     틀로 쓰는지가 관심사다 → '외부에서 본 안쪽 이슈' 섹션.
        _a("f1", "wapo",
           "Japan moves to raise defence spending toward 2 percent",
           "Japan will push defence spending toward 2 percent of GDP over 5 years, "
           "officials said, in what Washington called a historic shift.", "en", 1),
        _a("f2", "globaltimes",
           "Japan accelerates military expansion, raising regional concerns",
           "Japan's plan to lift military spending to 2 percent of GDP over 5 years "
           "revives concerns about remilitarization, analysts in Beijing said.", "en", 2),
        _a("f3", "thehindu",
           "Japan defence budget plan reshapes Indo-Pacific calculus",
           "Japan's move toward 2 percent of GDP in defence spending over 5 years is "
           "being read in New Delhi as a shift in the Indo-Pacific balance.", "en", 3),
    ]


def baseline_articles() -> list[Article]:
    """한국·일본 기사. 공백 계산에만 쓰이고 브리핑 본문에 인용되지 않는다 (P6).

    두 나라 모두 그날 기사를 냈다는 점이 중요하다 — 기사가 아예 없으면
    "안 다뤘다"가 아니라 "모른다"(no_data)여야 하기 때문이다 (ADR 0005).
    """
    return [
        # A — 한국·일본 모두 보도.
        _a("kr_a", "yonhap",
           "프랑스 연금개혁 반대 시위 격화…파리서 4500명 집결",
           "프랑스 파리에서 마크롱 대통령의 연금개혁에 반대하는 시위대 4500명이 "
           "모였고 경찰이 해산에 나섰다.", "ko", 5),
        _a("jp_a", "asahi",
           "フランス年金改革に反対するデモ、パリで4500人",
           "フランスのパリでマクロン大統領の年金改革に反対するデモに4500人が集まり、"
           "警察が解散させた。", "ja", 5),

        # D — 한국은 같은 운하를 다루지만 초점이 달라 애매, 일본은 명확히 보도.
        _a("kr_d", "yonhap",
           "파나마 운하 가뭄에 통항 제한 지속",
           "파나마 운하 당국이 가뭄으로 인한 일일 통항 선박 수 제한을 유지하기로 했다.", "ko", 6),
        _a("jp_d", "japantimes",
           "Panama Canal transit fee talks open",
           "Negotiators began talks on a proposed increase in パナマ運河 transit fees, "
           "with shipping groups watching closely.", "en", 6),

        # E — 한국만 보도. 일본 미보도 → 한·일 엇갈림.
        _a("kr_e", "yonhap",
           "인도-파키스탄 국경서 교전…초소 7곳 피해",
           "인도와 파키스탄 양군이 카슈미르 국경에서 교전을 확인했으며 초소 7곳이 "
           "피해를 입었다고 밝혔다.", "ko", 6),

        # F — 안쪽에서도 충분히 보도. 노출 격차는 작지만 외부 시선이 관심사다.
        _a("jp_f1", "asahi",
           "防衛費、GDP比2%へ 5年で段階的に引き上げ",
           "政府は防衛費をGDP比2%に向けて5年で段階的に引き上げる方針を固めた。", "ja", 4),
        _a("jp_f2", "japantimes",
           "Japan to lift 防衛費 toward 2% of GDP",
           "The government confirmed a 5-year path to 2 percent of GDP for defence "
           "spending, officials said.", "en", 4),
        _a("kr_f", "yonhap",
           "일본, 방위비 GDP 2%로 단계적 증액",
           "일본 정부가 5년에 걸쳐 방위비를 국내총생산 2% 수준으로 올리는 방안을 확정했다.", "ko", 4),

        # 잡음 — 두 나라 모두 그날 다른 기사를 냈다는 사실을 만든다.
        _a("kr_x", "yonhap",
           "국내 반도체 수출 3개월 연속 증가",
           "반도체 수출이 3개월 연속 증가하며 회복세를 보였다.", "ko", 7),
        _a("jp_x", "asahi",
           "国内の半導体輸出が3カ月連続で増加",
           "半導体の輸出が3カ月連続で増加し、回復の兆しを見せている。", "ja", 7),
    ]


# ── 가짜 임베딩: 주제 표식으로 벡터를 돌려준다. 모델 선택과 무관하게
#    클러스터링 로직을 검증하기 위한 것이다.
_TOPICS = {
    "pension": [1.0, 0.0, 0.0, 0.0],
    "Sahel": [0.0, 1.0, 0.0, 0.0],
    "retraites": [1.0, 0.0, 0.0, 0.0],
    "Mekong": [0.0, 0.0, 1.0, 0.0],
    "Panama": [0.0, 0.0, 0.0, 1.0],
    "scrutin": [0.0, 1.0, 0.0, 0.0],
    "poll": [0.0, 1.0, 0.0, 0.0],
    "election": [0.0, 1.0, 0.0, 0.0],
    "Border": [0.0, 0.0, 0.0, 0.0, 1.0],
    "border": [0.0, 0.0, 0.0, 0.0, 1.0],
    "Échanges": [0.0, 0.0, 0.0, 0.0, 1.0],
    "defence": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    "military expansion": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
}
_DIM = 6


def embedder(texts):
    out = []
    for text in texts:
        vec = [0.0] * _DIM
        for marker, v in _TOPICS.items():
            if marker.lower() in text.lower():
                vec = list(v) + [0.0] * (_DIM - len(v))
                break
        out.append(vec)
    return out


def baseline_sim(query: str, candidates):
    """가짜 교차언어 유사도.

    실제로는 다국어 임베딩이 계산한다. 여기서는 세 경우를 재현한다:
    명확한 매칭(A), 매칭 없음(B·C), 애매한 매칭(D).
    """
    sims = []
    q = query.lower()
    for cand in candidates:
        if "pension" in q and ("연금개혁" in cand or "年金改革" in cand):
            sims.append(0.90)                      # A: 한·일 모두 보도
        elif "panama" in q and "パナマ運河" in cand:
            sims.append(0.88)                      # D: 일본은 명확히 보도
        elif "panama" in q and "파나마" in cand:
            sims.append(0.44)                      # D: 한국은 애매 구간
        elif "border" in q and "국경" in cand:
            sims.append(0.90)                      # E: 안쪽 1건
        elif "defence" in q and ("防衛費" in cand or "방위비" in cand):
            sims.append(0.92)                      # F: 안쪽 3건
        else:
            sims.append(0.05)
    return sims


def analysis_for(cluster_id: str, article_ids: list[str]) -> ClusterAnalysis:
    """Phase 2 의 LLM 출력을 손으로 흉내낸 것.

    마지막 주장은 **클러스터에 없는 기사를 인용한다.** provenance validator 가
    이를 버리고 M1 에 집계하는지 확인하기 위해 일부러 넣었다.
    """
    if cluster_id != "A":
        return ClusterAnalysis(cluster_id=cluster_id, claims=[])
    a1, a2, a3, a4 = article_ids[:4]
    return ClusterAnalysis(
        cluster_id=cluster_id,
        claims=[
            Claim(text_en="About 4,500 people took part in the Paris demonstration on Tuesday.",
                  claim_type="fact", article_ids=[a1, a2, a3, a4]),
            Claim(text_en="The protest concerned a pension overhaul.",
                  claim_type="fact", article_ids=[a1, a2]),
            Claim(text_en="Police dispersed the crowd.",
                  claim_type="fact", article_ids=[a1]),
            Claim(text_en="The police action is described as a crackdown.",
                  claim_type="characterization", article_ids=[a1],
                  quoted_terms=[QuotedTerm(term_orig="crackdown", lang="en",
                                           gloss_en="crackdown", article_id=a1)]),
            Claim(text_en="The police action is described as lawful handling.",
                  claim_type="characterization", article_ids=[a3],
                  quoted_terms=[QuotedTerm(term_orig="handled according to law", lang="en",
                                           gloss_en="handled according to law", article_id=a3)]),
            Claim(text_en="The police action is described as a special policing operation.",
                  claim_type="characterization", article_ids=[a4],
                  quoted_terms=[QuotedTerm(term_orig="special policing operation", lang="en",
                                           gloss_en="special policing operation", article_id=a4)]),
            Claim(text_en="Chinese officials said France mishandled the protests.",
                  claim_type="attributed_position", article_ids=[a3]),
            # ↓ 환각: 이 클러스터에 없는 기사를 인용한다. validator 가 버린다.
            Claim(text_en="A government minister resigned over the protests.",
                  claim_type="fact", article_ids=["ghost_article"]),
        ],
    )
