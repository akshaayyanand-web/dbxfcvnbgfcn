"""Parse a realistic nested OpenSanctions entity and check the dossier."""
from sources import dossier

RAW = {
  "id": "NK-9xTest", "caption": "Imran Ahmed Khan", "schema": "Person",
  "target": True,
  "datasets": ["pk_nacta_proscribed", "us_ofac_sdn"],
  "referents": ["pk-nacta-4471"],
  "first_seen": "2019-03-14", "last_seen": "2026-07-01",
  "properties": {
    "name": ["Imran Ahmed Khan", "Imran Ahmed Khan"],
    "alias": ["Imran Khan", "Imran Khan", "عمران خان"],
    "fatherName": ["Ahmed Khan"],
    "birthDate": ["1972-11-05"],
    "birthPlace": ["Lahore"],
    "gender": ["male"],
    "nationality": ["pk"],
    "country": ["pk"],
    "passportNumber": ["AB1234567"],
    "idNumber": ["35202-1234567-1"],
    "position": ["Regional coordinator"],
    "topics": ["sanction", "crime.terror"],
    "notes": ["Listed under Schedule IV."],
    "someNewFieldNotInMyMap": ["future value"],
    "address": ["12 Mall Road, Lahore"],
    "addressEntity": [{
      "id": "addr-1", "schema": "Address", "caption": "12 Mall Road, Lahore, Pakistan",
      "properties": {"full": ["12 Mall Road, Lahore, Pakistan"]}
    }],
    "sanctions": [{
      "id": "sanc-1", "schema": "Sanction",
      "datasets": ["pk_nacta_proscribed"],
      "properties": {
        "authority": ["National Counter Terrorism Authority"],
        "program": ["Schedule IV — Proscribed Persons"],
        "reason": ["Proscribed under the Anti-Terrorism Act 1997."],
        "provisions": ["Asset freeze", "Travel ban"],
        "status": ["Active"], "listingDate": ["2019-03-14"], "startDate": ["2019-03-14"],
        "authorityId": ["PROSC-4471"],
        "sourceUrl": ["https://nacta.gov.pk/proscribed/4471"],
      }
    }],
    "familyPerson": [{
      "id": "fam-1", "schema": "Family",
      "properties": {
        "relationship": ["Brother"],
        "person": ["NK-9xTest"],
        "relative": [{"id": "NK-bro", "schema": "Person", "caption": "Kamran Khan"}],
      }
    }],
    "ownershipAsset": [{
      "id": "own-1", "schema": "Ownership",
      "properties": {
        "owner": ["NK-9xTest"],
        "asset": [{"id": "NK-co", "schema": "Company", "caption": "Khan Trading LLC"}],
        "percentage": ["60"],
      }
    }],
  },
}

TITLES = {
  "pk_nacta_proscribed": {"name": "pk_nacta_proscribed",
                          "title": "NACTA List of Proscribed Persons",
                          "publisher": "National Counter Terrorism Authority"},
  "us_ofac_sdn": {"name": "us_ofac_sdn", "title": "US OFAC Specially Designated Nationals"},
}

failures = []
def check(label, condition):
    print(("  ok   " if condition else "  FAIL ") + label)
    if not condition: failures.append(label)

d = dossier.build(RAW, TITLES)
rows = {r["key"]: r for g in d["groups"] for r in g["rows"]}

print("dossier parsing")
check("dataset slug resolved to published title",
      [x["title"] for x in d["datasets"]][0] == "NACTA List of Proscribed Persons")
check("patronymic captured", rows["fatherName"]["values"] == ["Ahmed Khan"])
check("patronymic labelled for a reader",
      "Patronymic" in rows["fatherName"]["label"])
check("birth date captured", rows["birthDate"]["values"] == ["1972-11-05"])
check("nationality captured", rows["nationality"]["values"] == ["pk"])
check("passport captured", rows["passportNumber"]["values"] == ["AB1234567"])
check("national ID captured", rows["idNumber"]["values"] == ["35202-1234567-1"])
check("repeated name not printed twice", rows["name"]["values"] == ["Imran Ahmed Khan"])
check("duplicate alias collapsed, script variant kept",
      rows["alias"]["values"] == ["Imran Khan", "عمران خان"])
check("address merged from string and nested Address entity",
      len(rows["address"]["values"]) == 2)
check("unmapped property still surfaces",
      any(r["key"] == "someNewFieldNotInMyMap" for r in rows.values()))

s = d["sanctions"][0]
check("one sanction parsed", len(d["sanctions"]) == 1)
check("sanction authority", s["authority"] == "National Counter Terrorism Authority")
check("sanction programme", s["program"].startswith("Schedule IV"))
check("sanction reason", "Anti-Terrorism Act" in s["reason"])
check("sanction provisions", s["provisions"] == ["Asset freeze", "Travel ban"])
check("sanction listing date", s["listing_date"] == "2019-03-14")
check("sanction source url", s["source_url"].startswith("https://nacta.gov.pk"))
check("sanction names its own list",
      s["datasets"][0]["title"] == "NACTA List of Proscribed Persons")

