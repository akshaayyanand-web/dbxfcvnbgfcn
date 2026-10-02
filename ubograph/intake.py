"""Pulls a counterparty name straight off an uploaded document (purchase
order, onboarding form, invoice) instead of someone typing it in.

Deliberately simple and deterministic — no AI model call, nothing sent to a
third party. It looks for a labelled line ("Buyer:", "Counterparty:", etc.)
and falls back to the first capitalised multi-word line in the document. A
free-text document with no such label returns no match; this is a quick
intake shortcut, not a document-understanding engine.
"""
import re
from io import BytesIO
from typing import Optional

LABELS = (
    "counterparty", "buyer", "client", "customer", "customer name",
    "purchased by", "purchaser", "company", "company name", "vendor",
    "seller", "supplier", "name", "full name", "account holder",
)

_COMPANY_HINT = re.compile(
    r"\b(ltd|llc|fze|fzc|inc|incorporated|corp|corporation|plc|llp|co\.|company|holdings|group|trading)\b",
    re.IGNORECASE,
)
_CAPITALISED_LINE = re.compile(r"^(?:[A-Z][\w.&'-]*\s*){2,6}$")


def extract_text(filename: str, raw: bytes) -> str:
    """Best-effort plain text from an uploaded .pdf or .txt file."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return raw.decode("utf-8", errors="ignore")


def _guess_entity_type(name: str) -> str:
    return "company" if _COMPANY_HINT.search(name) else "person"


def extract_counterparty(text: str) -> dict:
    """{"name": str|None, "entity_type": "person"|"company"|"any", "matched_label": str|None}"""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        label, _, value = line.partition(":")
        label = label.strip().lower()
        value = value.strip().strip('"')
        if label in LABELS and value:
            return {"name": value, "entity_type": _guess_entity_type(value), "matched_label": label}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if _CAPITALISED_LINE.match(line) and len(line) <= 80:
            return {"name": line, "entity_type": _guess_entity_type(line), "matched_label": None}

    return {"name": None, "entity_type": "any", "matched_label": None}
