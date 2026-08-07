"""Orchestration: one search across every configured source, merged into one graph."""
from typing import List, Optional

from rapidfuzz import fuzz

import config
import risk_rating
from graph import build_graph, run_detectors, subgraph_json
from reference import country_label, fatf_marking, un_sanctioned
from resolve import EntityStore
from schema import COMPANY, PERSON, Node, normalise_name
from sources import adverse_media, demo, opencorporates, opensanctions

DEMO_MATCH_THRESHOLD = 72


def _demo_roots(store: EntityStore, name: str, entity_type: str) -> List[str]:
    key = normalise_name(name, entity_type)
    scored = []
    for node_id, node in store.nodes.items():
        if entity_type in ("person", "company") and node.type != entity_type:
            continue
        score = max(
            [fuzz.token_sort_ratio(key, normalise_name(candidate, node.type))
             for candidate in {node.name, *node.aliases}] or [0]
        )
        if score >= DEMO_MATCH_THRESHOLD:
            scored.append((score, node_id))
    scored.sort(reverse=True)
    return [node_id for _, node_id in scored[:5]]


_NO_MEDIA_FOUND = "no reliable open-source information found"


def _media_has_content(media: Optional[dict]) -> bool:
    """Did adverse-media research actually turn something up, as opposed to
    running cleanly and finding nothing (or failing outright)?"""
    if not media or not media.get("available") or media.get("error"):
        return False
    if media.get("findings"):
        return True
    summary = (media.get("summary") or "").strip().lower()
    return bool(summary) and _NO_MEDIA_FOUND not in summary


def _add_adverse_media_node(store: EntityStore, name: str, entity_type: str, media: dict) -> str:
    """Ordinary people and businesses with no sanctions/PEP/registry hit still
    turn up in web search — someone with real media coverage but nothing
    adverse enough to be in a screening database. Without this, that research
    had nowhere to live except a side panel on a "no match" screen; this
    gives it an actual entry, so it gets a Table row, a Graph node and a
    proper report like anything else found — unmistakably marked as
    unverified and sourced from the open web, never a structured registry.
    """
    node_type = COMPANY if entity_type == "company" else PERSON
    node_id = f"webonly:{normalise_name(name, node_type)}"

    notes = []
    if media.get("summary"):
        notes.append(media["summary"])
    notes.append(
        "No match in the sanctions, PEP or company-registry sources checked. This "
        "entry is built entirely from open-web search results and is unverified — "
        "nothing here has been confirmed against a primary source."
    )

    source_urls = []
    for finding in media.get("findings") or []:
        url = finding.get("source_url")
        if url and url not in source_urls:
            source_urls.append(url)

    store.add_node(Node(
        id=node_id, type=node_type, name=name,
        sources={"adverse_media"}, source_ids={f"adverse_media:{node_id}"},
        source_urls=source_urls, notes=notes,
    ))
    return node_id


def _extra_match_properties(details: dict) -> dict:
    """Map the expanded identification form onto FollowTheMoney properties
    OpenSanctions' /match actually understands — every one supplied narrows
    the match and helps tell a real hit apart from a namesake. Fields with
    no FTM equivalent (occupation, employer, visa number, known associates,
    a PEP indicator, a free-text sanctions reference) aren't sent here —
    they're kept only as context on the returned screening record.
    """
    props: dict = {}
    single = {
        "alias": "alias", "place_of_birth": "birthPlace", "gender": "gender",
        "passport_number": "passportNumber", "national_id_number": "idNumber",
        "email": "email", "phone": "phone", "website": "website",
        "tax_id": "taxNumber", "position": "position",
    }
    for field, prop in single.items():
        value = (details.get(field) or "").strip()
        if value:
            props[prop] = [value]
    address = (details.get("address") or details.get("company_address") or "").strip()
    if address:
        props["address"] = [address]
    country_of_residence = (details.get("country_of_residence") or "").strip()
    if country_of_residence:
        props["country"] = [country_of_residence]
    return props


