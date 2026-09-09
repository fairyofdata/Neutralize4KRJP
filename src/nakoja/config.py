"""Configuration and settings for LLM-NAKOJA."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# Default Model Configuration
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 2000

# Supported Topic Categories
SUPPORTED_CATEGORIES = [
    "Politics",
    "Diplomacy",
    "Economy",
    "Security",
    "Culture",
    "History",
    "Sports",
    "Other",
]

# Outlet Metadata
OUTLETS = {
    "jungang": {
        "name": "JoongAng Ilbo",
        "name_kr": "중앙일보",
        "country": "Korea",
        "country_kr": "한국",
        "default_keyword": "한일",
    },
    "yomiuri": {
        "name": "Yomiuri Shimbun",
        "name_kr": "요미우리신문",
        "country": "Japan",
        "country_kr": "일본",
        "default_keyword": "日韓",
    },
}
