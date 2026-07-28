"""OpenSanctions adapter.

Two calls per search:
  POST /match/{scope}          -> candidate entities, scored against the query
  GET  /entities/{id}?nested=true -> that entity's ownership / directorship network

Auth is `Authorization: ApiKey <key>`. Everything is converted into the common
Node/Edge shape before it leaves this module.
"""
from typing import Dict, List, Optional, Tuple

import requests

from config import HTTP_TIMEOUT, OPENSANCTIONS_API_KEY, OPENSANCTIONS_BASE_URL
from resolve import EntityStore
from schema import (
    ADDRESS,
    COMPANY,
    DIRECTS,
    LINKED_TO,
    OWNS,
    PERSON,
    REGISTERED_AT,
    UNKNOWN,
    Edge,
    Node,
)

SOURCE = "opensanctions"

# FollowTheMoney relationship schemata -> (source property, target property, edge type)
RELATIONSHIPS: Dict[str, Tuple[str, str, str]] = {
    "Ownership": ("owner", "asset", OWNS),
    "Directorship": ("director", "organization", DIRECTS),
    "Membership": ("member", "organization", LINKED_TO),
    "Employment": ("employee", "employer", LINKED_TO),
    "Associate": ("person", "associate", LINKED_TO),
    "Family": ("person", "relative", LINKED_TO),
    "Representation": ("agent", "client", LINKED_TO),
    "Succession": ("predecessor", "successor", LINKED_TO),
    "UnknownLink": ("subject", "object", LINKED_TO),
}

PERSON_SCHEMATA = {"Person"}
ADDRESS_SCHEMATA = {"Address"}
COMPANY_SCHEMATA = {
    "Company", "Organization", "LegalEntity", "PublicBody", "Trust", "Airplane",
    "Vessel", "Asset", "Security",
}


class OpenSanctionsError(RuntimeError):
    pass


