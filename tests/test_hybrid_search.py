"""Tests for the RRF fusion logic in hybrid_search.

We stub the heavy dependencies (chromadb, torch, sentence-transformers) at the
sys.modules level BEFORE hybrid_search imports semantic_search, so the fusion
logic can be tested in isolation in <1s without a 200MB install.
"""
import sys
from unittest.mock import MagicMock

# Stub heavy deps and their submodules BEFORE hybrid_search transitively imports them.
# MagicMock covers arbitrary attribute access (Settings, PersistentClient, etc.)
# but we register both the parent and submodule names so `from chromadb.config import X` works.
for name in ("chromadb", "chromadb.config", "sentence_transformers", "torch"):
    sys.modules.setdefault(name, MagicMock())

import hybrid_search  # noqa: E402


def _mk_hit(rid: str, extra: dict | None = None) -> dict:
    base = {"id": rid, "date": "2026-01-01", "casino": "X", "department": "IT",
            "equipment": "eq", "problem": "p", "solution": "s", "status": "closed"}
    if extra:
        base.update(extra)
    return base


def _patch_engines(monkeypatch, kw_results, sem_results):
    monkeypatch.setattr(hybrid_search.keyword_search, "search",
                        lambda *a, **kw: kw_results)
    monkeypatch.setattr(hybrid_search.semantic_search, "search",
                        lambda *a, **kw: sem_results)


class TestRRFFusion:
    def test_fusion_prefers_documents_ranked_high_in_both_engines(self, monkeypatch):
        _patch_engines(monkeypatch,
                       [_mk_hit("a"), _mk_hit("b"), _mk_hit("c")],
                       [_mk_hit("a"), _mk_hit("c"), _mk_hit("d")])
        out = hybrid_search.search("q", top_k=4, pool=10)
        assert out[0]["id"] == "a"
        assert set(r["id"] for r in out) == {"a", "b", "c", "d"}

    def test_origins_tracks_both_engines(self, monkeypatch):
        _patch_engines(monkeypatch, [_mk_hit("a")], [_mk_hit("a")])
        out = hybrid_search.search("q", top_k=1, pool=10)
        assert set(out[0]["origins"]) == {"keyword", "semantic"}

    def test_engine_tag_is_hybrid(self, monkeypatch):
        _patch_engines(monkeypatch, [_mk_hit("a")], [])
        out = hybrid_search.search("q", top_k=1, pool=10)
        assert out[0]["engine"] == "hybrid"

    def test_top_k_limits_output(self, monkeypatch):
        _patch_engines(monkeypatch,
                       [_mk_hit(f"k{i}") for i in range(20)],
                       [_mk_hit(f"s{i}") for i in range(20)])
        out = hybrid_search.search("q", top_k=5, pool=20)
        assert len(out) == 5

    def test_scores_are_sorted_descending(self, monkeypatch):
        _patch_engines(monkeypatch,
                       [_mk_hit(f"k{i}") for i in range(5)],
                       [_mk_hit(f"s{i}") for i in range(5)])
        out = hybrid_search.search("q", top_k=5, pool=10)
        scores = [r["score"] for r in out]
        assert scores == sorted(scores, reverse=True)

    def test_empty_engines_returns_empty(self, monkeypatch):
        _patch_engines(monkeypatch, [], [])
        out = hybrid_search.search("q", top_k=5, pool=10)
        assert out == []
