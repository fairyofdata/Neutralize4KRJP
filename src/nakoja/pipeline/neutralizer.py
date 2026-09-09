"""Bilingual Neutral Article Synthesizer pipeline (경요세계 & 성신교린)."""

from openai import OpenAI
from ..config import DEFAULT_MODEL, DEFAULT_TEMPERATURE
from ..schemas import ArticleSummary, NeutralArticle, PerspectiveComparison


SYSTEM_PROMPT = """You are a master cross-border editor and historian of East Asian diplomacy.
Guided by the historic spirit of:
- 瓊瑤世界 (경요세계: 'Two Jade Orbs Reflecting Each Other', Park An-Gi, 1643)
- 誠信交隣 (성신교린: 'Exchange with Sincerity and Mutual Trust', Amenomori Hōshū, 1728)

Your mission is to synthesize an impeccably balanced, neutral news article from two intermediate summaries of the same event (one from a Korean outlet, one from a Japanese outlet).

Strict Principles:
1. Objectivity: Never take a side or use pejorative/provocative adjectives.
2. Explicit Attribution: Clearly indicate which media outlet made which assertion.
   - For Korean: Use attributions such as "중앙일보는 ~라고 보도한 반면, 요미우리신문은 ~라는 점을 강조했다."
   - For Japanese: Use attributions such as "中央日報は〜と報じた一方、読売新聞は〜の立場を示した。"
3. Divergence Analysis: Clearly explain where and why the two perspectives diverge (e.g., historical grievances vs. international law vs. economic interests).
4. Bilingual Output: Produce high-quality, native-level journalistic prose in BOTH Korean and Japanese."""


def generate_neutral_article(
    korean_summary: ArticleSummary,
    japanese_summary: ArticleSummary,
    client: OpenAI,
    model: str = DEFAULT_MODEL,
) -> NeutralArticle:
    """
    Synthesizes a structured neutral bilingual article and contrast matrix
    from intermediate summaries.
    """
    user_prompt = f"""--- [KOREAN MEDIA SUMMARY ({korean_summary.outlet})] ---
Intermediate English Summary:
{korean_summary.english_summary}

Key Facts Reported:
{korean_summary.key_facts}

Stated Positions / Tone:
{korean_summary.stated_positions}


--- [JAPANESE MEDIA SUMMARY ({japanese_summary.outlet})] ---
Intermediate English Summary:
{japanese_summary.english_summary}

Key Facts Reported:
{japanese_summary.key_facts}

Stated Positions / Tone:
{japanese_summary.stated_positions}

Please produce:
1. PerspectiveComparison (shared_facts, korean_emphasis, japanese_emphasis, framing_divergence)
2. topic_summary
3. headline_kr & headline_jp
4. content_kr (Full neutral article in Korean)
5. content_jp (Full neutral article in Japanese)"""

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=NeutralArticle,
            temperature=DEFAULT_TEMPERATURE,
        )
        return completion.choices[0].message.parsed

    except Exception:
        # Graceful fallback
        comparison = PerspectiveComparison(
            shared_facts=korean_summary.key_facts + japanese_summary.key_facts,
            korean_emphasis=korean_summary.stated_positions,
            japanese_emphasis=japanese_summary.stated_positions,
            framing_divergence="Differences in national focus and legal interpretation.",
        )
        return NeutralArticle(
            topic_summary="Bilateral issue coverage analysis",
            comparison=comparison,
            headline_kr="한일 관계 관련 양국 보도 분석 및 중립 기사",
            headline_jp="日韓関係をめぐる両国報道の分析と中立記事",
            content_kr=(
                f"본 기사는 {korean_summary.outlet}과 {japanese_summary.outlet}의 보도를 종합한 것입니다.\n\n"
                f"{korean_summary.outlet}은 다음과 같이 보도했습니다: {korean_summary.english_summary}\n\n"
                f"반면 {japanese_summary.outlet}은 다음과 같이 보도했습니다: {japanese_summary.english_summary}"
            ),
            content_jp=(
                f"本記事は{korean_summary.outlet}と{japanese_summary.outlet}の報道を統合したものです。\n\n"
                f"{korean_summary.outlet}は次のように報じました：{korean_summary.english_summary}\n\n"
                f"一方、{japanese_summary.outlet}は次のように報じました：{japanese_summary.english_summary}"
            ),
        )
