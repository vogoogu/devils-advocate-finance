"""Session state: one place that defines what the app remembers."""
import copy

import streamlit as st

from .util import now_iso

DEFAULTS = {
    "step": 1,
    "case_name": "",
    "analyst": "",
    "file_name": None,
    "file_text": "",
    "file_sig": None,
    "label_scheme": "",
    "truncated": False,
    "initial_view": None,    # frozen once saved: this is "my view before AI"
    "current_view": None,    # updated after each round
    "rounds": [],            # each: n, kind, ai, items, responses, view_after, gate, model, time
    "log": [],               # revision log
    "record": None,
}
KEEP_ON_RESET = {"api_key_input", "model_choice", "custom_model"}


def init():
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = copy.deepcopy(value)


def reset():
    for key in list(st.session_state.keys()):
        if key not in KEEP_ON_RESET:
            del st.session_state[key]
    init()


def log(event: str, detail: str = ""):
    st.session_state.log.append({"time": now_iso(), "event": event, "detail": detail})
