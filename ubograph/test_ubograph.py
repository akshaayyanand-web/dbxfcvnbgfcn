"""Smoke tests. Run with: python test_ubograph.py  (no pytest needed)."""
import sys

import pdf as pdf_renderer
from graph import band_reason, build_graph, find_ubos, risk_band, run_detectors
from reference import country_label, jurisdiction_label
from report import build_report
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


def test_flags_distinguish_sanctions_from_office():
    print("a politician is not a sanctioned party")
    from sources.opensanctions import _risk_flags

    def entity(topics, target=True, datasets=("in_peps",)):
        return {"target": target, "datasets": list(datasets),
                "properties": {"topics": list(topics)}}

    pep = _risk_flags(entity(["role.pep"]))
    check("PEP is flagged as a PEP", pep == {"pep"})
    check("PEP is NOT flagged sanctioned", "sanctioned" not in pep)
    check("PEP bands orange, not red", risk_band(0, pep) == "orange")

    check("dataset target flag alone means nothing",
          _risk_flags(entity([], target=True)) == set())
    check("PEP sub-topics still map to pep",
          _risk_flags(entity(["role.pep.gov"])) == {"pep"})
    check("PEP relatives are flagged separately",
          _risk_flags(entity(["role.rca"])) == {"pep_associate"})
    check("a sanctioned party is flagged sanctioned",
          _risk_flags(entity(["sanction"])) == {"sanctioned"})
    check("sanction.linked is NOT sanctioned",
          _risk_flags(entity(["sanction.linked"])) == {"sanction_linked"})
    check("sanction-linked bands orange",
          risk_band(0, {"sanction_linked"}) == "orange")
    check("counter-sanctions still count as a listing",
          _risk_flags(entity(["sanction.counter"])) == {"sanctioned"})
    check("band reason states PEP, not sanctions",
          "sanction" not in band_reason(0, {"pep"}).lower())


def test_risk_bands():
    print("risk bands")
    check("sanctions forces red at any score", risk_band(0, ["sanctioned"]) == "red")
    check("crime forces red", risk_band(5, ["crime"]) == "red")
    check("pep forces at least orange", risk_band(0, ["pep"]) == "orange")
    check("score 50 is red", risk_band(50, []) == "red")
    check("score 25 is orange", risk_band(25, []) == "orange")
    check("score 24 is green", risk_band(24, []) == "green")
    check("band reason explains itself", "sanctioned" in band_reason(0, ["sanctioned"]))


def test_bands_never_contradict_findings():
    print("bands agree with findings")
    payload = run_search("falcon capital", hops=4)
    bad = []
    for node in payload["nodes"]:
        severities = {
            f["severity"]
            for f in payload["findings"]
            if node["id"] in (f.get("principals") or f.get("nodes") or [])
        }
        if "high" in severities and node["risk_band"] != "red":
            bad.append(node["name"])
        if "medium" in severities and node["risk_band"] == "green":
            bad.append(node["name"])
    check("no entity is greener than its own findings", not bad)


def test_place_labels():
    print("country and jurisdiction labels")
    check("country code resolves", country_label("ae") == "United Arab Emirates")
    check("subdivision resolves", jurisdiction_label("ae_du").endswith("Dubai"))
    check("delaware resolves", "Delaware" in jurisdiction_label("us_de"))
    check("unknown code passes through", country_label("zz9") == "zz9")


def test_fatf_jurisdiction_detector():
    print("FATF / UN sanctions-regime jurisdictions (from the client risk workbook)")
    from reference import country_risk

    check("data file loaded — North Korea is UN-sanctioned-regime + FATF blacklist",
          country_risk("kp").get("fatf") == "FATF HRC" and country_risk("kp").get("uaeiec"))
    check("Kenya is FATF grey list only, no UN regime",
          country_risk("ke").get("fatf") == "FATF JUIM" and not country_risk("ke").get("uaeiec"))
    check("USA carries neither flag", not country_risk("us").get("fatf"))

    store = EntityStore()
    store.add_node(Node(id="c-un", type=COMPANY, name="Pyongyang Trading Co", jurisdiction="kp"))
    store.add_node(Node(id="c-grey", type=COMPANY, name="Mekong Ventures Ltd", jurisdiction="vn"))
    store.add_node(Node(id="c-clean", type=COMPANY, name="Ordinary Holdings Ltd", jurisdiction="us"))
    graph = build_graph(store)
    all_findings = run_detectors(graph)
    findings = [f for f in all_findings if f["kind"] == "fatf_jurisdiction"]
    high = [f for f in findings if f["severity"] == "high"]
    medium = [f for f in findings if f["severity"] == "medium"]
    check("UN-sanctioned-regime jurisdiction produces a high finding",
          high and "c-un" in high[0]["nodes"])
    check("FATF grey-list-only jurisdiction produces a medium finding, not high",
          medium and "c-grey" in medium[0]["nodes"]
          and not any("c-grey" in f["nodes"] for f in high))
    check("an unflagged jurisdiction produces no finding",
          not any("c-clean" in f["nodes"] for f in findings))
    check("independent of the curated secrecy-jurisdiction detector, which stays silent here",
          not any(f["kind"] == "high_risk_jurisdiction" for f in all_findings))


def test_report_and_pdf():
    print("report and PDF")
    payload = run_search("falcon capital", hops=4)
    webb = next(n["id"] for n in payload["nodes"] if n["name"] == "Marcus Webb")
    report = build_report(payload, webb)
    check("nominee bands orange, not green", report["subject"]["risk_band"] == "orange")
    check("all eight directorships listed", len(report["affiliations"]["current"]) == 8)
    check("narrative explains the band", any("controlling role" in p for p in report["narrative"]))

    branko = next(n["id"] for n in payload["nodes"] if n["name"] == "Viktor Branko")
    sanctioned = build_report(payload, branko)
    check("sanctioned subject bands red", sanctioned["subject"]["risk_band"] == "red")
    check("ownership route to the target is shown", sanctioned["ownership_paths"])
    check("affiliations carry their own band",
          all(a["band"] in {"red", "orange", "green"}
              for a in sanctioned["affiliations"]["current"]))

    data = pdf_renderer.render(sanctioned)
    check("PDF renders", data.startswith(b"%PDF") and len(data) > 2000)

    missing = build_report(payload, "does-not-exist")
    check("unknown entity returns an error, not a crash", "error" in missing)


def test_identity_matches_surface_in_report():
    print("unresolved identity matches reach the report")
    payload = run_search("falcon capital", hops=4)
    node = next((n["id"] for n in payload["nodes"] if n["name"] == "Rashid Al Mansoori"), None)
    check("subject present", node is not None)
    if node:
        report = build_report(payload, node)
        check("possible-match record is flagged for verification",
              len(report["identity_matches"]) == 1)


if __name__ == "__main__":
    for test in (
        test_name_normalisation,
        test_merge_on_registration_number,
        test_weak_match_links_rather_than_merges,
        test_conflicting_birth_years_do_not_merge,
        test_detectors_and_ubos,
        test_ubo_traversal_ignores_directorships,
        test_flags_distinguish_sanctions_from_office,
        test_risk_bands,
        test_bands_never_contradict_findings,
        test_place_labels,
        test_fatf_jurisdiction_detector,
        test_report_and_pdf,
        test_identity_matches_surface_in_report,
    ):
        test()
    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("all checks passed")
