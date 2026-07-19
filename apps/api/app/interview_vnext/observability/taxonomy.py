"""Committed execution taxonomy versions; existing meanings are never rewritten."""

from __future__ import annotations

from .events import ExecutionTaxonomy


INTERVIEW_VNEXT_EXECUTION_V1 = ExecutionTaxonomy(
    taxonomy_id="interview.vnext.execution",
    version="1.0.0",
    event_types=tuple(
        sorted(
            {
                "artifact.created",
                "human.review.accepted",
                "human.review.rejected",
                "model.call.completed",
                "model.call.failed",
                "model.call.started",
                "outcome.finalized",
                "state.transition.accepted",
                "state.transition.rejected",
                "tool.call.completed",
                "tool.call.failed",
                "tool.call.started",
                "verification.completed",
                "workflow.run.completed",
                "workflow.run.failed",
                "workflow.run.started",
                "workflow.step.completed",
                "workflow.step.failed",
                "workflow.step.skipped",
                "workflow.step.started",
            }
        )
    ),
    stages=tuple(
        sorted(
            {
                "capture.export",
                "episode.code",
                "evidence.reduce",
                "global.consolidate",
                "human.review",
                "job_model.reduce",
                "projection.ocs",
                "question.select_and_respond",
                "session.finish",
                "session.plan",
                "sufficiency.evaluate",
                "turn.interpret",
                "turn.receive",
                "workflow.run",
            }
        )
    ),
)


# V3-5A §7.2: v2 copies v1's meanings verbatim and adds the conformance-gate
# event. Existing v1 meanings are never rewritten; new runs use v2.
INTERVIEW_VNEXT_EXECUTION_V2 = ExecutionTaxonomy(
    taxonomy_id="interview.vnext.execution",
    version="2.0.0",
    event_types=tuple(
        sorted({*INTERVIEW_VNEXT_EXECUTION_V1.event_types, "provider.conformance.completed"})
    ),
    stages=INTERVIEW_VNEXT_EXECUTION_V1.stages,
)


EXECUTION_TAXONOMIES: dict[tuple[str, str], ExecutionTaxonomy] = {
    (
        INTERVIEW_VNEXT_EXECUTION_V1.taxonomy_id,
        INTERVIEW_VNEXT_EXECUTION_V1.version,
    ): INTERVIEW_VNEXT_EXECUTION_V1,
    (
        INTERVIEW_VNEXT_EXECUTION_V2.taxonomy_id,
        INTERVIEW_VNEXT_EXECUTION_V2.version,
    ): INTERVIEW_VNEXT_EXECUTION_V2,
}


def resolve_execution_taxonomy(taxonomy_id: str, version: str) -> ExecutionTaxonomy:
    try:
        return EXECUTION_TAXONOMIES[(taxonomy_id, version)]
    except KeyError as exc:
        raise KeyError(f"unknown execution taxonomy: {taxonomy_id}@{version}") from exc
