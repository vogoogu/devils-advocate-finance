"""Small helpers: text splitting, table conversion, view objects."""
import re
from datetime import datetime

import pandas as pd


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def split_lines(text: str) -> list:
    out = []
    for line in (text or "").splitlines():
        cleaned = line.strip().lstrip("-•*·").strip()
        if cleaned:
            out.append(cleaned)
    return out


def split_refs(text: str) -> list:
    return [r.strip() for r in re.split(r"[,;]", text or "") if r.strip()]


def reasons_to_df(reasons: list, min_rows: int = 3) -> pd.DataFrame:
    rows = [
        {"Reason": r.get("reason", ""), "Evidence refs": ", ".join(r.get("refs", []))}
        for r in reasons
    ]
    while len(rows) < min_rows:
        rows.append({"Reason": "", "Evidence refs": ""})
    return pd.DataFrame(rows)


def df_to_reasons(df: pd.DataFrame) -> list:
    out = []
    for _, row in df.iterrows():
        reason = row.get("Reason")
        refs = row.get("Evidence refs")
        reason = "" if pd.isna(reason) else str(reason).strip()
        refs = "" if pd.isna(refs) else str(refs)
        if reason:
            out.append({"reason": reason, "refs": split_refs(refs)})
    return out


def make_view(decision, confidence, reasons, assumptions, risks, triggers,
              amount="", basis="", uncertainties=None) -> dict:
    return {
        "decision": decision,
        "confidence": int(confidence),
        "reasons": reasons,
        "assumptions": assumptions,
        "risks": risks,
        "change_triggers": triggers,
        "proposed_terms": {"amount": (amount or "").strip(), "basis": (basis or "").strip()},
        "uncertainties": uncertainties or [],
    }