def screen_name(name: str, entity_type: str = "any", **details) -> dict:
    """A standalone sanctions/PEP screening lookup for the risk-rating tool's
    "Screen this name" button. Separate from the graph search above: no
    network expansion, just the raw match candidates and what each one is
    flagged for, so the screening outcome it suggests is never a black box.

    Accepts an expanded set of identifying details as keyword args (alias,
    nationality, birth_date, place_of_birth, gender, country_of_residence,
    address, passport_number, national_id_number, registration_number,
    country_of_registration, company_address, email, phone, website,
    tax_id, position — see _extra_match_properties) — the more of these are
    supplied, the fewer false-positive namesakes a live search returns. Any
    other keys (occupation, employer, industry, visa_number,
    known_associates, pep_indicator, sanctions_reference, notes) are carried
    through onto the returned record for audit purposes but don't affect
    the search itself.
    """
    name = (name or "").strip()
    if not name:
        return {"error": "A name is required."}

    if opensanctions.available():
        try:
            results = opensanctions.match(
                name=name, entity_type=entity_type, limit=5,
                nationality=details.get("nationality"),
                birth_date=details.get("birth_date"),
                reg_number=details.get("registration_number"),
                jurisdiction=details.get("country_of_registration"),
                extra_properties=_extra_match_properties(details),
            )
        except opensanctions.OpenSanctionsError as exc:
            return {"error": config.redact(str(exc))}
        matches = []
        for r in results:
            props = r.get("properties") or {}
            country = opensanctions._first(props, "country") or opensanctions._first(props, "nationality")
            matches.append({
                "name": (r.get("caption") or name),
                "score": r.get("score"),
                "flags": sorted(opensanctions._risk_flags(r)),
                "country": country_label(country) if country else None,
                "fatf_marking": fatf_marking(country) if country else None,
                "un_sanctioned": un_sanctioned(country) if country else False,
            })
        demo_mode = False
    else:
        # No live key: fall back to the same synthetic network the rest of the
        # app demos with, so the button still does something before keys arrive.
        store = EntityStore()
        demo.load(store)
        roots = _demo_roots(store, name, entity_type)
        matches = [
            {
                "name": store.nodes[r].name, "score": None,
                "flags": sorted(store.nodes[r].risk_flags),
                "country": country_label(store.nodes[r].country) if store.nodes[r].country else None,
                "fatf_marking": fatf_marking(store.nodes[r].country) if store.nodes[r].country else None,
                "un_sanctioned": un_sanctioned(store.nodes[r].country) if store.nodes[r].country else False,
            }
            for r in roots
        ]
        demo_mode = True

    all_flags = {flag for m in matches for flag in m["flags"]}
    context_fields = (
        "alias", "nationality", "birth_date", "place_of_birth", "gender",
        "country_of_residence", "address", "passport_number", "national_id_number",
        "visa_number", "occupation", "employer", "position", "industry",
        "company_name", "registration_number", "country_of_registration",
        "company_address", "email", "phone", "website", "tax_id",
        "known_associates", "pep_indicator", "sanctions_reference", "notes",
    )
    return {
        "outcome": risk_rating.screening_outcome_for(all_flags),
        "matches": matches,
        "demo_mode": demo_mode,
        # Every identifying detail actually supplied, kept on the record for the
        # audit trail — not just what was sent to the matching engine.
        "screening_details": {k: v for k, v in details.items() if k in context_fields and v},
    }


def batch_screen(names: List[str], entity_type: str = "any") -> List[dict]:
    """Screen a whole list of names in one pass — for onboarding a portfolio
    or an annual refresh instead of searching one client at a time.

    Runs a shallow (1-hop) search per name so a long list doesn't multiply
    into a full network expansion for every row; open the name individually
    from the Table tab for the full picture. Sequential, not parallel — a
    quota-respecting choice, not a performance one, so a long list will take
    a while. Adverse media is skipped here even when configured — searching
    it on every name in a portfolio would turn one API key's quota into
    hundreds of web-search calls per batch; run a name individually from the
    Table tab to get that check.
    """
    results = []
    for raw_name in names:
        name = (raw_name or "").strip()
        if not name:
            continue
        payload = run_search(name=name, entity_type=entity_type, hops=1, include_adverse_media=False)
        if payload.get("error"):
            results.append({"name": name, "error": payload["error"]})
            continue
        root = next((n for n in payload.get("nodes", []) if n.get("is_root")), None)
        if not root:
            results.append({"name": name, "matched": False})
            continue
        results.append({
            "name": name,
            "matched": True,
            "matched_name": root.get("name"),
            "type": root.get("type"),
            "risk_band": root.get("risk_band"),
            "risk_score": root.get("risk_score"),
            "flags": root.get("risk_flags") or [],
            "country": root.get("country"),
        })
    return results


