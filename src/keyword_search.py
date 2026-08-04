#!/usr/bin/env python3
"""CLI for the lexical (keyword) engine."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import DEFAULT_TOP_K
from keyword_engine import search


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", "--top-k", type=int, default=DEFAULT_TOP_K)
    ap.add_argument("--location")
    ap.add_argument("--department")
    ap.add_argument("--status")
    ap.add_argument("--from", dest="date_from")
    ap.add_argument("--to",   dest="date_to")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    results = search(
        args.query, top_k=args.top_k,
        location=args.location, department=args.department, status=args.status,
        date_from=args.date_from, date_to=args.date_to,
    )

    if args.pretty:
        for r in results:
            print(f"[{r['id']}] score={r['score']:.3f}  {r['date']} | {r['casino']} — {r['department']}")
            print(f"  Equipment: {r['equipment']}")
            print(f"  Problem  : {r['problem']}")
            print(f"  Solution : {r['solution']}\n")
    else:
        print(json.dumps({"count": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
