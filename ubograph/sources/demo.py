"""Synthetic demo network.

Loaded when no API keys are configured, so the app is demonstrable before
credentials arrive. Every name here is invented. Planted deliberately:
a circular ownership loop, a nominee director running many shells, a
brass-plate address, a PEP link and a sanctions hit.
"""
from resolve import EntityStore
from schema import (
    ADDRESS,
    COMPANY,
    DIRECTS,
    OWNS,
    PERSON,
    REGISTERED_AT,
    SHAREHOLDER_OF,
    Edge,
    Node,
)

SOURCE = "demo"


def _node(node_id, node_type, name, **kwargs):
    node = Node(id=f"demo:{node_id}", type=node_type, name=name, **kwargs)
    node.sources.add(SOURCE)
    return node


COMPANIES = [
    ("falcon-capital-fze", "Falcon Capital Holdings FZE", "ae", "DMCC-114872", "ae_du"),
    ("falcon-nominees-bvi", "Falcon Nominees Ltd", "vg", "BVI-1902334", "vg"),
    ("crescent-trade-fzc", "Crescent Trade Partners FZC", "ae", "SAIF-88120", "ae_sh"),
    ("marina-bay-ky", "Marina Bay Investments (Cayman) Ltd", "ky", "KY-556104", "ky"),
    ("harbour-line-pa", "Harbour Line Shipping SA", "pa", "PA-778213", "pa"),
    ("orient-star-sc", "Orient Star Trading Ltd", "sc", "SC-203991", "sc"),
    ("pearl-desert-ae", "Pearl Desert General Trading LLC", "ae", "DED-660412", "ae_du"),
    ("azure-holdings-cy", "Azure Holdings Cyprus Ltd", "cy", "HE-402117", "cy"),
]

SHELLS = [
    ("shell-alpha", "Alpha Meridian Ventures Ltd", "vg", "BVI-2210041"),
    ("shell-bravo", "Bravo Coastline Trading Ltd", "sc", "SC-210044"),
    ("shell-charlie", "Charlie Dune Commercial FZE", "ae", "RAK-330912"),
    ("shell-delta", "Delta Verde Investments Ltd", "bz", "BZ-118820"),
    ("shell-echo", "Echo Sands Holdings Ltd", "vg", "BVI-2210088"),
    ("shell-foxtrot", "Foxtrot Marine Services FZC", "ae", "SAIF-90114"),
]

BRASS_PLATE = "Office 1204, Level 12, Al Nakheel Tower, Jumeirah Lakes Towers, Dubai"


def load(store: EntityStore) -> None:
    for slug, name, country, reg, juris in COMPANIES:
        store.add_node(
            _node(slug, COMPANY, name, country=country, reg_number=reg, jurisdiction=juris)
        )
    for slug, name, country, reg in SHELLS:
        store.add_node(
            _node(slug, COMPANY, name, country=country, reg_number=reg, jurisdiction=country)
        )

    people = [
        ("rashid-al-mansoori", "Rashid Al Mansoori", "ae", "1971-04-18", set()),
        ("elena-kovacs", "Elena Kovacs", "cy", "1968-11-02", {"pep"}),
        ("viktor-branko", "Viktor Branko", "rs", "1963-07-25", {"sanctioned", "crime"}),
        ("james-okoro", "James Okoro", "gb", "1980-02-09", set()),
        ("marcus-webb", "Marcus Webb", "gb", "1975-09-30", set()),
    ]
    for slug, name, country, birth, flags in people:
        person = _node(slug, PERSON, name, country=country, birth_date=birth)
        person.risk_flags |= flags
        if "pep" in flags:
            person.notes.append("Recorded as politically exposed (former deputy minister).")
        if "sanctioned" in flags:
            person.notes.append("Appears on a demo sanctions list — synthetic data.")
        store.add_node(person)

    # A near-duplicate that should LINK, not merge: same name, no birth date,
    # different source. The resolver must leave it as a dashed edge.
    twin = _node("rashid-almansoori-alt", PERSON, "Rashid Almansoori", country="ae")
    twin.notes.append("Second record for a similar name — verify before treating as one person.")
    store.add_node(twin)

    address = _node("addr-jlt", ADDRESS, BRASS_PLATE, country="ae", jurisdiction="ae_du")
    store.add_node(address)

    def edge(source, target, edge_type, **kwargs):
        store.add_edge(
            Edge(source=f"demo:{source}", target=f"demo:{target}",
                 type=edge_type, origin=SOURCE, **kwargs)
        )

    # Layered ownership above the target company.
    edge("falcon-nominees-bvi", "falcon-capital-fze", OWNS, share_pct=76.0)
    edge("marina-bay-ky", "falcon-nominees-bvi", OWNS, share_pct=100.0)
    edge("azure-holdings-cy", "marina-bay-ky", OWNS, share_pct=60.0)
    edge("elena-kovacs", "azure-holdings-cy", OWNS, share_pct=55.0)
    edge("rashid-al-mansoori", "falcon-capital-fze", SHAREHOLDER_OF, share_pct=24.0)

    # The circular loop: Falcon -> Crescent -> Orient Star -> Falcon.
    edge("falcon-capital-fze", "crescent-trade-fzc", OWNS, share_pct=51.0)
    edge("crescent-trade-fzc", "orient-star-sc", OWNS, share_pct=100.0)
    edge("orient-star-sc", "falcon-capital-fze", OWNS, share_pct=15.0)

    # A sanctioned individual two hops away.
    edge("viktor-branko", "orient-star-sc", SHAREHOLDER_OF, share_pct=40.0)
    edge("harbour-line-pa", "orient-star-sc", OWNS, share_pct=45.0)
    edge("viktor-branko", "harbour-line-pa", DIRECTS, role="Director")

    # The nominee: one person, many shells.
    for slug, _, _, _ in SHELLS:
        edge("marcus-webb", slug, DIRECTS, role="Director")
    edge("marcus-webb", "falcon-nominees-bvi", DIRECTS, role="Director")
    edge("marcus-webb", "marina-bay-ky", DIRECTS, role="Director")

    # The brass-plate address.
    for slug in ("falcon-capital-fze", "crescent-trade-fzc", "pearl-desert-ae",
                 "shell-charlie", "shell-foxtrot"):
        edge(slug, "addr-jlt", REGISTERED_AT)

    edge("james-okoro", "pearl-desert-ae", DIRECTS, role="Manager")
    edge("pearl-desert-ae", "crescent-trade-fzc", SHAREHOLDER_OF, share_pct=9.0)
