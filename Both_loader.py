import pandas as pd
import streamlit as st


def load_and_initialize_data():
    """Load and combine Yomiuri and Jungang article CSVs."""
    yomiuri_df = pd.read_csv("yomiuri_articles_converted.csv", encoding="utf-8-sig")
    jungang_df = pd.read_csv("jungang_articles_converted.csv", encoding="utf-8-sig")
    combined_df = pd.concat([yomiuri_df, jungang_df], ignore_index=True)
    return combined_df