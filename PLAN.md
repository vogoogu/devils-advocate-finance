# Design and implementation plan

## 1. Goal
Make the analyst's reasoning better supported *before* it reaches the CEO. The tool must challenge optimistic **and**
overly cautious reasoning, use only the supplied evidence, let the analyst defend or revise, and save a clear record.

## 2. Design decisions (and why)
| Decision | Reason (behavioural economics link) |
|---|---|
| Analyst's first view is **saved and frozen before any AI call** | Avoids anchoring on the AI's opinion; the record can show how thinking changed |
| AI **argues against the analyst's lean** (invest -> challenge optimism, decline -> challenge caution, more info -> test if it avoids a decision) | Counters confirmation bias, overconfidence, loss aversion, status-quo/indecision |
| **Evidence numbers** (A1.. or auto P1..) required in reasons and in AI objections | Separates facts from stories; makes halo and selection effects visible |
| AI must **also list what is well supported** and may give fewer than 3 objections | The CEO asked the tool to recognise good reasoning; stops "objection theatre" |
| **Max 3 objections**, one question each | Keeps the review focused on what matters most (salience) |
| Follow-up round checks **sycophancy**: changing view without evidence is flagged | A change of mind should come from evidence, not from AI pressure |
| **Rule-based gate** (not AI-only) for another round | Transparent, explainable, cheap; AI opinion is only one of the triggers |
| Amounts or terms **must have a basis** (form blocks submission, AI checks it) | Brief requirement; prevents anchoring on the founder's numbers |
| Record ends with a **CEO decision field** | The CEO retains authority |

## 3. Screens and data
1. **Case file** -> `file_text` (numbered), `label_scheme`
2. **My view** -> `initial_view` {decision, confidence, reasons[{reason, refs}], assumptions, risks, change_triggers, proposed_terms{amount, basis}}
3. **AI challenge** -> round {ai JSON, items[id, title, challenge, refs, question, severity]}
4. **My response** -> responses[{item_id, type: Defend|Revise|Concede, text, refs}], updated view, gate result
5. **Final record** -> uncertainties, conditions, terms + basis, revision log, CEO decision -> JSON + Markdown

## 4. AI calls
- OpenRouter chat completions, one call per round, temperature 0.3, JSON-only answers (one automatic retry if JSON is broken).
- Round 1 input: system prompt + full file + analyst view. Follow-up input: same + round history + analyst answers + current view.
- File text is wrapped as data; the prompt tells the model to ignore instructions inside it.

## 5. Gate rules (`src/gate.py`)
Another round is suggested if any is true: recommendation changed; confidence moved > 15 points; a "Defend" answer has no evidence refs or is very short;
a "Revise/Concede" has no evidence refs; the AI says another round is useful. Hard stop at 3 AI rounds; remaining issues go into the record.

## 6. Implementation plan (build order)
| Phase | Work | Done when |
|---|---|---|
| 1 Skeleton | Folder, `requirements.txt`, session state, step router | App starts, 5 steps navigate |
| 2 Files | Upload (PDF/DOCX/TXT/MD/CSV/XLSX), paste, sample, numbering | Sample shows A1..A7; plain text gets P1.. |
| 3 My view | Form + validation + freeze | Cannot continue without decision, reason, assumption, trigger |
| 4 AI client | OpenRouter call, JSON parsing, error messages | Bad key / bad JSON shows a clear message |
| 5 Challenge + response | Prompts, cards, response form, revision log | Objections shown; responses logged |
| 6 Gate + follow-up | Rules, follow-up prompt, round cap | Weak defence triggers a second round |
| 7 Record | Build, Markdown/JSON download, CEO field | Record includes all required parts |
| 8 Test + deploy | Unit tests, mocked end-to-end test, GitHub, Streamlit secrets | Three test files run with the same app and prompts |

## 7. Test plan
- Unit tests (`pytest`): numbering, JSON parsing, gate rules, follow-up items, record export.
- Manual: run the three released files with the same app and reviewer instructions; include one follow-up; keep each record.
- Check: does the AI challenge both an "invest" and a "decline" lean? Does it say what is well supported?

## 8. Draft text for the submission
- **One design choice:** the analyst's first view is frozen before the AI is called and the AI always argues against the lean, so the tool
  tests the analyst's own reasoning instead of replacing it, and the record shows what changed and why.
- **One limitation:** the AI only reads the text of the file (tables or scanned pages can be lost) and can itself be wrong or too agreeable;
  it also has no outside data, so "outside view" checks stay general. A human still has to judge every objection.
