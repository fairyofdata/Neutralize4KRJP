"""Topic classification pipeline using OpenAI Structured Outputs."""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from ..config import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SUPPORTED_CATEGORIES
from ..schemas import TopicClassificationBatch, TitleClassificationItem


SYSTEM_PROMPT = """You are an expert analyst of Korea-Japan international relations.
Your task is to classify news article titles into broad topic categories:
- Economy
- Politics
- Diplomacy
- Security
- Culture
- History
- Sports
- Other

Classify each title precisely based on its headline content."""


def classify_titles(
    titles: List[str],
    client: OpenAI,
    model: str = DEFAULT_MODEL,
) -> List[str]:
    """
    Classifies a list of article titles into standard topic categories.
    Returns a list of category strings aligned with input indices.
    """
    if not titles:
        return []

    # Build enumerated title listing
    title_list_str = "\n".join([f"{idx + 1}. {title}" for idx, title in enumerate(titles)])
    user_prompt = f"Please classify the following {len(titles)} titles:\n\n{title_list_str}"

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=TopicClassificationBatch,
            temperature=DEFAULT_TEMPERATURE,
        )
        parsed: TopicClassificationBatch = completion.choices[0].message.parsed
        
        # Map back to ordered list
        result_map = {item.index: item.category for item in parsed.classifications}
        ordered_labels = [
            result_map.get(idx + 1, "Other") for idx in range(len(titles))
        ]
        return ordered_labels

    except Exception:
        # Fallback to standard chat completion if structured output fails
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + "\nOutput format: 1. [Category]\n2. [Category]"},
                {"role": "user", "content": user_prompt},
            ],
            temperature=DEFAULT_TEMPERATURE,
        )
        content = response.choices[0].message.content or ""
        labels = []
        lines = content.strip().split("\n")
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            parts = line_str.split(". ", 1)
            if len(parts) == 2:
                labels.append(parts[1].strip())
            else:
                labels.append("Other")
        
        # Ensure length matches
        while len(labels) < len(titles):
            labels.append("Other")
        return labels[:len(titles)]
