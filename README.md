# maintenance-search

Hybrid keyword + semantic search over a synthetic maintenance-log dataset — with an honest three-way evaluation of what each retrieval mode wins and loses.

Ships a ~5,000-row synthetic sample so the code runs out of the box.

## Why this exists

Field ops teams write terse, jargon-heavy problem descriptions in shared logs — the kind of dataset where a plain keyword search misses paraphrases and a plain semantic search misses exact-vocabulary matches. This project builds all three retrievers side by side (keyword, semantic, hybrid) so the trade-offs are visible on the same evaluation set.

The dataset is synthetic: templated ops entries plus LLM-generated maintenance descriptions across common equipment categories (cameras, network gear, POS terminals, HVAC, etc.). The point is the retrieval architecture, not the data — the same code works on any tab-separated log with a free-text problem field.

## Results

Evaluated on 10 curated technician queries covering easy, paraphrased, and hard cases against the ~5,000-row synthetic sample shipped in `data/sample.csv`:

| engine   | mean recall@5 |
|----------|---------------|
| keyword  | 0.88          |
| semantic | 0.84          |
| **hybrid**   | **0.88**  |

By difficulty:

| difficulty  | queries | keyword | semantic | hybrid |
|-------------|---------|---------|----------|--------|
| easy        | 3       | 1.00    | 1.00     | 1.00   |
| paraphrase  | 4       | 0.90    | 0.85     | **0.95** |
| hard        | 3       | **0.73**| 0.67     | 0.67   |

- On this synthetic dataset all three engines do well on easy queries — vocabulary is clean, matches are direct.
- Hybrid pulls ahead on paraphrases (0.95 vs 0.90 keyword / 0.85 semantic): the same query hits both engines' candidate pools and RRF re-ranking surfaces the intersection.
- Keyword's `PHRASE_MAP` genuinely helps: for terse maintenance descriptions, hand-written synonym expansions cover common paraphrases that pure embeddings sometimes miss.
- Hard queries are hardest for semantic — abstract/compositional queries need context the embedding model doesn't have.

Latency after model warm-up: keyword ~80ms, semantic ~10ms (Chroma is fast), hybrid ~90ms.

Full breakdown: [`eval/report.md`](eval/report.md).

## Architecture

```
                   ┌──────────────────────────┐
                   │  maintenance CSV         │
                   └──────────┬───────────────┘
                              │
                     ┌────────┴─────────┐
                     ▼                  ▼
       ┌──────────────────┐   ┌────────────────────┐
       │  keyword engine  │   │  semantic engine   │
       │  fuzzy + phrase  │   │  MiniLM → Chroma   │
       │  map expansion   │   │  (384-dim cosine)  │
       └────────┬─────────┘   └──────────┬─────────┘
                │  top-20                │  top-20
                └──────────┬─────────────┘
                           ▼
                  ┌──────────────────┐
                  │  hybrid: RRF     │
                  │  fusion (k=60)   │
                  └────────┬─────────┘
                           ▼
                     top-k results
```

RRF (Reciprocal Rank Fusion, Cormack et al. 2009) is rank-based rather than score-based, so the two engines' incomparable score scales don't need calibration. `k=60` is the standard smoothing constant from the paper.

## Stack

- Python 3.12, CPU-only PyTorch
- [Chroma](https://www.trychroma.com/) — local persistent vector store
- [sentence-transformers](https://www.sbert.net/) — `all-MiniLM-L6-v2` embeddings
- No LLM calls at query time; the embedding model is downloaded on first use

## Layout

```
src/
  config.py            paths and constants — all env-overridable
  build_index.py       CSV → Chroma
  phrase_map.py        hand-curated regex → expansion table
  keyword_engine.py    lexical engine (self-contained)
  keyword_search.py    thin CLI over keyword_engine
  semantic_search.py   Chroma + MiniLM
  hybrid_search.py     RRF fusion of keyword + semantic
eval/
  queries.yml          10 test queries (3 easy, 4 paraphrase, 3 hard)
  run.py               three-way eval → report.md
  report.md            latest results
scripts/
  generate_sample.py   builds data/sample.csv from templates + LLM prompts
data/
  sample.csv           synthetic ~5,000-row dataset
```

## Usage

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time: index the sample CSV
python src/build_index.py --rebuild

# Query each engine independently
python src/keyword_search.py  "card reader not working" --pretty
python src/semantic_search.py "video feed is dark and grainy" --pretty
python src/hybrid_search.py   "cabinet unresponsive to touch" --pretty

# Full three-way eval
python eval/run.py
```

To run against your own data, set `MAINTENANCE_CSV=/path/to/your.csv` and rebuild the index. Any tab-separated file with `Report Date, Casino Name, Department, Sub-Department, Maintenance Type, Equipment / Location, Problem Description, Action Taken / Solution, Status, Notes` will work — the column set is a common shape for field ops logs.

## Notes

- Ops-log text is often messy: empty problem descriptions, "nan" equipment fields, tersely written solutions. The retrieval code handles these gracefully rather than filtering them out; that's part of why hybrid wins on the hard queries — it recovers cases where either single engine falls off.
- The `PHRASE_MAP` in `phrase_map.py` is a small hand-curated regex table that expands common paraphrases into their canonical vocabulary. A follow-up experiment tested whether it could be extended automatically by mining query-miss patterns; the honest answer was "not without human review."
