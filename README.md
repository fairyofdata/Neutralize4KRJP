**🌐 Available README Versions:**  
[🇰🇷 한국어 (Korean)](./README_KR.md) | [🇯🇵 日本語 (Japanese)](./README_JP.md)

# LLM-NAKOJA 📰🤝🤖
### LLM-based Korea-Japan Relations Neutral Article Generator

> *[瓊瑤世界 (경요세계)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005): "Two Jade Orbs Reflecting Each Other"*  
> — Inscription by astronomer [Park An-Gi](https://encykorea.aks.ac.kr/Article/E0020900) at Seikenji Temple, Shizuoka, 1643  
>
> *[誠信交隣 (성신교린)](https://www.donga.com/news/People/article/all/20210416/106434451/1): "Exchange with Sincerity and Trust"*  
> — Written by [Amenomori Hōshū](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537) in「Kyoryo Seisei」, 1728

---

## 📌 Overview

NAKOJA is a Streamlit-based pipeline that crawls news articles on Korea-Japan relations from both **Joongang Ilbo (한국)** and **Yomiuri Shimbun (日本)**, clusters them by topic using GPT, and generates a **bilingual neutral article** that explicitly represents both perspectives.

The core question this project asks:

> *"Can an LLM produce truly balanced journalism by reading both sides simultaneously?"*

---

## 🏗️ Pipeline Architecture

```
[Joongang Ilbo 크롤러]    [Yomiuri Shimbun 크롤러]
         ↓                          ↓
    Korean articles            Japanese articles
              ↘                 ↙
           [Combined DataFrame]
                    ↓
        [GPT Topic Classifier]
          Economy / Politics / Culture
          Security / History / Other
                    ↓
      [Korean-Japanese Pair Selector (GPT)]
       → finds articles on the same specific event
                    ↓
         [Article Summarizer (GPT)]
          Korean article → English summary
         Japanese article → English summary
                    ↓
       [Neutral Article Generator (GPT)]
        Bilingual output: 한국어 + 日本語
```

---

## 🔬 Key Design Decisions

### Why English as the Intermediate Language?
Summaries are generated in English before neutral article synthesis. This forces the model to step outside both languages' implicit framing and reduces L1-specific bias in the output.

### Explicit Attribution Prompting
The neutralizer prompt explicitly instructs GPT to use constructions like *"Joongang Ilbo reported... while Yomiuri Shimbun reported..."* — making the perspective gap visible rather than eliding it.

### Modular Pipeline
Each stage (crawl → classify → pair → summarize → neutralize) is a separate module, making it easy to swap in different models or news sources at any step.

---

## 💻 Tech Stack

| Layer | Technology |
|---|---|
| Web Crawling | Selenium + BeautifulSoup |
| LLM (Classify / Select / Summarize / Generate) | OpenAI GPT-3.5 (SDK v1.x) |
| UI | Streamlit |
| Data | Pandas |

---

## 🚀 Setup & Run

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set your OpenAI API key
Create a `.env` file in the project root:
```
OPENAI_API_KEY=sk-...
```
Or enter it directly in the Streamlit UI when prompted.

### 3. Run
```bash
streamlit run main.py
```

### 4. Usage Flow
1. **Scrape** — click to collect articles from Joongang and Yomiuri
2. **Classify** — GPT clusters all titles by topic
3. **Select pair** — GPT identifies the most topically aligned Korean + Japanese article
4. **Generate** — read summaries and the neutral bilingual article

> 📸 [Preview the full workflow](./NAKOJA_Preview.png) without running the app

---

## 📁 Project Structure

```
LLM_NAKOJA/
├── main.py                  # Streamlit app entry point
├── Article_Jungang.py       # Joongang Ilbo Selenium crawler
├── Article_yomiuri.py       # Yomiuri Shimbun Selenium crawler
├── Both_loader.py           # CSV loader & DataFrame merger
├── Classifier.py            # GPT topic classification
├── Data_selector.py         # GPT Korean-Japanese pair selection
├── Each_summarizer.py       # GPT article summarization
├── Final_Neutralizer.py     # GPT neutral article generation
└── requirements.txt         # Minimal dependency list
```

---

## ⚙️ Technical Notes

- **OpenAI SDK**: Migrated to `openai>=1.0.0` client API (`client.chat.completions.create`)
- **ChromeDriver**: Selenium requires a matching ChromeDriver on PATH. Use [ChromeDriver Downloads](https://chromedriver.chromium.org/downloads) or install `webdriver-manager`
- **Yomiuri paywall**: Some articles may return partial content due to subscription restrictions

---

## 🔗 Author

**Jiheon Baek** — [@fairyofdata](https://github.com/fairyofdata)

Crawling pipeline, OpenAI prompt design, Streamlit UI architecture, SDK v1.x migration.
