"""Graph construction, red-flag detection, risk scoring and frontend export."""
from typing import Dict, List, Optional

import networkx as nx

from config import HIGH_RISK_JURISDICTIONS
from resolve import EntityStore
from schema import (
    ADDRESS,
    COMPANY,
    DIRECTS,
    OWNS,
    PERSON,
    POSSIBLY_SAME_AS,
    REGISTERED_AT,
    SHAREHOLDER_OF,
    norm_country,
)

OWNERSHIP_EDGES = {OWNS, SHAREHOLDER_OF}
CONTROL_EDGES = OWNERSHIP_EDGES | {DIRECTS}

NOMINEE_DIRECTORSHIP_THRESHOLD = 5
BRASS_PLATE_THRESHOLD = 4


def build_graph(store: EntityStore) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for node_id, node in store.nodes.items():
        graph.add_node(node_id, **node.to_dict())
    for edge in store.edges:
        if edge.source in graph and edge.target in graph:
            graph.add_edge(edge.source, edge.target, key=None, **edge.to_dict())
    return graph


# --------------------------------------------------------------------------
# Detectors. Each returns a list of findings:
#   {kind, severity, title, detail, nodes: [...], edges: [[src, dst], ...]}
# --------------------------------------------------------------------------


def _control_subgraph(graph: nx.MultiDiGraph) -> nx.DiGraph:
    simple = nx.DiGraph()
    simple.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        if data.get("type") in CONTROL_EDGES:
            simple.add_edge(source, target, **data)
    return simple


def detect_circular_ownership(graph: nx.MultiDiGraph) -> List[dict]:
    findings = []
    control = _control_subgraph(graph)
    try:
        cycles = list(nx.simple_cycles(control))
    except Exception:
        cycles = []
    for cycle in cycles:
        if len(cycle) < 2:
            continue
        names = [graph.nodes[n].get("name", n) for n in cycle]
        findings.append(
            {
                "kind": "circular_ownership",
                "severity": "high",
                "title": "Circular ownership loop",
                "detail": (
                    "Ownership or control returns to its starting point: "
                    + " → ".join(names + [names[0]])
                    + ". Loops like this can obscure who ultimately benefits."
                ),
                "nodes": cycle,
                "edges": [[cycle[i], cycle[(i + 1) % len(cycle)]] for i in range(len(cycle))],
            }
        )
    return findings[:25]


def detect_nominee_hubs(graph: nx.MultiDiGraph) -> List[dict]:
    findings = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != PERSON:
            continue
        controlled = {
            target
            for _, target, edge in graph.out_edges(node_id, data=True)
            if edge.get("type") in CONTROL_EDGES
        }
        if len(controlled) >= NOMINEE_DIRECTORSHIP_THRESHOLD:
            findings.append(
                {
                    "kind": "nominee_hub",
                    "severity": "medium",
                    "title": "Possible nominee director",
                    "detail": (
                        f"{data.get('name', node_id)} holds a controlling role in "
                        f"{len(controlled)} entities in this network. High counts are "
                        "common for professional service providers acting as nominees."
                    ),
                    "nodes": [node_id] + sorted(controlled),
                    "edges": [[node_id, target] for target in sorted(controlled)],
                }
            )
    return findings


def detect_shared_addresses(graph: nx.MultiDiGraph) -> List[dict]:
    findings = []
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != ADDRESS:
            continue
        occupants = {
            source
            for source, _, edge in graph.in_edges(node_id, data=True)
            if edge.get("type") == REGISTERED_AT
        }
        if len(occupants) >= BRASS_PLATE_THRESHOLD:
            findings.append(
                {
                    "kind": "shared_address",
                    "severity": "medium",
                    "title": "Shared registered address",
                    "detail": (
                        f"{len(occupants)} entities share the registered address "
                        f"“{data.get('name', node_id)}”. Company-formation agents "
                        "legitimately host many clients, so treat this as a prompt to "
                        "check substance, not as a finding on its own."
                    ),
                    "nodes": [node_id] + sorted(occupants),
                    "edges": [[occupant, node_id] for occupant in sorted(occupants)],
                }
            )
    return findings


def detect_high_risk_jurisdictions(graph: nx.MultiDiGraph) -> List[dict]:
    """One finding covering every offshore registration, not one row per company."""
    by_place: Dict[str, List[str]] = {}
    for node_id, data in graph.nodes(data=True):
        code = norm_country(data.get("jurisdiction") or data.get("country"))
        if code in HIGH_RISK_JURISDICTIONS and data.get("type") == COMPANY:
            by_place.setdefault(HIGH_RISK_JURISDICTIONS[code], []).append(node_id)
    if not by_place:
        return []

    nodes = [node_id for group in by_place.values() for node_id in group]
    breakdown = "; ".join(
        f"{place}: " + ", ".join(sorted(graph.nodes[n].get("name", n) for n in group))
        for place, group in sorted(by_place.items())
    )
    return [
        {
            "kind": "high_risk_jurisdiction",
            "severity": "low",
            "title": f"{len(nodes)} entities in limited-disclosure jurisdictions",
            "detail": (
                "Registered where beneficial-ownership disclosure is limited — "
                + breakdown
                + "."
            ),
            "nodes": nodes,
            "edges": [],
        }
    ]


