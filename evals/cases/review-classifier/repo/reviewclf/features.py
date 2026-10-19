"""Turn review text into binary term features."""

from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")


def tokenize(text: str) -> list[str]:
    return WORD.findall(text.lower())


def terms(text: str, pairs: bool) -> list[str]:
    """Return the words of a text and, with `pairs`, each pair of adjacent words."""
    words = tokenize(text)
    if not pairs:
        return words
    return words + [f"{first} {second}" for first, second in zip(words, words[1:])]


def select_vocabulary(rows: list[dict], size: int, pairs: bool) -> list[str]:
    """Keep the `size` terms whose document rate differs most between the two labels.

    Each rate is smoothed with one pseudo-document per label; ties keep alphabetical order.
    """
    documents = {0: Counter(), 1: Counter()}
    totals = Counter()
    for row in rows:
        documents[row["label"]].update(set(terms(row["text"], pairs)))
        totals[row["label"]] += 1

    def separation(term: str) -> float:
        complaint = (documents[1][term] + 1) / (totals[1] + 2)
        other = (documents[0][term] + 1) / (totals[0] + 2)
        return abs(math.log(complaint / other))

    candidates = documents[0].keys() | documents[1].keys()
    return sorted(candidates, key=lambda term: (-separation(term), term))[:size]


def vectorize(texts: list[str], vocabulary: list[str], pairs: bool) -> np.ndarray:
    """Return one row per text, with 1.0 in the column of each vocabulary term it contains."""
    column = {term: index for index, term in enumerate(vocabulary)}
    matrix = np.zeros((len(texts), len(vocabulary)))
    for row, text in enumerate(texts):
        for term in terms(text, pairs):
            if term in column:
                matrix[row, column[term]] = 1.0
    return matrix
