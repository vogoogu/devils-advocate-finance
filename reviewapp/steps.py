"""All screens of the app. One function per step."""
import copy
import json

import pandas as pd
import streamlit as st

from . import config, files, gate, openrouter, prompts, record, reviewer, state
from .util import df_to_reasons, make_view, now_iso, reasons_to_df, split_lines, split_refs

STEP_NAMES = {1: "Case file", 2: "My view", 3: "AI challenge", 4: "My response", 5: "Final record"}
SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}
VERDICT_ICON = {"resolved": "✅", "partly_resolved": "🟡", "unresolved": "❌"}


# --------------------------------------------------------------------------- helpers
def go(step: int):
    st.session_state.step = step
    st.rerun()


def call_ai(fn, *args):
    """Run an AI call with a spinner. Returns the result or None (error is shown)."""
    key = config.get_api_key()
    if not key:
        st.error("Please add your OpenRouter API key in the sidebar (or in the app secrets) first.")
        return None
    try:
        with st.spinner("The Devil's Advocate is reading the file and your reasoning..."):
            return fn(*args, config.get_model(), key)
    except openrouter.OpenRouterError as exc:
        st.error(str(exc))
        return None


def view_summary(view: dict, title: str):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.write(f"Decision: **{view['decision']}** · Confidence: **{view['confidence']}%**")
        for r in view["reasons"]:
            st.markdown(f"- {r['reason']}  \n  <small>Evidence: {', '.join(r['refs']) or 'none cited'}</small>", unsafe_allow_html=True)


def render_round(rd: dict):
    ai = rd["ai"]
    if rd["kind"] == "challenge":
        if ai.get("direction_note"):
            st.info(ai["direction_note"])
    else:
        for v in ai.get("verdicts") or []:
            if not isinstance(v, dict):
                continue
            verdict = str(v.get("verdict", "")).lower()
            st.markdown(f"{VERDICT_ICON.get(verdict, '•')} **{v.get('objection_id', '')}**: {verdict.replace('_', ' ')}. {v.get('comment', '')}")
        if ai.get("recommendation_check"):
            st.info("Is the updated recommendation supported? " + str(ai["recommendation_check"]))

    if rd["items"]:
        st.markdown("**Open objections**" if rd["kind"] != "challenge" else "**Objections**")
    for it in rd["items"]:
        with st.container(border=True):
            st.markdown(f"{SEVERITY_ICON.get(it['severity'], '🟠')} **{it['id']} · {it['title']}**" + (f" · *{it['flaw']}*" if it.get("flaw") else ""))
            st.write(it["challenge"])
            if it["refs"]:
                st.caption("Evidence: " + ", ".join(it["refs"]))
            st.markdown(f"**Question for you:** {it['question']}")

    well = [w for w in (ai.get("well_supported") or []) if isinstance(w, dict)]
    if well:
        st.markdown("**Well supported**")
        for w in well:
            refs = w.get("evidence_refs") or []
            refs = refs if isinstance(refs, list) else [refs]
            st.markdown(f"- ✅ {w.get('point', '')} *({', '.join(map(str, refs))})*")

    unsupported = [u for u in (ai.get("unsupported_amounts_or_terms") or []) if isinstance(u, dict)]
    if unsupported:
        st.markdown("**Amounts or terms without a clear basis**")
        for u in unsupported:
            st.markdown(f"- ⚠️ {u.get('item', '')}: {u.get('issue', '')}")

    if ai.get("overall_assessment"):
        st.markdown(f"**Overall:** {ai['overall_assessment']}")
    if rd["kind"] != "challenge":
        flag = "yes" if ai.get("adequately_supported") else "not yet"
        st.markdown(f"**Adequately supported?** {flag}. {ai.get('reason', '')}")


def load_text(raw: str, name: str):
    raw = (raw or "").strip()
    if not raw:
        st.error("No text found. If this is a scanned PDF, it has no text layer and cannot be read. Paste the text instead.")
        return
    raw, truncated = files.truncate(raw)
    labelled, scheme = files.add_labels(raw)
    st.session_state.file_text = labelled
    st.session_state.file_name = name
    st.session_state.label_scheme = scheme
    st.session_state.truncated = truncated
    state.log("Case file loaded", f"{name}, {len(labelled)} characters, labels: {scheme}")


