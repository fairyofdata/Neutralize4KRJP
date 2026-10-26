<!-- Source: README_KR.md (Korean is the source; English and Japanese are translations) · synced 2026-10-26 -->

# Neutralize4KRJP — neutral articles from Korean and Japanese coverage (LLM-NAKOJA)

[English](README.md) · [한국어](README_KR.md) · [日本語](README_JP.md)

[![tests](https://github.com/fairyofdata/Neutralize4KRJP/actions/workflows/tests.yml/badge.svg)](https://github.com/fairyofdata/Neutralize4KRJP/actions/workflows/tests.yml)

> *[瓊瑤世界 (경요세계)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005): "Two Jade Orbs Reflecting Each Other"*  
> — Inscription by astronomer [Park An-Gi](https://encykorea.aks.ac.kr/Article/E0020900) at Seikenji Temple, Shizuoka, 1643  
>
> *[誠信交隣 (성신교린)](https://www.donga.com/news/People/article/all/20210416/106434451/1): "Exchange with Sincerity and Mutual Trust"*  
> — Written by [Amenomori Hōshū](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537) in *Kōrin Teisei*, 1728

A pipeline that pairs JoongAng Ilbo and Yomiuri Shimbun articles on the same issue and has an LLM write a **neutral article in Korean and Japanese** that separates shared facts from each side's emphasis.

*Individual project (Oct–Nov 2024), building on the SW021 "ChatGPT for Business" program at Sungshin Women's University. The app is called LLM-NAKOJA; the repository was formerly `LLM_NAKOJA`.*

![NAKOJA dashboard preview](./NAKOJA_Preview.png)

## Motivation

Diplomatic, historical and economic issues between Korea and Japan are often reported in conflicting ways, shaped by each country's media framing.

> *"If a language model reads and cross-analyzes both countries' coverage, can it write an article that leans toward neither side?"*

Answering that needs a way to measure neutrality, and this repository has not reached that point yet (see [Limitations](#limitations)).

## Design decisions

### 1. Go through English as an intermediate language
Korean and Japanese originals carry national sentiment and implicit framing in their word choice and tone. So the articles are not synthesized directly: each is first **summarized in English, with facts and positions separated**, and the synthesis works from those summaries.
This is a **design intent** to strip first-language framing; whether it actually reduces bias has not been measured.

### 2. Take output through Pydantic schemas
Instead of splitting on newlines or regexes, the pipeline uses OpenAI's `beta.chat.completions.parse` with **Pydantic v2** schemas. There is no hand-written parsing, and the comparison (shared facts / Korean emphasis / Japanese emphasis / framing divergence) arrives as typed data. The parse failure rate against the live API has not been measured.

### 3. Keep the UI apart from the logic
- `src/nakoja/crawler/`: Selenium (headless Chrome) scrapers
- `src/nakoja/pipeline/`: LLM pipeline with no Streamlit dependency (classify → pair → English summary → synthesis)
- `src/nakoja/schemas.py`: output schemas
- `src/nakoja/ui/`: Streamlit UI
- `tests/`: unit tests with a mocked OpenAI client

## Pipeline

```
[JoongAng Ilbo scraper]             [Yomiuri Shimbun scraper]
          ↓                                     ↓
    Korean articles                       Japanese articles
          ↘                                     ↙
            [Combined dataset / sample data in data/]
                                ↓
                 [1. Topic classifier (GPT)]
              Diplomacy / Security / Economy / etc.
                                ↓
               [2. Pair selector (structured output)]
              Articles on the same summit or issue
                                ↓
             [3. Intermediate English summaries]
             Korean summary        Japanese summary
             (instructed to drop L1 framing)
                                ↓
          [4. Comparison & neutral article synthesis]
           - Shared facts
           - Contrasting emphases (KR vs JP)
           - Framing divergence
           - 🇰🇷 Korean neutral article
           - 🇯🇵 Japanese neutral article
```

## Tech stack

- Python 3.10+, OpenAI API (`gpt-4o-mini` by default, set `OPENAI_MODEL` in `.env` to change), Pydantic v2
- Selenium (headless Chrome), BeautifulSoup4, Streamlit
- pytest, pytest-mock, `pyproject.toml` (PEP 621)

## Quick start

```bash
git clone https://github.com/fairyofdata/Neutralize4KRJP.git
cd Neutralize4KRJP
pip install -r requirements.txt
```

Create a `.env` file in the project root:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

```bash
streamlit run main.py
```
Open `http://localhost:8501`. The **[샘플 데이터셋 즉시 로드]** (load sample dataset) button runs the whole pipeline on the articles in `data/` without scraping. Classification, pairing, summarizing and synthesis call the API, so a key is still needed.

## Tests

```bash
pytest
```
- 10 unit tests. With a mocked OpenAI client they check **schema serialization and pipeline branches**. No API key, no network, no cost.
- They do not measure the quality of the LLM output (factual accuracy, neutrality).
- GitHub Actions runs the same tests on every push (tests only, no deployment).

## Data

The four CSV files in `data/` are articles collected from the JoongAng Ilbo and Yomiuri Shimbun websites on 2024-11-23 (23 JoongAng articles; 25 Yomiuri articles, 13 of them with body text). They are a small sample for the demo and the tests. Copyright of the articles belongs to each publisher; do not redistribute them or use them for other purposes.

## Limitations

- **Neutrality is not measured.** There is no evaluation (human ratings or reference data) of whether the English step reduces bias or whether the synthesized article is actually balanced. The output is "designed to aim for neutrality".
- No code check that the LLM did not add facts absent from the source articles.
- Two publishers, one day's sample. The choice of publishers itself shapes the result.
- The scrapers follow the sites' structure as of November 2024 and may break when the sites change.

## Author

**Jiheon Baek (백지헌)** · Software engineer (Okayama, Japan)  
GitHub [@fairyofdata](https://github.com/fairyofdata) · LinkedIn [in/hjbaek](https://www.linkedin.com/in/hjbaek/)

## License

MIT — see [LICENSE](LICENSE). The article text in `data/` is not covered by this license.
