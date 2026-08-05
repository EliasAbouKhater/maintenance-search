"""Unit tests for the keyword engine's pure functions."""
from keyword_engine import _fuzzy_score, _preprocess_query, _tokenize


class TestTokenize:
    def test_lowercases_input(self):
        assert _tokenize("SLOT Machine") == ["slot", "machine"]

    def test_strips_short_tokens(self):
        assert _tokenize("a bb ccc") == ["ccc"]

    def test_strips_stop_words(self):
        assert "the" not in _tokenize("the slot machine")

    def test_handles_empty_input(self):
        assert _tokenize("") == []
        assert _tokenize(None) == []

    def test_keeps_alphanumeric_only(self):
        assert _tokenize("slot#123 machine!") == ["slot", "123", "machine"]


class TestFuzzyScore:
    def test_exact_match_scores_highest(self):
        assert _fuzzy_score("slot", "slot") == 5

    def test_substring_match(self):
        assert _fuzzy_score("slot", "slots") == 3
        assert _fuzzy_score("slots", "slot") == 3

    def test_no_match_scores_zero(self):
        assert _fuzzy_score("aaaa", "zzzz") == 0

    def test_short_words_only_match_exact_or_substring(self):
        assert _fuzzy_score("abc", "xyz") == 0


class TestPreprocessQuery:
    def test_deduplicates_tokens(self):
        result = _preprocess_query("slot slot machine")
        assert result.count("slot") == 1

    def test_returns_list(self):
        assert isinstance(_preprocess_query("test query"), list)