# --------------------------------------------------------------------------- sidebar
def sidebar():
    with st.sidebar:
        st.title("Decision review")
        st.caption("Teaching prototype · fictional scenario")

        st.subheader("AI settings")
        if config.secret_key_available():
            st.success("API key loaded from secrets")
        else:
            st.text_input("OpenRouter API key", type="password", key="api_key_input",
                          help="Kept only in this browser session. Not saved to any file.")
        choice = st.selectbox("Model", config.MODEL_SUGGESTIONS + [config.CUSTOM_MODEL_LABEL], key="model_choice")
        if choice == config.CUSTOM_MODEL_LABEL:
            st.text_input("Model name on OpenRouter", key="custom_model", placeholder="provider/model-name")

        st.subheader("Progress")
        for n, name in STEP_NAMES.items():
            icon = "✅" if n < st.session_state.step else ("👉" if n == st.session_state.step else "⚪")
            st.write(f"{icon} {n}. {name}")

        with st.expander("Reviewer instructions"):
            st.caption("Round 1 (challenge)")
            st.code(prompts.REVIEWER_SYSTEM_PROMPT, language="markdown")
            st.caption("Follow-up rounds: the same rules plus")
            st.code(prompts.FOLLOWUP_RULES + prompts.FOLLOWUP_FORMAT, language="markdown")

        with st.expander("Saved records (this server)"):
            saved = sorted(config.RECORDS_DIR.glob("*.md"), reverse=True) if config.RECORDS_DIR.exists() else []
            if not saved:
                st.caption("Nothing saved yet.")
            for path in saved[:10]:
                st.download_button(path.stem, path.read_text(encoding="utf-8"), file_name=path.name, key=f"dl_{path.stem}")
            st.caption("On Streamlit Cloud this folder is temporary. Always download your records.")

        if st.button("Start a new case"):
            state.reset()
            st.rerun()


# --------------------------------------------------------------------------- step 1
def step_case():
    st.header("Step 1 · Case file")
    c1, c2 = st.columns(2)
    c1.text_input("Case name", value=st.session_state.case_name, key="w_case_name", placeholder="e.g. AsterFlow")
    c2.text_input("Analyst name (optional)", value=st.session_state.analyst, key="w_analyst")

    source = st.radio("Where does the file come from?", ["Upload a file", "Paste text", "Use the sample (AsterFlow)"],
                      horizontal=True, key="w_source")

    if source == "Upload a file":
        up = st.file_uploader("PDF, Word, text, Markdown, CSV or Excel", type=config.ACCEPTED_TYPES, key="w_upload")
        if up is not None and st.session_state.file_sig != (up.name, up.size):
            try:
                raw = files.read_uploaded(up)
            except Exception as exc:  # unreadable or corrupt file
                st.error(f"Could not read this file: {exc}")
            else:
                load_text(raw, up.name)
                st.session_state.file_sig = (up.name, up.size)
    elif source == "Paste text":
        st.text_area("Paste the file text here", height=220, key="w_paste")
        if st.button("Use this text"):
            load_text(st.session_state.get("w_paste", ""), "pasted text")
    else:
        if st.button("Load the AsterFlow sample"):
            load_text((config.DATA_DIR / "asterflow_sample.md").read_text(encoding="utf-8"), "asterflow_sample.md")

    if st.session_state.file_text:
        scheme = st.session_state.label_scheme
        st.success(f"Loaded: {st.session_state.file_name}")
        if scheme == "existing":
            st.caption("The file already has numbered items (like A1, A2). Cite them in your reasoning.")
        else:
            st.caption("The file had no numbered items, so paragraphs were numbered P1, P2, ... Cite these in your reasoning.")
        if st.session_state.truncated:
            st.warning(f"The file was long, so only the first {config.MAX_FILE_CHARS:,} characters are used.")
        with st.expander("Preview the file as the AI will see it"):
            st.text_area("file", st.session_state.file_text, height=320, disabled=True, label_visibility="collapsed")
        if st.button("Continue: form my own view", type="primary"):
            fallback = "AsterFlow" if st.session_state.file_name == "asterflow_sample.md" else st.session_state.file_name
            st.session_state.case_name = (st.session_state.get("w_case_name") or "").strip() or fallback
            st.session_state.analyst = (st.session_state.get("w_analyst") or "").strip()
            state.log("Case started", st.session_state.case_name)
            go(2)


