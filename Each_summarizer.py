import streamlit as st


def summarize_article(article_content, language):
    """Summarize a news article in English, capturing key points in 5-6 sentences."""
    client = st.session_state["openai_client"]

    # Trim to avoid token overflow while preserving meaningful content
    truncated_content = article_content[:3000]

    message_content = (
        f"The following is a news article written in {language} about Japan-Korea relations. "
        "Summarize the key points in 5-6 sentences in English. "
        "Focus on: the main event, the positions of each side, and any notable quotes or data.\n\n"
        f"Article:\n{truncated_content}\n\nSummary:"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a skilled news editor who distills articles into concise, accurate summaries.",
            },
            {"role": "user", "content": message_content},
        ],
        max_tokens=400,
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()