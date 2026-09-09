# LLM-NAKOJA 📰🤝🤖
### LLM-based Korea-Japan Relations Neutral Article Generator

> *[瓊瑤世界 (경요세계)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005): "Two Jade Orbs Reflecting Each Other"*  
> — Inscription by astronomer [Park An-Gi](https://encykorea.aks.ac.kr/Article/E0020900) at Seikenji Temple, Shizuoka, 1643  
>
> *[誠信交隣 (성신교린)](https://www.donga.com/news/People/article/all/20210416/106434451/1): "Exchange with Sincerity and Mutual Trust"*  
> — Written by [Amenomori Hōshū](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537) in *Kyōryō Seisei*, 1728

---

**🌐 Available README Versions:**  
[🇰🇷 한국어 (Korean)](./README_KR.md) | [🇯🇵 日本語 (Japanese)](./README_JP.md) | [🌐 English](./README.md)

---

## 📌 Overview

**LLM-NAKOJA** is a dual-perspective media synthesis pipeline that ingests news articles on Korea-Japan relations from both **JoongAng Ilbo (Korea)** and **Yomiuri Shimbun (Japan)**, clusters them by topic, and produces a **bilingual neutral article** that explicitly reconciles both perspectives.

The foundational research question:
> *"Can an LLM produce truly balanced journalism by reading and cross-analyzing both national narratives simultaneously?"*

---

## 🔬 Key Engineering & Design Decisions

### 1. English as the Neutral Intermediate Language (L1 Bias Elimination)
Generating direct translations or synthesizing directly between Korean and Japanese carries high risks of implicit framing bias, nationalistic word choice, and emotional undertones.  
NAKOJA utilizes **English as an intermediate lingua franca**. Facts and subjective assertions are distilled into English first, neutralizing first-language (L1) framing before the final bilingual article is produced.

### 2. Pydantic v2 Structured Outputs
Departing from fragile regex and newline splitting, NAKOJA enforces OpenAI's `beta.chat.completions.parse` with **Pydantic schemas**.  
This guarantees zero parsing failures, enforces type safety, and extracts structured comparative insights (shared facts, Korean emphasis, Japanese emphasis, and framing divergence).

### 3. Clean Modular Architecture
The codebase cleanly separates UI from core business logic:
- `src/nakoja/crawler/`: Headless, robust web scraping modules.
- `src/nakoja/pipeline/`: Pure Python LLM pipelines independent of any UI framework.
- `src/nakoja/schemas.py`: Domain validation models.
- `src/nakoja/ui/`: Rich Streamlit web dashboard.
- `tests/`: Complete unit tests with mock OpenAI clients.

---

## 🏗️ Pipeline Architecture

```
[JoongAng Ilbo Scraper]             [Yomiuri Shimbun Scraper]
          ↓                                     ↓
    Korean Articles                       Japanese Articles
          ↘                                     ↙
            [Combined Dataset / Sample Data in data/]
                                ↓
                 [1. Topic Classifier (GPT)]
              Diplomacy / Security / Economy / etc.
                                ↓
               [2. Pair Selector (Structured)]
              Matches identical bilateral events
                                ↓
             [3. Intermediate English Summarizer]
             Korean Summary        Japanese Summary
             (Strips L1 national framing bias)
                                ↓
          [4. Bilingual Neutral Article Synthesizer]
           - Mutual Facts (Shared baseline)
           - Contrasting Emphases (KR vs JP)
           - Framing Divergence Analysis
           - 🇰🇷 Korean Neutral Article
           - 🇯🇵 Japanese Neutral Article
```

---

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **LLM:** OpenAI API (`gpt-4o-mini`, `gpt-4o`)
- **Validation:** Pydantic v2 (Structured Outputs)
- **Scraping:** Selenium (Headless Chrome), BeautifulSoup4
- **UI:** Streamlit
- **Testing:** Pytest, Pytest-mock
- **Packaging:** PEP 621 (`pyproject.toml`)

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/fairyofdata/LLM_NAKOJA.git
cd LLM_NAKOJA
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the project root:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 3. Launch App
```bash
streamlit run main.py
```
Open `http://localhost:8501` in your browser.

> **💡 Quick Demo Mode:**  
> Click **[샘플 데이터셋 즉시 로드 (Quick Demo)]** to explore the entire pipeline immediately using pre-collected datasets without needing to scrape live sites.

---

## 🧪 Running Unit Tests

```bash
pytest tests/ -v
```
Mocked tests run entirely offline with zero API token consumption.

---

## 👤 Author

**Jiheon Baek (백지헌)**  
- Software Engineer / AI Engineer (Okayama, Japan)  
- GitHub: [@fairyofdata](https://github.com/fairyofdata)  
- LinkedIn: [in/hjbaek](https://www.linkedin.com/in/hjbaek/)
