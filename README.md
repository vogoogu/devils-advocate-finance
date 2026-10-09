# Before we invest: decision review tool

Student prototype for the *AI Driven Decision Making* course (Westbridge Capital, fictional scenario).
An analyst forms their own view of an investment file, an AI **Devil's Advocate** challenges it, the analyst
defends or revises, and a **review record** is saved for the CEO. The CEO keeps the final authority.

## How it works (5 steps)
1. **Case file**: upload a PDF, Word, text, CSV or Excel file (or paste text, or load the AsterFlow sample).
   Every part of the file gets a number (A1, A2 ... or P1, P2 ...) so reasoning can cite evidence.
2. **My view** (before AI): recommendation, reasons with evidence numbers, assumptions, risks, confidence, what would change my view.
   Saved and frozen.
3. **AI challenge**: the file plus my reasoning go to the AI through OpenRouter. It argues *against* my lean
   (challenges optimism *and* excess caution), lists what is well supported and flags amounts or terms without a basis.
4. **My response**: defend, revise or concede each point. A simple **gate** then decides whether another AI round is useful
   (recommendation changed, confidence moved more than 15 points, weak defence, concession without evidence, or the AI asks for one). Maximum 3 AI rounds.
5. **Final record**: reasons, confidence before/after, unresolved uncertainties, conditions that would change the decision,
   amounts or terms with their basis, revision log, and a field for the CEO's decision. Download as Markdown or JSON.

The reviewer instructions are in `reviewapp/prompts.py` and are shown in the app (sidebar, "Reviewer instructions").

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then put your OpenRouter key inside
streamlit run app.py
```
No secrets file? Paste the key into the sidebar instead (kept only for the browser session).

## Deploy on Streamlit Community Cloud
1. Push this folder to a GitHub repository (the real key is git-ignored; never commit it).
2. On share.streamlit.io choose **New app**, pick the repo, main file `app.py`.
3. App **Settings -> Secrets**, add: `OPENROUTER_API_KEY = "sk-or-..."`
4. Deploy. Saved records on the server are temporary, so download each record at the end.

## Run the tests
```bash
pip install pytest
pytest -q
```

## Folder
```
app.py                    entry point (page + step router)
reviewapp/config.py             settings, models, gate thresholds
reviewapp/steps.py              the five screens + sidebar
reviewapp/prompts.py            reviewer instructions (Devil's Advocate)
reviewapp/reviewer.py           builds what the AI sees, reads its JSON answer
reviewapp/openrouter.py         OpenRouter API client
reviewapp/files.py              file reading + evidence numbering
reviewapp/gate.py               rules for "is another review useful?"
reviewapp/record.py             review record: build, save, Markdown export
reviewapp/state.py, util.py     session state, helpers
data/asterflow_sample.md  the AsterFlow file as text (for testing)
tests/test_core.py        unit tests
records/                  saved review records (created at runtime)
PLAN.md                   app design and implementation plan
```
