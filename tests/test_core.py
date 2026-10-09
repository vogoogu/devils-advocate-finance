import copy
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reviewapp import files, gate, openrouter, record, reviewer
from reviewapp.util import make_view

SAMPLE = (Path(__file__).resolve().parent.parent / "data" / "asterflow_sample.md").read_text(encoding="utf-8")


def view(decision="Request more information", conf=60):
    return make_view(decision, conf, [{"reason": "r", "refs": ["A2"]}], ["a"], ["risk"], ["trigger"])


def test_existing_labels_kept():
    text, scheme = files.add_labels(SAMPLE)
    assert scheme == "existing" and "A4 Growth forecast" in text


def test_auto_labels_for_plain_text():
    text, scheme = files.add_labels("First paragraph.\n\nSecond one.\n\nThird.")
    assert scheme == "auto" and text.startswith("[P1] First")


def test_truncate():
    long = "x" * 70000
    out, cut = files.truncate(long)
    assert cut and len(out) == 60000


def test_extract_json_variants():
    assert openrouter.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert openrouter.extract_json('Sure! {"a": 2} Hope that helps') == {"a": 2}


def test_gate_triggers():
    prev, new = view(), view("Decline", 30)
    resp = [{"item_id": "R1-1", "type": "Defend", "text": "no", "refs": []}]
    g = gate.evaluate(prev, new, resp, {}, rounds_done=1)
    assert g["needed"] and len(g["reasons"]) >= 3


def test_gate_quiet_when_stable_and_evidenced():
    prev = view()
    resp = [{"item_id": "R1-1", "type": "Defend", "text": " ".join(["word"] * 20), "refs": ["A3"]}]
    g = gate.evaluate(prev, copy.deepcopy(prev), resp, {}, rounds_done=1)
    assert not g["needed"] and not g["reasons"]


def test_gate_cap():
    prev, new = view(), view("Decline", 10)
    g = gate.evaluate(prev, new, [], {}, rounds_done=3)
    assert g["capped"] and not g["needed"]


def test_followup_items_and_record(monkeypatch):
    round1 = {"n": 1, "kind": "challenge", "ai": {"overall_assessment": "ok"},
              "items": [{"id": "R1-1", "title": "Forecast", "challenge": "c", "flaw": "", "refs": ["A4"],
                         "question": "q", "severity": "high"}],
              "responses": [{"item_id": "R1-1", "title": "Forecast", "type": "Defend", "text": "t", "refs": ["A4"]}],
              "view_after": view(), "gate": {"needed": False, "capped": False, "reasons": []}}
    fake = {"verdicts": [{"objection_id": "R1-1", "verdict": "unresolved", "remaining_concern": "still open",
                          "question_for_analyst": "why?"}],
            "new_objections": [{"title": "New", "challenge": "n", "question_for_analyst": "q2"}],
            "adequately_supported": False, "another_round_useful": True, "reason": "x"}
    monkeypatch.setattr(openrouter, "chat_json", lambda *a, **k: (fake, "raw"))
    parsed, items = reviewer.run_followup("file", view(), [round1], view(), 2, "m", "k")
    assert [i["id"] for i in items] == ["R1-1", "R2-N1"]
    round2 = {"n": 2, "kind": "follow-up", "ai": parsed, "items": items, "responses": None,
              "view_after": None, "gate": None}
    final = view()
    final["uncertainties"] = ["u"]
    rec = record.build("Test", "me", "m", "f.md", view(), final, [round1, round2], [], "existing")
    md = record.to_markdown(rec)
    assert "Round 2" in md and "R2-N1" in md and "CEO decision" in md
