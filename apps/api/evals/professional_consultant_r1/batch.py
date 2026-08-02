"""Sequential no-network batch orchestration for the pre-registered R1 plans."""

from __future__ import annotations

from typing import Any

from .matrix import ObservationPlan, build_observation_plans
from .runner import ModelPort, ObservationResult, run_observation


async def run_batch(
    cases: list[dict[str, Any]],
    port: ModelPort,
) -> tuple[list[ObservationPlan], list[ObservationResult]]:
    plans = build_observation_plans(cases)
    cases_by_id = {case["case_id"]: case for case in cases}
    results = [
        await run_observation(cases_by_id[plan.case_id], plan, port)
        for plan in plans
    ]
    return plans, results
