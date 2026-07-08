from openai import OpenAI
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
import os
from Article_Jungang import scrape_jungang_articles
from Article_yomiuri import scrape_yomiuri_articles
from Both_loader import load_and_initialize_data
from Classifier import classify_titles_with_general_labels
from Data_selector import select_korean_japanese_pair
from Each_summarizer import summarize_article
from Final_Neutralizer import generate_neutral_article

# Load environment variables from .env file
load_dotenv()


def main():
    st.title("🌏 Korean-Japanese Article Analysis and Neutral Article Generation 🌏")
    st.markdown(
        """
        **Welcome!**  
        This app allows you to:  
        1️⃣ Scrape articles from **Jungang Ilbo** and **Yomiuri Shimbun**  
        2️⃣ Classify and cluster article topics with GPT  
        3️⃣ Generate **neutral summaries** that reflect both perspectives
        """
    )

    st.divider()

    # --- OpenAI API key setup ---
    st.markdown("### 🔑 OpenAI API Key")
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        api_key = st.text_input(
            "Enter your OpenAI API key (or set OPENAI_API_KEY in .env):",
            type="password"
        )
        if not api_key:
            st.warning("⚠️ An OpenAI API key is required. See the README for setup instructions.")
            return

    # Initialize client and store in session state
    if "openai_client" not in st.session_state:
        st.session_state["openai_client"] = OpenAI(api_key=api_key)

    st.success("✅ OpenAI API key is set.")
    st.divider()

    # --- Step 1: Article Scraping ---
    st.header("📥 Step 1: Scrape Articles")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📰 Scrape Yomiuri Articles"):
            scrape_yomiuri_articles()
            st.success("Yomiuri articles scraped successfully!")
    with col2:
        if st.button("📰 Scrape Jungang Articles"):
            scrape_jungang_articles()
            st.success("Jungang articles scraped successfully!")

    st.divider()

    # --- Step 2: Load Data ---
    st.header("📂 Step 2: Load and View Articles")
    if "combined_df" not in st.session_state:
        st.session_state.combined_df = load_and_initialize_data()

    combined_df = st.session_state.combined_df

    if st.checkbox("👀 Show Loaded Articles"):
        st.dataframe(combined_df[["title", "content"]])

    st.divider()

    # --- Step 3: Classify Titles ---
    st.header("🏷️ Step 3: Classify Article Topics")
    titles = combined_df["title"].tolist()

    if st.button("🧩 Classify Titles"):
        labels = classify_titles_with_general_labels(titles)
        st.session_state.combined_df["label"] = labels
        st.session_state.combined_df.to_csv(
            "combined_articles_with_labels.csv", index=False, encoding="utf-8-sig"
        )
        st.success("🎉 Classification complete!")
        st.dataframe(st.session_state.combined_df[["title", "label"]])

    st.divider()

    # --- Step 4: Select Article Pair ---
    st.header("🔍 Step 4: Refine Articles by Topic")
    if "label" not in st.session_state.combined_df.columns:
        st.warning("⚠️ Please classify article titles first (Step 3).")
        return

    unique_labels = st.session_state.combined_df["label"].unique()
    selected_label = st.selectbox("🗂️ Select a topic label:", unique_labels)

    filtered_df = st.session_state.combined_df[
        st.session_state.combined_df["label"] == selected_label
    ]
    filtered_titles = filtered_df["title"].tolist()

    if st.button("🔗 Select Korean-Japanese Article Pair"):
        korean_idx, japanese_idx = select_korean_japanese_pair(filtered_titles)
        if korean_idx is not None and japanese_idx is not None:
            selected_articles = filtered_df.iloc[[korean_idx, japanese_idx]]
            korean_article_content = selected_articles.iloc[0]["content"]
            japanese_article_content = selected_articles.iloc[1]["content"]

            st.markdown("### **Selected Articles**")
            st.dataframe(selected_articles[["title", "content"]])

            st.markdown("### 📝 Article Summaries")
            korean_summary = summarize_article(korean_article_content, "Korean")
            japanese_summary = summarize_article(japanese_article_content, "Japanese")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("🇰🇷 Korean Summary")
                st.write(korean_summary)
            with col2:
                st.subheader("🇯🇵 Japanese Summary")
                st.write(japanese_summary)

            st.markdown("### 🌐 Generated Neutral Article")
            neutral_article = generate_neutral_article(korean_summary, japanese_summary)
            st.write(neutral_article)

            filtered_df.to_csv(
                "filtered_articles_with_detailed_labels.csv", index=False, encoding="utf-8-sig"
            )
            st.success("📄 Refined data saved.")
        else:
            st.error("❌ Article pair selection failed. Try another topic label.")


if __name__ == "__main__":
    main()
