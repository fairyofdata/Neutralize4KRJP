<!-- 원본: README_KR.md (한국어판이 원본, 영·일은 번역) · 동기화: 2026-10-26 -->

# Neutralize4KRJP — 한일 양국 보도로 쓰는 중립 기사 (LLM-NAKOJA)

[English](README.md) · [한국어](README_KR.md) · [日本語](README_JP.md)

[![tests](https://github.com/fairyofdata/Neutralize4KRJP/actions/workflows/tests.yml/badge.svg)](https://github.com/fairyofdata/Neutralize4KRJP/actions/workflows/tests.yml)

> **[경요세계(瓊瑤世界)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005) : '두 옥구슬이 서로를 비추다'**  
> ‐ 1643년 천문학자 [박안기(朴安期)](https://encykorea.aks.ac.kr/Article/E0020900)가 시즈오카현 청견사에 남긴 2층 종루 현판의 문장  
>
> **[성신교린(誠信交隣)](https://www.donga.com/news/People/article/all/20210416/106434451/1) : '성실과 진심으로써 교류하다'**  
> ‐ 1728년 [아메노모리 호슈(雨森芳洲)](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537)가 부산 초량왜관에서 집필한 「교린제성」의 문장

중앙일보와 요미우리신문이 같은 사안을 다룬 기사를 짝지어, 공통 사실과 양국의 강조점 차이를 나눠 적은 **한국어·일본어 중립 기사**를 LLM 으로 만드는 파이프라인입니다.

*2024년 10~11월 개인 프로젝트. 성신여자대학교 SW021 「ChatGPT for Business」 과정에서 배운 내용의 연장선에서 만들었습니다. 서비스 이름은 LLM-NAKOJA, 저장소 옛 이름은 `LLM_NAKOJA` 입니다.*

![NAKOJA 대시보드 미리보기](./NAKOJA_Preview.png)

## 문제의식

한일 양국의 외교·역사·경제 이슈는 각국 언론의 프레이밍과 자국 중심적 시각에 따라 엇갈리게 보도되는 경우가 많습니다.

> *"언어 모델이 양국 언론의 기사를 함께 읽고 교차 분석하면, 어느 한쪽에 기울지 않은 기사를 쓸 수 있을까?"*

이 질문에 답하려면 "중립적인가"를 재는 방법이 필요한데, 이 저장소는 아직 그 측정까지는 가지 않았습니다 (아래 [한계](#한계)).

## 설계 결정

### 1. 중간 언어로 영어를 거친다
한국어·일본어 원문에는 단어 선택과 어조에 각국의 정서와 암묵적 프레이밍이 배어 있습니다. 그래서 기사를 바로 합성하지 않고, 먼저 **영어로 사실(facts)과 주장(positions)을 나눠 요약**한 뒤 그 요약으로 합성합니다.
모국어 프레이밍을 덜어내려는 **설계 의도**이고, 실제로 편향이 줄었는지는 측정하지 않았습니다.

### 2. 출력은 Pydantic 스키마로 받는다
줄바꿈 분리나 정규표현식 대신 OpenAI 의 `beta.chat.completions.parse` 와 **Pydantic v2** 스키마를 씁니다. 손으로 쓴 파싱 코드가 없어지고, 양국 관점 대조(공통 사실 / 한국 측 강조 / 일본 측 강조 / 프레이밍 차이)가 타입이 정해진 데이터로 나옵니다. 실제 API 에서의 파싱 실패율은 측정하지 않았습니다.

### 3. 화면과 로직을 나눈다
- `src/nakoja/crawler/`: Selenium(헤드리스 Chrome) 크롤러
- `src/nakoja/pipeline/`: Streamlit 에 의존하지 않는 LLM 파이프라인 (분류 → 짝짓기 → 영어 요약 → 합성)
- `src/nakoja/schemas.py`: 출력 스키마
- `src/nakoja/ui/`: Streamlit 화면
- `tests/`: OpenAI 클라이언트를 mock 으로 바꾼 단위 테스트

## 파이프라인

```
[중앙일보 크롤러 (Selenium)]          [요미우리신문 크롤러 (Selenium)]
           ↓                                      ↓
    한국 기사 데이터                           일본 기사 데이터
           ↘                                      ↙
             [병합 데이터셋 / 샘플 데이터 (data/)]
                               ↓
                 [1. 토픽 분류 (GPT)]
               외교 / 안보 / 경제 / 역사 / 문화 등
                               ↓
               [2. 한일 기사 짝짓기 (구조화 출력)]
               같은 정상회담·이슈를 다룬 기사끼리
                               ↓
            [3. 영어 중간 요약]
             한국 기사 요약       일본 기사 요약
             (모국어 프레이밍을 덜어내도록 지시)
                               ↓
         [4. 관점 대조 & 중립 기사 합성]
          - 공통 사실
          - 양국 강조점 대비
          - 프레이밍 차이 분석
          - 🇰🇷 한국어 중립 기사
          - 🇯🇵 일본어 중립 기사
```

## 기술 스택

- Python 3.10+, OpenAI API (기본 `gpt-4o-mini`, `.env` 의 `OPENAI_MODEL` 로 변경), Pydantic v2
- Selenium (헤드리스 Chrome), BeautifulSoup4, Streamlit
- pytest, pytest-mock, `pyproject.toml` (PEP 621)

## 빠른 시작

```bash
git clone https://github.com/fairyofdata/Neutralize4KRJP.git
cd Neutralize4KRJP
pip install -r requirements.txt
```

루트에 `.env` 파일을 만들고 OpenAI API 키를 넣습니다.
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

```bash
streamlit run main.py
```
브라우저에서 `http://localhost:8501` 로 접속합니다. 상단의 **[샘플 데이터셋 즉시 로드]** 버튼을 누르면 크롤링 없이 `data/` 의 기사로 전체 파이프라인을 돌려 볼 수 있습니다. 분류·짝짓기·요약·합성은 API 를 호출하므로 키가 필요합니다.

## 테스트

```bash
pytest
```
- 단위 테스트 10건. OpenAI 클라이언트를 mock 으로 바꿔 **스키마 직렬화와 파이프라인 분기**를 확인합니다. API 키와 네트워크가 필요 없고 비용이 들지 않습니다.
- LLM 출력의 품질(사실 정확성, 중립성)은 이 테스트가 재지 않습니다.
- push 할 때마다 GitHub Actions 에서 같은 테스트를 돌립니다 (테스트만, 배포 없음).

## 데이터

`data/` 의 CSV 4개는 2024-11-23 에 중앙일보·요미우리신문 웹사이트에서 수집한 기사입니다 (중앙일보 23건, 요미우리 25건 중 본문이 있는 것 13건). 시연과 테스트를 위한 소량 표본이며, 기사 저작권은 각 언론사에 있습니다. 다시 배포하거나 다른 용도로 쓰지 마세요.

## 한계

- **중립성을 측정하지 않았습니다.** 영어 중간 요약이 편향을 줄이는지, 합성 기사가 실제로 균형 잡혔는지에 대한 평가(사람 평가나 기준 데이터)가 없습니다. 지금 결과물은 "중립을 지향하도록 설계한 출력"입니다.
- LLM 이 원문에 없는 사실을 덧붙이지 않았는지 코드로 검증하지 않습니다.
- 언론사 두 곳, 수집일 하루치 표본입니다. 언론사 선택 자체가 결과에 영향을 줍니다.
- 크롤러는 2024-11 기준 사이트 구조에 맞춰져 있어, 사이트가 바뀌면 동작하지 않을 수 있습니다.

## 만든 사람

**백지헌 (Jiheon Baek)** · AI 엔지니어 (일본 오카야마)  
GitHub [@fairyofdata](https://github.com/fairyofdata) · LinkedIn [in/hjbaek](https://www.linkedin.com/in/hjbaek/)

## 라이선스

MIT — [LICENSE](LICENSE). `data/` 의 기사 본문은 이 라이선스에 포함되지 않습니다.
