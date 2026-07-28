"""Turns a raw OpenSanctions entity into the full dossier a lawyer wants to read.

OpenSanctions publishes far more than a name and a flag: patronymic, place of
birth, passport and national ID numbers, addresses, positions held, the sanction
record itself (authority, programme, reason, listing date) and which published
list it came from — "NACTA List of Proscribed Persons", not "pk_nacta".

This module extracts all of it, and merges several records into one dossier
without repeating a value that appears on more than one list.
"""
from typing import Dict, List, Optional

from schema import english_name

# Display groups, in report order. Anything not listed still appears, under
# "Other recorded details" — a new FollowTheMoney property should never vanish
# silently just because this file predates it.
PROPERTY_GROUPS = [
    # `name` and `alias` are deliberately absent: the report already carries one
    # chosen English name as its heading, and repeating every spelling and script
    # variant under it made the identity block noise rather than information.
    ("Identity", [
        "firstName", "middleName", "secondName",
        "lastName", "fatherName", "patronymic", "motherName", "nameSuffix",
        "title", "gender", "birthDate", "birthPlace", "birthCountry",
        "deathDate", "position", "religion", "ethnicity", "education",
    ]),
    ("Nationality & country", [
        "nationality", "citizenship", "country", "jurisdiction", "mainCountry",
    ]),
    ("Identifiers", [
        "idNumber", "passportNumber", "taxNumber", "socialSecurityNumber",
        "innCode", "ogrnCode", "okpoCode", "registrationNumber", "leiCode",
        "swiftBic", "dunsCode", "imoNumber", "ticker", "isin", "npiCode",
        "unscId", "wikidataId", "sourceUrl",
    ]),
    ("Contact & address", [
        "address", "postalCode", "phone", "email", "website",
    ]),
    ("Status & classification", [
        "status", "classification", "program", "topics", "keywords", "notes",
        "summary", "createdAt", "modifiedAt", "retrievedAt",
    ]),
]

LABELS = {
    "name": "Name", "alias": "Also known as", "weakAlias": "Weak alias",
    "firstName": "First name", "middleName": "Middle name", "secondName": "Second name",
    "lastName": "Last name", "fatherName": "Patronymic / father's name",
    "patronymic": "Patronymic", "motherName": "Mother's name",
    "nameSuffix": "Name suffix", "title": "Title", "gender": "Gender",
    "birthDate": "Date of birth", "birthPlace": "Place of birth",
    "birthCountry": "Country of birth", "deathDate": "Date of death",
    "position": "Position held", "religion": "Religion", "ethnicity": "Ethnicity",
    "education": "Education", "nationality": "Nationality", "citizenship": "Citizenship",
    "country": "Country", "jurisdiction": "Jurisdiction", "mainCountry": "Main country",
    "idNumber": "National ID number", "passportNumber": "Passport number",
    "taxNumber": "Tax number", "socialSecurityNumber": "Social security number",
    "innCode": "INN code", "ogrnCode": "OGRN code", "okpoCode": "OKPO code",
    "registrationNumber": "Registration number", "leiCode": "LEI code",
    "swiftBic": "SWIFT / BIC", "dunsCode": "DUNS", "imoNumber": "IMO number",
    "ticker": "Ticker", "isin": "ISIN", "npiCode": "NPI code",
    "unscId": "UN Security Council ID", "wikidataId": "Wikidata",
    "sourceUrl": "Source URL", "address": "Address", "postalCode": "Postal code",
    "phone": "Phone", "email": "Email", "website": "Website", "status": "Status",
    "classification": "Classification", "program": "Sanctions programme",
    "topics": "Topics", "keywords": "Keywords", "notes": "Notes",
    "summary": "Summary", "createdAt": "First recorded", "modifiedAt": "Last modified",
    "retrievedAt": "Retrieved",
}

# Properties handled elsewhere in the report, or pure plumbing.
SKIP = {"name", "alias", "weakAlias", "sanctions", "addressEntity", "associates", "familyPerson", "familyRelative",
        "ownershipOwner", "ownershipAsset", "directorshipDirector",
        "directorshipOrganization", "membershipMember", "membershipOrganization",
        "employmentEmployee", "employmentEmployer", "positionOccupancies",
        "parent", "children", "proof"}

# For each relationship schema: (property naming the first party, property naming
# the second, how it reads when the subject is the first party, how it reads when
# the subject is the second). FollowTheMoney relationships are DIRECTED — a
# Family record says "the relative is the <relationship> of the person" — so which
# side the subject sits on decides the wording entirely.
RELATIONSHIP_SPECS = {
    "Family":         ("person", "relative", "{term}", "{term} of"),
    "Associate":      ("person", "associate", "Associate", "Associate"),
    "Ownership":      ("owner", "asset", "Owner of", "Owned by"),
    "Directorship":   ("director", "organization", "Director of", "Directed by"),
    "Membership":     ("member", "organization", "Member of", "Has member"),
    "Employment":     ("employee", "employer", "Employed by", "Employs"),
    "Representation": ("agent", "client", "Acts for", "Represented by"),
    "Succession":     ("predecessor", "successor", "Succeeded by", "Successor to"),
    "UnknownLink":    ("subject", "object", "Linked to", "Linked to"),
}