def detect_sanctions_and_peps(graph: nx.MultiDiGraph) -> List[dict]:
    findings = []
    for node_id, data in graph.nodes(data=True):
        flags = set(data.get("risk_flags") or [])
        if "sanctioned" in flags:
            findings.append(
                {
                    "kind": "sanctioned",
                    "severity": "high",
                    "title": "Sanctions listing",
                    "detail": f"{data.get('name', node_id)} appears on a sanctions list.",
                    "nodes": [node_id],
                    "edges": [],
                }
            )
        if "pep" in flags:
            findings.append(
                {
                    "kind": "pep",
                    "severity": "medium",
                    "title": "Politically exposed person",
                    "detail": (
                        f"{data.get('name', node_id)} is recorded as politically exposed "
                        "or closely associated with a PEP."
                    ),
                    "nodes": [node_id],
                    "edges": [],
                }
            )
    return findings


def detect_layering_depth(graph: nx.MultiDiGraph, roots: List[str]) -> List[dict]:
    """Long ownership chains above a company are the classic layering signature."""
    findings = []
    control = _control_subgraph(graph)
    reverse = control.reverse(copy=True)
    for root in roots:
        if root not in reverse:
            continue
        depths = nx.single_source_shortest_path_length(reverse, root)
        deepest = max(depths.values()) if depths else 0
        if deepest >= 3:
            chain = max(
                (nx.shortest_path(reverse, root, n) for n, d in depths.items() if d == deepest),
                key=len,
                default=[],
            )
            findings.append(
                {
                    "kind": "deep_layering",
                    "severity": "medium",
                    "title": f"{deepest}-tier ownership chain",
                    "detail": (
                        "Control over "
                        + graph.nodes[root].get("name", root)
                        + " passes through "
                        + str(deepest)
                        + " intermediate tiers: "
                        + " ← ".join(graph.nodes[n].get("name", n) for n in chain)
                    ),
                    "nodes": chain,
                    "edges": [[chain[i + 1], chain[i]] for i in range(len(chain) - 1)],
                }
            )
    return findings


def run_detectors(graph: nx.MultiDiGraph, roots: Optional[List[str]] = None) -> List[dict]:
    findings: List[dict] = []
    findings += detect_sanctions_and_peps(graph)
    findings += detect_circular_ownership(graph)
    findings += detect_nominee_hubs(graph)
    findings += detect_shared_addresses(graph)
    findings += detect_layering_depth(graph, roots or [])
    findings += detect_high_risk_jurisdictions(graph)
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))
    return findings


# --------------------------------------------------------------------------
# Risk score
# --------------------------------------------------------------------------

_SEVERITY_POINTS = {"high": 35, "medium": 18, "low": 7}


def score_nodes(graph: nx.MultiDiGraph, findings: List[dict]) -> Dict[str, int]:
    scores: Dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    for finding in findings:
        points = _SEVERITY_POINTS.get(finding["severity"], 5)
        for node_id in finding.get("nodes", []):
            if node_id in scores:
                scores[node_id] += points
    for node_id in scores:
        scores[node_id] = min(100, scores[node_id])
    return scores


def find_ubos(graph: nx.MultiDiGraph, root: str) -> List[dict]:
    """People with no owner above them who reach `root` through ownership edges.

    Ownership only — a director sits in the control graph but is not a
    beneficial owner, and listing one as a UBO is exactly the error a nominee
    arrangement is designed to produce.
    """
    ownership = nx.DiGraph()
    ownership.add_nodes_from(graph.nodes(data=True))
    for source, target, data in graph.edges(data=True):
        if data.get("type") in OWNERSHIP_EDGES:
            ownership.add_edge(source, target, **data)
    if root not in ownership:
        return []
    reverse = ownership.reverse(copy=True)
    reachable = nx.single_source_shortest_path_length(reverse, root)
    ubos = []
    for node_id, distance in reachable.items():
        if node_id == root:
            continue
        data = graph.nodes[node_id]
        owners_above = [
            source
            for source, _, edge in graph.in_edges(node_id, data=True)
            if edge.get("type") in OWNERSHIP_EDGES
        ]
        if data.get("type") == PERSON and not owners_above:
            path = nx.shortest_path(reverse, root, node_id)
            ubos.append(
                {
                    "id": node_id,
                    "name": data.get("name"),
                    "tiers": distance,
                    "path": [graph.nodes[n].get("name", n) for n in reversed(path)],
                    "risk_flags": data.get("risk_flags") or [],
                }
            )
    ubos.sort(key=lambda u: u["tiers"])
    return ubos


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------


def subgraph_json(
    graph: nx.MultiDiGraph,
    roots: List[str],
    hops: int = 3,
    findings: Optional[List[dict]] = None,
) -> dict:
    """Everything within `hops` of the matched entities, ready to draw."""
    undirected = graph.to_undirected(as_view=True)
    keep = set()
    for root in roots:
        if root in undirected:
            keep |= set(nx.single_source_shortest_path_length(undirected, root, cutoff=hops))
    if not keep:
        keep = set(graph.nodes)

    findings = findings if findings is not None else run_detectors(graph, roots)
    relevant = [f for f in findings if not f.get("nodes") or set(f["nodes"]) & keep]
    scores = score_nodes(graph, relevant)

    nodes = []
    for node_id in keep:
        data = dict(graph.nodes[node_id])
        data["risk_score"] = scores.get(node_id, 0)
        data["is_root"] = node_id in roots
        nodes.append(data)

    edges = []
    for source, target, data in graph.edges(data=True):
        if source in keep and target in keep:
            edges.append(dict(data))

    return {
        "nodes": nodes,
        "edges": edges,
        "roots": [r for r in roots if r in keep],
        "findings": relevant,
        "ubos": [ubo for root in roots for ubo in find_ubos(graph, root)],
        "stats": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "possible_matches": sum(1 for e in edges if e.get("type") == POSSIBLY_SAME_AS),
        },
    }
