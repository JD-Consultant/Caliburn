"""Small R1 batch report; scripted runs are never quality evidence."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .matrix import ObservationPlan
from .runner import ObservationResult


def build_batch_report(
    plans: list[ObservationPlan],
    results: list[ObservationResult],
    *,
    scripted: bool,
) -> dict[str, Any]:
    if len(plans) != len(results):
        raise ValueError("every observation plan must have exactly one result")
    return {
        "observation_count": len(results),
        "generator_call_count": sum(result.call_count for result in results),
        "outcomes": dict(sorted(Counter(result.outcome for result in results).items())),
        "scripted_only": scripted,
        "quality_conclusion_eligible": not scripted,
        "limitations": (
            ["scripted plumbing run; no model-quality conclusion is permitted"]
            if scripted
            else []
        ),
    }
