#!/usr/bin/env python3
"""
Three-way retrieval eval — keyword vs semantic vs hybrid.

For each query in eval/queries.yml:
  1. Run all three engines independently (top-5 each).
  2. Judge relevance of each result:
       - `judge: auto` → keyword-match against relevant_keywords groups
       - `judge: manual` → prompt human
  3. Report recall@5 per engine per difficulty bucket.

Writes:
  eval/results.json  — raw results per query per engine
  eval/report.md     — Markdown report (this is what goes in the README)

Usage:
  python eval/run.py [--top-k 5]
"""
import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import keyword_search
import semantic_search
import hybrid_search

EVAL_DIR = Path(__file__).resolve().parent
QUERIES_FILE = EVAL_DIR / "queries.yml"
RESULTS_FILE = EVAL_DIR / "results.json"
REPORT_FILE  = EVAL_DIR / "report.md"

ENGINES = [
    ("keyword",  keyword_search.search),
    ("semantic", semantic_search.search),
    ("hybrid",   hybrid_search.search),
]


def is_relevant_auto(result: dict, keyword_groups: list[list[str]]) -> bool:
    """A result is relevant if any keyword group is fully present in problem+solution+equipment."""
    text = " ".join([
        result.get("equipment", ""),
        result.get("problem", ""),
        result.get("solution", ""),
    ]).lower()
    for group in keyword_groups:
        if all(kw.lower() in text for kw in group):
            return True
    return False


def evaluate_one(query_spec: dict, top_k: int) -> dict:
    q = query_spec["query"]
    print(f"\n── [{query_spec['id']}] ({query_spec['difficulty']}) {q!r}")

    engine_results = {}
    for name, fn in ENGINES:
        t0 = time.time()
        hits = fn(q, top_k=top_k)
        elapsed_ms = int((time.time() - t0) * 1000)

        if query_spec.get("judge", "auto") == "auto":
            relevant_flags = [
                is_relevant_auto(h, query_spec.get("relevant_keywords", []))
                for h in hits
            ]
        else:
            relevant_flags = [None] * len(hits)  # manual mode: not judged here

        hit_count = sum(1 for f in relevant_flags if f)
        recall = hit_count / top_k if top_k else 0

        engine_results[name] = {
            "elapsed_ms": elapsed_ms,
            "hits": [
                {**h, "relevant": r}
                for h, r in zip(hits, relevant_flags)
            ],
            "recall_at_k": round(recall, 3),
        }
        marker = "✓" if hit_count >= 3 else ("~" if hit_count >= 1 else "✗")
        print(f"   {marker} {name:9s}  recall@{top_k}={recall:.2f}  ({hit_count}/{top_k}, {elapsed_ms}ms)")

    return {"query": query_spec, "engines": engine_results}


def build_report(results: list[dict], top_k: int) -> str:
    lines = []
    lines.append(f"# Retrieval eval — keyword / semantic / hybrid")
    lines.append("")
    lines.append(f"**{len(results)} queries × 3 engines × top-{top_k}**  "
                 f"— relevance judged automatically via keyword-group matching on result text.")
    lines.append("")

    # ── Per-query table ────────────────────────────────────────────────────────
    lines.append("## Per-query recall@5")
    lines.append("")
    lines.append("| id  | difficulty  | query                                                 | keyword | semantic | hybrid |")
    lines.append("|-----|-------------|-------------------------------------------------------|---------|----------|--------|")
    for r in results:
        q = r["query"]
        row = f"| {q['id']:<3s} | {q['difficulty']:<11s} | {q['query'][:53]:<53s} "
        for name, _ in ENGINES:
            row += f"| {r['engines'][name]['recall_at_k']:.2f}   "
        row += "|"
        lines.append(row)
    lines.append("")

    # ── Aggregate by difficulty ────────────────────────────────────────────────
    lines.append("## Aggregate recall@5 by difficulty")
    lines.append("")
    lines.append("| difficulty  | queries | keyword | semantic | hybrid |")
    lines.append("|-------------|---------|---------|----------|--------|")
    bucket = defaultdict(lambda: defaultdict(list))
    for r in results:
        diff = r["query"]["difficulty"]
        for name, _ in ENGINES:
            bucket[diff][name].append(r["engines"][name]["recall_at_k"])
    for diff in ["easy", "paraphrase", "hard"]:
        if diff not in bucket:
            continue
        n = len(bucket[diff]["keyword"])
        row = f"| {diff:<11s} | {n:^7d} "
        for name, _ in ENGINES:
            vals = bucket[diff][name]
            avg = sum(vals) / len(vals) if vals else 0
            row += f"| {avg:.2f}   "
        row += "|"
        lines.append(row)
    lines.append("")

    # ── Overall ────────────────────────────────────────────────────────────────
    lines.append("## Overall recall@5")
    lines.append("")
    lines.append("| engine   | mean recall@5 |")
    lines.append("|----------|---------------|")
    for name, _ in ENGINES:
        vals = [r["engines"][name]["recall_at_k"] for r in results]
        avg = sum(vals) / len(vals) if vals else 0
        lines.append(f"| {name:<8s} | {avg:.2f}          |")
    lines.append("")

    # ── Timing ─────────────────────────────────────────────────────────────────
    lines.append("## Mean latency (ms)")
    lines.append("")
    lines.append("| engine   | mean ms |")
    lines.append("|----------|---------|")
    for name, _ in ENGINES:
        vals = [r["engines"][name]["elapsed_ms"] for r in results]
        avg = sum(vals) / len(vals) if vals else 0
        lines.append(f"| {name:<8s} | {avg:.0f}     |")
    lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", "--top-k", type=int, default=5)
    args = ap.parse_args()

    with QUERIES_FILE.open() as f:
        spec = yaml.safe_load(f)
    queries = spec["queries"]

    results = [evaluate_one(q, args.top_k) for q in queries]

    RESULTS_FILE.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nwrote {RESULTS_FILE}")

    report = build_report(results, args.top_k)
    REPORT_FILE.write_text(report)
    print(f"wrote {REPORT_FILE}")


if __name__ == "__main__":
    main()
