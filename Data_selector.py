import streamlit as st


def select_korean_japanese_pair(titles):
    """Use GPT to select the most topically aligned Korean-Japanese article pair."""
    client = st.session_state["openai_client"]

    message_content = (
        "The following are news article titles, all under the same broad topic. "
        "Select ONE Korean article and ONE Japanese article that discuss the same specific event or individual. "
        "Identify the most relevant pair.\n\n"
    )
    for idx, title in enumerate(titles):
        message_content += f"{idx + 1}. {title}\n"
    message_content += (
        "\nRespond ONLY in this exact format (no extra text):\n"
        "Korean: [Number]\nJapanese: [Number]"
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are an expert in Japan-Korea relations. Select the most relevant article pair on the same specific topic.",
            },
            {"role": "user", "content": message_content},
        ],
        max_tokens=50,
        temperature=0.2,
    )

    selection = response.choices[0].message.content.strip()
    korean_idx = japanese_idx = None

    try:
        for line in selection.split("\n"):
            if line.startswith("Korean:"):
                korean_idx = int(line.split(":")[1].strip()) - 1
            elif line.startswith("Japanese:"):
                japanese_idx = int(line.split(":")[1].strip()) - 1
    except (ValueError, IndexError) as e:
        st.error(f"Error parsing article pair selection: {e}")
        st.code(selection)
        return None, None

    if korean_idx is None or japanese_idx is None:
        st.error("Failed to select a valid Korean-Japanese pair. Try a different topic label.")
        return None, None

    return korean_idx, japanese_idx