# --------------------------------------------------------------------------- step 2
def step_view():
    st.header("Step 2 · Form my own view")
    st.info("Do this **before** any AI output. Your first view is saved and cannot be edited afterwards, so the review can show how your thinking changed.")

    with st.expander("Case file (for reference)"):
        st.text_area("file", st.session_state.file_text, height=300, disabled=True, label_visibility="collapsed", key="ref_file_2")
    with st.expander("Quick bias checks (optional, 1 minute)"):
        st.markdown(
            "- **Forecast:** what usually happens to forecasts like this? Imagine it is a year later and it failed. Why? *(outside view, pre-mortem)*\n"
            "- **Founder and story:** which facts come from the founder, and which from independent sources? Write one reason to say the opposite of your lean. *(consider the opposite)*\n"
            "- **Risks and returns:** what is the downside if I am wrong? Is one risk or the deadline deciding everything? *(downside check)*"
        )

    with st.form("view_form"):
        decision = st.radio("My recommendation", config.DECISIONS, index=None, horizontal=True)
        confidence = st.slider("How confident am I? (%)", 0, 100, 50)
        st.markdown("**My strongest reasons** (add evidence numbers, e.g. A3 or P4)")
        reasons_df = st.data_editor(reasons_to_df([]), num_rows="dynamic", hide_index=True, key="reasons_editor_initial")
        assumptions = st.text_area("Key assumptions (one per line)", height=100)
        risks = st.text_area("Main risks (one per line)", height=100)
        triggers = st.text_area("What would change my view? (one per line)", height=100)
        with st.expander("Amount or alternative terms (optional)"):
            amount = st.text_input("Amount or terms I would propose", placeholder="e.g. EUR 1.5m for 10%, in two tranches")
            basis = st.text_area("Basis for it (required if you propose something)", height=80)
        submitted = st.form_submit_button("Save my view and continue", type="primary")

    if st.button("Back"):
        go(1)

    if submitted:
        reasons = df_to_reasons(reasons_df)
        problems = []
        if not decision:
            problems.append("Choose a recommendation.")
        if not reasons:
            problems.append("Add at least one reason.")
        if not split_lines(assumptions):
            problems.append("Add at least one key assumption.")
        if not split_lines(triggers):
            problems.append("Say what would change your view.")
        if amount.strip() and not basis.strip():
            problems.append("An amount or alternative terms need an explicit basis.")
        if problems:
            for p in problems:
                st.error(p)
            return
        view = make_view(decision, confidence, reasons, split_lines(assumptions), split_lines(risks),
                         split_lines(triggers), amount, basis)
        st.session_state.initial_view = view
        st.session_state.current_view = copy.deepcopy(view)
        state.log("Own view saved before AI", f"{decision}, {confidence}% confident")
        go(3)


# --------------------------------------------------------------------------- step 3
def step_challenge():
    st.header("Step 3 · AI challenge (Devil's Advocate)")
    rounds = st.session_state.rounds
    view_summary(st.session_state.initial_view, "My view before the AI (saved)")

    if not rounds:
        st.write("The AI gets the whole file and your reasoning. It will argue against your lean and also say what is well supported.")
        if st.button("Ask the Devil's Advocate", type="primary"):
            out = call_ai(reviewer.run_initial, st.session_state.file_text, st.session_state.initial_view)
            if out:
                parsed, items = out
                rounds.append({"n": 1, "kind": "challenge", "ai": parsed, "items": items, "responses": None,
                               "view_after": None, "gate": None, "model": config.get_model(), "time": now_iso()})
                state.log("AI challenge received", f"{len(items)} objections, model {config.get_model()}")
                st.rerun()
        return

    for rd in rounds[:-1]:
        with st.expander(f"Round {rd['n']} ({rd['kind']}): earlier"):
            render_round(rd)
    latest = rounds[-1]
    st.subheader(f"Round {latest['n']} ({latest['kind']})")
    render_round(latest)

    if latest["items"]:
        if st.button("Answer the AI", type="primary"):
            go(4)
    else:
        st.success("The AI has no open objections. You can go to the final record.")
        if st.button("Go to the final record", type="primary"):
            go(5)


