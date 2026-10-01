"""Blind projection of generator products for the R1 eval grader.

ADR 0040 §15 requires the R1 grader to be blind: it must not read the
generator's own rationale, and it must not learn which ablation arm produced a
result. That guarantee is expressed as *shape*, not as a runtime filter — the
models below simply have no field in which a rationale could travel, so adding
one later is a visible contract change rather than a silent leak.

``SourceClaim`` is re-used verbatim: its fields (including ``action``, the verb
of the described work) are extracted content, not self-justification, and the
rubric's ``role_responsibility``/``source_grounding`` dimensions are scored
against exactly those values.
"""

from __future__ import annotations

import hashlib
from typing import Literal

from app.professional_consultant.contracts import (
    EmployeeMessage,
    Identifier,
    Identifiers,
    QuestionContext,
    QuestionText,
    ReconciliationKind,
    ShortText,
    SourceClaim,
    SourceSpan,
    StatementText,
    Story,
    TaskCandidate,
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
    TranscriptTurn,
    UnmappedSignal,
    WorkUnit,
)

from .contracts import R1EvalModel
from .minimal_harness import MinimalTaskDiscoveryOutput


# Generator self-justification and self-assessment. No blind model may declare
# any of these names; the byte-level tests additionally prove no value leaks.
REDACTED_GENERATOR_FIELDS: tuple[str, ...] = (
    "boundary",
    "gaps",
    "limitations",
    "missing_information",
    "rationale",
    "significance",
    "target_gap",
    "unresolved_boundary",
)


class BlindUnmappedSignal(R1EvalModel):
    signal_id: Identifier
    summary: StatementText
    anchors: tuple[SourceSpan, ...]


class BlindStory(R1EvalModel):
    story_id: Identifier
    summary: StatementText
    claim_ids: Identifiers
    outcome: ShortText | None


class BlindWorkUnit(R1EvalModel):
    work_unit_id: Identifier
    statement: StatementText
    claim_ids: Identifiers
    story_ids: Identifiers
    outcome: ShortText | None
    support_claim_ids: Identifiers
    counter_claim_ids: Identifiers


class BlindTaskCandidate(R1EvalModel):
    candidate_id: Identifier
    statement: StatementText
    work_unit_ids: Identifiers
    support_claim_ids: Identifiers
    counter_claim_ids: Identifiers


class BlindDecision(R1EvalModel):
    decision_id: Identifier
    kind: ReconciliationKind
    candidate_id: Identifier | None
    existing_candidate_ids: Identifiers
    work_unit_ids: Identifiers


class BlindNextQuestion(R1EvalModel):
    """Only the question itself; the declared action and gap are self-report."""

    text: QuestionText
    claim_ids: Identifiers


class BlindTaskDiscoveryArtifact(R1EvalModel):
    schema_version: Literal["r1_blind_task_discovery_artifact.v1"]
    claims: tuple[SourceClaim, ...]
    unmapped_signals: tuple[BlindUnmappedSignal, ...]
    stories: tuple[BlindStory, ...]
    work_units: tuple[BlindWorkUnit, ...]
    decisions: tuple[BlindDecision, ...]
    task_candidates: tuple[BlindTaskCandidate, ...]
    next_question: BlindNextQuestion


class BlindSourcePacket(R1EvalModel):
    schema_version: Literal["r1_blind_source_packet.v1"]
    employee_message: EmployeeMessage
    question_context: QuestionContext | None
    recent_transcript: tuple[TranscriptTurn, ...]
    recent_questions: tuple[QuestionText, ...]
    prior_claims: tuple[SourceClaim, ...]
    prior_stories: tuple[BlindStory, ...]
    prior_work_units: tuple[BlindWorkUnit, ...]
    existing_task_candidates: tuple[BlindTaskCandidate, ...]
    omitted_relevant_context: bool


def _blind_signal(signal: UnmappedSignal) -> BlindUnmappedSignal:
    return BlindUnmappedSignal(
        signal_id=signal.signal_id,
        summary=signal.summary,
        anchors=signal.anchors,
    )


