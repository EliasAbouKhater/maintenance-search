#!/usr/bin/env python3
"""
Hybrid search — fuses keyword + semantic results via Reciprocal Rank Fusion (RRF).

RRF is rank-based, not score-based, so it's insensitive to the score scales of
the two engines (which are not comparable). Formula:

    RRF(d) = sum over engines of  1 / (k + rank(d))

k=60 is the standard smoothing constant from the RRF paper (Cormack et al.).

Each engine remains independently callable via keyword_search.search /
semantic_search.search — this module only combines their outputs.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import keyword_search
import semantic_search
from config import DEFAULT_TOP_K

RRF_K = 60


def search(query: str, top_k: int = DEFAULT_TOP_K, pool: int = 20, **filters) -> list[dict]:
    """
    Pull `pool` candidates from each engine, fuse via RRF, return top_k.

    `pool` should be larger than top_k so we have overlap to fuse.
    """
    kw_hits  = keyword_search.search(query, top_k=pool, **filters)
    sem_hits = semantic_search.search(query, top_k=pool, **filters)

    scores: dict[str, float] = {}
    origins: dict[str, list[str]] = {}
    rows: dict[str, dict] = {}

    for engine_hits, tag in [(kw_hits, "keyword"), (sem_hits, "semantic")]:
        for rank, hit in enumerate(engine_hits):
            rid = hit["id"]
            scores[rid] = scores.get(rid, 0.0) + 1.0 / (RRF_K + rank + 1)
            origins.setdefault(rid, []).append(tag)
            # Prefer semantic's row payload (has richer text); keyword payload if missing
            if rid not in rows or tag == "semantic":
                rows[rid] = hit

    fused = sorted(scores.items(), key=lambda x: -x[1])[:top_k]

    out = []
    for rid, rrf_score in fused:
        row = dict(rows[rid])
        row["score"]  = round(rrf_score, 5)
        row["engine"] = "hybrid"
        row["origins"] = origins[rid]  # ['keyword'], ['semantic'], or both
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("-k", "--top-k", type=int, default=DEFAULT_TOP_K)
    ap.add_argument("--pool", type=int, default=20)
    ap.add_argument("--location")
    ap.add_argument("--department")
    ap.add_argument("--status")
    ap.add_argument("--from", dest="date_from")
    ap.add_argument("--to",   dest="date_to")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    results = search(
        args.query, top_k=args.top_k, pool=args.pool,
        location=args.location, department=args.department, status=args.status,
        date_from=args.date_from, date_to=args.date_to,
    )

    if args.pretty:
        for r in results:
            src = "+".join(r.get("origins", []))
            print(f"[{r['id']}] rrf={r['score']:.4f}  ({src})  {r['date']} | {r['casino']} — {r['department']}")
            print(f"  Equipment: {r['equipment']}")
            print(f"  Problem  : {r['problem']}")
            print(f"  Solution : {r['solution']}")
            print()
    else:
        print(json.dumps({"count": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
