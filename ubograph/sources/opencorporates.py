"""OpenCorporates adapter (API v0.4).

Company search gives registry records plus officers and registered addresses.
Officer search is the other direction, and it is what makes a nominee director
visible: one person, thirty companies.

Auth is the `api_token` query parameter.
"""
from typing import List, Optional

import requests

from config import HTTP_TIMEOUT, OPENCORPORATES_API_TOKEN, OPENCORPORATES_BASE_URL
from resolve import EntityStore
from schema import ADDRESS, COMPANY, DIRECTS, PERSON, REGISTERED_AT, Edge, Node

SOURCE = "opencorporates"

DIRECTOR_TITLES = (
    "director", "manager", "partner", "secretary", "officer", "president",
    "chairman", "member", "governor", "trustee", "agent",
)


class OpenCorporatesError(RuntimeError):
    pass


def available() -> bool:
    return bool(OPENCORPORATES_API_TOKEN)


def _get(path: str, **params) -> dict:
    params["api_token"] = OPENCORPORATES_API_TOKEN
    response = requests.get(
        f"{OPENCORPORATES_BASE_URL}{path}", params=params, timeout=HTTP_TIMEOUT
    )
    if response.status_code in (401, 403):
        raise OpenCorporatesError(
            "OpenCorporates rejected the token (%s). Tokens need approval for API access."
            % response.status_code
        )
    if response.status_code == 429:
        raise OpenCorporatesError("OpenCorporates rate limit reached (429).")
    if not response.ok:
        raise OpenCorporatesError(
            f"OpenCorporates {path} failed: {response.status_code} {response.text[:200]}"
        )
    return response.json() or {}


def _company_node(company: dict) -> Node:
    number = company.get("company_number")
    jurisdiction = company.get("jurisdiction_code")
    node = Node(
        id=f"oc:{jurisdiction}/{number}",
        type=COMPANY,
        name=company.get("name") or f"{jurisdiction}/{number}",
        country=jurisdiction,
        reg_number=number,
        jurisdiction=jurisdiction,
        status=company.get("current_status") or ("inactive" if company.get("inactive") else None),
    )
    node.sources.add(SOURCE)
    if company.get("opencorporates_url"):
        node.source_urls.append(company["opencorporates_url"])
    if company.get("incorporation_date"):
        node.notes.append(f"Incorporated {company['incorporation_date']}")
    if company.get("company_type"):
        node.notes.append(str(company["company_type"]))
    for previous in (company.get("previous_names") or [])[:5]:
        if isinstance(previous, dict) and previous.get("company_name"):
            node.aliases.add(previous["company_name"])
    return node


def _address_node(address: str, jurisdiction: Optional[str]) -> Node:
    key = " ".join(address.split()).lower()
    node = Node(
        id=f"addr:{key}",
        type=ADDRESS,
        name=" ".join(address.split()),
        country=jurisdiction,
        jurisdiction=jurisdiction,
    )
    node.sources.add(SOURCE)
    return node


def _officer_node(officer: dict) -> Node:
    node = Node(
        id=f"oc:officer/{officer.get('id')}",
        type=PERSON,
        name=officer.get("name") or "unknown officer",
        country=officer.get("nationality"),
        birth_date=officer.get("date_of_birth"),
    )
    node.sources.add(SOURCE)
    if officer.get("opencorporates_url"):
        node.source_urls.append(officer["opencorporates_url"])
    if officer.get("occupation"):
        node.notes.append(str(officer["occupation"]))
    return node


def _edge_type_for(position: Optional[str]) -> str:
    text = (position or "").lower()
    return DIRECTS if any(title in text for title in DIRECTOR_TITLES) else DIRECTS


def ingest_company(company: dict, store: EntityStore) -> Optional[str]:
    if not company or not company.get("company_number"):
        return None
    company_id = store.add_node(_company_node(company))

    address = company.get("registered_address_in_full")
    if address:
        address_id = store.add_node(_address_node(address, company.get("jurisdiction_code")))
        store.add_edge(
            Edge(source=company_id, target=address_id, type=REGISTERED_AT, origin=SOURCE)
        )

    for wrapper in company.get("officers") or []:
        officer = wrapper.get("officer") if isinstance(wrapper, dict) else None
        if not officer:
            continue
        officer_id = store.add_node(_officer_node(officer))
        store.add_edge(
            Edge(
                source=officer_id,
                target=company_id,
                type=_edge_type_for(officer.get("position")),
                role=officer.get("position"),
                origin=SOURCE,
                start_date=officer.get("start_date"),
                end_date=officer.get("end_date"),
            )
        )
    return company_id


def search_companies(store: EntityStore, name: str, jurisdiction: Optional[str] = None,
                     per_page: int = 8, fetch_detail: int = 2) -> List[str]:
    if not available():
        return []
    params = {"q": name, "per_page": per_page}
    if jurisdiction:
        params["jurisdiction_code"] = jurisdiction
    data = _get("/companies/search", **params)
    companies = ((data.get("results") or {}).get("companies")) or []

    roots: List[str] = []
    for index, wrapper in enumerate(companies):
        company = wrapper.get("company") if isinstance(wrapper, dict) else None
        if not company:
            continue
        if index < fetch_detail:
            try:
                detail = _get(
                    f"/companies/{company['jurisdiction_code']}/{company['company_number']}",
                    sparse="false",
                )
                company = (detail.get("results") or {}).get("company") or company
            except OpenCorporatesError:
                pass  # fall back to the sparse search record
        node_id = ingest_company(company, store)
        if node_id and node_id not in roots:
            roots.append(node_id)
    return roots


def search_officers(store: EntityStore, name: str, jurisdiction: Optional[str] = None,
                    per_page: int = 30) -> List[str]:
    """Every company a person is an officer of — the nominee-director view."""
    if not available():
        return []
    params = {"q": name, "per_page": per_page}
    if jurisdiction:
        params["jurisdiction_code"] = jurisdiction
    data = _get("/officers/search", **params)
    officers = ((data.get("results") or {}).get("officers")) or []

    roots: List[str] = []
    for wrapper in officers:
        officer = wrapper.get("officer") if isinstance(wrapper, dict) else None
        if not officer:
            continue
        officer_id = store.add_node(_officer_node(officer))
        if officer_id not in roots:
            roots.append(officer_id)
        company = officer.get("company") or {}
        if company.get("company_number"):
            company_id = ingest_company(company, store)
            if company_id:
                store.add_edge(
                    Edge(
                        source=officer_id,
                        target=company_id,
                        type=_edge_type_for(officer.get("position")),
                        role=officer.get("position"),
                        origin=SOURCE,
                        start_date=officer.get("start_date"),
                        end_date=officer.get("end_date"),
                    )
                )
    return roots
