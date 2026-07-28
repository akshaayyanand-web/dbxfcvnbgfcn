"""Smoke tests. Run with: python test_ubograph.py  (no pytest needed)."""
import sys

from graph import build_graph, find_ubos, run_detectors
from resolve import EntityStore
from schema import COMPANY, OWNS, PERSON, POSSIBLY_SAME_AS, Edge, Node, normalise_name
from search import run_search

failures = []


def check(label, condition):
    print(("  ok   " if condition else "  FAIL ") + label)
    if not condition:
        failures.append(label)


def test_name_normalisation():
    print("name normalisation")
    check("legal suffixes stripped",
          normalise_name("Falcon Capital Holdings FZE", COMPANY) == "falcon capital")
    check("punctuation and case folded",
          normalise_name("A.C.M.E. Ltd.", COMPANY) == normalise_name("acme limited", COMPANY))
    check("honorifics stripped from people",
          normalise_name("Mr. Rashid Al Mansoori", PERSON) == "rashid al mansoori")


def test_merge_on_registration_number():
    print("merge on exact identifier")
    store = EntityStore()
    a = Node(id="oc:ae_du/DMCC-1", type=COMPANY, name="Falcon Capital Holdings FZE",
             reg_number="DMCC-1", jurisdiction="ae_du")
    b = Node(id="os:xyz", type=COMPANY, name="FALCON CAPITAL HLDGS",
             reg_number="dmcc-1", jurisdiction="ae")
    first = store.add_node(a)
    second = store.add_node(b)
    check("same registration number merges", first == second)
    check("alias preserved on merge", "FALCON CAPITAL HLDGS" in store.nodes[first].aliases)


def test_weak_match_links_rather_than_merges():
    print("weak match links, never merges")
    store = EntityStore()
    first = store.add_node(Node(id="a", type=PERSON, name="Rashid Al Mansoori",
                                country="ae", birth_date="1971-04-18"))
    second = store.add_node(Node(id="b", type=PERSON, name="Rashid Almansoori", country="ae"))
    check("kept as two separate entities", first != second)
    links = [e for e in store.edges if e.type == POSSIBLY_SAME_AS]
    check("a possible-match edge was created", len(links) == 1)
    check("possible-match edge is not asserted", links[0].to_dict()["asserted"] is False)


def test_conflicting_birth_years_do_not_merge():
    print("namesakes with different birth years stay separate")
    store = EntityStore()
    first = store.add_node(Node(id="a", type=PERSON, name="John Smith",
                                country="gb", birth_date="1970-01-01"))
    second = store.add_node(Node(id="b", type=PERSON, name="John Smith",
                                 country="gb", birth_date="1985-06-02"))
    check("different birth years are different people", first != second)


def test_detectors_and_ubos():
    print("detectors on the demo network")
    payload = run_search("falcon capital")
    kinds = {f["kind"] for f in payload["findings"]}
    check("circular ownership detected", "circular_ownership" in kinds)
    check("nominee hub detected", "nominee_hub" in kinds)
    check("shared address detected", "shared_address" in kinds)
    check("sanctions hit detected", "sanctioned" in kinds)
    check("deep layering detected", "deep_layering" in kinds)
    names = {u["name"] for u in payload["ubos"]}
    check("PEP surfaced as a UBO four tiers up", "Elena Kovacs" in names)
    check("nominee director is NOT listed as a UBO", "Marcus Webb" not in names)
    check("graph is non-trivial", payload["stats"]["node_count"] > 10)


def test_ubo_traversal_ignores_directorships():
    print("UBO traversal follows ownership only")
    store = EntityStore()
    store.add_node(Node(id="c", type=COMPANY, name="Target Ltd"))
    store.add_node(Node(id="owner", type=PERSON, name="Real Owner"))
    store.add_node(Node(id="dir", type=PERSON, name="Hired Director"))
    store.add_edge(Edge(source="owner", target="c", type=OWNS, share_pct=100.0))
    store.add_edge(Edge(source="dir", target="c", type="directs"))
    graph = build_graph(store)
    names = {u["name"] for u in find_ubos(graph, "c")}
    check("owner found", names == {"Real Owner"})
    run_detectors(graph, ["c"])


if __name__ == "__main__":
    for test in (
        test_name_normalisation,
        test_merge_on_registration_number,
        test_weak_match_links_rather_than_merges,
        test_conflicting_birth_years_do_not_merge,
        test_detectors_and_ubos,
        test_ubo_traversal_ignores_directorships,
    ):
        test()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("all checks passed")
