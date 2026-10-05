"""Windowed full-document reranking; token rules stay testable without torch."""

from __future__ import annotations

import math
from collections.abc import Callable


def token_windows(
    query: list[int], document: list[int], *, max_tokens: int = 8192, overlap: int = 64
) -> list[list[int]]:
    capacity = max_tokens - len(query) - 4  # XLM-R pair special tokens.
    if overlap < 0 or capacity <= overlap:
        raise ValueError("query leaves insufficient document capacity")
    windows = []
    start = 0
    while start < len(document):
        windows.append(document[start : start + capacity])
        if start + capacity >= len(document):
            break
        start += capacity - overlap
    return windows or [[]]


def score_documents(
    query: str,
    documents: list[str],
    *,
    encode: Callable[[str], list[int]],
    pair_score: Callable[[list[int], list[int]], float],
    max_tokens: int = 8192,
    overlap: int = 64,
) -> list[float]:
    query_tokens = encode(query)
    # Validate even an empty candidate list; never silently truncate the query.
    token_windows(query_tokens, [], max_tokens=max_tokens, overlap=overlap)
    scores = []
    for document in documents:
        windows = token_windows(
            query_tokens, encode(document), max_tokens=max_tokens, overlap=overlap
        )
        logits = [pair_score(query_tokens, window) for window in windows]
        if not all(math.isfinite(logit) for logit in logits):
            raise RuntimeError("reranker returned a non-finite logit")
        scores.append(max(logits))
    return scores
