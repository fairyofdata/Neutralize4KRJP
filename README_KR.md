# LLM 기반 한일관계 중립기사 자동생성기 (LLM-NAKOJA) 📰🤝🤖

> **[경요세계(瓊瑤世界)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005) : '두 옥구슬이 서로를 비추다'**  
> ‐ 1643년 천문학자 [박안기(朴安期)](https://encykorea.aks.ac.kr/Article/E0020900)가 시즈오카현 청견사에 남긴 2층 종루 현판의 문장  
>
> **[성신교린(誠信交隣)](https://www.donga.com/news/People/article/all/20210416/106434451/1) : '성실과 진심으로써 교류하다'**  
> ‐ 1728년 [아메노모리 호슈(雨森芳洲)](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537)가 부산 초량왜관에서 집필한 「교린제성」의 문장

---

**🌐 언어별 README:**  
[🇰🇷 한국어 (Korean)](./README_KR.md) | [🇯🇵 日本語 (Japanese)](./README_JP.md) | [🌐 English](./README.md)

*2024년 10~11월 개인 프로젝트. 성신여자대학교 SW021 「ChatGPT for Business」 과정에서 배운 내용의 연장선에서 만들었습니다.*

---

## 📌 프로젝트 기획 및 문제의식

![NAKOJA 대시보드 미리보기](./NAKOJA_Preview.png)

한일 양국의 외교·역사·경제 이슈는 각국 언론의 프레이밍과 자국 중심적 시각에 의해 첨예하게 대립되어 보도되는 경우가 많습니다.

> *"언어 모델이 양국 언론의 기사를 동시에 교차 분석하고, 각자의 편향을 걷어낸 진정한 중립적 저널리즘을 구현할 수 있을까?"*

**LLM-NAKOJA**는 한국 언론(**중앙일보**)과 일본 언론(**요미우리신문**)의 동일 사안 보도를 수집·분석하여, 객관적 공통 사실(Common Facts)과 양국의 입장 차이(Divergence)를 명확히 대비하고 **한국어와 일본어 양국어로 균형 잡힌 중립 기사를 자동 합성하는 파이프라인**입니다.

---

## 🔬 핵심 아키텍처 & 기술적 의사결정 (Key Engineering Decisions)

### 1. 왜 중간 매개 언어로 영어(English)를 택했는가? (L1 Bias Removal)
한국어와 일본어 원문은 단어 선택과 어조 자체에 각국의 민족적 정서와 암묵적 프레이밍(Implicit Framing)이 깊게 배어 있습니다.
NAKOJA는 기사를 바로 합성하지 않고, **제3의 중립 언어인 영어(English)로 1차 사실(Facts)과 주장(Positions)을 분리·요약**합니다. 이 중간 단계를 거침으로써 언어적 모국어 편향(L1 bias)을 획기적으로 완화합니다.

### 2. OpenAI Pydantic Structured Outputs 기반 무결성 확보
줄글 텍스트 파싱(`split('\n')`, 정규표현식)에 의존하던 구형 구조를 탈피하고, OpenAI의 최신 `beta.chat.completions.parse`와 **Pydantic v2 스키마**를 결합했습니다.
직접 작성한 파싱 로직을 없애고, 양국 관점 대조표(Contrast Matrix)를 스키마로 타입이 보장된 정형 데이터로 추출합니다.

### 3. 클린 아키텍처 (Clean Architecture) 분리
기존 Streamlit과 강하게 결합되어 있던 비즈니스 로직을 `src/nakoja/` 하위로 완전 격리했습니다.
- `crawler/`: 헤드리스 브라우저 기반 독립 크롤러 모듈
- `pipeline/`: Streamlit 비의존형 순수 파이썬 LLM 파이프라인
- `ui/`: 대시보드 프레젠테이션 계층
- `tests/`: `pytest` 기반 단위 테스트 및 Mocking 스위트 지원

---

## 🏗️ 시스템 파이프라인 다이어그램

```
[중앙일보 크롤러 (Selenium)]          [요미우리신문 크롤러 (Selenium)]
           ↓                                      ↓
    한국 기사 데이터                           일본 기사 데이터
           ↘                                      ↙
             [병합 데이터셋 / 샘플 데이터 (data/)]
                               ↓
                 [1. 토픽 분류기 (Classifier)]
               외교 / 안보 / 경제 / 역사 / 문화 등
                               ↓
               [2. 한일 기사 페어 매칭 (Selector)]
               동일한 특정 정상회담/이슈 기사 매칭
                               ↓
            [3. 중간 영어 요약 (Intermediate English)]
             한국 기사 요약       일본 기사 요약
             (L1 Framing Bias & 감정 배제)
                               ↓
         [4. 관점 대조 & 중립 기사 합성 (Neutralizer)]
          - 공통 인정 사실 (Shared Facts)
          - 양국 강조점 대비 (Korean vs Japanese Emphasis)
          - 프레이밍 분기 분석 (Framing Divergence)
          - 🇰🇷 한국어 중립 기사 전문
          - 🇯🇵 일본어 중립 기사 전문
```

---

## 🛠️ 기술 스택

- **Language & Runtime:** Python 3.10+
- **LLM Engine:** OpenAI API (`gpt-4o-mini`, `gpt-4o`)
- **Schema & Validation:** Pydantic v2 (Structured Outputs)
- **Web Scraping:** Selenium (Headless Chrome), BeautifulSoup4
- **Dashboard UI:** Streamlit
- **Testing:** Pytest, Pytest-mock
- **Packaging:** PEP 621 (`pyproject.toml`)

---

## 🚀 빠른 시작 (Quick Start)

### 1. 저장소 클론 및 환경 설정
```bash
git clone https://github.com/fairyofdata/Neutralize4KRJP.git
cd Neutralize4KRJP
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
루트 디렉토리에 `.env` 파일을 생성하고 OpenAI API 키를 입력합니다:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 4. 앱 실행
```bash
streamlit run main.py
```
브라우저에서 `http://localhost:8501`로 접속합니다.

> **💡 원클릭 데모 모드 (Quick Demo)**  
> 실시간 크롤링 없이도 상단의 **[샘플 데이터셋 즉시 로드]** 버튼을 클릭하면, 미리 수집된 기사 데이터를 바탕으로 즉시 전체 파이프라인을 체험하실 수 있습니다.

---

## ⚙️ 프로덕션 엔지니어링 및 실운영 설계 (Production & Operations)

- **스키마로 출력 강제**: 줄바꿈 분리나 정규표현식 대신 OpenAI의 공식 `beta.chat.completions.parse`와 **Pydantic v2** 스키마를 사용합니다. 단위 테스트 10건(Mock OpenAI 클라이언트)으로 스키마 직렬화와 파이프라인 분기를 검증하며, 실제 API에서의 파싱 실패율은 측정하지 않았습니다.
- **2단계 컨텍스트 압축**: 원문 기사 전체를 합성 모델에 그대로 투입하지 않고, 1차 정형 영어 요약(`ArticleSummary`, 팩트와 입장 분리)으로 먼저 압축한 뒤 합성합니다. 이 단계는 모국어 프레이밍 편향을 줄이는 것도 목표로 합니다.
- **API 비용 $0의 독립형 CI/CD 테스트**: 단위 테스트(`tests/`) 전체가 Mock OpenAI 클라이언트 기반으로 격리되어 있어, 외부 API 장애나 네트워크 환경과 무관하게 비용 $0으로 안정적인 회귀 테스트를 수행합니다.

---

## 🧪 단위 테스트 실행

```bash
pytest tests/ -v
```
Mock OpenAI 클라이언트가 내장되어 있어, API 호출 요금 없이 스키마 직렬화와 파이프라인 분기 로직을 검증할 수 있습니다.

---

## 👤 Author

**Jiheon Baek (백지헌)**  
- Software Engineer / AI Engineer (Okayama, Japan)  
- GitHub: [@fairyofdata](https://github.com/fairyofdata)  
- LinkedIn: [in/hjbaek](https://www.linkedin.com/in/hjbaek/)
