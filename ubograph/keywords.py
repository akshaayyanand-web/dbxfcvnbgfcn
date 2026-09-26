"""The structured adverse-media keyword string and the manual search it builds.

Adverse media screening only counts as "structured" under FATF guidance if
it is repeatable and documented — a compliance officer typing a bare name
into Google and scrolling five results is neither. This module is the fixed
input side of that: one AML/CFT keyword taxonomy, always the same unless a
screener deliberately edits it for a session, joined with the subject's
name into a single reproducible query. Anyone can hand-verify a finding by
re-running the exact same search.

This module never calls the network. It only builds a query string and the
URL a human (or the AI adverse-media search in sources/adverse_media.py)
would run against it. Nothing here requires an API key.
"""
from typing import Iterable, Optional
from urllib.parse import urlencode

# Five typology categories, matching how FATF and UAE supervisors group
# financial-crime risk for CDD/EDD purposes. Order is preserved end to end
# so a screener editing the string in the UI sees the same grouping.
CATEGORIES: dict[str, list[str]] = {
    "Money laundering & financial crime": [
        "launder", "money laundering", "financial crime", "economic crime",
        "fraud", "embezzle", "extortion", "kickback", "forgery",
        "counterfeiting", "identity theft", "ponzi", "pyramid scheme",
        "insider trading", "market manipulation", "accounting fraud",
        "asset misappropriation", "tax evasion", "tax fraud", "vat fraud",
        "cyber fraud", "wire fraud",
    ],
    "Terrorist financing": [
        "terrorism", "terrorist financing", "financing of terrorism",
        "terror funding", "extremist", "radicalisation",
        "designated terrorist", "militant",
    ],
    "Proliferation financing": [
        "proliferation financing", "weapons of mass destruction", "wmd",
        "dual-use", "sanctions evasion", "arms trafficking",
        "weapons smuggling", "nuclear", "chemical weapons",
        "biological weapons",
    ],
    "Corruption, bribery & organised crime": [
        "corrupt", "bribe", "corruption", "abuse of power",
        "conflict of interest", "misuse of funds", "kleptocracy",
        "state capture", "organised crime", "drug trafficking",
        "narcotics", "cartel", "human trafficking", "people smuggling",
        "forced labour", "modern slavery", "wildlife trafficking",
        "cybercrime", "ransomware", "darknet",
    ],
    "Legal, criminal & regulatory proceedings": [
        "arrest", "blackmail", "breach", "convicted", "court case",
        "felon", "fined", "guilty", "illegal", "imprisonment", "jail",
        "litigation", "murder", "prosecuted", "sanctions", "theft",
        "unlawful", "verdict", "debarred", "blacklisted",
        "regulatory breach",
    ],
}

DEFAULT_KEYWORDS: list[str] = [term for terms in CATEGORIES.values() for term in terms]

CLASSIFICATIONS = ("unreviewed", "confirmed", "partial", "false", "no_match")
CLASSIFICATION_LABELS = {
    "unreviewed": "Unreviewed",
    "confirmed": "Confirmed match",
    "partial": "Partial match",
    "false": "False match",
    "no_match": "No match",
}
# Highest severity wins when deriving the overall decision from a set of
# per-finding classifications — same logic AML screening tools use to roll
# many results up into one outcome.
_SEVERITY_ORDER = {"confirmed": 3, "partial": 2, "false": 1, "no_match": 0, "unreviewed": -1}


def overall_decision(classifications: Iterable[str]) -> str:
    """The single most severe classification present, or "unreviewed" if
    every result is still unclassified, or "no_match" if there is nothing
    to classify at all."""
    values = [c for c in classifications if c in _SEVERITY_ORDER]
    if not values:
        return "no_match"
    if all(v == "unreviewed" for v in values):
        return "unreviewed"
    reviewed = [v for v in values if v != "unreviewed"]
    return max(reviewed, key=lambda v: _SEVERITY_ORDER[v])


def build_query(name: str, aka: Optional[str] = None, nationality: Optional[str] = None,
                 associated_company: Optional[str] = None,
                 keywords: Optional[Iterable[str]] = None) -> str:
    """The single Google query: the subject (and AND-joined context) against
    every keyword, OR-joined. `keywords` lets a screener narrow or extend the
    default list for one session without changing it for anyone else."""
    terms = list(keywords) if keywords is not None else DEFAULT_KEYWORDS
    subject_bits = [f'"{name.strip()}"'] if name and name.strip() else []
    if aka and aka.strip():
        subject_bits.append(f'OR "{aka.strip()}"')
    subject = " ".join(subject_bits)
    context_bits = []
    if nationality and nationality.strip():
        context_bits.append(f'"{nationality.strip()}"')
    if associated_company and associated_company.strip():
        context_bits.append(f'"{associated_company.strip()}"')
    context = " ".join(context_bits)
    keyword_clause = "(" + " OR ".join(f'"{t}"' if " " in t else t for t in terms) + ")"
    parts = [p for p in (subject, context, keyword_clause) if p]
    return " ".join(parts)


def search_url(query: str) -> str:
    return "https://www.google.com/search?" + urlencode({"q": query})


def general_search_url(name: str) -> str:
    """A plain, unfiltered search on just the subject's name — for general
    background research alongside the keyword-filtered adverse-media query,
    not a replacement for it."""
    return search_url(f'"{name.strip()}"') if name and name.strip() else ""


def manual_search(name: str, aka: Optional[str] = None, nationality: Optional[str] = None,
                   associated_company: Optional[str] = None,
                   keywords: Optional[Iterable[str]] = None) -> dict:
    """Everything the UI needs to offer a "run this in your browser" link —
    available with no configuration and no API key at all."""
    terms = list(keywords) if keywords is not None else DEFAULT_KEYWORDS
    query = build_query(name, aka=aka, nationality=nationality,
                         associated_company=associated_company, keywords=terms)
    return {
        "query": query,
        "url": search_url(query),
        "keyword_count": len(terms),
        "general_url": general_search_url(name),
    }
