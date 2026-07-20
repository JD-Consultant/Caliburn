"""Turn interpretation dialogue vocabulary and durable receipt.

Every employee turn that clears the local semantic gate leaves a
``TurnInterpretationRecord`` — even when it produced zero Evidence (dont-know,
decline, off-topic, fully dropped proposals). The receipt makes the turn
replayable and auditable and lets the domain consume the eligible frame exactly
once (ADR 0037 §6; amendment plan §6.6).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import field_validator, model_validator

from .base import DomainModel
from .identifiers import Sha256, UtcDatetime


class DialogueAct(StrEnum):
    STANDALONE_ANSWER = "standalone_answer"
    AFFIRM = "affirm"
    DENY = "deny"
    SLOT_VALUE = "slot_value"
    CHOOSE = "choose"
    CORRECTION = "correction"
    DONT_KNOW = "dont_know"
    DECLINE = "decline"
    STOP = "stop"
    OFF_TOPIC = "off_topic"
    MIXED = "mixed"


class EpisodeSignal(StrEnum):
    CONTINUE = "continue"
    POSSIBLE_SHIFT = "possible_shift"
    EXPLICIT_SHIFT = "explicit_shift"
    POSSIBLE_CLOSE = "possible_close"


class TurnInsufficiencyCode(StrEnum):
    AMBIGUOUS_FREQUENCY = "ambiguous_frequency"
    AMBIGUOUS_OWNERSHIP = "ambiguous_ownership"
    AMBIGUOUS_SUBJECT = "ambiguous_subject"
    AMBIGUOUS_TIME_SCOPE = "ambiguous_time_scope"
    CONTRADICTION_UNRESOLVED = "contradiction_unresolved"
    CORRECTION_TARGET_UNKNOWN = "correction_target_unknown"
    INSUFFICIENT_DETAIL = "insufficient_detail"
    NO_WORK_FACT = "no_work_fact"
    ANSWER_BINDING_AMBIGUOUS = "answer_binding_ambiguous"
    QUESTION_FRAME_MISSING = "question_frame_missing"
    QUESTION_FRAME_STALE = "question_frame_stale"
    QUESTION_FRAME_NOT_IMMEDIATE = "question_frame_not_immediate"
    CHOICE_SELECTION_AMBIGUOUS = "choice_selection_ambiguous"


# Insufficiency codes serialize in domain declaration order, never alphabetical
# (amendment plan §10.1).
_INSUFFICIENCY_ORDER: dict[TurnInsufficiencyCode, int] = {
    code: index for index, code in enumerate(TurnInsufficiencyCode)
}


class TurnInterpretationRecord(DomainModel):
    schema_version: Literal["turn_interpretation_record.v1"] = "turn_interpretation_record.v1"
    interpretation_id: UUID
    session_id: UUID
    employee_turn_id: UUID
    operation_id: UUID
    question_frame_id: UUID | None = None
    question_frame_definition_hash: Sha256 | None = None
    context_packet_hash: Sha256
    output_hash: Sha256
    verification_report_hash: Sha256
    accepted_evidence_ids: tuple[UUID, ...] = ()
    dialogue_act: DialogueAct
    episode_signal: EpisodeSignal
    insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()
    applied_at: UtcDatetime

    @field_validator("accepted_evidence_ids")
    @classmethod
    def accepted_ids_unique(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("accepted_evidence_ids must be unique")
        return value

    @field_validator("insufficiency_codes")
    @classmethod
    def insufficiency_unique_and_domain_ordered(
        cls, value: tuple[TurnInsufficiencyCode, ...]
    ) -> tuple[TurnInsufficiencyCode, ...]:
        if len(value) != len(set(value)):
            raise ValueError("insufficiency_codes must be unique")
        if list(value) != sorted(value, key=_INSUFFICIENCY_ORDER.__getitem__):
            raise ValueError("insufficiency_codes must follow domain enum order")
        return value

    @model_validator(mode="after")
    def frame_scope_is_paired(self) -> "TurnInterpretationRecord":
        if (self.question_frame_id is None) != (self.question_frame_definition_hash is None):
            raise ValueError("question_frame_id and definition_hash must both be set or both null")
        return self
