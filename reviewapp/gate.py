"""Decision gate: is another AI review round useful? Plain rules, easy to explain."""
from . import config


def evaluate(prev_view, new_view, responses, ai, rounds_done,
             max_rounds=config.MAX_AI_ROUNDS, threshold=config.CONFIDENCE_SWING_THRESHOLD):
    reasons = []

    if prev_view["decision"] != new_view["decision"]:
        reasons.append(f"The recommendation changed ({prev_view['decision']} to {new_view['decision']}), so the new position should be tested.")

    swing = abs(new_view["confidence"] - prev_view["confidence"])
    if swing > threshold:
        reasons.append(f"Confidence moved by {swing} points (limit: {threshold}).")

    weak = [r["item_id"] for r in responses
            if r["type"] == "Defend" and (not r["refs"] or len(r["text"].split()) < 12)]
    if weak:
        reasons.append("Defended without evidence references or enough detail: " + ", ".join(weak) + ".")

    no_evidence = [r["item_id"] for r in responses if r["type"] in ("Revise", "Concede") and not r["refs"]]
    if no_evidence:
        reasons.append("Revised or conceded without citing evidence: " + ", ".join(no_evidence)
                       + ". Check this is not just agreeing with the AI.")

    if ai and ai.get("another_round_useful") is True:
        why = ai.get("reason") or "no reason given"
        reasons.append(f"The AI thinks another round would help: {why}")

    capped = rounds_done >= max_rounds
    return {
        "needed": bool(reasons) and not capped,
        "capped": capped and bool(reasons),
        "reasons": reasons,
    }
