"""Deterministic high-value question agenda for the next consultant turn.

The agenda is an application projection, not stored workflow state and not a
planner-agent output.  It narrows the model's choice to a few questions that
can be justified by committed Evidence (ADR 0038 §8).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid5

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.episode import (
    GapDimension,
    GapPriorityFeatures,
    GapStatus,
    Sensitivity,
    ValueLevel,
)
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceStatus,
    EvidenceSubject,
    Ownership,
    Polarity,
    TimeScope,
)
from app.interview_vnext.domain.identifiers import NonEmptyText, StableName
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.transcript import TranscriptRole
from app.job_authoring.contracts import JobStateDigest


MAX_AGENDA_CANDIDATES = 3
MAX_HIGH_VALUE_QUESTIONS_PER_EPISODE = 2


class QuestionAgendaSource(StrEnum):
    EXISTING_GAP = "existing_gap"
    SYNTHETIC_COVERAGE = "synthetic_coverage"


class QuestionAgendaCandidate(DomainModel):
    ordinal: int = Field(ge=1, le=MAX_AGENDA_CANDIDATES)
    stable_key: NonEmptyText
    source: QuestionAgendaSource
    existing_gap_id: UUID | None = None
    dimension: GapDimension
    question_goal: NonEmptyText
    supporting_evidence_ids: tuple[UUID, ...] = ()
    priority_features: GapPriorityFeatures

    @model_validator(mode="after")
    def source_shape_is_coherent(self) -> "QuestionAgendaCandidate":
        if self.source == QuestionAgendaSource.EXISTING_GAP:
            if self.existing_gap_id is None:
                raise ValueError("existing gap candidate requires existing_gap_id")
        elif self.existing_gap_id is not None:
            raise ValueError("synthetic candidate cannot claim an existing_gap_id")
        if len(self.supporting_evidence_ids) != len(
            set(self.supporting_evidence_ids)
        ):
            raise ValueError("supporting evidence IDs must be unique")
        return self


class QuestionAgenda(DomainModel):
    schema_version: Literal["question_agenda.v1"] = "question_agenda.v1"
    session_id: UUID
    state_version: int = Field(ge=0)
    active_episode_id: UUID | None
    candidates: tuple[QuestionAgendaCandidate, ...]
    allow_broaden_coverage: bool
    allow_offer_finish: bool
    remaining_high_value_questions: int = Field(
        ge=0, le=MAX_HIGH_VALUE_QUESTIONS_PER_EPISODE
    )
    decision_reasons: tuple[StableName, ...]

    @model_validator(mode="after")
    def agenda_is_canonical(self) -> "QuestionAgenda":
        ordinals = tuple(item.ordinal for item in self.candidates)
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("agenda ordinals must be contiguous from 1")
        if len(self.candidates) > MAX_AGENDA_CANDIDATES:
            raise ValueError("agenda exceeds candidate cap")
        keys = tuple(item.stable_key for item in self.candidates)
        if len(keys) != len(set(keys)):
            raise ValueError("agenda candidate keys must be unique")
        if tuple(sorted(set(self.decision_reasons))) != self.decision_reasons:
            raise ValueError("agenda reasons must be unique and sorted")
        if self.candidates and self.remaining_high_value_questions == 0:
            raise ValueError("agenda cannot offer candidates after question budget")
        return self


def _is_relevant_employee_work(evidence: Evidence) -> bool:
    """Count unknown time as coverage without rewriting it to ``current``.

    R5 deliberately leaves 「我核對訂單」 at unknown time scope unless the
    employee says 現在/目前. Question selection must still notice that action
    or it will ask the employee to repeat it. Past/future/hypothetical work is
    excluded; the original qualifier remains unchanged for later review.
    """

    return (
        evidence.status == EvidenceStatus.ACTIVE
        and evidence.subject
        in {EvidenceSubject.EMPLOYEE, EvidenceSubject.EMPLOYEE_TEAM}
        and evidence.qualifiers.time_scope
        in {TimeScope.CURRENT, TimeScope.UNKNOWN}
        and evidence.qualifiers.polarity != Polarity.DENIED
        and evidence.qualifiers.ownership != Ownership.NOT_RESPONSIBLE
    )


def _priority_key(candidate: QuestionAgendaCandidate) -> tuple:
    features = candidate.priority_features
    level = {ValueLevel.HIGH: 0, ValueLevel.MEDIUM: 1, ValueLevel.LOW: 2}
    sensitivity = {
        Sensitivity.LOW: 0,
        Sensitivity.MEDIUM: 1,
        Sensitivity.HIGH: 2,
        Sensitivity.PROHIBITED: 3,
    }
    return (
        0 if features.contradiction else 1,
        level[features.jd_value],
        1 if features.redundancy else 0,
        sensitivity[features.sensitivity],
        level[features.burden],
        candidate.dimension.value,
        candidate.stable_key,
    )


def _synthetic_candidate(
    *,
    session_id: UUID,
    episode_id: UUID,
    dimension: GapDimension,
    question_goal: str,
    supporting_evidence_ids: tuple[UUID, ...],
    value: ValueLevel,
) -> QuestionAgendaCandidate:
    # The UUID is only a stable projection key. It is never persisted as a Gap.
    projection_id = uuid5(
        episode_id, f"question-agenda/1.0.0/{dimension.value}"
    )
    return QuestionAgendaCandidate(
        ordinal=1,
        stable_key=f"synthetic/{session_id}/{projection_id}",
        source=QuestionAgendaSource.SYNTHETIC_COVERAGE,
        dimension=dimension,
        question_goal=question_goal,
        supporting_evidence_ids=tuple(sorted(supporting_evidence_ids)),
        priority_features=GapPriorityFeatures(
            jd_value=value,
            sensitivity=Sensitivity.LOW,
            burden=ValueLevel.LOW,
        ),
    )


def build_question_agenda(
    *,
    state: InterviewState,
    job_digest: JobStateDigest,
) -> QuestionAgenda:
    """Project at most three worthwhile next questions from committed state."""

    state = InterviewState.model_validate(state.model_dump())
    job_digest = JobStateDigest.model_validate(job_digest.model_dump())
    if job_digest.session_id != state.session.session_id:
        raise ValueError("job digest belongs to another interview session")

    episode_id = state.session.active_episode_id
    if episode_id is None:
        return QuestionAgenda(
            session_id=state.session.session_id,
            state_version=state.session.state_version,
            active_episode_id=None,
            candidates=(),
            allow_broaden_coverage=True,
            allow_offer_finish=bool(job_digest.tasks),
            remaining_high_value_questions=MAX_HIGH_VALUE_QUESTIONS_PER_EPISODE,
            decision_reasons=("no_active_episode",),
        )

    episode = next(
        (item for item in state.episodes if item.episode_id == episode_id), None
    )
    if episode is None:
        raise ValueError("active episode pointer does not resolve")

    opened_sequence = next(
        turn.sequence
        for turn in state.turns
        if turn.turn_id == episode.opened_turn_id
    )
    # Counts both persisted-gap and synthetic follow-ups. The opening consultant
    # turn starts the episode but is not itself a follow-up.
    asked_count = sum(
        1
        for turn in state.turns
        if turn.role == TranscriptRole.CONSULTANT
        and turn.sequence > opened_sequence
    )
    remaining = max(0, MAX_HIGH_VALUE_QUESTIONS_PER_EPISODE - asked_count)
    if remaining == 0:
        return QuestionAgenda(
            session_id=state.session.session_id,
            state_version=state.session.state_version,
            active_episode_id=episode_id,
            candidates=(),
            allow_broaden_coverage=False,
            allow_offer_finish=True,
            remaining_high_value_questions=0,
            decision_reasons=("episode_question_budget_reached",),
        )

    evidence = tuple(
        item
        for item in state.evidence
        if item.episode_id == episode_id and _is_relevant_employee_work(item)
    )
    evidence_by_kind = {
        kind: tuple(
            sorted(
                (
                    item
                    for item in evidence
                    if item.kind == kind
                ),
                key=lambda item: str(item.evidence_id),
            )
        )
        for kind in EvidenceKind
    }
    existing_dimensions = {
        gap.dimension
        for gap in state.gaps
        if gap.episode_id == episode_id
        and gap.status in {GapStatus.OPEN, GapStatus.DEFERRED}
    }

    candidates: list[QuestionAgendaCandidate] = []
    for gap in state.gaps:
        if (
            gap.episode_id != episode_id
            or gap.status not in {GapStatus.OPEN, GapStatus.DEFERRED}
            or gap.priority_features.sensitivity == Sensitivity.PROHIBITED
        ):
            continue
        candidates.append(
            QuestionAgendaCandidate(
                ordinal=1,
                stable_key=f"gap/{gap.gap_id}",
                source=QuestionAgendaSource.EXISTING_GAP,
                existing_gap_id=gap.gap_id,
                dimension=gap.dimension,
                question_goal=gap.question_goal,
                supporting_evidence_ids=gap.supporting_evidence_ids,
                priority_features=gap.priority_features,
            )
        )

    actions = evidence_by_kind[EvidenceKind.ACTION]
    if (
        not actions
        and GapDimension.ACTION_DECISION not in existing_dimensions
    ):
        candidates.append(
            _synthetic_candidate(
                session_id=state.session.session_id,
                episode_id=episode_id,
                dimension=GapDimension.ACTION_DECISION,
                question_goal="釐清員工在這項工作中實際執行的主要動作或判斷",
                supporting_evidence_ids=(),
                value=ValueLevel.HIGH,
            )
        )
    elif actions:
        action_ids = tuple(item.evidence_id for item in actions)
        if (
            not evidence_by_kind[EvidenceKind.OUTPUT]
            and GapDimension.OUTPUT_RECIPIENT not in existing_dimensions
        ):
            candidates.append(
                _synthetic_candidate(
                    session_id=state.session.session_id,
                    episode_id=episode_id,
                    dimension=GapDimension.OUTPUT_RECIPIENT,
                    question_goal="確認這項工作實際產出的文件、資料、系統結果或服務結果",
                    supporting_evidence_ids=action_ids,
                    value=ValueLevel.HIGH,
                )
            )
        if (
            not evidence_by_kind[EvidenceKind.PURPOSE]
            and GapDimension.PURPOSE not in existing_dimensions
        ):
            candidates.append(
                _synthetic_candidate(
                    session_id=state.session.session_id,
                    episode_id=episode_id,
                    dimension=GapDimension.PURPOSE,
                    question_goal="確認這項工作要解決的問題或達成的目的",
                    supporting_evidence_ids=action_ids,
                    value=ValueLevel.MEDIUM,
                )
            )

    ordered = sorted(candidates, key=_priority_key)[
        : min(MAX_AGENDA_CANDIDATES, remaining)
    ]
    numbered = tuple(
        item.model_copy(update={"ordinal": ordinal})
        for ordinal, item in enumerate(ordered, 1)
    )
    reasons = (
        ("high_value_gaps_available",)
        if numbered
        else ("active_episode_has_no_high_value_gap",)
    )
    return QuestionAgenda(
        session_id=state.session.session_id,
        state_version=state.session.state_version,
        active_episode_id=episode_id,
        candidates=numbered,
        allow_broaden_coverage=False,
        allow_offer_finish=not numbered,
        remaining_high_value_questions=remaining,
        decision_reasons=reasons,
    )
