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


# A synthetic dossier in the same shape sources/dossier.py produces from a real
# OpenSanctions entity, so the detail view is demonstrable without a key. Every
# value is invented, including the list names.
_DEMO_DOSSIERS = {
    "demo:viktor-branko": {
        "id": "demo-NK-4f2a91",
        "caption": "Viktor Branko",
        "schema": "Person",
        "target": True,
        "record_ids": ["demo-NK-4f2a91", "demo-NK-88b120"],
        "record_count": 2,
        "first_seen": "2019-03-14",
        "last_seen": "2026-07-01",
        "last_change": "2025-11-08",
        "referents": ["demo-NK-88b120"],
        "url": "https://www.opensanctions.org/entities/demo-NK-4f2a91/",
        "datasets": [
            {"name": "demo_sanctions_list", "title": "Demo National Sanctions List",
             "publisher": "Demo Ministry of Finance", "publisher_country": "xx",
             "url": "https://example.invalid/sanctions"},
            {"name": "demo_proscribed", "title": "Demo Register of Proscribed Persons",
             "publisher": "Demo Counter-Terrorism Authority", "publisher_country": "xx",
             "url": "https://example.invalid/proscribed"},
        ],
        "groups": [
            {"title": "Identity", "rows": [
                {"key": "name", "label": "Name", "values": ["Viktor Branko"]},
                {"key": "alias", "label": "Also known as",
                 "values": ["Viktor Branko-Petrović", "V. Branko"]},
                {"key": "fatherName", "label": "Patronymic / father's name",
                 "values": ["Milanovich"]},
                {"key": "birthDate", "label": "Date of birth", "values": ["1963-07-25"]},
                {"key": "birthPlace", "label": "Place of birth", "values": ["Novi Sad"]},
                {"key": "gender", "label": "Gender", "values": ["male"]},
                {"key": "position", "label": "Position held",
                 "values": ["Director, Harbour Line Shipping SA"]},
            ]},
            {"title": "Nationality & country", "rows": [
                {"key": "nationality", "label": "Nationality", "values": ["Serbia"]},
                {"key": "country", "label": "Country", "values": ["Serbia", "Panama"]},
            ]},
            {"title": "Identifiers", "rows": [
                {"key": "passportNumber", "label": "Passport number", "values": ["RS-0042118"]},
                {"key": "idNumber", "label": "National ID number", "values": ["2507963800115"]},
                {"key": "taxNumber", "label": "Tax number", "values": ["SRB-118820044"]},
            ]},
            {"title": "Contact & address", "rows": [
                {"key": "address", "label": "Address",
                 "values": ["Bulevar Oslobodenja 114, Novi Sad, Serbia",
                            "c/o Harbour Line Shipping SA, Panama City, Panama"]},
            ]},
            {"title": "Status & classification", "rows": [
                {"key": "topics", "label": "Topics", "values": ["sanction", "crime.fin"]},
                {"key": "notes", "label": "Notes",
                 "values": ["Synthetic record for demonstration. Not a real person."]},
            ]},
        ],
        "sanctions": [
            {"authority": "Demo Ministry of Finance",
             "program": "Demo Financial Crime Designations (DFC-2019)",
             "reason": "Designated for money laundering through shipping and trade "
                       "invoicing on behalf of a proscribed organisation.",
             "provisions": ["Asset freeze", "Travel ban"],
             "status": "Active", "listing_date": "2019-03-14",
             "start_date": "2019-03-14", "end_date": None,
             "unsc_id": None, "authority_id": "DFC-2019-0412",
             "source_url": "https://example.invalid/sanctions/DFC-2019-0412",
             "country": "xx",
             "datasets": [{"name": "demo_sanctions_list",
                           "title": "Demo National Sanctions List"}]},
            {"authority": "Demo Counter-Terrorism Authority",
             "program": "Schedule IV — Proscribed Persons",
             "reason": "Listed as a financier of a proscribed organisation.",
             "provisions": ["Asset freeze", "Reporting obligation"],
             "status": "Active", "listing_date": "2021-08-02",
             "start_date": "2021-08-02", "end_date": None,
             "unsc_id": None, "authority_id": "PROSC-4471",
             "source_url": "https://example.invalid/proscribed/4471",
             "country": "xx",
             "datasets": [{"name": "demo_proscribed",
                           "title": "Demo Register of Proscribed Persons"}]},
        ],
        "relationships": [
            {"kind": "Family", "role": "Brother", "name": "Milan Branko",
             "id": None, "start_date": None, "end_date": None},
            {"kind": "Associate", "role": "Business associate", "name": "Marcus Webb",
             "id": None, "start_date": "2018", "end_date": None},
            {"kind": "Directorship", "role": "Director",
             "name": "Harbour Line Shipping SA", "id": None,
             "start_date": "2017-06", "end_date": None},
        ],
    },
}


def dossier_for(node_id: str):
    """Sample source detail for a demo entity, or None."""
    return _DEMO_DOSSIERS.get(node_id)
