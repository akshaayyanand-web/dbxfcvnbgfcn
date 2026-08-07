"""Graph construction, red-flag detection, risk scoring and frontend export."""
from typing import Dict, List, Optional

import networkx as nx

from config import HIGH_RISK_JURISDICTIONS
from reference import country_label, country_risk, jurisdiction_label, risk_data_meta
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
                    "principals": [node_id],  # the nominee, not the companies
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
                    "principals": [node_id],  # the address, not every tenant
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


def detect_fatf_jurisdictions(graph: nx.MultiDiGraph) -> List[dict]:
    """Company registration somewhere FATF or the UAE's own sanctions regime
    currently flags. Separate from the curated secrecy-jurisdiction list above:
    that one is a fixed judgement call about disclosure practice, this one reads
    a dated, sourced FATF/UN list — see reference.risk_data_meta() for when it
    was last updated.

    FATF's own two lists get their own marking so a reader can tell "grey
    list" and "black list" apart at a glance, rather than both just reading as
    a generic red/orange severity pill: Call for Action is informally the
    "black list", Increased Monitoring is informally the "grey list". A UN
    Security Council sanctions regime is checked independently of FATF status
    (not as a fallback) and gets its own "un_sanctions" marking and finding —
    a jurisdiction can be on a FATF list AND under UN sanctions at once (Iran,
    North Korea and several others are both), and both get written up rather
    than whichever check happens to fire first. FATF's (rare) suspended-
    cooperation status has no marking of its own — real and severe, but not
    literally either FATF list or a UN sanctions regime.
    """
    black_hits: Dict[str, List[str]] = {}
    grey_hits: Dict[str, List[str]] = {}
    un_hits: Dict[str, List[str]] = {}
    other_high_hits: Dict[str, List[str]] = {}
    for node_id, data in graph.nodes(data=True):
        if data.get("type") != COMPANY:
            continue
        code = norm_country(data.get("jurisdiction") or data.get("country"))
        info = country_risk(code)
        if not info:
            continue
        tag, un_regime = info.get("fatf"), info.get("uaeiec")
        place = info.get("name") or country_label(code) or code
        if tag == "FATF HRC":
            black_hits.setdefault(place, []).append(node_id)
        elif tag == "FATF JUIM":
            grey_hits.setdefault(place, []).append(node_id)
        elif tag == "FATF Suspended":
            other_high_hits.setdefault(f"{place} (FATF-suspended cooperation)", []).append(node_id)
        if un_regime:
            un_hits.setdefault(place, []).append(node_id)

    updated = (risk_data_meta().get("fatf_last_update") or "")[:10]
    updated_note = f" FATF/UN lists as of {updated}." if updated else ""

    def _breakdown(hits: Dict[str, List[str]]) -> str:
        return "; ".join(
            f"{place}: " + ", ".join(sorted(graph.nodes[n].get("name", n) for n in group))
            for place, group in sorted(hits.items())
        )

    findings = []
    groups = (
        (black_hits, "high", "black_list", "FATF black list (Call for Action)"),
        (grey_hits, "medium", "grey_list", "FATF grey list (Increased Monitoring)"),
        (un_hits, "high", "un_sanctions", "a UN Security Council targeted financial sanctions regime"),
        (other_high_hits, "high", None, "a live FATF or UN sanctions-regime listing"),
    )
    for hits, severity, marking, list_name in groups:
        if not hits:
            continue
        nodes = sorted({n for group in hits.values() for n in group})
        finding = {
            "kind": "fatf_jurisdiction",
            "severity": severity,
            "title": (
                f"{len(nodes)} " + ("entity" if len(nodes) == 1 else "entities")
                + f" registered under {list_name}"
            ),
            "detail": (
                _breakdown(hits) + ". This flags the registration jurisdiction, not the "
                "entity itself — treat it the way a real-estate compliance policy "
                "treats a high-risk country: a trigger for enhanced diligence, not "
                "a finding on its own." + updated_note
            ),
            "nodes": nodes,
            "edges": [],
        }
        if marking:
            finding["marking"] = marking
        findings.append(finding)
    return findings


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
                        f"{data.get('name', node_id)} holds or has held public office. "
                        "PEP status is not an allegation of wrongdoing and does not mean "
                        "sanctioned; it raises the standard of source-of-funds enquiry."
                    ),
                    "nodes": [node_id],
                    "edges": [],
                }
            )
        if "pep_associate" in flags:
            findings.append(
                {
                    "kind": "pep_associate",
                    "severity": "medium",
                    "title": "Close associate of a PEP",
                    "detail": (
                        f"{data.get('name', node_id)} is recorded as a relative or close "
                        "associate of a politically exposed person."
                    ),
                    "nodes": [node_id],
                    "edges": [],
                }
            )
        if "sanction_linked" in flags:
            findings.append(
                {
                    "kind": "sanction_linked",
                    "severity": "medium",
                    "title": "Linked to a sanctioned party",
                    "detail": (
                        f"{data.get('name', node_id)} is recorded as connected to a "
                        "sanctioned party. The entity is NOT itself sanctioned — check "
                        "whether the connection brings it within the measures."
                    ),
                    "nodes": [node_id],
                    "edges": [],
                }
            )
        if "debarred" in flags:
            findings.append(
                {
                    "kind": "debarred",
                    "severity": "medium",
                    "title": "Debarment or export-control listing",
                    "detail": (
                        f"{data.get('name', node_id)} appears on a debarment or "
                        "export-control list."
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
                    "principals": [root],  # the company being layered over
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
    findings += detect_fatf_jurisdictions(graph)
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: order.get(f["severity"], 3))
    return findings


# --------------------------------------------------------------------------
# Risk score
# --------------------------------------------------------------------------

# Calibrated so the bands and the findings can never contradict each other:
# one high finding alone reaches red (50), one medium alone reaches orange (25),
# and low findings accumulate without tipping an otherwise clean entity.
_SEVERITY_POINTS = {"high": 50, "medium": 25, "low": 8}

# One definition of the traffic-light bands, used by the graph, the table and
# the PDF so they can never disagree.
RED, ORANGE, GREEN = "red", "orange", "green"


RED_FLAGS = {"sanctioned", "crime", "wanted"}
# Being connected to a sanctioned party, or holding office, is a reason to look
# harder — not a reason to state that someone is sanctioned.
ORANGE_FLAGS = {"pep", "pep_associate", "sanction_linked", "debarred", "leak"}


def risk_band(score: int, flags) -> str:
    flags = set(flags or [])
    if flags & RED_FLAGS or score >= 50:
        return RED
    if flags & ORANGE_FLAGS or score >= 25:
        return ORANGE
    return GREEN


ORANGE_REASONS = {
    "pep": "recorded as a politically exposed person",
    "pep_associate": "recorded as a close associate of a politically exposed person",
    "sanction_linked": "recorded as linked to a sanctioned party, not sanctioned itself",
    "debarred": "subject to a debarment or export-control listing",
    "leak": "appears in leaked offshore records",
}


def band_reason(score: int, flags) -> str:
    flags = set(flags or [])
    if flags & RED_FLAGS:
        listed = ", ".join(sorted(flags & RED_FLAGS))
        return f"Red: carries a {listed} flag, which sets the band regardless of score."
    if score >= 50:
        return f"Red: risk score {score}/100 from the findings below."
    matched = [ORANGE_REASONS[f] for f in sorted(flags & ORANGE_FLAGS) if f in ORANGE_REASONS]
    if matched:
        return "Orange: " + "; ".join(matched) + "."
    if score >= 25:
        return f"Orange: risk score {score}/100 from the findings below."
    return (
        f"Green: risk score {score}/100 and no sanctions, criminal or political-exposure "
        "flag in the sources searched."
    )


# An entity that merely appears in someone else's finding carries a share of the
# weight, not all of it: being one of eight companies a nominee runs is context,
# not the same fact as being the nominee.
BYSTANDER_SHARE = 0.4


def score_nodes(graph: nx.MultiDiGraph, findings: List[dict]) -> Dict[str, int]:
    scores: Dict[str, int] = {node_id: 0 for node_id in graph.nodes}
    for finding in findings:
        points = _SEVERITY_POINTS.get(finding["severity"], 5)
        principals = set(finding.get("principals") or finding.get("nodes") or [])
        for node_id in finding.get("nodes", []):
            if node_id not in scores:
                continue
            scores[node_id] += points if node_id in principals else round(points * BYSTANDER_SHARE)
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
        score = scores.get(node_id, 0)
        data["risk_score"] = score
        data["risk_band"] = risk_band(score, data.get("risk_flags"))
        data["band_reason"] = band_reason(score, data.get("risk_flags"))
        data["is_root"] = node_id in roots
        data["country_label"] = country_label(data.get("country"))
        data["jurisdiction_label"] = jurisdiction_label(
            data.get("jurisdiction") or data.get("country")
        )
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
