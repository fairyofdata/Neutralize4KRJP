import streamlit as st
import pandas as pd


def classify_titles_with_general_labels(titles):
    """Classify article titles into broad topic categories using GPT."""
    client = st.session_state["openai_client"]

    message_content = (
        "The following are news article titles related to Japan-Korea relations. "
        "Please classify each title into a broad topic category such as: "
        "Economy, Politics, Culture, Sports, Diplomacy, Security, History, or Other. "
        "Ensure that each category contains at least one Korean and one Japanese article where possible. "
        "If a category cannot have both, reassign to 'Other'.\n\n"
    )
    for idx, title in enumerate(titles):
        message_content += f"{idx + 1}. {title}\n"
    message_content += (
        "\nProvide the classification for each title in the format:\n"
        "1. [Label]\n2. [Label]\n..."
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are an expert analyst of Japan-Korea relations who classifies news articles into clear topic categories.",
            },
            {"role": "user", "content": message_content},
        ],
        max_tokens=1000,
        temperature=0.3,
    )

    classifications = response.choices[0].message.content.strip()
    labels = []
    for line in classifications.split("\n"):
        parts = line.split(". ", 1)
        if len(parts) == 2:
            labels.append(parts[1].strip())
        elif line.strip():
            labels.append("Unknown")
    return labels