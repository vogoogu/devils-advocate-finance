"""Build, save and print the review record that goes to the CEO."""
import json
import re

from . import config
from .util import now_iso


def build(case_name, analyst, model, file_name, initial_view, final_view, rounds, log, label_scheme):
    last_ai = rounds[-1]["ai"] if rounds else {}
    return {
        "case_name": case_name,
        "analyst": analyst,
        "created": now_iso(),
        "model": model,
        "file_name": file_name,
        "evidence_labels": label_scheme,
        "initial_view": initial_view,
        "final_view": final_view,
        "rounds": [
            {
                "round": r["n"],
                "kind": r["kind"],
                "model": r.get("model"),
                "ai_output": r["ai"],
                "items": r["items"],
                "analyst_responses": r.get("responses"),
                "position_after": r.get("view_after"),
                "gate": r.get("gate"),
            }
            for r in rounds
        ],
        "ai_last_assessment": {
            "adequately_supported": last_ai.get("adequately_supported"),
            "overall": last_ai.get("overall_assessment") or last_ai.get("recommendation_check"),
        },
        "revision_log": log,
        "ceo": {"decision": "Not yet decided", "note": ""},
    }


def _bullets(items):
    return "\n".join(f"- {i}" for i in items) if items else "- (none)"


def _reasons(reasons):
    if not reasons:
        return "- (none)"
    return "\n".join(f"- {r['reason']} *(evidence: {', '.join(r['refs']) or 'none cited'})*" for r in reasons)


def to_markdown(rec: dict) -> str:
    iv, fv = rec["initial_view"], rec["final_view"]
    terms = fv.get("proposed_terms") or {}
    md = [
        f"# Review record: {rec['case_name']}",
        f"Analyst: {rec['analyst'] or '-'} | Created: {rec['created']} | File: {rec['file_name']} | AI model: {rec['model']}",
        "",
        "## Recommendation",
        "| | Before AI | Final |",
        "|---|---|---|",
        f"| Decision | {iv['decision']} | {fv['decision']} |",
        f"| Confidence | {iv['confidence']}% | {fv['confidence']}% |",
        "",
        "## Final reasons", _reasons(fv["reasons"]), "",
        "## Key assumptions", _bullets(fv["assumptions"]), "",
        "## Main risks", _bullets(fv["risks"]), "",
        "## Unresolved uncertainties", _bullets(fv["uncertainties"]), "",
        "## What would change the decision", _bullets(fv["change_triggers"]), "",
        "## Amount or alternative terms",
    ]
    if terms.get("amount"):
        md += [f"- Proposal: {terms['amount']}", f"- Basis: {terms.get('basis') or '(none)'}"]
    else:
        md.append("- None proposed")
    last = rec["ai_last_assessment"]
    md += ["", "## AI reviewer's last assessment",
           f"- Adequately supported: {last.get('adequately_supported')}",
           f"- Comment: {last.get('overall') or '-'}", "", "## Review rounds"]
    for r in rec["rounds"]:
        md.append(f"### Round {r['round']} ({r['kind']})")
        resp = {x["item_id"]: x for x in (r.get("analyst_responses") or [])}
        if not r["items"]:
            md.append("- AI raised no open objections.")
        for it in r["items"]:
            md.append(f"**{it['id']} {it['title']}** ({it['severity']}): {it['challenge']}")
            md.append(f"- Question: {it['question']}")
            a = resp.get(it["id"])
            if a:
                md.append(f"- Analyst ({a['type']}): {a['text']} *(evidence: {', '.join(a['refs']) or 'none'})*")
        g = r.get("gate")
        if g:
            md.append(f"- Gate: {'another round suggested' if g['needed'] else 'no further round needed'}"
                      + (" (round limit reached)" if g.get("capped") else ""))
            md += [f"  - {x}" for x in g["reasons"]]
        md.append("")
    md += ["## Revision log"] + [f"- {e['time']}: {e['event']}" + (f" ({e['detail']})" if e["detail"] else "") for e in rec["revision_log"]]
    md += ["", "## CEO decision (the CEO keeps the final authority)",
           f"- Decision: {rec['ceo']['decision']}", f"- Note: {rec['ceo']['note'] or '-'}"]
    return "\n".join(md)


def save(rec: dict):
    """Write JSON + Markdown into records/. Returns the JSON path, or None if the disk is read-only."""
    try:
        config.RECORDS_DIR.mkdir(exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", rec["case_name"].lower()).strip("-") or "case"
        stamp = rec["created"].replace(":", "").replace("-", "")
        base = config.RECORDS_DIR / f"{stamp}_{slug}"
        base.with_suffix(".json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        base.with_suffix(".md").write_text(to_markdown(rec), encoding="utf-8")
        return base.with_suffix(".json")
    except OSError:
        return None
