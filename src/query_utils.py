"""Query normalization helpers."""
import re
import os


def normalize_query(query):
    query = query.strip().lower()
    query = re.sub(r"\s+", " ", query)
    return query


def load_query_from_file(path):
    with open(path) as f:
        data = f.read()
    return normalize_query(data)