# --------------------------------------------------------------------------- step 4
def step_response():
    st.header("Step 4 · My response")
    rounds = st.session_state.rounds
    latest = rounds[-1]

    if latest["responses"] is not None:
        gate_panel(latest)
        return

    cur = st.session_state.current_view
    with st.form(f"response_form_{latest['n']}"):
        st.markdown("**Answer each point.** Defend (with evidence), revise your reasoning, or concede.")
        for it in latest["items"]:
            key = f"{latest['n']}_{it['id']}"
            with st.container(border=True):
                st.markdown(f"**{it['id']} · {it['title']}**")
                st.write(it["challenge"])
                st.markdown(f"*Question: {it['question']}*")
                st.radio("My answer", config.RESPONSE_TYPES, index=None, horizontal=True, key=f"type_{key}")
                st.text_area("Why? Use evidence from the file.", key=f"text_{key}", height=90)
                st.text_input("Evidence numbers (e.g. A3, A5)", key=f"refs_{key}")

        st.markdown("**My updated position**")
        decision = st.radio("Recommendation", config.DECISIONS, index=config.DECISIONS.index(cur["decision"]), horizontal=True)
        confidence = st.slider("Confidence (%)", 0, 100, cur["confidence"])
        st.markdown("Reasons (edit, add or delete rows)")
        reasons_df = st.data_editor(reasons_to_df(cur["reasons"]), num_rows="dynamic", hide_index=True,
                                    key=f"reasons_editor_{latest['n']}")
        submitted = st.form_submit_button("Submit my response", type="primary")

    if st.button("Back to the AI's points"):
        go(3)

    if submitted:
        responses, problems = [], []
        for it in latest["items"]:
            key = f"{latest['n']}_{it['id']}"
            rtype = st.session_state.get(f"type_{key}")
            text = (st.session_state.get(f"text_{key}") or "").strip()
            if not rtype or not text:
                problems.append(f"Answer {it['id']}: choose Defend, Revise or Concede and explain.")
                continue
            responses.append({"item_id": it["id"], "title": it["title"], "type": rtype, "text": text,
                              "refs": split_refs(st.session_state.get(f"refs_{key}", ""))})
        reasons = df_to_reasons(reasons_df)
        if not reasons:
            problems.append("Keep at least one reason.")
        if problems:
            for p in problems:
                st.error(p)
            return

        prev = copy.deepcopy(cur)
        new = copy.deepcopy(cur)
        new.update({"decision": decision, "confidence": int(confidence), "reasons": reasons})
        if prev["decision"] != new["decision"]:
            state.log("Recommendation changed", f"{prev['decision']} to {new['decision']}")
        if prev["confidence"] != new["confidence"]:
            state.log("Confidence changed", f"{prev['confidence']}% to {new['confidence']}%")
        if prev["reasons"] != new["reasons"]:
            state.log("Reasons edited")
        for r in responses:
            state.log(f"Analyst response to {r['item_id']}", r["type"])

        latest["responses"] = responses
        latest["view_after"] = new
        latest["gate"] = gate.evaluate(prev, new, responses, latest["ai"], len(rounds))
        st.session_state.current_view = new
        st.rerun()


def gate_panel(latest: dict):
    g = latest["gate"]
    rounds = st.session_state.rounds
    st.subheader("Gate: is another AI review useful?")
    if g["reasons"]:
        for r in g["reasons"]:
            st.markdown(f"- {r}")
    else:
        st.success("No trigger found: the answers cite evidence and the position is stable.")
    if g["capped"]:
        st.warning(f"The limit of {config.MAX_AI_ROUNDS} AI rounds is reached. Remaining points go into the record as open uncertainties.")
    elif g["needed"]:
        st.info("Another round is suggested.")

    can_run = len(rounds) < config.MAX_AI_ROUNDS
    c1, c2 = st.columns(2)
    if c1.button("Run follow-up review", type="primary" if g["needed"] else "secondary", disabled=not can_run):
        out = call_ai(reviewer.run_followup, st.session_state.file_text, st.session_state.initial_view,
                      rounds, st.session_state.current_view, len(rounds) + 1)
        if out:
            parsed, items = out
            rounds.append({"n": len(rounds) + 1, "kind": "follow-up", "ai": parsed, "items": items,
                           "responses": None, "view_after": None, "gate": None,
                           "model": config.get_model(), "time": now_iso()})
            state.log("AI follow-up received", f"{len(items)} open points")
            go(3)
    if c2.button("Finish and write the record", type="primary" if not g["needed"] else "secondary"):
        go(5)


