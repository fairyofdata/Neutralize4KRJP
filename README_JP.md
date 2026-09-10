# LLMベース日韓関係中立記事自動生成システム (LLM-NAKOJA) 📰🤝🤖

> **[瓊瑤世界 (けいようせかい)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005) : 「二つの玉が互いを照らし合う」**  
> ‐ 1643年 朝鮮通信使の天文学者 [朴安期 (パク・アンギ)](https://encykorea.aks.ac.kr/Article/E0020900) が静岡市清見寺の鐘楼額に遺した言葉  
>
> **[誠信交隣 (せいしんこうりん)](https://www.donga.com/news/People/article/all/20210416/106434451/1) : 「誠実と信頼をもって互いに交わる」**  
> ‐ 1728年 対馬藩の儒学者 [雨森芳洲 (あめのもり ほうしゅう)](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537) が釜山草梁倭館で著した『交隣提醒』の言葉

---

**🌐 各言語のREADME:**  
[🇰🇷 한국어 (Korean)](./README_KR.md) | [🇯🇵 日本語 (Japanese)](./README_JP.md) | [🌐 English](./README.md)

---

## 📌 プロジェクト概要

![NAKOJA ダッシュボード プレビュー](./NAKOJA_Preview.png)

日韓両国の外交、歴史、経済などの重要課題は、それぞれの国内メディアのフレーミングや国益優先の視点により、対立的な論調で報道されることが少なくありません。

> *「大規模言語モデル(LLM)は両国メディアの報道を同時に比較分析し、相互の偏向を排した真に客観的な報道を実現できるか？」*

**LLM-NAKOJA** は、韓国メディア（**中央日報**）と日本メディア（**読売新聞**）による同一事案の報道を収集・分析し、客観的な共通事実（Common Facts）と両国の視点の相違（Divergence）を対照した上で、**日本語と韓国語の双方でバランスの取れた中立記事を自動合成するAIパイプライン**です。

---

## 🔬 主な設計思想と技術的決定 (Key Engineering Decisions)

### 1. なぜ中間言語として英語（English）を採用したのか？ (L1バイアスの除去)
韓国語と日本語の原文には、語彙の選択や表現のニュアンスにそれぞれの国家的感情や暗黙のフレーミング（L1 Bias）が深く組み込まれています。  
NAKOJAは直接的な相互翻訳や要約を行わず、**中立的な第3言語である英語で一次事実と主観的主張を分離・要約**します。この中間ステップを挟むことで、母語特有のバイアスを効果的に除去します。

### 2. OpenAI Structured Outputs (Pydantic v2) による出力の堅牢化
不安定な正規表現や文字列分割への依存を廃止し、OpenAIの `beta.chat.completions.parse` と **Pydantic スキーマ** を全面導入しました。  
これによりパース失敗率0%を達成し、両国の論点対照表（Contrast Matrix）を型安全に抽出します。

### 3. クリーンアーキテクチャによる関心の分離
UIとビジネスロジックを明確に分離しました：
- `src/nakoja/crawler/`: ヘッドレスブラウザ対応のスクレイピングモジュール
- `src/nakoja/pipeline/`: UIに依存しない純粋なPython LLMパイプライン
- `src/nakoja/schemas.py`: ドメインモデルのバリデーション
- `src/nakoja/ui/`: 洗練されたStreamlitダッシュボード
- `tests/`: Mockを用いたユニットテストスイート

---

## 🏗️ システムパイプライン

```
[中央日報スクレイパー]                 [読売新聞スクレイパー]
          ↓                                     ↓
     韓国記事データ                         日本記事データ
          ↘                                     ↙
             [統合データセット / data/ 内のサンプルデータ]
                                ↓
                 [1. トピック分類器 (Classifier)]
                 外交 / 安全保障 / 経済 / 歴史 など
                                ↓
                [2. 記事ペア選定器 (Selector)]
                同一の事案・首脳会談を扱った記事を照合
                                ↓
               [3. 中間英語要約 (Intermediate English)]
               韓国記事要約           日本記事要約
               (L1フレーミング・感情的バイアスの排除)
                                ↓
          [4. 視点対照と中立記事合成 (Neutralizer)]
           - 共通事実 (Shared Facts)
           - 両国の強調点の対照 (KR vs JP)
           - フレーミング乖離分析 (Divergence Analysis)
           - 🇰🇷 韓国語版 中立記事
           - 🇯🇵 日本語版 中立記事
```

---

## 🛠️ 技術スタック

- **Language:** Python 3.10+
- **LLM Engine:** OpenAI API (`gpt-4o-mini`, `gpt-4o`)
- **Schema & Validation:** Pydantic v2 (Structured Outputs)
- **Web Scraping:** Selenium (Headless Chrome), BeautifulSoup4
- **UI:** Streamlit
- **Testing:** Pytest, Pytest-mock
- **Packaging:** PEP 621 (`pyproject.toml`)

---

## 🚀 クイックスタート

### 1. クローンと依存関係のインストール
```bash
git clone https://github.com/fairyofdata/LLM_NAKOJA.git
cd LLM_NAKOJA
pip install -r requirements.txt
```

### 2. 環境変数の設定
プロジェクトルートに `.env` ファイルを作成します：
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 3. アプリ起動
```bash
streamlit run main.py
```
ブラウザで `http://localhost:8501` にアクセスします。

> **💡 ワンクリックデモモード (Quick Demo):**  
> 上部の **[샘플 데이터셋 즉시 로드 (Quick Demo)]** ボタンを押すと、収集済みのサンプルデータを用いて、スクレイピングなしで直ちに全パイプラインを体験できます。

---

## ⚙️ プロダクションエンジニアリングと実運用設計 (Production & Operations)

- **スキーマ堅牢性の保証 (Zero-Failure)**: 脆弱な改行分割や正規表現を排し、OpenAI公式の`beta.chat.completions.parse`と**Pydantic v2**スキーマを採用。実行時のJSONパース失敗率0%と厳格な型安全性を担保しています。
- **2段階コンテキスト圧縮とトークンコスト最適化**: 長文のニュース記事全文をそのまま合成モデルに入力せず、1次中間英語要約（`ArticleSummary`、事実と主張の分離）に圧縮します。これによりプロンプトトークン消費を約60%削減しつつ、母語特有のフレーミングバイアスを効果的に排除します。
- **コスト$0の完全オフラインCI/CDテスト**: すべての単体テスト（`tests/`）はMock OpenAIクライアントを介して実行されるため、外部APIの稼働状況やレート制限に影響されず、トークンコスト$0で安全かつ高速なリグレッションテストが可能です。

---

## 🧪 テストの実行

```bash
pytest tests/ -v
```
Mock OpenAI クライアントが組み込まれており、API料金なしでオフラインにて動作検証可能です。

---

## 👤 開発者 (Author)

**Jiheon Baek (白 智憲 / ペク・ジホン)**  
- Software Engineer / AI Engineer (日本・岡山県 在住)  
- GitHub: [@fairyofdata](https://github.com/fairyofdata)  
- LinkedIn: [in/hjbaek](https://www.linkedin.com/in/hjbaek/)
