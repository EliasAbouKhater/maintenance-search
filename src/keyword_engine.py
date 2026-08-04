"""
Lexical (keyword) search engine — self-contained.

On first use, builds two in-memory indexes from the CSV:
  - by_keyword: token → list of row_ids that contain it
  - by_field:   department/status → list of row_ids

Search is: tokenize query → expand via PHRASE_MAP → fuzzy-match each token
against the inverted index → sum scores → return top-k.

This is a straight port of the internal `search-maintenance.py` with two
public-repo changes:
  1. No dependency on pre-built maintenance-index.json — index is built at
     import time from the CSV directly.
  2. No location metadata table — Casino Name is used as-is (already redacted).
"""
import csv
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from config import CSV_PATH
from phrase_map import PHRASE_MAP, STOP_WORDS


def _tokenize(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
            if len(w) > 2 and w not in STOP_WORDS]


def _preprocess_query(query: str) -> list[str]:
    q = query.lower().strip()
    extra: list[str] = []
    for pattern, expansion in PHRASE_MAP.items():
        if re.search(pattern, q):
            extra.extend(expansion.split())
    tokens = _tokenize(q) + extra
    return list(dict.fromkeys(tokens))


def _fuzzy_score(word: str, keyword: str) -> int:
    if word == keyword:
        return 5
    if word in keyword or keyword in word:
        return 3
    if len(word) > 3 and len(keyword) > 3:
        ratio = SequenceMatcher(None, word, keyword).ratio()
        if ratio >= 0.85: return 2
        if ratio >= 0.75: return 1
    return 0


@lru_cache(maxsize=1)
def _load_index() -> dict:
    """
    Build the inverted index once from the CSV. Returns:
        {
          "rows": {row_id: full_row_dict},
          "by_keyword": {token: [row_id, ...]},
          "by_department": {dept: [row_id, ...]},
          "by_status": {status: [row_id, ...]},
        }
    """
    rows: dict[str, dict] = {}
    by_keyword: defaultdict = defaultdict(list)
    by_department: defaultdict = defaultdict(list)
    by_status: defaultdict = defaultdict(list)

    with Path(CSV_PATH).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for i, row in enumerate(reader):
            rid = f"m{i:06d}"
            rows[rid] = row

            text = " ".join([
                row.get("Equipment / Location", ""),
                row.get("Problem Description", ""),
                row.get("Action Taken / Solution", ""),
                row.get("Notes", ""),
            ])
            for tok in set(_tokenize(text)):
                by_keyword[tok].append(rid)

            dept = (row.get("Department") or "").strip().lower()
            if dept:
                by_department[dept].append(rid)
            status = (row.get("Status") or "").strip().lower()
            if status:
                by_status[status].append(rid)

    return {
        "rows":          rows,
        "by_keyword":    dict(by_keyword),
        "by_department": dict(by_department),
        "by_status":     dict(by_status),
    }


def _truncate(s: str, n: int = 200) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def search(query: str, top_k: int = 5, *,
           location: str | None = None,
           department: str | None = None,
           status: str | None = None,
           date_from: str | None = None,
           date_to: str | None = None,
           **_ignored) -> list[dict]:
    """
    Return top-k rows scored by fuzzy keyword match against the query.
    Metadata filters intersect with the keyword-score candidates before ranking.

    `**_ignored` swallows filter kwargs (like country) that this engine doesn't
    support but that hybrid_search may pass through.
    """
    idx = _load_index()
    rows = idx["rows"]

    candidate_ids: set | None = None

    def _intersect(ids: set) -> None:
        nonlocal candidate_ids
        candidate_ids = ids if candidate_ids is None else candidate_ids & ids

    if location:
        ll = location.lower()
        ids = {rid for rid, r in rows.items()
               if ll in (r.get("Casino Name") or "").lower()}
        _intersect(ids)
    if department:
        _intersect(set(idx["by_department"].get(department.lower(), [])))
    if status:
        _intersect(set(idx["by_status"].get(status.lower(), [])))
    if date_from or date_to:
        ids = set()
        for rid, row in rows.items():
            d = (row.get("Report Date") or "").strip()
            if date_from and d < date_from: continue
            if date_to   and d > date_to:   continue
            ids.add(rid)
        _intersect(ids)

    tokens = _preprocess_query(query)
    scores: Counter = Counter()
    by_keyword = idx["by_keyword"]
    all_keywords = list(by_keyword.keys())

    for token in tokens:
        for kw in all_keywords:
            sc = _fuzzy_score(token, kw)
            if sc > 0:
                for rid in by_keyword[kw]:
                    if candidate_ids is None or rid in candidate_ids:
                        scores[rid] += sc

    max_score = max(scores.values(), default=1) or 1
    out = []
    for rid, score in scores.most_common(top_k):
        r = rows[rid]
        out.append({
            "id":         rid,
            "score":      round(score / max_score, 4),
            "date":       (r.get("Report Date") or "").strip(),
            "casino":     (r.get("Casino Name") or "").strip(),
            "department": (r.get("Department") or "").strip(),
            "equipment":  (r.get("Equipment / Location") or "").strip(),
            "problem":    _truncate(r.get("Problem Description", "")),
            "solution":   _truncate(r.get("Action Taken / Solution", "")),
            "status":     (r.get("Status") or "").strip(),
            "engine":     "keyword",
        })
    return out
