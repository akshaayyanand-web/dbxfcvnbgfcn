"""The one common shape every source is normalised into.

Every adapter converts its source into exactly two things: Nodes and Edges.
Nothing downstream (resolver, graph, detectors, frontend) knows or cares which
API a record came from.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

PERSON = "person"
COMPANY = "company"
ADDRESS = "address"
UNKNOWN = "unknown"

# Edge types
OWNS = "owns"
DIRECTS = "directs"
SHAREHOLDER_OF = "shareholder_of"
REGISTERED_AT = "registered_at"
LINKED_TO = "linked_to"
POSSIBLY_SAME_AS = "possibly_same_as"

_COMPANY_SUFFIXES = {
    "ltd", "limited", "llc", "lllc", "inc", "incorporated", "corp", "corporation",
    "plc", "gmbh", "ag", "sa", "sarl", "bv", "nv", "oy", "ab", "as", "aps",
    "fze", "fzc", "fzco", "fz", "dmcc", "llp", "lp", "pte", "pty", "co",
    "company", "holdings", "holding", "group", "trust", "foundation", "spa",
    "srl", "sl", "kft", "zrt", "doo", "ou", "ug", "pjsc", "jsc", "psc",
}

_PERSON_TITLES = {"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "hh", "he", "sheikh"}

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")
# "A.C.M.E." is one word, not four. Collapse dotted acronyms before the general
# punctuation pass turns every period into a space.
_ACRONYM = re.compile(r"\b(?:[A-Za-z]\.){2,}")


def normalise_name(name: str, entity_type: str = UNKNOWN) -> str:
    """Lowercase, strip punctuation, strip legal-form suffixes and honorifics.

    "Falcon Capital Holdings FZE" and "falcon capital holdings" collapse to the
    same key, which is what makes fuzzy matching usable at all.
    """
    if not name:
        return ""
    text = _ACRONYM.sub(lambda m: m.group(0).replace(".", ""), name)
    text = _PUNCT.sub(" ", text.lower())
    text = _SPACE.sub(" ", text).strip()
    tokens = [t for t in text.split(" ") if t]
    drop = _COMPANY_SUFFIXES if entity_type != PERSON else _PERSON_TITLES
    while tokens and tokens[-1] in drop:
        tokens.pop()
    while tokens and tokens[0] in _PERSON_TITLES:
        tokens.pop(0)
    return " ".join(tokens)


def year_of(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    match = re.match(r"(\d{4})", str(date_str))
    return match.group(1) if match else None


def norm_country(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    # OpenCorporates jurisdiction codes look like "ae_du" or "gb"; keep the country part.
    return text.split("_")[0][:2] if len(text) <= 6 else text


@dataclass
class Node:
    id: str
    type: str
    name: str
    country: Optional[str] = None
    birth_date: Optional[str] = None
    reg_number: Optional[str] = None
    jurisdiction: Optional[str] = None
    status: Optional[str] = None
    sources: set = field(default_factory=set)
    source_ids: set = field(default_factory=set)   # e.g. "opensanctions:NK-abc123"
    risk_flags: set = field(default_factory=set)
    source_urls: list = field(default_factory=list)
    aliases: set = field(default_factory=set)
    notes: list = field(default_factory=list)

    @property
    def key_name(self) -> str:
        return normalise_name(self.name, self.type)

    def merge(self, other: "Node") -> None:
        """Fold another record for the same real-world entity into this one."""
        if other.name and other.name != self.name:
            self.aliases.add(other.name)
        self.aliases |= other.aliases
        self.sources |= other.sources
        self.source_ids |= other.source_ids
        self.risk_flags |= other.risk_flags
        for url in other.source_urls:
            if url not in self.source_urls:
                self.source_urls.append(url)
        for note in other.notes:
            if note not in self.notes:
                self.notes.append(note)
        for attr in ("country", "birth_date", "reg_number", "jurisdiction", "status"):
            if not getattr(self, attr) and getattr(other, attr):
                setattr(self, attr, getattr(other, attr))
        if self.type in (UNKNOWN, None) and other.type not in (UNKNOWN, None):
            self.type = other.type

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "country": self.country,
            "birth_date": self.birth_date,
            "reg_number": self.reg_number,
            "jurisdiction": self.jurisdiction,
            "status": self.status,
            "sources": sorted(self.sources),
            "source_ids": sorted(self.source_ids),
            "risk_flags": sorted(self.risk_flags),
            "source_urls": self.source_urls,
            "aliases": sorted(self.aliases),
            "notes": self.notes,
        }


@dataclass
class Edge:
    source: str
    target: str
    type: str
    share_pct: Optional[float] = None
    role: Optional[str] = None
    origin: Optional[str] = None
    confidence: float = 1.0
    start_date: Optional[str] = None
    end_date: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "target": self.target,
            "type": self.type,
            "share_pct": self.share_pct,
            "role": self.role,
            "origin": self.origin,
            "confidence": self.confidence,
            "start_date": self.start_date,
            "end_date": self.end_date,
            # A dashed edge in the UI means "the resolver thinks these might be
            # the same entity" — a lead to check, never an assertion.
            "asserted": self.type != POSSIBLY_SAME_AS,
        }
