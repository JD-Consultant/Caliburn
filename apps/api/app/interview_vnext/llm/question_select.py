"""Portable contracts for selecting and wording one next consultant question."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.episode import EpisodeStatus, GapDimension
from app.interview_vnext.domain.evidence import EvidenceKind
from app.interview_vnext.domain.identifiers import Locale, NonEmptyText
from app.interview_vnext.llm.context import INJECTION_BOUNDARY


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value cannot be blank")
    return value


QuestionText = Annotated[
    str, Field(min_length=1, max_length=320), AfterValidator(_not_blank)
]


class QuestionSelectAction(StrEnum):
    ASK_GAP = "ask_gap"
    BROADEN_COVERAGE = "broaden_coverage"
    OFFER_FINISH = "offer_finish"


class QuestionSelectInputTurn(DomainModel):
    sequence: int = Field(ge=1)
    locale: Locale
    text: NonEmptyText


class QuestionSelectInputEpisode(DomainModel):
    target: NonEmptyText
    status: EpisodeStatus


class QuestionSelectInputEvidence(DomainModel):
    ordinal: int = Field(ge=1)
    kind: EvidenceKind
    claim: NonEmptyText


class QuestionSelectInputCandidate(DomainModel):
    ordinal: int = Field(ge=1, le=3)
    dimension: GapDimension
    question_goal: NonEmptyText
    supporting_evidence_ordinals: tuple[int, ...]
    existing_gap: bool

    @model_validator(mode="after")
    def supporting_ordinals_are_canonical(
        self,
    ) -> "QuestionSelectInputCandidate":
        if (
            tuple(sorted(set(self.supporting_evidence_ordinals)))
            != self.supporting_evidence_ordinals
        ):
            raise ValueError("supporting evidence ordinals must be unique and sorted")
        return self


class QuestionSelectInputTask(DomainModel):
    ordinal: NonEmptyText
    statement_excerpt: NonEmptyText
    output_excerpts: tuple[str, ...]


class QuestionSelectInputJobDigest(DomainModel):
    job_title: NonEmptyText
    tasks: tuple[QuestionSelectInputTask, ...]
    omitted_task_count: int = Field(ge=0)
    pending_proposal_count: int = Field(ge=0)
    stale_proposal_count: int = Field(ge=0)


class QuestionSelectInput(DomainModel):
    schema_version: Literal["question_select_input.v1"] = "question_select_input.v1"
    input_boundary: Literal[INJECTION_BOUNDARY]
    latest_employee_turn: QuestionSelectInputTurn | None
    recent_consultant_question: NonEmptyText | None
    active_episode: QuestionSelectInputEpisode | None
    candidates: tuple[QuestionSelectInputCandidate, ...]
    supporting_evidence: tuple[QuestionSelectInputEvidence, ...]
    job_state: QuestionSelectInputJobDigest
    allow_broaden_coverage: bool
    allow_offer_finish: bool
    remaining_high_value_questions: int = Field(ge=0, le=2)

    @model_validator(mode="after")
    def ordinals_and_actions_are_coherent(self) -> "QuestionSelectInput":
        candidate_ordinals = tuple(item.ordinal for item in self.candidates)
        if candidate_ordinals != tuple(range(1, len(candidate_ordinals) + 1)):
            raise ValueError("candidate ordinals must be contiguous from 1")
        evidence_ordinals = tuple(item.ordinal for item in self.supporting_evidence)
        if evidence_ordinals != tuple(range(1, len(evidence_ordinals) + 1)):
            raise ValueError("evidence ordinals must be contiguous from 1")
        available = set(evidence_ordinals)
        if any(
            not set(item.supporting_evidence_ordinals) <= available
            for item in self.candidates
        ):
            raise ValueError("candidate references unknown evidence ordinal")
        if self.candidates and self.remaining_high_value_questions == 0:
            raise ValueError("candidate list requires remaining question budget")
        return self


class QuestionSelectOutput(DomainModel):
    schema_version: Literal["question_select_output.v1"] = (
        "question_select_output.v1"
    )
    acknowledgement: str = Field(max_length=160)
    action: QuestionSelectAction
    selected_gap_ordinal: int | None = Field(default=None, ge=1, le=3)
    question_text: QuestionText

    @model_validator(mode="after")
    def selection_shape_matches_action(self) -> "QuestionSelectOutput":
        if self.action == QuestionSelectAction.ASK_GAP:
            if self.selected_gap_ordinal is None:
                raise ValueError("ask_gap requires selected_gap_ordinal")
        elif self.selected_gap_ordinal is not None:
            raise ValueError("non-gap action cannot select a gap ordinal")
        return self


class QuestionSelectRejectCode(StrEnum):
    ACTION_NOT_ALLOWED = "action_not_allowed"
    GAP_ORDINAL_OUT_OF_RANGE = "gap_ordinal_out_of_range"
    DUPLICATE_RECENT_QUESTION = "duplicate_recent_question"
    QUESTION_LOOKS_COMPOUND = "question_looks_compound"


_REJECT_ORDER = {code: index for index, code in enumerate(QuestionSelectRejectCode)}


class QuestionSelectVerificationReport(DomainModel):
    schema_version: Literal["question_select_verification_report.v1"] = (
        "question_select_verification_report.v1"
    )
    accepted: bool
    action: QuestionSelectAction
    selected_gap_ordinal: int | None
    reason_codes: tuple[QuestionSelectRejectCode, ...]

    @model_validator(mode="after")
    def verdict_is_canonical(self) -> "QuestionSelectVerificationReport":
        if tuple(sorted(set(self.reason_codes), key=_REJECT_ORDER.__getitem__)) != (
            self.reason_codes
        ):
            raise ValueError("question select reject codes must follow enum order")
        if self.accepted == bool(self.reason_codes):
            raise ValueError("accepted must mean no reject reasons")
        return self
