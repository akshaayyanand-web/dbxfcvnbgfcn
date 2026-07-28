"""Orchestration: one search across every configured source, merged into one graph."""
from typing import List, Optional

from rapidfuzz import fuzz

import config
from graph import build_graph, run_detectors, subgraph_json
from resolve import EntityStore
from schema import PERSON, normalise_name
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


def run_search(
    name: str,
    entity_type: str = "any",
    nationality: Optional[str] = None,
    birth_date: Optional[str] = None,
    reg_number: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    scope: str = "default",
    hops: int = 3,
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

    demo_mode = not sources_used or (not roots and not store.nodes)
    if demo_mode:
        demo.load(store)
        roots = _demo_roots(store, name, entity_type)
        if "demo" not in sources_used:
            sources_used.append("demo")

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
        }
    )

    # Only fall back to the open web when the structured sources found nothing.
    if not roots and adverse_media.available():
        payload["adverse_media"] = adverse_media.research(name, query)
    else:
        payload["adverse_media"] = None

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
