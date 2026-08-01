"""OpenSanctions adapter.

Two calls per search:
  POST /match/{scope}          -> candidate entities, scored against the query
  GET  /entities/{id}?nested=true -> that entity's ownership / directorship network

Auth is `Authorization: ApiKey <key>`. Everything is converted into the common
Node/Edge shape before it leaves this module.
"""
from typing import Dict, List, Optional, Tuple

import requests

from config import HTTP_TIMEOUT, MATCH_SCORE_THRESHOLD, OPENSANCTIONS_API_KEY, OPENSANCTIONS_BASE_URL
from resolve import EntityStore
from sources import dossier as dossier_builder
from schema import (
    ADDRESS,
    english_name,
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

# A /match score of 1.0 means the record matched the *query* perfectly — not that
# two records describe the same person. Searching a bare "Imran Khan" scores every
# same-named record 1.0, several of whom are different men. So a 100% group is only
# collapsed when nothing in the records contradicts the identification.
PERFECT_MATCH = 0.999
CONFLICT_KEYS = ("birthDate", "passportNumber", "idNumber", "nationality")

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


# OpenSanctions topic taxonomy. The distinctions matter: "sanction" is a listed
# party, "sanction.linked" is somebody connected to one, and a PEP is neither.
SANCTIONED_TOPICS = {"sanction", "sanction.counter"}
LINKED_TOPICS = {"sanction.linked"}
DEBARMENT_TOPICS = {"debarment", "export.control", "export.risk"}


def _risk_flags(entity: dict) -> set:
    """Map source topics to our flags.

    Deliberately NOT derived from `target`. In OpenSanctions `target: true` means
    the entity is a subject of interest *in that dataset* — in the PEPs dataset
    every politician is a target — so treating it as a sanctions signal labelled
    ordinary elected officials as sanctioned. Only an explicit sanctions topic
    sets the sanctions flag.
    """
    props = entity.get("properties") or {}
    topics = {t.lower().strip() for t in (props.get("topics") or []) if isinstance(t, str)}
    datasets = {d.lower() for d in (entity.get("datasets") or []) if isinstance(d, str)}
    flags = set()

    if topics & SANCTIONED_TOPICS:
        flags.add("sanctioned")
    if topics & LINKED_TOPICS:
        flags.add("sanction_linked")
    if any(t == "role.pep" or t.startswith("role.pep.") for t in topics):
        flags.add("pep")
    if any(t == "role.rca" or t.startswith("role.rca.") for t in topics):
        flags.add("pep_associate")
    if any(t == "crime" or t.startswith("crime.") for t in topics):
        flags.add("crime")
    if topics & DEBARMENT_TOPICS:
        flags.add("debarred")
    if any(t == "wanted" or t.startswith("wanted.") for t in topics):
        flags.add("wanted")
    if any("leak" in d or "icij" in d or "offshore" in d for d in datasets):
        flags.add("leak")
    return flags


def _to_node(entity: dict) -> Node:
    props = entity.get("properties") or {}
    schema = entity.get("schema") or ""
    node = Node(
        id=f"os:{entity.get('id')}",
        type=_node_type(schema),
        name=english_name(
            [entity.get("caption"), *(props.get("name") or []), *(props.get("alias") or [])],
            entity.get("id", "unknown"),
        ),
        country=_first(props, "country") or _first(props, "nationality"),
        birth_date=_first(props, "birthDate"),
        reg_number=_first(props, "registrationNumber") or _first(props, "idNumber"),
        jurisdiction=_first(props, "jurisdiction") or _first(props, "country"),
        status=_first(props, "status"),
    )
    node.sources.add(SOURCE)
    node.source_ids.add(f"{SOURCE}:{entity.get('id')}")
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


_catalog_cache: Optional[dict] = None


def dataset_titles() -> dict:
    """Slug -> published title, so a report can say "NACTA List of Proscribed
    Persons" rather than "pk_nacta_proscribed"."""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    _catalog_cache = {}
    if not available():
        return _catalog_cache
    try:
        response = requests.get(
            f"{OPENSANCTIONS_BASE_URL}/catalog", headers=_headers(), timeout=HTTP_TIMEOUT
        )
        if response.ok:
            for dataset in (response.json() or {}).get("datasets") or []:
                name = dataset.get("name")
                if not name:
                    continue
                publisher = dataset.get("publisher") or {}
                _catalog_cache[name] = {
                    "name": name,
                    "title": dataset.get("title") or name,
                    "url": dataset.get("url") or dataset.get("link"),
                    "publisher": publisher.get("name"),
                    "publisher_country": publisher.get("country"),
                    "summary": dataset.get("summary"),
                }
    except requests.RequestException:
        pass  # titles are a nicety; the slug is still shown
    return _catalog_cache


def fetch_dossier(raw_ids: List[str]) -> Optional[dict]:
    """Full detail for one entity, or several records merged into one."""
    if not available() or not raw_ids:
        return None
    titles = dataset_titles()
    built = []
    for raw_id in raw_ids[:6]:  # a sane ceiling on API calls per report
        entity = fetch_entity(raw_id, nested=True)
        if entity:
            built.append(dossier_builder.build(entity, titles))
    return dossier_builder.merge(built)


def _identity_conflict(a: dict, b: dict) -> Optional[str]:
    """Is there positive evidence these are different people?

    Absence of data is not evidence of difference — only a direct contradiction
    on a hard identifier blocks the merge.
    """
    a_props = a.get("properties") or {}
    b_props = b.get("properties") or {}
    for key in CONFLICT_KEYS:
        a_values = {str(v).strip().lower() for v in (a_props.get(key) or []) if isinstance(v, str)}
        b_values = {str(v).strip().lower() for v in (b_props.get(key) or []) if isinstance(v, str)}
        if not a_values or not b_values:
            continue
        if key == "birthDate":
            a_values = {v[:4] for v in a_values}
            b_values = {v[:4] for v in b_values}
        if a_values.isdisjoint(b_values):
            return key
    return None


def _match_schema(
    name: str,
    schema: str,
    nationality: Optional[str] = None,
    birth_date: Optional[str] = None,
    reg_number: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    scope: str = "default",
    limit: int = 5,
) -> List[dict]:
    """POST /match against one concrete FollowTheMoney schema (Person or
    Company) — the optional fields are what kill namesake false positives,
    and only apply once the schema is concrete enough to carry them."""
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


def _merge_by_score(*result_lists: List[dict]) -> List[dict]:
    """Combine several /match result lists, keeping each entity's best score."""
    best: Dict[str, dict] = {}
    for results in result_lists:
        for r in results:
            entity = r if r.get("schema") else r.get("match") or {}
            entity_id = entity.get("id")
            if not entity_id:
                continue
            if entity_id not in best or (r.get("score") or 0) > (best[entity_id].get("score") or 0):
                best[entity_id] = r
    return sorted(best.values(), key=lambda r: -(r.get("score") or 0))


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
    """POST /match — the optional fields are what kill namesake false positives.

    When entity_type is "person" or "company", queries that concrete schema
    directly. When it's unspecified ("any" — the search form's own default),
    this used to fall back to FollowTheMoney's abstract "LegalEntity" schema,
    which strips out every person/company-specific identifying property
    (nationality, birth date, registration number) and leaves a name-only
    query against the loosest schema OpenSanctions has — exactly the shape of
    query that returns a same-surname stranger ranked above "not found". So
    "any" instead queries Person and Company as two separate concrete
    schemas and merges the results by best score, at the cost of a second API
    call.
    """
    if not available():
        return []

    if entity_type == "person":
        return _match_schema(name, "Person", nationality, birth_date, reg_number, jurisdiction, scope, limit)
    if entity_type == "company":
        return _match_schema(name, "Company", nationality, birth_date, reg_number, jurisdiction, scope, limit)

    person_results = _match_schema(name, "Person", nationality, birth_date, reg_number, jurisdiction, scope, limit)
    company_results = _match_schema(name, "Company", nationality, birth_date, reg_number, jurisdiction, scope, limit)
    return _merge_by_score(person_results, company_results)[:limit]


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


def _filter_weak_matches(results: List[dict], min_score: float = MATCH_SCORE_THRESHOLD) -> List[dict]:
    """Drop /match candidates scoring below `min_score`.

    A bare name search scores every same-ish-sounding record, however loosely
    related — without this, an unrelated namesake with a weak score becomes
    "the" result just because it's the top of a short list, and the real
    person (who may simply not be in this database) never gets reported as
    genuinely not found. The searched name still gets a second look via the
    adverse-media open-web fallback either way.
    """
    return [r for r in results if float(r.get("score") or 0) >= min_score]


def search_and_expand(store: EntityStore, query: dict, expand: int = 2) -> List[str]:
    """Match the query, collapse certain duplicates, then pull the network."""
    results = match(
        name=query["name"],
        entity_type=query.get("entity_type", "any"),
        nationality=query.get("nationality"),
        birth_date=query.get("birth_date"),
        reg_number=query.get("reg_number"),
        jurisdiction=query.get("jurisdiction"),
        scope=query.get("scope") or "default",
    )
    results = _filter_weak_matches(results)

    candidates = []
    for result in results:
        entity = result if result.get("schema") else result.get("match") or {}
        if entity.get("id"):
            candidates.append({"entity": entity, "score": float(result.get("score") or 0)})

    roots: List[str] = []
    seen: dict = {}
    node_for_raw: dict = {}

    for index, candidate in enumerate(candidates):
        entity = candidate["entity"]
        node_id = ingest_entity(entity, store, seen)
        if not node_id:
            continue
        node_for_raw[entity["id"]] = node_id
        if index < expand:
            detailed = fetch_entity(entity["id"], nested=True)
            if detailed:
                node_id = ingest_entity(detailed, store, seen) or node_id
                candidate["entity"] = detailed
                node_for_raw[entity["id"]] = node_id
        if node_id not in roots:
            roots.append(node_id)

    merged_ids = _collapse_duplicates(store, candidates, node_for_raw)
    roots = [r for r in (store.canonical(x) for x in roots) if r] if merged_ids else roots

    deduped = []
    for root in roots:
        if root not in deduped:
            deduped.append(root)
    return deduped


def _collapse_duplicates(store: EntityStore, candidates: List[dict], node_for_raw: dict) -> int:
    """Fold perfect-scoring records into one entity where nothing contradicts it.

    Also honours OpenSanctions' own `referents`, which are records it has
    already determined to be the same thing.
    """
    perfect = [c for c in candidates if c["score"] >= PERFECT_MATCH]
    merged = 0
    for index, keeper in enumerate(perfect):
        keeper_entity = keeper["entity"]
        keeper_node = store.canonical(node_for_raw.get(keeper_entity["id"]))
        if not keeper_node:
            continue
        for other in perfect[index + 1:]:
            other_entity = other["entity"]
            other_node = store.canonical(node_for_raw.get(other_entity["id"]))
            if not other_node or other_node == keeper_node:
                continue

            asserted = (
                other_entity["id"] in (keeper_entity.get("referents") or [])
                or keeper_entity["id"] in (other_entity.get("referents") or [])
            )
            conflict = _identity_conflict(keeper_entity, other_entity)
            if not asserted and conflict:
                continue  # a contradicting identifier — leave them separate

            note = (
                f"Merged with OpenSanctions record {other_entity['id']} "
                + ("(same record per OpenSanctions referents)" if asserted
                   else "(100% match on the search query, no contradicting identifier)")
            )
            node = store.nodes.get(keeper_node)
            if node and note not in node.notes:
                node.notes.append(note)
            store.merge_nodes(keeper_node, other_node)
            merged += 1
    return merged
