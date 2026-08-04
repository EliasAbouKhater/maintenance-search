#!/usr/bin/env python3
"""
Semantic search over the Chroma index. Independent of keyword/hybrid engines.

Result shape (shared by all three engines):
    {
        "id":        str,   # row id
        "score":     float, # higher = better
        "date":      str,
        "casino":    str,
        "department":str,
        "equipment": str,
        "problem":   str,   # first ~200 chars
        "solution":  str,   # first ~200 chars
        "status":    str,
        "engine":    "semantic" | "keyword" | "hybrid",
    }
"""
import argparse
import csv
import json
import sys
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from config import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL, CSV_PATH, DEFAULT_TOP_K


@lru_cache(maxsize=1)
def _model():
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def _collection():
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    return client.get_collection(COLLECTION_NAME)


@lru_cache(maxsize=1)
def _row_lookup() -> dict:
    """Load the CSV once to return full problem/solution text for each row_id."""
    lookup = {}
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            lookup[f"m{i:06d}"] = row
    return lookup


def _build_where(location=None, country=None, department=None, status=None,
                 date_from=None, date_to=None) -> dict | None:
    """Chroma metadata filter. Uses $and when multiple predicates are combined."""
    preds = []
    if location:   preds.append({"casino":     {"$eq": location}})
    if department: preds.append({"department": {"$eq": department}})
    if status:     preds.append({"status":     {"$eq": status}})
    if date_from:  preds.append({"date":       {"$gte": date_from}})
    if date_to:    preds.append({"date":       {"$lte": date_to}})
    # country isn't stored as metadata (it's derived from casino) — leave to post-filter if needed
    if not preds:
        return None
    if len(preds) == 1:
        return preds[0]
    return {"$and": preds}


def _truncate(s: str, n: int = 200) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def search(query: str, top_k: int = DEFAULT_TOP_K, **filters) -> list[dict]:
    """
    Semantic search. Returns top-k rows ranked by cosine similarity.

    Chroma returns distances (0 = identical, higher = further). We convert to a
    similarity score in [0, 1] roughly so higher = better, matching the other engines.
    """
    where = _build_where(**filters)
    q_embedding = _model().encode([query]).tolist()

    # Chroma HNSW can throw "Cannot return results in contiguous 2D array"
    # when the requested n_results exceeds what the graph can produce (small
    # candidate pool after many upserts). Fall back to progressively smaller k.
    collection = _collection()
    effective_k = min(top_k, max(1, collection.count()))
    results = None
    for attempt_k in [effective_k, max(1, effective_k // 2), 5, 1]:
        try:
            results = collection.query(
                query_embeddings=q_embedding,
                n_results=attempt_k,
                where=where,
            )
            break
        except RuntimeError as e:
            if "contigious" in str(e).lower() or "ef" in str(e).lower():
                continue
            raise
    if results is None or not results["ids"] or not results["ids"][0]:
        return []

    lookup = _row_lookup()
    out = []
    for rid, meta, distance in zip(
        results["ids"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        row = lookup.get(rid, {})
        # Cosine distance in [0, 2]; convert to similarity in ~[-1, 1] then clamp to [0, 1]
        score = max(0.0, 1.0 - distance / 2.0)
        out.append({
            "id":         rid,
            "score":      round(score, 4),
            "date":       meta.get("date", ""),
            "casino":     meta.get("casino", ""),
            "department": meta.get("department", ""),
            "equipment":  meta.get("equipment", ""),
            "problem":    _truncate(row.get("Problem Description", "")),
            "solution":   _truncate(row.get("Action Taken / Solution", "")),
            "status":     meta.get("status", ""),
            "engine":     "semantic",
        })
    return out


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
            print(f"  Solution : {r['solution']}")
            print()
    else:
        print(json.dumps({"count": len(results), "results": results}, indent=2))


if __name__ == "__main__":
    main()
