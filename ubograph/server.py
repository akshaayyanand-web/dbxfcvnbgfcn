"""Flask server: static frontend + the /api endpoints it calls."""
import json
import re
import secrets

from flask import Flask, Response, jsonify, request, send_from_directory

import config
import db
import edd
import geocode
import goaml
import pdf as pdf_renderer
import reference
import risk_rating
from report import build_report
from search import batch_screen, run_search, screen_name

app = Flask(__name__, static_folder="frontend", static_url_path="")
db.init()


@app.before_request
def _require_password():
    """Gate the whole app behind a password when APP_PASSWORD is set.

    A deployed instance searches on your API keys. Without this, anyone who
    finds the URL spends your OpenSanctions and OpenCorporates quota, and the
    first you know of it is a rate-limit error mid-demo. Unset locally, so
    development is unaffected.
    """
    if not config.APP_PASSWORD:
        return None
    # The platform's health probe cannot send credentials. Gating it makes the
    # deploy fail as "unhealthy" while the app itself is perfectly fine, so the
    # probe is exempt — it exposes nothing but the word "ok".
    if request.path == "/healthz":
        return None
    auth = request.authorization
    if auth and auth.username == config.APP_USERNAME and \
            secrets.compare_digest(auth.password or "", config.APP_PASSWORD):
        return None
    return Response(
        "Authentication required.", 401,
        {"WWW-Authenticate": 'Basic realm="Sanctions+"'},
    )


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/status")
def api_status():
    return jsonify(config.status())


@app.get("/api/search")
@app.post("/api/search")
def api_search():
    if request.method == "POST":
        params = request.get_json(silent=True) or {}
    else:
        params = request.args.to_dict()

    try:
        hops = max(1, min(4, int(params.get("hops") or 3)))
    except (TypeError, ValueError):
        hops = 3

    payload = run_search(
        name=params.get("name", ""),
        entity_type=params.get("entity_type") or "any",
        nationality=(params.get("nationality") or "").strip() or None,
        birth_date=(params.get("birth_date") or "").strip() or None,
        reg_number=(params.get("reg_number") or "").strip() or None,
        jurisdiction=(params.get("jurisdiction") or "").strip() or None,
        scope=params.get("scope") or "default",
        hops=hops,
    )
    if payload.get("error"):
        return jsonify(payload), 400
    db.log_activity("search", params.get("name", ""))
    return jsonify(payload)


@app.get("/api/reference")
def api_reference():
    """Country and jurisdiction lists for the form dropdowns."""
    return jsonify({
        "countries": reference.countries(),
        "jurisdictions": reference.jurisdictions(),
    })


@app.get("/api/risk_rating/options")
def api_risk_rating_options():
    """Dropdown option lists and weights for the client risk-rating panel."""
    return jsonify(risk_rating.options())


def _rate_from_request(body: dict) -> dict:
    """Every field taken straight from the request — no search, entity or
    screening result required. This is a standalone worksheet, not something
    derived from whoever might currently be selected in the app.
    """
    return risk_rating.rate(
        nationality=body.get("nationality"),
        country_of_birth=body.get("country_of_birth"),
        country_of_residence=body.get("country_of_residence"),
        business_work_location=body.get("business_work_location"),
        screening_outcome=body.get("screening_outcome"),
        employment_type=body.get("employment_type"),
        employment_industry=body.get("employment_industry"),
        mode_of_payment=body.get("mode_of_payment"),
        source_of_funds=body.get("source_of_funds"),
    )


@app.post("/api/risk_rating")
def api_risk_rating():
    """Score a client against the risk-rating rubric from manual inputs alone —
    independent of any search, entity or PEP/sanctions screening result.
    """
    body = request.get_json(silent=True) or {}
    return jsonify(_rate_from_request(body))


