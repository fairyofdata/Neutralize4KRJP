"""Article pair selector pipeline to identify direct Korea-Japan topical counterparts."""

from typing import List, Tuple, Optional
from openai import OpenAI
from ..config import DEFAULT_MODEL, DEFAULT_TEMPERATURE
from ..schemas import PairSelectionResult


SYSTEM_PROMPT = """You are a senior diplomatic and media intelligence analyst specializing in Northeast Asia.
You are given a list of news headlines under a shared broad category.
Your goal is to identify ONE Korean article and ONE Japanese article that discuss the exact same specific event, summit, policy conflict, or figure, making them an ideal pair for balanced comparative analysis."""


def select_article_pair(
    korean_titles: List[str],
    japanese_titles: List[str],
    client: OpenAI,
    model: str = DEFAULT_MODEL,
) -> Tuple[Optional[int], Optional[int], Optional[PairSelectionResult]]:
    """
    Selects the most closely aligned (Korean article index, Japanese article index).
    Returns 0-based indices and the full PairSelectionResult metadata.
    """
    if not korean_titles or not japanese_titles:
        return None, None, None

    prompt_lines = ["--- [KOREAN ARTICLES] ---"]
    for idx, title in enumerate(korean_titles):
        prompt_lines.append(f"K{idx + 1}. {title}")

    prompt_lines.append("\n--- [JAPANESE ARTICLES] ---")
    for idx, title in enumerate(japanese_titles):
        prompt_lines.append(f"J{idx + 1}. {title}")

    prompt_lines.append(
        "\nSelect the best matching pair discussing the exact same issue. "
        "korean_index must be the integer number after 'K', and japanese_index must be the integer number after 'J'."
    )

    user_prompt = "\n".join(prompt_lines)

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=PairSelectionResult,
            temperature=DEFAULT_TEMPERATURE,
        )
        result: PairSelectionResult = completion.choices[0].message.parsed
        
        # Convert 1-based index to 0-based
        k_idx = result.korean_index - 1
        j_idx = result.japanese_index - 1

        if 0 <= k_idx < len(korean_titles) and 0 <= j_idx < len(japanese_titles):
            return k_idx, j_idx, result
        else:
            return 0, 0, result

    except Exception:
        # Simple fallback
        return 0, 0, None
