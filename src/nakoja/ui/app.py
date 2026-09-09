"""Modern Streamlit UI for LLM-NAKOJA."""

import os
from pathlib import Path
import pandas as pd
import streamlit as st
from openai import OpenAI

from ..config import DEFAULT_MODEL, DATA_DIR, OUTLETS
from ..schemas import ArticleSummary, PerspectiveComparison, NeutralArticle
from ..pipeline.classifier import classify_titles
from ..pipeline.selector import select_article_pair
from ..pipeline.summarizer import summarize_to_intermediate_english
from ..pipeline.neutralizer import generate_neutral_article
from ..crawler.jungang import JungangCrawler
from ..crawler.yomiuri import YomiuriCrawler


def init_session_state():
    """Initializes default session state variables."""
    if "df_korean" not in st.session_state:
        st.session_state.df_korean = None
    if "df_japanese" not in st.session_state:
        st.session_state.df_japanese = None
    if "combined_df" not in st.session_state:
        st.session_state.combined_df = None
    if "selected_k_idx" not in st.session_state:
        st.session_state.selected_k_idx = None
    if "selected_j_idx" not in st.session_state:
        st.session_state.selected_j_idx = None
    if "k_summary" not in st.session_state:
        st.session_state.k_summary = None
    if "j_summary" not in st.session_state:
        st.session_state.j_summary = None
    if "neutral_result" not in st.session_state:
        st.session_state.neutral_result = None


def load_offline_sample_data():
    """Loads pre-collected sample data from data/ directory."""
    jungang_csv = DATA_DIR / "jungang_articles_converted.csv"
    yomiuri_csv = DATA_DIR / "yomiuri_articles_converted.csv"
    combined_csv = DATA_DIR / "combined_articles_with_labels.csv"

    if combined_csv.exists():
        df_all = pd.read_csv(combined_csv)
        st.session_state.combined_df = df_all
        st.session_state.df_korean = df_all[df_all["country"] == "Korea"].reset_index(drop=True)
        st.session_state.df_japanese = df_all[df_all["country"] == "Japan"].reset_index(drop=True)
        return True
    elif jungang_csv.exists() and yomiuri_csv.exists():
        df_k = pd.read_csv(jungang_csv)
        df_j = pd.read_csv(yomiuri_csv)
        df_k["country"] = "Korea"
        df_j["country"] = "Japan"
        df_k["outlet"] = "JoongAng Ilbo"
        df_j["outlet"] = "Yomiuri Shimbun"
        st.session_state.df_korean = df_k
        st.session_state.df_japanese = df_j
        st.session_state.combined_df = pd.concat([df_k, df_j], ignore_index=True)
        return True
    return False


