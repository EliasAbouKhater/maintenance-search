"""Central config — all paths and constants live here so the project is portable."""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR     = PROJECT_ROOT / "data"
INDEX_DIR    = PROJECT_ROOT / "index"
EVAL_DIR     = PROJECT_ROOT / "eval"

# By default the demo uses the redacted public sample. Override with
# MAINTENANCE_CSV=/path/to/full.csv to run on the internal dataset.
CSV_PATH        = Path(os.environ.get("MAINTENANCE_CSV", DATA_DIR / "sample.csv"))
CHROMA_DIR      = Path(os.environ.get("CHROMA_DIR",      INDEX_DIR / "chroma"))
COLLECTION_NAME = "maintenance"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM   = 384

DEFAULT_TOP_K = 5