@app.post("/api/geocode")
def api_geocode():
    """Turn a free-text address into coordinates plus a satellite-image URL
    and an OpenStreetMap link — free, keyless, for the address-entity report's
    satellite view. Geocoding failures return an empty result, not a 500;
    an address that doesn't resolve is common and not an application error.
    """
    body = request.get_json(silent=True) or {}
    address = body.get("address", "")
    try:
        hit = geocode.geocode(address)
    except geocode.GeocodeError as exc:
        return jsonify({"error": str(exc)}), 502
    if not hit:
        return jsonify({"found": False})
    return jsonify({
        "found": True,
        "lat": hit["lat"],
        "lon": hit["lon"],
        "display_name": hit["display_name"],
        "satellite_url": geocode.satellite_image_url(hit["lat"], hit["lon"]),
        "osm_url": geocode.osm_url(hit["lat"], hit["lon"]),
    })


@app.post("/api/risk_rating.pdf")
def api_risk_rating_pdf():
    """The Risk Assessment tab's worksheet as its own PDF — same manual inputs
    as /api/risk_rating, no payload or node_id, no dependency on any report.
    """
    body = request.get_json(silent=True) or {}
    rating = _rate_from_request(body)
    return app.response_class(
        pdf_renderer.render_risk_rating(rating),
        mimetype="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="SanctionsPlus_Client_Risk_Rating.pdf"'},
    )


@app.post("/api/screen")
def api_screen():
    """"Screen this name" — a quick, standalone sanctions/PEP lookup for the
    Risk Assessment tab. Returns the suggested screening-rubric outcome plus
    the raw matches behind it; the caller still picks the dropdown value.
    """
    body = request.get_json(silent=True) or {}
    result = screen_name(body.get("name", ""), body.get("entity_type") or "any")
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


