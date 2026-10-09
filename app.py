import streamlit as st

st.set_page_config(page_title="Decision review tool", page_icon="🧭", layout="wide")

try:
    from reviewapp import config, state, steps
except Exception as exc:  # show a readable error instead of a endless loading circle
    st.error("The app could not start. Check that all files were uploaded to GitHub (folder `reviewapp` with its .py files, `data`, `requirements.txt`).")
    st.exception(exc)
    st.stop()

state.init()

st.title(config.APP_TITLE)
st.caption("Westbridge Capital · Form your own view, face the Devil's Advocate, record better-supported reasoning.")

steps.sidebar()
step = st.session_state.step
st.progress((step - 1) / (len(steps.STEP_NAMES) - 1), text=f"Step {step} of {len(steps.STEP_NAMES)}: {steps.STEP_NAMES[step]}")
steps.STEP_FUNCS[step]()