def available() -> bool:
    return bool(OPENSANCTIONS_API_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"ApiKey {OPENSANCTIONS_API_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _first(props: dict, key: str) -> Optional[str]:
    values = props.get(key)
    if isinstance(values, list):
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    if isinstance(values, str) and values.strip():
        return values.strip()
    return None


def _node_type(schema: str) -> str:
    if schema in PERSON_SCHEMATA:
        return PERSON
    if schema in ADDRESS_SCHEMATA:
        return ADDRESS
    if schema in COMPANY_SCHEMATA:
        return COMPANY
    return UNKNOWN


def _risk_flags(entity: dict) -> set:
    props = entity.get("properties") or {}
    topics = {t.lower() for t in (props.get("topics") or []) if isinstance(t, str)}
    datasets = {d.lower() for d in (entity.get("datasets") or []) if isinstance(d, str)}
    flags = set()
    if entity.get("target") or any(t.startswith("sanction") for t in topics):
        flags.add("sanctioned")
    if any(t.startswith("role.pep") or t.startswith("role.rca") for t in topics):
        flags.add("pep")
    if any(t.startswith("crime") for t in topics):
        flags.add("crime")
    if any("leak" in d or "icij" in d or "offshore" in d for d in datasets):
        flags.add("leak")
    if any(t.startswith("wanted") for t in topics):
        flags.add("wanted")
    return flags


def _to_node(entity: dict) -> Node:
    props = entity.get("properties") or {}
    schema = entity.get("schema") or ""
    node = Node(
        id=f"os:{entity.get('id')}",
        type=_node_type(schema),
        name=entity.get("caption") or _first(props, "name") or entity.get("id", "unknown"),
        country=_first(props, "country") or _first(props, "nationality"),
        birth_date=_first(props, "birthDate"),
        reg_number=_first(props, "registrationNumber") or _first(props, "idNumber"),
        jurisdiction=_first(props, "jurisdiction") or _first(props, "country"),
        status=_first(props, "status"),
    )
    node.sources.add(SOURCE)
    node.risk_flags |= _risk_flags(entity)
    node.source_urls.append(f"https://www.opensanctions.org/entities/{entity.get('id')}/")
    for alias in (props.get("alias") or [])[:8]:
        if isinstance(alias, str):
            node.aliases.add(alias)
    if entity.get("datasets"):
        node.notes.append("Listed on: " + ", ".join(sorted(set(entity["datasets"]))[:6]))
    return node


def ingest_entity(entity: dict, store: EntityStore, seen: Optional[dict] = None,
                  depth: int = 0, max_depth: int = 4) -> Optional[str]:
    """Walk one (possibly nested) OpenSanctions entity into the store.

    Nested mode inlines adjacent entities inside `properties`, so relationship
    schemata (Ownership, Directorship, ...) arrive as nested objects and become
    edges; everything else becomes a node.
    """
    if not isinstance(entity, dict) or not entity.get("id") or depth > max_depth:
        return None
    seen = seen if seen is not None else {}
    raw_id = entity["id"]
    schema = entity.get("schema") or ""
    props = entity.get("properties") or {}

    if schema in RELATIONSHIPS:
        source_prop, target_prop, edge_type = RELATIONSHIPS[schema]
        source_id = _resolve_endpoint(props.get(source_prop), store, seen, depth, max_depth)
        target_id = _resolve_endpoint(props.get(target_prop), store, seen, depth, max_depth)
        if source_id and target_id:
            share = _first(props, "percentage")
            store.add_edge(
                Edge(
                    source=source_id,
                    target=target_id,
                    type=edge_type,
                    share_pct=_percent(share),
                    role=_first(props, "role") or _first(props, "relationship") or schema,
                    origin=SOURCE,
                    start_date=_first(props, "startDate"),
                    end_date=_first(props, "endDate"),
                )
            )
        return None

    if raw_id in seen:
        node_id = seen[raw_id]
    else:
        node_id = store.add_node(_to_node(entity))
        seen[raw_id] = node_id

    for prop_name, values in props.items():
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            child_schema = value.get("schema") or ""
            if child_schema in RELATIONSHIPS:
                ingest_entity(value, store, seen, depth + 1, max_depth)
            elif child_schema in ADDRESS_SCHEMATA:
                address_id = ingest_entity(value, store, seen, depth + 1, max_depth)
                if address_id:
                    store.add_edge(
                        Edge(source=node_id, target=address_id,
                             type=REGISTERED_AT, origin=SOURCE, role=prop_name)
                    )
            else:
                ingest_entity(value, store, seen, depth + 1, max_depth)
    return node_id


def _resolve_endpoint(values, store: EntityStore, seen: dict, depth: int, max_depth: int):
    """An endpoint is either an inlined entity object or a bare entity id string."""
    if not values:
        return None
    if not isinstance(values, list):
        values = [values]
    for value in values:
        if isinstance(value, dict):
            resolved = ingest_entity(value, store, seen, depth + 1, max_depth)
            if resolved:
                return resolved
        elif isinstance(value, str):
            if value in seen:
                return seen[value]
            candidate = store.canonical(f"os:{value}")
            if candidate and candidate in store.nodes:
                return candidate
    return None


def _percent(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except ValueError:
        return None


def match(
    name: str,
    entity_type: str = "any",
    nationality: Optional[str] = None,
    birth_date: Optional[str] = None,
    reg_number: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    scope: str = "default",
    limit: int = 5,
) -> List[dict]:
    """POST /match — the optional fields are what kill namesake false positives."""
    if not available():
        return []

    schema = {"person": "Person", "company": "Company"}.get(entity_type, "LegalEntity")
    properties: Dict[str, List[str]] = {"name": [name]}
    if nationality:
        properties["nationality" if schema == "Person" else "country"] = [nationality]
        properties.setdefault("country", [nationality])
    if birth_date and schema == "Person":
        properties["birthDate"] = [birth_date]
    if reg_number and schema != "Person":
        properties["registrationNumber"] = [reg_number]
    if jurisdiction:
        properties["jurisdiction"] = [jurisdiction]

    payload = {"queries": {"q1": {"schema": schema, "properties": properties}}}
    url = f"{OPENSANCTIONS_BASE_URL}/match/{scope}"
    response = requests.post(
        url, json=payload, headers=_headers(),
        params={"limit": limit}, timeout=HTTP_TIMEOUT,
    )
    if response.status_code == 401:
        raise OpenSanctionsError("OpenSanctions rejected the API key (401).")
    if response.status_code == 429:
        raise OpenSanctionsError("OpenSanctions rate limit reached (429).")
    if not response.ok:
        raise OpenSanctionsError(
            f"OpenSanctions /match failed: {response.status_code} {response.text[:200]}"
        )

    data = response.json() or {}
    block = (data.get("responses") or {}).get("q1") or {}
    results = block.get("results") or []
    return [r for r in results if isinstance(r, dict)]


def fetch_entity(entity_id: str, nested: bool = True) -> Optional[dict]:
    if not available():
        return None
    url = f"{OPENSANCTIONS_BASE_URL}/entities/{entity_id}"
    response = requests.get(
        url, headers=_headers(),
        params={"nested": "true" if nested else "false"}, timeout=HTTP_TIMEOUT,
    )
    if response.status_code == 404:
        return None
    if not response.ok:
        raise OpenSanctionsError(
            f"OpenSanctions /entities failed: {response.status_code} {response.text[:200]}"
        )
    return response.json()


def search_and_expand(store: EntityStore, query: dict, expand: int = 2) -> List[str]:
    """Match the query, then pull the network around the strongest candidates."""
    results = match(
        name=query["name"],
        entity_type=query.get("entity_type", "any"),
        nationality=query.get("nationality"),
        birth_date=query.get("birth_date"),
        reg_number=query.get("reg_number"),
        jurisdiction=query.get("jurisdiction"),
        scope=query.get("scope") or "default",
    )
    roots: List[str] = []
    seen: dict = {}
    for index, result in enumerate(results):
        entity = result if result.get("schema") else result.get("match") or {}
        if not entity.get("id"):
            continue
        node_id = ingest_entity(entity, store, seen)
        if node_id and index < expand:
            detailed = fetch_entity(entity["id"], nested=True)
            if detailed:
                node_id = ingest_entity(detailed, store, seen) or node_id
        if node_id and node_id not in roots:
            roots.append(node_id)
    return roots