def run_app():
    st.set_page_config(
        page_title="LLM-NAKOJA | 한일관계 중립기사 생성기",
        page_icon="⚖️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    # --- Sidebar Configuration ---
    with st.sidebar:
        st.image("https://img.shields.io/badge/LLM--NAKOJA-v0.2.0-blue?style=for-the-badge", use_container_width=True)
        st.title("⚙️ 설정 (Settings)")

        # API Key input
        api_key = os.getenv("OPENAI_API_KEY", "")
        user_api_key = st.text_input(
            "OpenAI API Key:",
            value=api_key,
            type="password",
            help="OpenAI API 키를 입력하세요. (.env에 설정된 경우 자동 로드됩니다)",
        )

        selected_model = st.selectbox(
            "LLM Model:",
            ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
            index=0,
            help="기본으로 가성비와 추론 능력이 뛰어난 gpt-4o-mini를 권장합니다.",
        )

        st.divider()
        st.markdown("### 📜 프로젝트 철학")
        st.caption(
            "**瓊瑤世界 (경요세계)**\n'두 옥구슬이 서로를 비추다'\n— 1643년 천문학자 박안기"
        )
        st.caption(
            "**誠信交隣 (성신교린)**\n'성실과 진심으로써 교류하다'\n— 1728년 아메노모리 호슈"
        )
        st.divider()
        st.markdown(
            "[GitHub Repository](https://github.com/fairyofdata/LLM_NAKOJA)  \n"
            "Developed by **Jiheon Baek**"
        )

    client = OpenAI(api_key=user_api_key) if user_api_key else None

    # --- Header Banner ---
    st.markdown(
        """
        <div style="padding: 1.5rem 1rem; border-radius: 10px; background: linear-gradient(135deg, #1e293b, #0f172a); color: white; margin-bottom: 2rem;">
            <h1 style="margin: 0; font-size: 2.2rem; font-weight: 700;">🌏 LLM-NAKOJA : 한일관계 중립기사 자동생성기</h1>
            <p style="margin: 0.5rem 0 0 0; color: #94a3b8; font-size: 1.05rem;">
                양국 언론(중앙일보 & 요미우리)의 보도를 수집·분석하고, <b>중간 언어(English)</b>를 매개로 L1 언어적 편향을 제거한 균형 잡힌 중립 기사를 합성합니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Mode Selection & Quick Demo ---
    col_demo, col_status = st.columns([2, 3])
    with col_demo:
        if st.button("📦 샘플 데이터셋 즉시 로드 (Quick Demo)", type="primary", use_container_width=True):
            if load_offline_sample_data():
                st.success(f"샘플 기사 {len(st.session_state.combined_df)}건이 로드되었습니다!")
            else:
                st.error("data/ 디렉토리에서 샘플 CSV를 찾을 수 없습니다.")

    with col_status:
        if st.session_state.combined_df is not None:
            st.info(f"📊 현재 로드된 기사: 한국 {len(st.session_state.df_korean)}건 / 일본 {len(st.session_state.df_japanese)}건")

    st.divider()

    # --- Steps as Tabs ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1️⃣ 기사 수집/로드",
        "2️⃣ 주제별 분류",
        "3️⃣ 한일 기사 페어 매칭",
        "4️⃣ 중간 영어 요약 (L1 Bias 배제)",
        "5️⃣ 중립 기사 & 관점 대조표"
    ])

    # ------------------ Tab 1: Scraping / Data Load ------------------
    with tab1:
        st.subheader("📥 1단계: 양국 언론사 기사 수집 및 확인")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🇰🇷 중앙일보 (JoongAng Ilbo)")
            kw_kr = st.text_input("수집 키워드 (한국):", value="한일", key="kw_kr")
            if st.button("중앙일보 실시간 수집 시작"):
                with st.spinner("헤드리스 브라우저로 중앙일보 기사 수집 중..."):
                    crawler = JungangCrawler(max_articles=10, headless=True)
                    articles = crawler.scrape(keyword=kw_kr)
                    if articles:
                        crawler.save_to_csv(articles)
                        st.session_state.df_korean = pd.DataFrame([a.model_dump() for a in articles])
                        st.success(f"중앙일보 {len(articles)}건 수집 완료!")
                    else:
                        st.warning("수집된 기사가 없습니다.")

        with col2:
            st.markdown("#### 🇯🇵 요미우리신문 (Yomiuri Shimbun)")
            kw_jp = st.text_input("수집 키워드 (일본):", value="日韓", key="kw_jp")
            if st.button("요미우리신문 실시간 수집 시작"):
                with st.spinner("헤드리스 브라우저로 요미우리 기사 수집 중..."):
                    crawler = YomiuriCrawler(max_articles=10, headless=True)
                    articles = crawler.scrape(keyword=kw_jp)
                    if articles:
                        crawler.save_to_csv(articles)
                        st.session_state.df_japanese = pd.DataFrame([a.model_dump() for a in articles])
                        st.success(f"요미우리신문 {len(articles)}건 수집 완료!")
                    else:
                        st.warning("수집된 기사가 없습니다.")

        if st.session_state.df_korean is not None and st.session_state.df_japanese is not None:
            if st.button("양국 데이터 병합 (Combine Dataset)"):
                st.session_state.combined_df = pd.concat(
                    [st.session_state.df_korean, st.session_state.df_japanese],
                    ignore_index=True
                )
                st.success("데이터 병합 완료!")

        if st.session_state.combined_df is not None:
            st.dataframe(
                st.session_state.combined_df[["outlet", "title", "date", "url"]],
                use_container_width=True,
            )

    # ------------------ Tab 2: Topic Classification ------------------
    with tab2:
        st.subheader("🏷️ 2단계: 기사 주제별 분류 (Topic Classification)")
        st.markdown("수집된 기사들을 **외교(Diplomacy), 경제(Economy), 안보(Security), 역사(History), 문화(Culture)** 등으로 자동 분류합니다.")

        if st.session_state.combined_df is None:
            st.warning("먼저 1단계에서 기사를 수집하거나 [샘플 데이터셋 즉시 로드]를 클릭하세요.")
        else:
            if "label" not in st.session_state.combined_df.columns:
                if st.button("🧩 GPT 토픽 분류 실행 (Structured Output)"):
                    if not client:
                        st.error("사이드바에 OpenAI API Key를 입력해주세요.")
                    else:
                        with st.spinner("기사 제목들을 분석하여 분류 중..."):
                            titles = st.session_state.combined_df["title"].tolist()
                            labels = classify_titles(titles, client, model=selected_model)
                            st.session_state.combined_df["label"] = labels
                            st.success("분류가 완료되었습니다!")
                            st.dataframe(st.session_state.combined_df[["outlet", "title", "label"]], use_container_width=True)
            else:
                st.success("이미 분류된 데이터가 준비되어 있습니다.")
                st.dataframe(st.session_state.combined_df[["outlet", "title", "label"]], use_container_width=True)

    # ------------------ Tab 3: Pair Matching ------------------
    with tab3:
        st.subheader("🔍 3단계: 동일 사안을 다룬 한일 기사 페어 매칭")
        st.markdown("동일한 카테고리 내에서 **정확히 같은 사건, 정상회담, 외교 갈등**을 다룬 한국 기사 1건과 일본 기사 1건을 선별합니다.")

        if st.session_state.combined_df is None or "label" not in st.session_state.combined_df.columns:
            st.warning("먼저 2단계에서 토픽 분류를 완료하세요.")
        else:
            categories = st.session_state.combined_df["label"].dropna().unique().tolist()
            selected_cat = st.selectbox("분석할 카테고리 선택:", categories)

            filtered_df = st.session_state.combined_df[st.session_state.combined_df["label"] == selected_cat]
            k_articles = filtered_df[filtered_df["country"] == "Korea"].reset_index(drop=True)
            j_articles = filtered_df[filtered_df["country"] == "Japan"].reset_index(drop=True)

            col_k, col_j = st.columns(2)
            with col_k:
                st.markdown(f"**🇰🇷 한국 기사 ({len(k_articles)}건)**")
                for i, r in k_articles.iterrows():
                    st.text(f"[{i+1}] {r['title']}")
            with col_j:
                st.markdown(f"**🇯🇵 일본 기사 ({len(j_articles)}건)**")
                for i, r in j_articles.iterrows():
                    st.text(f"[{i+1}] {r['title']}")

            if len(k_articles) > 0 and len(j_articles) > 0:
                if st.button("🔗 자동 최적 페어 매칭 (GPT Selector)"):
                    if not client:
                        st.error("사이드바에 OpenAI API Key를 입력해주세요.")
                    else:
                        with st.spinner("양국 기사의 맥락을 비교하여 최적의 페어를 찾는 중..."):
                            k_idx, j_idx, result_meta = select_article_pair(
                                k_articles["title"].tolist(),
                                j_articles["title"].tolist(),
                                client,
                                model=selected_model,
                            )
                            st.session_state.selected_k_idx = k_idx
                            st.session_state.selected_j_idx = j_idx
                            st.session_state.current_k_article = k_articles.iloc[k_idx]
                            st.session_state.current_j_article = j_articles.iloc[j_idx]

                            if result_meta:
                                st.success(f"🎯 매칭 성공: {result_meta.common_topic}")
                                st.info(f"**선정 사유:** {result_meta.selection_reason}")
            else:
                st.warning("해당 카테고리에 한국과 일본 기사가 모두 최소 1건 이상 존재해야 매칭이 가능합니다.")

    # ------------------ Tab 4: Intermediate Summaries ------------------
    with tab4:
        st.subheader("📝 4단계: 중간 영어 요약 (L1 Framing Bias 제거)")
        st.markdown(
            """> **💡 핵심 설계 의도 (Key Design Decision)**  
            > 한국어와 일본어에는 각국의 민족적 정서, 역사적 입장, 암묵적 뉘앙스가 깊게 각인되어 있습니다.  
            > 중립적인 제3의 언어인 **영어(English)**로 객관적 팩트와 주관적 주장을 1차 분리·요약함으로써 언어적 편향을 획기적으로 낮춥니다."""
        )

        if "current_k_article" not in st.session_state or "current_j_article" not in st.session_state:
            st.warning("먼저 3단계에서 한일 기사 페어를 매칭하세요.")
        else:
            k_art = st.session_state.current_k_article
            j_art = st.session_state.current_j_article

            col_s1, col_s2 = st.columns(2)
            with col_s1:
                st.markdown(f"**🇰🇷 [선택됨] {k_art['title']}**")
                with st.expander("한국 기사 원문 보기"):
                    st.write(k_art["content"])

            with col_s2:
                st.markdown(f"**🇯🇵 [선택됨] {j_art['title']}**")
                with st.expander("일본 기사 원문 보기"):
                    st.write(j_art["content"])

            if st.button("🌐 중간 영어 요약 생성 (Intermediate English Synthesis)"):
                if not client:
                    st.error("사이드바에 OpenAI API Key를 입력해주세요.")
                else:
                    with st.spinner("L1 편향을 배제하고 영어 요약을 생성하는 중..."):
                        st.session_state.k_summary = summarize_to_intermediate_english(
                            content=k_art["content"],
                            outlet=k_art["outlet"],
                            country="Korea",
                            client=client,
                            model=selected_model,
                        )
                        st.session_state.j_summary = summarize_to_intermediate_english(
                            content=j_art["content"],
                            outlet=j_art["outlet"],
                            country="Japan",
                            client=client,
                            model=selected_model,
                        )
                        st.success("영어 중간 요약이 생성되었습니다!")

            if st.session_state.k_summary and st.session_state.j_summary:
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.markdown("#### 🇰🇷 한국 언론 영문 중간 요약")
                    st.markdown(f"**Facts:** {', '.join(st.session_state.k_summary.key_facts)}")
                    st.info(st.session_state.k_summary.english_summary)
                with col_res2:
                    st.markdown("#### 🇯🇵 일본 언론 영문 중간 요약")
                    st.markdown(f"**Facts:** {', '.join(st.session_state.j_summary.key_facts)}")
                    st.info(st.session_state.j_summary.english_summary)

    # ------------------ Tab 5: Neutral Article Generation ------------------
    with tab5:
        st.subheader("⚖️ 5단계: 중립 기사 및 관점 대조표 (Neutral Synthesis)")
        st.markdown("경요세계(瓊瑤世界)와 성신교린(誠信交隣)의 정신을 바탕으로, 명확한 출처 표기와 균형 잡힌 기사를 한국어/일본어 양국어로 생성합니다.")

        if not st.session_state.k_summary or not st.session_state.j_summary:
            st.warning("먼저 4단계에서 중간 영어 요약을 생성하세요.")
        else:
            if st.button("🚀 최종 중립 기사 생성 (Generate Neutral Article)", type="primary"):
                if not client:
                    st.error("사이드바에 OpenAI API Key를 입력해주세요.")
                else:
                    with st.spinner("양국의 시각을 대조하고 중립 기사를 집필하는 중..."):
                        neutral_obj = generate_neutral_article(
                            korean_summary=st.session_state.k_summary,
                            japanese_summary=st.session_state.j_summary,
                            client=client,
                            model=selected_model,
                        )
                        st.session_state.neutral_result = neutral_obj
                        st.success("🎉 중립 기사 생성이 완료되었습니다!")

            if st.session_state.neutral_result:
                nr: NeutralArticle = st.session_state.neutral_result

                # 1. Perspective Matrix
                st.markdown("### 📊 보도 관점 대조표 (Perspective Contrast Matrix)")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🇰🇷 한국 언론의 강조점**")
                    for pt in nr.comparison.korean_emphasis:
                        st.markdown(f"- {pt}")
                with c2:
                    st.markdown("**🇯🇵 일본 언론의 강조점**")
                    for pt in nr.comparison.japanese_emphasis:
                        st.markdown(f"- {pt}")

                st.markdown(f"**🤝 공통 인정 사실:** {', '.join(nr.comparison.shared_facts)}")
                st.warning(f"**🔍 프레이밍 분기 분석 (Framing Divergence):** {nr.comparison.framing_divergence}")

                st.divider()

                # 2. Bilingual Neutral Articles
                st.markdown("### 📰 생성된 중립 기사 (Bilingual Output)")
                subtab_kr, subtab_jp = st.tabs(["🇰🇷 한국어 버전 (Korean)", "🇯🇵 日本語バージョン (Japanese)"])
                with subtab_kr:
                    st.markdown(f"### {nr.headline_kr}")
                    st.write(nr.content_kr)
                with subtab_jp:
                    st.markdown(f"### {nr.headline_jp}")
                    st.write(nr.content_jp)


if __name__ == "__main__":
    run_app()
