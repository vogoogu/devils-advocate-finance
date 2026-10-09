"""Read uploaded files into plain text and add evidence labels."""
import io
import re

import pandas as pd

from . import config

LABEL_RE = re.compile(r"^\s*(?:#+\s*)?([A-Z]{1,2}\d{1,2})\s+\S")


def read_uploaded(uploaded) -> str:
    name = uploaded.name.lower()
    data = uploaded.getvalue()
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        return _read_pdf(io.BytesIO(data))
    if name.endswith(".docx"):
        return _read_docx(io.BytesIO(data))
    if name.endswith(".csv"):
        return pd.read_csv(io.BytesIO(data)).to_string(index=False)
    if name.endswith(".xlsx"):
        sheets = pd.read_excel(io.BytesIO(data), sheet_name=None)
        return "\n\n".join(f"Sheet: {n}\n{df.to_string(index=False)}" for n, df in sheets.items())
    raise ValueError("Unsupported file type.")


def _read_pdf(buf) -> str:
    from pypdf import PdfReader

    reader = PdfReader(buf)
    pages = [(p.extract_text() or "").strip() for p in reader.pages]
    return "\n\n".join(p for p in pages if p)


def _read_docx(buf) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(buf)
    blocks = []
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = Paragraph(child, doc).text.strip()
            if text:
                blocks.append(text)
        elif child.tag.endswith("}tbl"):
            table = Table(child, doc)
            for row in table.rows:
                blocks.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n\n".join(blocks)


def add_labels(text: str):
    """Make sure every part of the file has a label the AI and the analyst can cite.

    If the file already has labels like A1, A2, A3 they are kept.
    Otherwise every paragraph gets a label [P1], [P2], ...
    Returns (labelled_text, scheme) where scheme is "existing" or "auto".
    """
    text = text.strip()
    found = {m.group(1) for line in text.splitlines() if (m := LABEL_RE.match(line))}
    if len(found) >= 3:
        return text, "existing"

    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) < 5:
        blocks = [b.strip() for b in text.splitlines() if b.strip()]
    labelled = "\n\n".join(f"[P{i}] {b}" for i, b in enumerate(blocks, 1))
    return labelled, "auto"


def truncate(text: str):
    if len(text) <= config.MAX_FILE_CHARS:
        return text, False
    return text[: config.MAX_FILE_CHARS], True
