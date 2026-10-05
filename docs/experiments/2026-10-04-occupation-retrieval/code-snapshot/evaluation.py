"""Deterministic experiment scoring; empty relevance is not a retrieval hit."""

import math
import re
from collections import defaultdict

import numpy as np


def ranking_metrics(ranked_ids, grades):
    ids = list(dict.fromkeys(ranked_ids))
    relevant = {key for key, grade in grades.items() if grade >= 2}
    if not relevant:
        return {key: None for key in ["hit_1", "hit_5", "hit_10", "mrr",
                                      "ndcg_10", "recall_5", "primary_rank"]}
    ranks = [index for index, key in enumerate(ids, 1) if key in relevant]
    primary = [index for index, key in enumerate(ids, 1) if grades.get(key) == 3]

    def dcg(values):
        return sum((2 ** grade - 1) / math.log2(index + 2)
                   for index, grade in enumerate(values))

    ideal = dcg(sorted(grades.values(), reverse=True)[:10])
    return {
        **{f"hit_{k}": int(any(rank <= k for rank in ranks)) for k in (1, 5, 10)},
        "mrr": 1 / min(ranks) if ranks else 0,
        "ndcg_10": dcg([grades.get(key, 0) for key in ids[:10]]) / ideal,
        "recall_5": len(set(ids[:5]) & relevant) / len(relevant),
        "primary_rank": min(primary) if primary else None,
    }


def rrf(rankings, depth=50, constant=60):
    if depth <= 0 or constant <= 0:
        raise ValueError("RRF depth and constant must be positive")
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, key in enumerate(dict.fromkeys(ranking), 1):
            if rank > depth:
                break
            # Qdrant's configured k uses a zero-based rank in the denominator.
            scores[key] += 1 / (constant + rank - 1)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def validate_dense(vectors, expected_count, dim=1024):
    array = np.asarray(vectors, dtype=np.float64)
    if array.shape != (expected_count, dim) or not np.isfinite(array).all():
        raise ValueError("Embedding count, dimension or finite-value check failed")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Zero embedding has no cosine similarity")
    return array / norms


def fuse_rankings(dense, sparse, depth=50, constant=60):
    return rrf([[key for key, _ in dense], [key for key, score in sparse if score > 0]], depth, constant)


def clean_text(text):
    lines = []
    for line in (text or "").splitlines():
        line = re.sub(r"^\s*#{1,6}\s+", "", line)
        line = re.sub(r"(?<![A-Za-z0-9])[TOPKS]\d+(?:[.\-]\d+)*(?=\s|[:：、,，;；)]|$)", "", line)
        line = re.sub(r"^\s*[-*•⚫]\s*", "", line).replace("**", "")
        line = re.sub(r"\s+", " ", line).strip()
        if line and line not in {"工作產出", "行為指標", "知識", "技能", "工作內容"}:
            lines.append(line)
    return "\n".join(lines)


def ranking_check(actual, expected, limit=10, tolerance=1e-6):
    expected_scores = dict(expected)
    sufficient = len(actual) == min(limit, len(expected))
    unique = len({key for key, _ in actual}) == len(actual)
    ordered = all(actual[index][1] + tolerance >= actual[index + 1][1]
                  for index in range(len(actual) - 1))
    score_valid = all(key in expected_scores and abs(score - expected_scores[key]) <= tolerance
                      for key, score in actual)
    rank_valid = sufficient and all(abs(score - expected[index][1]) <= tolerance
                                   for index, (_, score) in enumerate(actual))
    return {"correct": sufficient and unique and ordered and score_valid and rank_valid,
            "sufficient": sufficient, "unique": unique, "ordered": ordered,
            "score_valid": score_valid, "tie_aware_rank_valid": rank_valid}