def _blind_story(story: Story) -> BlindStory:
    return BlindStory(
        story_id=story.story_id,
        summary=story.summary,
        claim_ids=story.claim_ids,
        outcome=story.outcome,
    )


def _blind_work_unit(work: WorkUnit) -> BlindWorkUnit:
    return BlindWorkUnit(
        work_unit_id=work.work_unit_id,
        statement=work.statement,
        claim_ids=work.claim_ids,
        story_ids=work.story_ids,
        outcome=work.outcome,
        support_claim_ids=work.support_claim_ids,
        counter_claim_ids=work.counter_claim_ids,
    )


def _blind_candidate(candidate: TaskCandidate) -> BlindTaskCandidate:
    return BlindTaskCandidate(
        candidate_id=candidate.candidate_id,
        statement=candidate.statement,
        work_unit_ids=candidate.work_unit_ids,
        support_claim_ids=candidate.support_claim_ids,
        counter_claim_ids=candidate.counter_claim_ids,
    )


def project_blind_source(source: TaskDiscoveryInput) -> BlindSourcePacket:
    """Project the operation input the grader is allowed to read."""

    return BlindSourcePacket(
        schema_version="r1_blind_source_packet.v1",
        employee_message=source.employee_message,
        question_context=source.question_context,
        recent_transcript=source.recent_transcript,
        recent_questions=source.recent_questions,
        prior_claims=source.prior_claims,
        prior_stories=tuple(
            _blind_story(story) for story in source.prior_stories
        ),
        prior_work_units=tuple(
            _blind_work_unit(work) for work in source.prior_work_units
        ),
        existing_task_candidates=tuple(
            _blind_candidate(candidate)
            for candidate in source.existing_task_candidates
        ),
        omitted_relevant_context=source.omitted_relevant_context,
    )


def project_blind_artifact(
    result: TaskDiscoveryOutput | MinimalTaskDiscoveryOutput,
) -> BlindTaskDiscoveryArtifact:
    """Project one generator result; A1's smaller output is never padded out."""

    if isinstance(result, MinimalTaskDiscoveryOutput):
        return BlindTaskDiscoveryArtifact(
            schema_version="r1_blind_task_discovery_artifact.v1",
            claims=(),
            unmapped_signals=(),
            stories=(),
            work_units=(),
            decisions=(),
            task_candidates=tuple(
                BlindTaskCandidate(
                    candidate_id=candidate.candidate_id,
                    statement=candidate.statement,
                    work_unit_ids=(),
                    support_claim_ids=(),
                    counter_claim_ids=(),
                )
                for candidate in result.task_candidates
            ),
            next_question=BlindNextQuestion(
                text=result.next_question.text,
                claim_ids=result.next_question.claim_ids,
            ),
        )
    return BlindTaskDiscoveryArtifact(
        schema_version="r1_blind_task_discovery_artifact.v1",
        claims=result.claims,
        unmapped_signals=tuple(
            _blind_signal(signal) for signal in result.unmapped_signals
        ),
        stories=tuple(_blind_story(story) for story in result.stories),
        work_units=tuple(
            _blind_work_unit(work) for work in result.work_units
        ),
        decisions=tuple(
            BlindDecision(
                decision_id=decision.decision_id,
                kind=decision.kind,
                candidate_id=decision.candidate_id,
                existing_candidate_ids=decision.existing_candidate_ids,
                work_unit_ids=decision.work_unit_ids,
            )
            for decision in result.decisions
        ),
        task_candidates=tuple(
            _blind_candidate(candidate) for candidate in result.task_candidates
        ),
        next_question=BlindNextQuestion(
            text=result.next_question.text,
            claim_ids=result.next_question.claim_ids,
        ),
    )


def submission_id_for(trial_id: str) -> str:
    """Derive an opaque submission ID that does not spell out the arm."""

    digest = hashlib.sha256(trial_id.encode("utf-8")).hexdigest()
    return f"sub-{digest[:32]}"
