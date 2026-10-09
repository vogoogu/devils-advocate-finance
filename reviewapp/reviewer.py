"""Talks to the AI reviewer: builds the text it sees and normalises what comes back."""
from . import openrouter, prompts


def format_view(view: dict) -> str:
    lines = [f"Decision: {view.get('decision', '-')}", f"Confidence: {view.get('confidence', '-')}%", "Strongest reasons:"]
    for r in view.get("reasons", []):
        refs = ", ".join(r.get("refs", [])) or "no refs given"
        lines.append(f"  - {r['reason']} (evidence: {refs})")
    for title, key in (("Key assumptions", "assumptions"), ("Main risks", "risks"),
                       ("What would change my view", "change_triggers"),
                       ("Open uncertainties", "uncertainties")):
        vals = view.get(key) or []
        if vals:
            lines.append(f"{title}:")
            lines += [f"  - {v}" for v in vals]
    terms = view.get("proposed_terms") or {}
    if terms.get("amount"):
        lines.append(f"Proposed amount / terms: {terms['amount']}")
        lines.append(f"Basis given: {terms.get('basis') or 'NONE GIVEN'}")
    return "\n".join(lines)


def format_history(rounds: list) -> str:
    out = []
    for r in rounds:
        out.append(f"ROUND {r['n']} ({r['kind']})")
        for it in r["items"]:
            out.append(f"  AI [{it['id']}] {it['title']}: {it['challenge']} | Question: {it['question']}")
        for resp in r.get("responses") or []:
            refs = ", ".join(resp["refs"]) or "none"
            out.append(f"  Analyst on [{resp['item_id']}] {resp['type'].upper()}: {resp['text']} (evidence cited: {refs})")
        va = r.get("view_after")
        if va:
            out.append(f"  Analyst position after round {r['n']}: {va['decision']}, {va['confidence']}% confident")
    return "\n".join(out)


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.replace(";", ",").split(",") if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def _items_from(objections, prefix: str) -> list:
    items = []
    for i, o in enumerate(objections or [], 1):
        if not isinstance(o, dict):
            continue
        items.append({
            "id": f"{prefix}{i}",
            "title": str(o.get("title") or "Objection"),
            "challenge": str(o.get("challenge") or ""),
            "flaw": str(o.get("reasoning_flaw") or ""),
            "refs": _as_list(o.get("evidence_refs")),
            "question": str(o.get("question_for_analyst") or ""),
            "severity": str(o.get("severity") or "medium").lower(),
        })
    return items


def run_initial(file_text, view, model, api_key):
    msgs = prompts.build_initial_messages(file_text, format_view(view))
    parsed, _raw = openrouter.chat_json(msgs, model, api_key)
    return parsed, _items_from(parsed.get("objections"), "R1-")


def run_followup(file_text, initial_view, rounds, current_view, round_n, model, api_key):
    msgs = prompts.build_followup_messages(
        file_text, format_view(initial_view), format_history(rounds), format_view(current_view)
    )
    parsed, _raw = openrouter.chat_json(msgs, model, api_key)

    prior = {it["id"]: it for r in rounds for it in r["items"]}
    items = []
    for v in parsed.get("verdicts") or []:
        if not isinstance(v, dict):
            continue
        if str(v.get("verdict", "")).lower() == "resolved":
            continue
        oid = str(v.get("objection_id") or "")
        base = prior.get(oid, {})
        items.append({
            "id": oid or f"R{round_n}-open{len(items) + 1}",
            "title": base.get("title", "Earlier objection"),
            "challenge": str(v.get("remaining_concern") or v.get("comment") or ""),
            "flaw": base.get("flaw", ""),
            "refs": base.get("refs", []),
            "question": str(v.get("question_for_analyst") or ""),
            "severity": base.get("severity", "medium"),
        })
    items += _items_from(parsed.get("new_objections"), f"R{round_n}-N")
    return parsed, items