kinds = {(r["kind"], r["name"]) for r in d["relationships"]}
check("family relationship parsed", ("Family", "Kamran Khan") in kinds)
check("ownership relationship parsed", ("Ownership", "Khan Trading LLC") in kinds)
check("relationship role kept",
      any(r["role"] == "Brother" for r in d["relationships"]))

print("\nmerging two records for one person")
second = dict(RAW, id="NK-second", datasets=["us_ofac_sdn"])
second["properties"] = dict(RAW["properties"],
                            passportNumber=["AB1234567"],          # same fact
                            idNumber=["35202-1234567-1"],          # same fact
                            address=["Flat 4, Karachi"])           # new fact
d2 = dossier.build(second, TITLES)
m = dossier.merge([d, d2])
mrows = {r["key"]: r for g in m["groups"] for r in g["rows"]}
check("record count reported", m["record_count"] == 2)
check("both record ids kept", m["record_ids"] == ["NK-9xTest", "NK-second"])
check("repeated passport stated once", mrows["passportNumber"]["values"] == ["AB1234567"])
check("repeated ID stated once", mrows["idNumber"]["values"] == ["35202-1234567-1"])
check("addresses combined without repeats",
      sorted(mrows["address"]["values"]) == sorted(
          ["12 Mall Road, Lahore", "12 Mall Road, Lahore, Pakistan", "Flat 4, Karachi"]))
check("datasets combined without repeats", len(m["datasets"]) == 2)
check("identical sanction not duplicated", len(m["sanctions"]) == 1)
check("relationships not duplicated", len(m["relationships"]) == 2)

print("\n100% match merging — the Imran Khan case")
from resolve import EntityStore
from sources import opensanctions as os_adapter

def person(raw_id, name, **props):
    return {"id": raw_id, "schema": "Person", "caption": name,
            "properties": dict({"name": [name]}, **props)}

# Two records, same name, no contradicting identifier -> one person.
a = person("os-a", "Imran Khan", birthDate=["1972-11-05"], nationality=["pk"])
b = person("os-b", "Imran Khan", nationality=["pk"])          # sparser record
check("no conflict when one record is silent", os_adapter._identity_conflict(a, b) is None)

# Two records, same name, different birth year -> different men.
c = person("os-c", "Imran Khan", birthDate=["1952-01-09"], nationality=["pk"])
check("different birth year is a conflict",
      os_adapter._identity_conflict(a, c) == "birthDate")

d1 = person("os-d", "Imran Khan", passportNumber=["AB1234567"])
d2 = person("os-e", "Imran Khan", passportNumber=["ZZ9999999"])
check("different passport is a conflict",
      os_adapter._identity_conflict(d1, d2) == "passportNumber")

def run_collapse(entities):
    store = EntityStore()
    node_for_raw, candidates = {}, []
    for entity in entities:
        node_id = os_adapter.ingest_entity(entity, store, {})
        node_for_raw[entity["id"]] = node_id
        candidates.append({"entity": entity, "score": 1.0})
    os_adapter._collapse_duplicates(store, candidates, node_for_raw)
    return store

store = run_collapse([a, b])
check("perfect match with no contradiction collapses to one entity",
      len(store.nodes) == 1)
merged = list(store.nodes.values())[0]
check("merged entity keeps both source records", len(merged.source_ids) == 2)
check("merge is explained in the record",
      any("Merged with OpenSanctions record" in n for n in merged.notes))

store = run_collapse([a, c])
check("perfect match with different birth years stays two entities",
      len(store.nodes) == 2)

# OpenSanctions asserting the identity overrides the conflict guard.
e1 = person("os-f", "Imran Khan", birthDate=["1972-11-05"])
e2 = person("os-g", "Imran Khan", birthDate=["1952-01-09"])
e1["referents"] = ["os-g"]
store = run_collapse([e1, e2])
check("an OpenSanctions referent merges even against a conflict",
      len(store.nodes) == 1)

# A 91% match must never collapse, whatever else agrees.
store = EntityStore()
node_for_raw, candidates = {}, []
for entity, score in ((a, 1.0), (person("os-h", "Imran Khan", nationality=["pk"]), 0.91)):
    node_id = os_adapter.ingest_entity(entity, store, {})
    node_for_raw[entity["id"]] = node_id
    candidates.append({"entity": entity, "score": score})
os_adapter._collapse_duplicates(store, candidates, node_for_raw)
check("91% is not collapsed", len(store.nodes) == 2)

print()
print(f"{len(failures)} failed" if failures else "all fixture checks passed")
raise SystemExit(1 if failures else 0)