# --------------------------------------------------------------------------- step 5
def step_record():
    st.header("Step 5 · Final record for the CEO")
    ss = st.session_state

    if ss.record:
        show_record(ss.record)
        return

    iv, cv = ss.initial_view, ss.current_view
    st.table(pd.DataFrame({"Before AI": [iv["decision"], f"{iv['confidence']}%"],
                           "Now": [cv["decision"], f"{cv['confidence']}%"]}, index=["Decision", "Confidence"]))
    view_summary(cv, "My final reasons")

    last = ss.rounds[-1] if ss.rounds else None
    if last and last["items"] and last["responses"] is None:
        st.warning("The last AI points were not answered yet. They will be listed in the record as open.")
        st.caption("Open: " + "; ".join(f"{i['id']} {i['title']}" for i in last["items"]))

    terms = cv.get("proposed_terms") or {}
    with st.form("final_form"):
        uncertainties = st.text_area("What is still uncertain? (one per line)", height=110,
                                     help="Things you could not resolve with the file.")
        conditions = st.text_area("What would change my decision? (one per line)", value="\n".join(cv["change_triggers"]), height=110)
        amount = st.text_input("Amount or alternative terms (optional)", value=terms.get("amount", ""))
        basis = st.text_area("Basis for the amount or terms", value=terms.get("basis", ""), height=80)
        submitted = st.form_submit_button("Save the review record", type="primary")

    if st.button("Back"):
        go(3 if last and last["responses"] is None else 4)

    if submitted:
        problems = []
        if not split_lines(uncertainties):
            problems.append("Name at least one remaining uncertainty (or write: none found, and why).")
        if not split_lines(conditions):
            problems.append("Say what would change your decision.")
        if amount.strip() and not basis.strip():
            problems.append("An amount or alternative terms need an explicit basis.")
        if problems:
            for p in problems:
                st.error(p)
            return
        final = copy.deepcopy(cv)
        final["uncertainties"] = split_lines(uncertainties)
        final["change_triggers"] = split_lines(conditions)
        final["proposed_terms"] = {"amount": amount.strip(), "basis": basis.strip()}
        state.log("Final record saved")
        rec = record.build(ss.case_name, ss.analyst, config.get_model(), ss.file_name, ss.initial_view,
                           final, ss.rounds, ss.log, ss.label_scheme)
        record.save(rec)
        ss.record = rec
        st.rerun()


def show_record(rec: dict):
    st.success("Record saved. Download it below. It is also written to the records folder on this server (temporary on Streamlit Cloud).")
    st.markdown(record.to_markdown(rec))
    st.divider()
    st.subheader("CEO decision")
    st.caption("The CEO keeps the final authority. The tool only prepares the reasoning.")
    options = ["Not yet decided", "Approve as proposed", "Approve with changes", "Decline", "Ask for more information"]
    ceo_choice = st.selectbox("Decision", options, index=options.index(rec["ceo"]["decision"]))
    ceo_note = st.text_area("Note", value=rec["ceo"]["note"], height=80)
    if st.button("Update the CEO decision in the record"):
        rec["ceo"] = {"decision": ceo_choice, "note": ceo_note}
        record.save(rec)
        st.rerun()
    c1, c2 = st.columns(2)
    stem = f"review_{rec['case_name'].replace(' ', '_')}"
    c1.download_button("Download record (Markdown)", record.to_markdown(rec), file_name=f"{stem}.md")
    c2.download_button("Download record (JSON)", json.dumps(rec, indent=2, ensure_ascii=False), file_name=f"{stem}.json")
    st.info("For the next test file, press **Start a new case** in the sidebar. Keep the same app and reviewer instructions.")


STEP_FUNCS = {1: step_case, 2: step_view, 3: step_challenge, 4: step_response, 5: step_record}
