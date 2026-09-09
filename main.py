"""Main entrypoint for LLM-NAKOJA Streamlit Application."""

import sys
from pathlib import Path

# Add src to sys.path so package can be run directly
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from nakoja.ui.app import run_app

if __name__ == "__main__":
    run_app()
