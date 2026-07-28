"""Command-line entry point.

    python pipeline.py "falcon capital"
    python pipeline.py "Elena Kovacs" --type person --nationality cy --json out.json
"""
import argparse
import json
import sys

import config
from search import check_sources, run_search, summarise


def main() -> int:
    parser = argparse.ArgumentParser(description="Map corporate ownership networks.")
    parser.add_argument("name", nargs="?", help="Person or company name to search for")
    parser.add_argument("--check-keys", action="store_true",
                        help="Test each configured API key and exit")
    parser.add_argument("--type", dest="entity_type", default="any",
                        choices=["any", "person", "company"])
    parser.add_argument("--nationality", default=None, help="ISO country code, e.g. ae")
    parser.add_argument("--dob", dest="birth_date", default=None, help="YYYY or YYYY-MM-DD")
    parser.add_argument("--reg", dest="reg_number", default=None, help="Registration number")
    parser.add_argument("--jurisdiction", default=None, help="e.g. ae_du, gb, ky")
    parser.add_argument("--hops", type=int, default=3)
    parser.add_argument("--json", dest="json_out", default=None,
                        help="Write the full graph payload to this file")
    args = parser.parse_args()

    if args.check_keys:
        print("\nChecking configured sources…\n")
        worst = 0
        for result in check_sources():
            mark = {"ok": "  OK  ", "failed": " FAIL ", "not configured": "  --  "}[result["state"]]
            print(f"[{mark}] {result['source']}: {result['detail']}")
            worst = max(worst, 1 if result["state"] == "failed" else 0)
        print()
        return worst

    if not args.name:
        parser.error("a name is required (or use --check-keys)")

    status = config.status()
    print(
        "sources: opensanctions=%s opencorporates=%s adverse_media=%s"
        % (
            "on" if status["opensanctions"] else "off",
            "on" if status["opencorporates"] else "off",
            "on" if status["adverse_media"] else "off",
        )
    )

    payload = run_search(
        name=args.name,
        entity_type=args.entity_type,
        nationality=args.nationality,
        birth_date=args.birth_date,
        reg_number=args.reg_number,
        jurisdiction=args.jurisdiction,
        hops=args.hops,
    )
    if payload.get("error"):
        print(payload["error"], file=sys.stderr)
        return 1

    if payload.get("demo_mode"):
        print("running on synthetic demo data\n")
    print(summarise(payload))

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nwrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
