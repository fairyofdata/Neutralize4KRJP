import streamlit as st


def generate_neutral_article(korean_summary, japanese_summary):
    """Generate a neutral bilingual article from Korean and Japanese summaries."""
    client = st.session_state["openai_client"]

    message_content = (
        "Below are summaries of two news articles covering the same Japan-Korea relations topic — "
        "one from a Korean outlet and one from a Japanese outlet.\n\n"
        "Write a single neutral news article that:\n"
        "- Presents the key facts from both sides without bias\n"
        "- Explicitly highlights where the two reporting perspectives differ\n"
        "- Uses attributions like 'Joongang Ilbo reported...' and 'Yomiuri Shimbun reported...'\n"
        "- Provides the result in TWO versions: first in Korean (한국어), then in Japanese (日本語)\n\n"
        f"Korean Summary:\n{korean_summary}\n\n"
        f"Japanese Summary:\n{japanese_summary}\n\n"
        "Neutral Article (Korean then Japanese):"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an experienced bilingual journalist specializing in Japan-Korea relations. "
                    "You write balanced, factual articles that fairly represent both sides."
                ),
            },
            {"role": "user", "content": message_content},
        ],
        max_tokens=1500,
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()
