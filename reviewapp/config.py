"""Settings and small helpers shared across the app."""
import os
import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RECORDS_DIR = ROOT / "records"
DATA_DIR = ROOT / "data"

APP_TITLE = "Before we invest: decision review tool"

# Model slugs are OpenRouter slugs. They can be edited in the sidebar,
# because model names on OpenRouter change from time to time.
DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"
MODEL_SUGGESTIONS = [
    "anthropic/claude-sonnet-5.5",
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash",
    "meta-llama/llama-3.3-70b-instruct",
]
CUSTOM_MODEL_LABEL = "Other (type your own)"

DECISIONS = ["Invest", "Decline", "Request more information"]
RESPONSE_TYPES = ["Defend", "Revise", "Concede"]

# Gate rules (when is another AI review useful?)
CONFIDENCE_SWING_THRESHOLD = 15   # percentage points
MAX_AI_ROUNDS = 3                 # 1 challenge + up to 2 follow-ups

MAX_FILE_CHARS = 60_000
ACCEPTED_TYPES = ["pdf", "docx", "txt", "md", "csv", "xlsx"]


def _secret_key():
    try:
        return st.secrets.get("OPENROUTER_API_KEY")
    except Exception:
        return None


def secret_key_available() -> bool:
    return bool(_secret_key() or os.environ.get("OPENROUTER_API_KEY"))


def get_api_key() -> str:
    key = (
        _secret_key()
        or os.environ.get("OPENROUTER_API_KEY")
        or st.session_state.get("api_key_input", "")
        or ""
    )
    # remove spaces, line breaks, hidden characters and quotes that sneak in when pasting
    key = re.sub(r"[\s\u200b\u200c\u200d\ufeff\"']", "", str(key))
    if key.lower().startswith("bearer"):
        key = key[6:]
    return key


def get_model() -> str:
    choice = st.session_state.get("model_choice", DEFAULT_MODEL)
    if choice == CUSTOM_MODEL_LABEL:
        return (st.session_state.get("custom_model") or "").strip() or DEFAULT_MODEL
    return choice