@app.post("/api/report")
def api_report():
    """Build a report from a result set the client already has."""
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    if not payload or not node_id:
        return jsonify({"error": "payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    if report.get("error"):
        return jsonify(report), 404
    db.log_activity("report_viewed", report["subject"].get("name", ""))
    return jsonify(report)


@app.post("/api/report.pdf")
def api_report_pdf():
    """Same content as the on-screen report, plus the client risk rating if the
    caller has one in progress — set include_risk_rating and send the same
    fields /api/risk_rating takes (country_of_birth, employment_type, etc.)
    alongside payload/node_id, and the PDF gets a "Client risk rating"
    section; leave it unset and the PDF is unchanged.
    """
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    if not payload or not node_id:
        return jsonify({"error": "payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    if report.get("error"):
        return jsonify(report), 404
    rating = _rate_from_request(body) if body.get("include_risk_rating") else None
    name = re.sub(r"[^A-Za-z0-9]+", "_", report["subject"].get("name") or "report").strip("_")
    return app.response_class(
        pdf_renderer.render(report, risk_rating=rating),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SanctionsPlus_{name}.pdf"'},
    )


@app.get("/api/export")
def api_export():
    """Same payload as /api/search, served as a downloadable file."""
    payload = run_search(
        name=request.args.get("name", ""),
        entity_type=request.args.get("entity_type") or "any",
        nationality=request.args.get("nationality") or None,
        birth_date=request.args.get("birth_date") or None,
        reg_number=request.args.get("reg_number") or None,
        jurisdiction=request.args.get("jurisdiction") or None,
    )
    body = json.dumps(payload, indent=2)
    filename = (payload.get("query", {}).get("name") or "sanctions-plus").replace(" ", "_")
    return app.response_class(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@app.post("/api/edd.pdf")
def api_edd_pdf():
    """The Enhanced Due Diligence checklist for one entity, as its own PDF."""
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    if not payload or not node_id:
        return jsonify({"error": "payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    if report.get("error"):
        return jsonify(report), 404
    rows = edd.build_checklist(report)
    name = re.sub(r"[^A-Za-z0-9]+", "_", report["subject"].get("name") or "report").strip("_")
    db.log_activity("edd_checklist", report["subject"].get("name", ""))
    return app.response_class(
        pdf_renderer.render_edd_checklist(report, rows),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SanctionsPlus_EDD_{name}.pdf"'},
    )


@app.post("/api/mou.pdf")
def api_mou_pdf():
    """A resale MOU draft with the searched entity pre-filled as buyer or seller."""
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    if not payload or not node_id:
        return jsonify({"error": "payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    if report.get("error"):
        return jsonify(report), 404
    role = body.get("role") if body.get("role") in ("seller", "purchaser") else "purchaser"
    name = re.sub(r"[^A-Za-z0-9]+", "_", report["subject"].get("name") or "report").strip("_")
    db.log_activity("mou_draft", report["subject"].get("name", ""))
    return app.response_class(
        pdf_renderer.render_mou_draft(report, role=role),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="SanctionsPlus_MOU_{name}.pdf"'},
    )


@app.post("/api/goaml.xml")
def api_goaml_xml():
    """A starting-point goAML XML draft for one entity — see goaml.py for the
    honest limits (not validated against the real goAML schema)."""
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    if not payload or not node_id:
        return jsonify({"error": "payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    if report.get("error"):
        return jsonify(report), 404
    name = re.sub(r"[^A-Za-z0-9]+", "_", report["subject"].get("name") or "report").strip("_")
    db.log_activity("goaml_export", report["subject"].get("name", ""))
    return app.response_class(
        goaml.build_xml(report, reason=body.get("reason", "")),
        mimetype="application/xml",
        headers={"Content-Disposition": f'attachment; filename="SanctionsPlus_goAML_{name}.xml"'},
    )


@app.post("/api/batch_screen")
def api_batch_screen():
    """Screen a list of names in one pass. Accepts either a JSON body
    {"names": [...], "entity_type": "any"} or a multipart file upload under
    "file" — one name per line, or the first column of a CSV.
    """
    entity_type = (request.form.get("entity_type") or request.args.get("entity_type")
                   or "any")
    names = []
    if "file" in request.files:
        raw = request.files["file"].read().decode("utf-8", errors="ignore")
        for line in raw.splitlines():
            first_cell = line.split(",")[0].strip().strip('"')
            if first_cell and first_cell.lower() not in ("name", "names"):
                names.append(first_cell)
    else:
        body = request.get_json(silent=True) or {}
        names = body.get("names") or []
        entity_type = body.get("entity_type") or entity_type
    if not names:
        return jsonify({"error": "No names found — upload a CSV/text file or send {\"names\": [...]}."}), 400
    if len(names) > 200:
        return jsonify({"error": f"{len(names)} names is too many for one batch (limit 200) — "
                                  "split the list to stay within API rate limits."}), 400
    results = batch_screen(names, entity_type=entity_type)
    db.log_activity("batch_screen", f"{len(names)} names")
    return jsonify({"results": results})


@app.get("/api/batch_screen.csv")
def api_batch_screen_csv():
    """Same as /api/batch_screen but returns the results as a downloadable CSV
    — pass the names as repeated ?name=... query params (kept as GET so the
    browser can trigger a file download directly).
    """
    names = request.args.getlist("name")
    entity_type = request.args.get("entity_type") or "any"
    if not names:
        return jsonify({"error": "No names supplied."}), 400
    results = batch_screen(names, entity_type=entity_type)
    lines = ["name,matched,matched_name,type,risk_band,risk_score,flags,country"]
    for r in results:
        if r.get("error"):
            lines.append(f'"{r["name"]}",error,,,,,{r["error"]},')
        elif not r.get("matched"):
            lines.append(f'"{r["name"]}",false,,,,,,')
        else:
            flags = "|".join(r.get("flags") or [])
            lines.append(
                f'"{r["name"]}",true,"{r.get("matched_name", "")}",{r.get("type", "")},'
                f'{r.get("risk_band", "")},{r.get("risk_score", "")},"{flags}",{r.get("country", "")}'
            )
    db.log_activity("batch_screen_csv", f"{len(names)} names")
    return app.response_class(
        "\n".join(lines),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="SanctionsPlus_batch_screening.csv"'},
    )


@app.post("/api/cases")
def api_cases_create():
    """Save the current result set + entity as a named case for later."""
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    name = (body.get("name") or "").strip()
    if not payload or not node_id or not name:
        return jsonify({"error": "name, payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    node_name = report["subject"].get("name") if not report.get("error") else node_id
    case_id = db.save_case(name, node_id, node_name, payload, notes=body.get("notes", ""))
    return jsonify({"id": case_id})


@app.get("/api/cases")
def api_cases_list():
    return jsonify({"cases": db.list_cases()})


@app.get("/api/cases/<int:case_id>")
def api_cases_get(case_id):
    case = db.get_case(case_id)
    if not case:
        return jsonify({"error": "No such case."}), 404
    return jsonify(case)


@app.post("/api/cases/<int:case_id>/notes")
def api_cases_notes(case_id):
    body = request.get_json(silent=True) or {}
    if not db.update_case_notes(case_id, body.get("notes", "")):
        return jsonify({"error": "No such case."}), 404
    return jsonify({"ok": True})


@app.delete("/api/cases/<int:case_id>")
def api_cases_delete(case_id):
    if not db.delete_case(case_id):
        return jsonify({"error": "No such case."}), 404
    return jsonify({"ok": True})


@app.post("/api/watchlist")
def api_watchlist_add():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "A name is required."}), 400
    watch_id = db.add_watch(
        name, entity_type=body.get("entity_type") or "any",
        nationality=body.get("nationality"), birth_date=body.get("birth_date"),
    )
    return jsonify({"id": watch_id})


@app.get("/api/watchlist")
def api_watchlist_list():
    return jsonify({"watches": db.list_watches()})


@app.delete("/api/watchlist/<int:watch_id>")
def api_watchlist_delete(watch_id):
    if not db.delete_watch(watch_id):
        return jsonify({"error": "No such watch."}), 404
    return jsonify({"ok": True})


def _check_watch(watch: dict) -> dict:
    payload = run_search(
        name=watch["name"], entity_type=watch["entity_type"],
        nationality=watch.get("nationality"), birth_date=watch.get("birth_date"), hops=1,
    )
    root = next((n for n in payload.get("nodes", []) if n.get("is_root")), None)
    new_flags = sorted(root.get("risk_flags") or []) if root else []
    new_band = root.get("risk_band") if root else None
    previous_flags = set(watch.get("last_flags") or [])
    newly_added = sorted(set(new_flags) - previous_flags)
    db.update_watch_result(watch["id"], new_flags, new_band)
    if newly_added:
        db.log_activity("watch_alert", f"{watch['name']}: new flag(s) {', '.join(newly_added)}")
    return {
        "id": watch["id"], "name": watch["name"], "matched": bool(root),
        "risk_band": new_band, "flags": new_flags, "new_flags": newly_added,
    }


@app.post("/api/watchlist/<int:watch_id>/check")
def api_watchlist_check(watch_id):
    watch = db.get_watch(watch_id)
    if not watch:
        return jsonify({"error": "No such watch."}), 404
    return jsonify(_check_watch(watch))


@app.post("/api/watchlist/check_all")
def api_watchlist_check_all():
    """Re-screen every saved watch in one call. There's no scheduler built
    into this app — Render's free tier has no cron — so "ongoing monitoring"
    means pointing an external scheduler (Render's own paid Cron Jobs, or a
    free service like cron-job.org) at this endpoint on whatever cadence
    makes sense, rather than it running itself.
    """
    results = [_check_watch(watch) for watch in db.list_watches()]
    return jsonify({"results": results})


@app.get("/api/activity")
def api_activity():
    return jsonify({"activity": db.recent_activity()})


@app.get("/healthz")
def healthz():
    """Liveness probe for hosting platforms (and a cheap way to warm a cold start)."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    status = config.status()
    print("Sanctions+")
    print(f"  OpenSanctions : {'live' if status['opensanctions'] else 'off'}")
    print(f"  OpenCorporates: {'live' if status['opencorporates'] else 'off'}")
    print(f"  Adverse media : {'live' if status['adverse_media'] else 'off'}")
    if status["demo_mode"]:
        print("  No keys found — serving synthetic demo data.")
    print(f"\n  http://localhost:{config.PORT}\n")
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
