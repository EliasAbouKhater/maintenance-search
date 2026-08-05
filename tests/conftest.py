"""Pytest configuration — makes src/ importable without installing the package."""
import sys
from pathlib import Path

SRC = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC))
