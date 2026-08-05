#!/usr/bin/env python3
"""
Build a Chroma vector index over the casino maintenance CSV.

Each row becomes one document. The embedded text concatenates the fields
that carry semantic content (equipment, problem, solution, notes). Structured
fields (date, casino, country, department, status) are stored as Chroma
metadata so they can be used as filters at query time.

Usage:
  python src/build_index.py [--limit N] [--rebuild]
"""
import argparse
import csv
import sys
import time
from pathlib import Path

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from config import CHROMA_DIR, COLLECTION_NAME, CSV_PATH, EMBED_MODEL


def build_doc_text(row: dict) -> str:
    """Concatenate semantic fields into the text we embed."""
    parts = [
        row.get("Equipment / Location", ""),
        f"Problem: {row.get('Problem Description', '')}",
        f"Solution: {row.get('Action Taken / Solution', '')}",
    ]
    notes = row.get("Notes", "").strip()
    if notes:
        parts.append(f"Notes: {notes}")
    return " | ".join(p for p in parts if p.strip())


def build_metadata(row: dict, row_id: str) -> dict:
    """Chroma metadata must be str/int/float/bool — no None, no lists."""
    return {
        "row_id":         row_id,
        "date":           (row.get("Report Date") or "").strip(),
        "casino":         (row.get("Casino Name") or "").strip(),
        "department":     (row.get("Department") or "").strip(),
        "sub_department": (row.get("Sub-Department") or "").strip(),
        "maint_type":     (row.get("Maintenance Type") or "").strip(),
        "equipment":      (row.get("Equipment / Location") or "").strip(),
        "status":         (row.get("Status") or "").strip(),
    }


def load_rows(csv_path: Path, limit: int | None = None):
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            yield i, row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Index only the first N rows (for quick tests)")
    ap.add_argument("--rebuild", action="store_true",
                    help="Drop existing collection first")
    ap.add_argument("--batch", type=int, default=256,
                    help="Rows per embed/insert batch")
    args = ap.parse_args()

    print(f"[1/4] Loading embedding model: {EMBED_MODEL}")
    t0 = time.time()
    model = SentenceTransformer(EMBED_MODEL)
    print(f"      model loaded in {time.time() - t0:.1f}s")

    print(f"[2/4] Opening Chroma at {CHROMA_DIR}")
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(anonymized_telemetry=False),
    )
    if args.rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"      dropped existing collection '{COLLECTION_NAME}'")
        except Exception:
            pass
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"[3/4] Reading {CSV_PATH}")
    docs, metas, ids = [], [], []
    total = 0

    def flush():
        nonlocal docs, metas, ids
        if not docs:
            return
        embeddings = model.encode(docs, show_progress_bar=False, batch_size=64).tolist()
        collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
        docs, metas, ids = [], [], []

    t0 = time.time()
    for i, row in load_rows(CSV_PATH, args.limit):
        text = build_doc_text(row)
        if not text.strip():
            continue
        row_id = f"m{i:06d}"
        docs.append(text)
        metas.append(build_metadata(row, row_id))
        ids.append(row_id)
        total += 1
        if len(docs) >= args.batch:
            flush()
            if total % (args.batch * 4) == 0:
                elapsed = time.time() - t0
                rate = total / elapsed if elapsed else 0
                print(f"      indexed {total} rows  ({rate:.1f} rows/s)")
    flush()

    elapsed = time.time() - t0
    print(f"[4/4] Done. Indexed {total} rows in {elapsed:.1f}s "
          f"({total/elapsed:.1f} rows/s)")
    print(f"      collection '{COLLECTION_NAME}' count = {collection.count()}")


if __name__ == "__main__":
    main()
