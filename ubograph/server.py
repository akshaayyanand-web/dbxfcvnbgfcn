"""Flask server: static frontend + the /api endpoints it calls."""
import json
import re
import secrets

from flask import Flask, Response, jsonify, request, send_from_directory

import config
import pdf as pdf_renderer
import reference
from report import build_report
from search import run_search

app = Flask(__name__, static_folder="frontend", static_url_path="")


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
    auth = request.authorization
    if auth and auth.username == config.APP_USERNAME and \
            secrets.compare_digest(auth.password or "", config.APP_PASSWORD):
        return None
    return Response(
        "Authentication required.", 401,
        {"WWW-Authenticate": 'Basic realm="UBOgraph"'},
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
    return jsonify(payload)


@app.get("/api/reference")
def api_reference():
    """Country and jurisdiction lists for the form dropdowns."""
    return jsonify({
        "countries": reference.countries(),
        "jurisdictions": reference.jurisdictions(),
    })


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
    return jsonify(report)


@app.post("/api/report.pdf")
def api_report_pdf():
    body = request.get_json(silent=True) or {}
    payload, node_id = body.get("payload"), body.get("node_id")
    if not payload or not node_id:
        return jsonify({"error": "payload and node_id are required."}), 400
    report = build_report(payload, node_id)
    if report.get("error"):
        return jsonify(report), 404
    name = re.sub(r"[^A-Za-z0-9]+", "_", report["subject"].get("name") or "report").strip("_")
    return app.response_class(
        pdf_renderer.render(report),
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="UBOgraph_{name}.pdf"'},
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
    filename = (payload.get("query", {}).get("name") or "ubograph").replace(" ", "_")
    return app.response_class(
        body,
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
    )


@app.get("/healthz")
def healthz():
    """Liveness probe for hosting platforms (and a cheap way to warm a cold start)."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    status = config.status()
    print("UBOgraph")
    print(f"  OpenSanctions : {'live' if status['opensanctions'] else 'off'}")
    print(f"  OpenCorporates: {'live' if status['opencorporates'] else 'off'}")
    print(f"  Adverse media : {'live' if status['adverse_media'] else 'off'}")
    if status["demo_mode"]:
        print("  No keys found — serving synthetic demo data.")
    print(f"\n  http://localhost:{config.PORT}\n")
    app.run(host="0.0.0.0", port=config.PORT, debug=False)
