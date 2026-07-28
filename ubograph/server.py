"""Flask server: static frontend + the /api endpoints it calls."""
import json

from flask import Flask, jsonify, request, send_from_directory

import config
from search import run_search

app = Flask(__name__, static_folder="frontend", static_url_path="")


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