def run_search(
    name: str,
    entity_type: str = "any",
    nationality: Optional[str] = None,
    birth_date: Optional[str] = None,
    reg_number: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    scope: str = "default",
    hops: int = 3,
    include_adverse_media: bool = True,
) -> dict:
    name = (name or "").strip()
    if not name:
        return {"error": "A name is required."}

    store = EntityStore()
    roots: List[str] = []
    errors: List[dict] = []
    sources_used: List[str] = []
    query = {
        "name": name,
        "entity_type": entity_type,
        "nationality": nationality,
        "birth_date": birth_date,
        "reg_number": reg_number,
        "jurisdiction": jurisdiction,
        "scope": scope,
    }

    if opensanctions.available():
        try:
            found = opensanctions.search_and_expand(store, query)
            roots += [r for r in found if r not in roots]
            sources_used.append("opensanctions")
        except Exception as exc:
            errors.append({"source": "opensanctions", "message": config.redact(str(exc))[:300]})

    if opencorporates.available():
        try:
            if entity_type != "person":
                found = opencorporates.search_companies(
                    store, name, jurisdiction=jurisdiction
                )
                roots += [r for r in found if r not in roots]
            if entity_type != "company":
                found = opencorporates.search_officers(
                    store, name, jurisdiction=jurisdiction
                )
                roots += [r for r in found if r not in roots]
            sources_used.append("opencorporates")
        except Exception as exc:
            errors.append({"source": "opencorporates", "message": config.redact(str(exc))[:300]})

    # Demo data stands in only when no source is configured at all. Once a key is
    # present, "nothing found" must be reported as nothing found — showing an
    # invented network for a real name is the worst failure this tool could have.
    configured = opensanctions.available() or opencorporates.available()
    demo_mode = not configured
    if demo_mode:
        demo.load(store)
        roots = _demo_roots(store, name, entity_type)
        sources_used.append("demo")

    # Runs on every search, not only when the structured sources found nothing —
    # a weak or wrong structured match (a namesake, a stale record) shouldn't
    # silently suppress the one check that could catch it. The cost is a web-search
    # call on every search rather than only on a miss; report.py folds anything
    # this finds about the actually-searched name into that entity's own report.
    media = None
    if include_adverse_media and adverse_media.available():
        media = adverse_media.research(name, query)

    # An ordinary person or business with no sanctions/PEP/registry hit isn't
    # "nothing" if the open web has real coverage of them — give that its own
    # entry instead of leaving it stranded in the media panel with no Table
    # row, Graph node or report to open. Only for live sources: demo mode
    # already has its own synthetic roots.
    if not roots and not demo_mode and _media_has_content(media):
        roots = [_add_adverse_media_node(store, name, entity_type, media)]
        sources_used.append("adverse_media")

    graph = build_graph(store)
    findings = run_detectors(graph, roots)
    payload = subgraph_json(graph, roots, hops=hops, findings=findings)

    payload.update(
        {
            "query": query,
            "sources_used": sources_used,
            "errors": errors,
            "demo_mode": demo_mode,
            "matched": bool(roots),
            "adverse_media": media,
        }
    )

    return payload


def summarise(payload: dict) -> str:
    """Plain-text summary for the CLI."""
    lines = [
        f"Nodes: {payload['stats']['node_count']}  "
        f"Edges: {payload['stats']['edge_count']}  "
        f"Possible-match links: {payload['stats']['possible_matches']}",
        f"Sources: {', '.join(payload.get('sources_used') or ['none'])}",
        "",
    ]
    if payload.get("ubos"):
        lines.append("Candidate ultimate beneficial owners:")
        for ubo in payload["ubos"][:10]:
            flags = f"  [{', '.join(ubo['risk_flags'])}]" if ubo["risk_flags"] else ""
            lines.append(f"  - {ubo['name']} ({ubo['tiers']} tiers up){flags}")
            lines.append("      " + " → ".join(ubo["path"]))
        lines.append("")
    if payload.get("findings"):
        lines.append("Red flags:")
        for finding in payload["findings"][:15]:
            lines.append(f"  [{finding['severity'].upper()}] {finding['title']}")
            lines.append(f"      {finding['detail']}")
    else:
        lines.append("No red flags detected in this subgraph.")
    for error in payload.get("errors") or []:
        lines.append(f"! {error['source']}: {error['message']}")
    return "\n".join(lines)


def check_sources() -> list:
    """Probe each configured source with a trivial query.

    Separates "my key is wrong" from "the app is broken", which is otherwise
    guesswork once a live search comes back thin.
    """
    results = []

    if not opensanctions.available():
        results.append({"source": "OpenSanctions", "state": "not configured",
                        "detail": "OPENSANCTIONS_API_KEY is empty in .env"})
    else:
        try:
            hits = opensanctions.match(name="Vladimir Putin", entity_type="person", limit=1)
            results.append({"source": "OpenSanctions", "state": "ok",
                            "detail": f"key accepted, {len(hits)} candidate(s) for the test query"})
        except Exception as exc:
            results.append({"source": "OpenSanctions", "state": "failed",
                            "detail": config.redact(str(exc))[:240]})

    if not opencorporates.available():
        results.append({"source": "OpenCorporates", "state": "not configured",
                        "detail": "OPENCORPORATES_API_TOKEN is empty in .env"})
    else:
        try:
            store = EntityStore()
            found = opencorporates.search_companies(store, "Barclays", per_page=1, fetch_detail=0)
            results.append({"source": "OpenCorporates", "state": "ok",
                            "detail": f"token accepted, {len(found)} company record(s) returned"})
        except Exception as exc:
            results.append({"source": "OpenCorporates", "state": "failed",
                            "detail": config.redact(str(exc))[:240]})

    if not adverse_media.available():
        results.append({"source": "Adverse media", "state": "not configured",
                        "detail": "ANTHROPIC_API_KEY and GEMINI_API_KEY are both empty (optional)"})
    else:
        results.append({"source": "Adverse media", "state": "ok",
                        "detail": f"{adverse_media.provider()} key present; "
                                  f"used only when a search finds nothing"})
    return results