RELATIONSHIP_LABELS = {schema: schema for schema in RELATIONSHIP_SPECS}
RELATIONSHIP_LABELS["UnknownLink"] = "Linked"

TERM_KEYS = ("relationship", "role", "description", "position")


def _label(key: str) -> str:
    if key in LABELS:
        return LABELS[key]
    # camelCase -> "Camel case", so an unmapped property is still readable.
    spaced = "".join(f" {c.lower()}" if c.isupper() else c for c in key).strip()
    return spaced[:1].upper() + spaced[1:]


def _stringify(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("caption") or value.get("id")
    text = str(value).strip()
    return text or None


def _dedupe(values: List[str]) -> List[str]:
    """Preserve order, drop repeats case-insensitively.

    The same passport number appearing on four sanctions lists is one fact, and
    a report that prints it four times reads like four findings.
    """
    seen, out = set(), []
    for value in values:
        if not value:
            continue
        key = " ".join(str(value).lower().split())
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def parse_sanction(entity: dict, dataset_titles: Dict[str, dict]) -> dict:
    props = entity.get("properties") or {}

    def first(key):
        values = props.get(key) or []
        return _stringify(values[0]) if values else None

    def every(key):
        return _dedupe([_stringify(v) for v in (props.get(key) or [])])

    datasets = entity.get("datasets") or []
    return {
        "authority": first("authority") or first("country"),
        "program": first("program"),
        "reason": first("reason") or first("summary"),
        "provisions": every("provisions"),
        "status": first("status"),
        "listing_date": first("listingDate"),
        "start_date": first("startDate"),
        "end_date": first("endDate"),
        "unsc_id": first("unscId"),
        "authority_id": first("authorityId"),
        "source_url": first("sourceUrl"),
        "country": first("country"),
        "datasets": [dataset_titles.get(d, {"name": d, "title": d}) for d in datasets],
    }


def _endpoints(inner: dict, prop: str):
    """Both shapes an endpoint arrives in: an inlined entity, or a bare id."""
    out = []
    for value in inner.get(prop) or []:
        if isinstance(value, dict):
            out.append({"id": value.get("id"), "name": value.get("caption"), "inline": True})
        elif isinstance(value, str):
            out.append({"id": value, "name": None, "inline": False})
    return out


def parse_relationships(entity: dict) -> List[dict]:
    """Family, associates, ownership and the rest, worded from the subject's side.

    Getting this wrong is not cosmetic. A Family record states that the relative
    is the mother of the person; read from the mother's own record without
    checking sides, that becomes a child she does not have. So the subject's
    position is established first, and the source's own term is never inverted —
    when the subject is the "mother of" someone, it says exactly that.
    """
    props = entity.get("properties") or {}
    entity_id = entity.get("id")
    out = []

    for values in props.values():
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            schema = value.get("schema")
            if schema not in RELATIONSHIP_SPECS:
                continue

            inner = value.get("properties") or {}
            prop_a, prop_b, forward, reverse = RELATIONSHIP_SPECS[schema]
            side_a, side_b = _endpoints(inner, prop_a), _endpoints(inner, prop_b)

            if any(e["id"] == entity_id for e in side_a):
                template, others = forward, side_b
            elif any(e["id"] == entity_id for e in side_b):
                template, others = reverse, side_a
            else:
                # Subject named on neither side (it can be absent from a nested
                # payload). Fall back to the forward reading, which is how the
                # record is written, rather than guessing.
                template, others = forward, side_b or side_a

            other = next((e for e in others if e.get("name")), None)
            if not other:
                continue

            term = None
            for key in TERM_KEYS:
                for candidate in inner.get(key) or []:
                    if isinstance(candidate, str) and candidate.strip():
                        term = candidate.strip()
                        break
                if term:
                    break

            if "{term}" in template:
                if not term:
                    # No term to direct: state the bare fact instead of inventing one.
                    label = "Relative" if template == forward else "Relative of"
                else:
                    label = template.format(term=term[:1].upper() + term[1:])
            else:
                label = template

            out.append({
                "kind": RELATIONSHIP_LABELS.get(schema, schema),
                "role": label,
                "name": other["name"],
                "id": other["id"],
                "start_date": (inner.get("startDate") or [None])[0],
                "end_date": (inner.get("endDate") or [None])[0],
            })
    return out


def build(entity: dict, dataset_titles: Optional[Dict[str, dict]] = None) -> dict:
    """One raw OpenSanctions entity -> one structured dossier."""
    dataset_titles = dataset_titles or {}
    props = entity.get("properties") or {}
    sanctions, addresses = [], []

    for values in props.values():
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            if value.get("schema") == "Sanction":
                sanctions.append(parse_sanction(value, dataset_titles))
            elif value.get("schema") == "Address":
                caption = value.get("caption") or _stringify(
                    ((value.get("properties") or {}).get("full") or [None])[0]
                )
                if caption:
                    addresses.append(caption)

    groups, claimed = [], set()
    for title, keys in PROPERTY_GROUPS:
        rows = []
        for key in keys:
            claimed.add(key)
            values = _dedupe([_stringify(v) for v in (props.get(key) or [])])
            if key == "address":
                values = _dedupe(values + addresses)
            if values:
                rows.append({"key": key, "label": _label(key), "values": values})
        if rows:
            groups.append({"title": title, "rows": rows})

    leftovers = []
    for key, values in props.items():
        if key in claimed or key in SKIP or not isinstance(values, list):
            continue
        plain = _dedupe([_stringify(v) for v in values if not isinstance(v, dict)])
        if plain:
            leftovers.append({"key": key, "label": _label(key), "values": plain})
    if leftovers:
        groups.append({"title": "Other recorded details", "rows": leftovers})

    datasets = [
        dataset_titles.get(d, {"name": d, "title": d})
        for d in (entity.get("datasets") or [])
    ]

    name_candidates = [entity.get("caption")]
    for key in ("name", "alias"):
        name_candidates += [_stringify(v) for v in (props.get(key) or [])]

    return {
        "id": entity.get("id"),
        "caption": english_name(name_candidates, entity.get("caption") or ""),
        "schema": entity.get("schema"),
        "target": bool(entity.get("target")),
        "first_seen": entity.get("first_seen"),
        "last_seen": entity.get("last_seen"),
        "last_change": entity.get("last_change"),
        "referents": entity.get("referents") or [],
        "datasets": datasets,
        "groups": groups,
        "sanctions": sanctions,
        "relationships": parse_relationships(entity),
        "url": f"https://www.opensanctions.org/entities/{entity.get('id')}/",
    }


def merge(dossiers: List[dict]) -> Optional[dict]:
    """Combine several dossiers for one person, without repeating anything.

    Records for the same individual on four lists share a birth date and a
    passport number; each is stated once, and the reader sees which lists
    contributed rather than the same fact four times over.
    """
    dossiers = [d for d in dossiers if d]
    if not dossiers:
        return None
    if len(dossiers) == 1:
        merged = dict(dossiers[0])
        merged["record_ids"] = [dossiers[0]["id"]]
        merged["record_count"] = 1
        return merged

    base = dict(dossiers[0])
    base["record_ids"] = [d["id"] for d in dossiers]
    base["record_count"] = len(dossiers)

    # Datasets, de-duplicated by slug.
    datasets, seen_datasets = [], set()
    for dossier in dossiers:
        for dataset in dossier.get("datasets") or []:
            if dataset["name"] not in seen_datasets:
                seen_datasets.add(dataset["name"])
                datasets.append(dataset)
    base["datasets"] = datasets

    # Property groups, merged group-by-group then row-by-row.
    group_order, group_rows = [], {}
    for dossier in dossiers:
        for group in dossier.get("groups") or []:
            if group["title"] not in group_rows:
                group_order.append(group["title"])
                group_rows[group["title"]] = {}
            for row in group["rows"]:
                existing = group_rows[group["title"]].setdefault(
                    row["key"], {"key": row["key"], "label": row["label"], "values": []}
                )
                existing["values"] = _dedupe(existing["values"] + row["values"])
    base["groups"] = [
        {"title": title, "rows": list(group_rows[title].values())}
        for title in group_order
    ]

    # Sanctions: one entry per (authority, programme, listing date).
    sanctions, seen_sanctions = [], set()
    for dossier in dossiers:
        for sanction in dossier.get("sanctions") or []:
            key = (
                (sanction.get("authority") or "").lower(),
                (sanction.get("program") or "").lower(),
                sanction.get("listing_date") or "",
            )
            if key in seen_sanctions:
                continue
            seen_sanctions.add(key)
            sanctions.append(sanction)
    base["sanctions"] = sanctions

    relationships, seen_rel = [], set()
    for dossier in dossiers:
        for relationship in dossier.get("relationships") or []:
            key = (relationship.get("kind"), (relationship.get("name") or "").lower())
            if key in seen_rel:
                continue
            seen_rel.add(key)
            relationships.append(relationship)
    base["relationships"] = relationships

    base["target"] = any(d.get("target") for d in dossiers)
    base["url"] = dossiers[0].get("url")
    return base
