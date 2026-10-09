import streamlit as st

from src import config, state, steps

st.set_page_config(page_title="Decision review tool", page_icon="🧭", layout="wide")
state.init()

st.title(config.APP_TITLE)
st.caption("Westbridge Capital · Form your own view, face the Devil's Advocate, record better-supported reasoning.")

steps.sidebar()
step = st.session_state.step
st.progress((step - 1) / (len(steps.STEP_NAMES) - 1), text=f"Step {step} of {len(steps.STEP_NAMES)}: {steps.STEP_NAMES[step]}")
steps.STEP_FUNCS[step]()
