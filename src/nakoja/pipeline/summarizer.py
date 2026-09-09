"""Intermediate English summarizer pipeline.

Core Philosophy:
Generating summaries in English as a neutral intermediate language strips away
the implicit linguistic framing and emotional undertones of both L1 languages
(Korean and Japanese), producing an objective factual baseline.
"""

from openai import OpenAI
from ..config import DEFAULT_MODEL, DEFAULT_TEMPERATURE
from ..schemas import ArticleSummary


SYSTEM_PROMPT = """You are a neutral, objective international investigative journalist.
Your assignment is to distill a news article into an intermediate, unbiased factual summary written in English.

Guidelines:
1. Separate concrete verifiable facts from subjective claims, government press releases, or nationalistic rhetoric.
2. Formulate the intermediate English summary in clear, impartial prose.
3. Explicitly list verified facts in `key_facts` and national/political claims in `stated_positions`."""


def summarize_to_intermediate_english(
    content: str,
    outlet: str,
    country: str,
    client: OpenAI,
    model: str = DEFAULT_MODEL,
) -> ArticleSummary:
    """
    Summarizes an article from Korean or Japanese into an intermediate neutral English summary.
    """
    user_prompt = f"""Outlet: {outlet} ({country})
Article Body:
{content}

Please extract the core verifiable facts, subjective/official positions, and synthesize a neutral intermediate English summary."""

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ArticleSummary,
            temperature=DEFAULT_TEMPERATURE,
        )
        return completion.choices[0].message.parsed
    except Exception:
        # Fallback if parsing fails
        return ArticleSummary(
            outlet=outlet,
            country=country,
            key_facts=["Reporting on bilateral relations"],
            stated_positions=["National perspective on the event"],
            english_summary=content[:500] if len(content) > 500 else content,
        )
