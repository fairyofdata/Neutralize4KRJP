<!-- 原本: README_KR.md（韓国語版が原本、英語・日本語は翻訳） · 同期: 2026-10-26 -->

# Neutralize4KRJP — 日韓両国の報道から書く中立記事 (LLM-NAKOJA)

[English](README.md) · [한국어](README_KR.md) · [日本語](README_JP.md)

[![tests](https://github.com/fairyofdata/Neutralize4KRJP/actions/workflows/tests.yml/badge.svg)](https://github.com/fairyofdata/Neutralize4KRJP/actions/workflows/tests.yml)

> **[瓊瑤世界 (けいようせかい)](https://www.seoul.co.kr/news/editOpinion/world-stories/2024/07/12/20240712035005) : 「二つの玉が互いを照らし合う」**  
> ‐ 1643年 朝鮮通信使の天文学者 [朴安期 (パク・アンギ)](https://encykorea.aks.ac.kr/Article/E0020900) が静岡市清見寺の鐘楼額に遺した言葉  
>
> **[誠信交隣 (せいしんこうりん)](https://www.donga.com/news/People/article/all/20210416/106434451/1) : 「誠実と信頼をもって互いに交わる」**  
> ‐ 1728年 対馬藩の儒学者 [雨森芳洲 (あめのもり ほうしゅう)](https://busan.grandculture.net/Contents?local=busan&dataType=01&contents_id=GC04203537) が釜山草梁倭館で著した『交隣提醒』の言葉

中央日報と読売新聞が同じ事案を扱った記事を組み合わせ、共通の事実と両国の強調点の違いを分けて書いた**日本語・韓国語の中立記事**を LLM で生成するパイプラインです。

*2024年10〜11月の個人プロジェクト。誠信女子大学 SW021「ChatGPT for Business」課程で学んだ内容の発展として制作しました。アプリ名は LLM-NAKOJA、リポジトリの旧名は `LLM_NAKOJA` です。*

![NAKOJA ダッシュボード プレビュー](./NAKOJA_Preview.png)

## 問題意識

日韓の外交・歴史・経済の課題は、それぞれの国内メディアのフレーミングによって食い違う形で報道されることが少なくありません。

> *「言語モデルが両国の報道を一緒に読んで比較分析すれば、どちらにも偏らない記事を書けるか？」*

これに答えるには「中立かどうか」を測る方法が必要ですが、このリポジトリはまだその測定まで進んでいません（下の[限界](#限界)）。

## 設計上の判断

### 1. 中間言語として英語を経由する
韓国語・日本語の原文には、語の選び方や語調にそれぞれの国の感情や暗黙のフレーミングが含まれています。そこで記事を直接合成せず、まず**英語で事実（facts）と主張（positions）を分けて要約**し、その要約から合成します。
母語のフレーミングを取り除くための**設計上の意図**であり、実際に偏りが減ったかどうかは測定していません。

### 2. 出力は Pydantic スキーマで受け取る
改行分割や正規表現の代わりに、OpenAI の `beta.chat.completions.parse` と **Pydantic v2** スキーマを使います。手書きのパース処理がなくなり、両国の視点の対照（共通の事実 / 韓国側の強調 / 日本側の強調 / フレーミングの違い）が型の決まったデータとして得られます。実際の API でのパース失敗率は測定していません。

### 3. 画面とロジックを分ける
- `src/nakoja/crawler/`: Selenium（ヘッドレス Chrome）のクローラー
- `src/nakoja/pipeline/`: Streamlit に依存しない LLM パイプライン（分類 → 組み合わせ → 英語要約 → 合成）
- `src/nakoja/schemas.py`: 出力スキーマ
- `src/nakoja/ui/`: Streamlit の画面
- `tests/`: OpenAI クライアントをモックにした単体テスト

## パイプライン

```
[中央日報クローラー (Selenium)]        [読売新聞クローラー (Selenium)]
           ↓                                      ↓
     韓国の記事                               日本の記事
           ↘                                      ↙
             [統合データセット / サンプルデータ (data/)]
                               ↓
                 [1. トピック分類 (GPT)]
               外交 / 安全保障 / 経済 / 歴史 / 文化 など
                               ↓
               [2. 日韓記事の組み合わせ (構造化出力)]
               同じ首脳会談・事案を扱った記事どうし
                               ↓
            [3. 英語の中間要約]
             韓国記事の要約       日本記事の要約
             (母語のフレーミングを除くよう指示)
                               ↓
         [4. 視点の対照と中立記事の合成]
          - 共通の事実
          - 両国の強調点の対比
          - フレーミングの違いの分析
          - 🇰🇷 韓国語の中立記事
          - 🇯🇵 日本語の中立記事
```

## 技術スタック

- Python 3.10+、OpenAI API（既定は `gpt-4o-mini`、`.env` の `OPENAI_MODEL` で変更）、Pydantic v2
- Selenium（ヘッドレス Chrome）、BeautifulSoup4、Streamlit
- pytest、pytest-mock、`pyproject.toml`（PEP 621）

## クイックスタート

```bash
git clone https://github.com/fairyofdata/Neutralize4KRJP.git
cd Neutralize4KRJP
pip install -r requirements.txt
```

ルートに `.env` ファイルを作り、OpenAI API キーを入れます。
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

```bash
streamlit run main.py
```
ブラウザで `http://localhost:8501` を開きます。上部の **[샘플 데이터셋 즉시 로드]**（サンプルデータを読み込む）ボタンを押すと、クロールせずに `data/` の記事でパイプライン全体を試せます。分類・組み合わせ・要約・合成は API を呼ぶため、キーは必要です。

## テスト

```bash
pytest
```
- 単体テスト 10 件。OpenAI クライアントをモックにして、**スキーマのシリアライズとパイプラインの分岐**を確認します。API キーもネットワークも不要で、費用はかかりません。
- LLM 出力の品質（事実の正確さ、中立性）はこのテストでは測りません。
- push のたびに GitHub Actions で同じテストを実行します（テストのみ、デプロイなし）。

## データ

`data/` の CSV 4 つは、2024-11-23 に中央日報・読売新聞のウェブサイトから収集した記事です（中央日報 23 件、読売新聞 25 件のうち本文があるもの 13 件）。デモとテストのための少量のサンプルで、記事の著作権は各新聞社にあります。再配布や他の用途への利用はしないでください。

## 限界

- **中立性は測定していません。** 英語の中間要約が偏りを減らすのか、合成記事が実際にバランスが取れているのかについての評価（人による評価や基準データ）はありません。現在の出力は「中立を目指すよう設計した出力」です。
- LLM が原文にない事実を付け加えていないかを、コードで検証していません。
- 新聞社 2 社、収集日 1 日分のサンプルです。新聞社の選び方そのものが結果に影響します。
- クローラーは 2024年11月時点のサイト構造に合わせているため、サイトが変わると動かない可能性があります。

## 作者

**백지헌 (Jiheon Baek)** · ソフトウェアエンジニア（岡山）  
GitHub [@fairyofdata](https://github.com/fairyofdata) · LinkedIn [in/hjbaek](https://www.linkedin.com/in/hjbaek/)

## ライセンス

MIT — [LICENSE](LICENSE)。`data/` の記事本文はこのライセンスの対象外です。
