"""QuestionFrame contracts for grounded short-answer interpretation.

A QuestionFrame is the application-validated record of a consultant question:
its exact text hash, a single question ``mode``, and a minimal semantic target
that a following short employee answer may accept, deny, fill, or choose from.

These are pure, immutable value objects. They enforce intra-model coherence
(mode/target cardinality, introduced-dimension maps, self hashes, lifecycle
field coherence) only. Whether a target is actually supported by active employee
Evidence, and every lifecycle transition, are reducer concerns (amendment plan
§6.3 field gates, §7 reducers) and are not validated here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import DomainModel
from .evidence import EvidenceKind, EvidenceQualifiers, EvidenceSubject
from .hashing import canonical_hash_excluding, sha256_utf8_text
from .identifiers import NonEmptyText, Sha256, UtcDatetime

TargetOrdinal = Annotated[int, Field(ge=1, le=16)]


class QuestionMode(StrEnum):
    OPEN_NARRATIVE = "open_narrative"
    ATOMIC_CONFIRMATION = "atomic_confirmation"
    SLOT_REQUEST = "slot_request"
    CHOICE = "choice"
    CORRECTION_CHECK = "correction_check"


class QuestionFrameStatus(StrEnum):
    ACTIVE = "active"
    CONSUMED = "consumed"
    SUPERSEDED = "superseded"
    STALE = "stale"


class QuestionTargetKind(StrEnum):
    PROPOSITION = "proposition"
    SLOT = "slot"
    CHOICE = "choice"


class QuestionDimension(StrEnum):
    ACTION = "action"
    INPUT = "input"
    OUTPUT = "output"
    PURPOSE = "purpose"
    CONDITION = "condition"
    STANDARD = "standard"
    FREQUENCY = "frequency"
    IMPORTANCE = "importance"
    OWNERSHIP = "ownership"
    TOOL = "tool"
    RECIPIENT = "recipient"
    DEPENDENCY = "dependency"
    EXCEPTION = "exception"
    TIME_SCOPE = "time_scope"
    TYPICALITY = "typicality"
    POLARITY = "polarity"


class QuestionSlotKind(StrEnum):
    FREQUENCY = "frequency"
    RECIPIENT = "recipient"
    OUTPUT = "output"
    STANDARD = "standard"
    TOOL = "tool"
    CONDITION = "condition"
    PURPOSE = "purpose"
    OWNERSHIP = "ownership"
    IMPORTANCE = "importance"
    TIME_SCOPE = "time_scope"
    TYPICALITY = "typicality"


class QuestionSourceKind(StrEnum):
    EMPLOYEE_EVIDENCE = "employee_evidence"
    EMPLOYEE_DOCUMENT = "employee_document"
    PUBLIC_REFERENCE = "public_reference"
    CONSULTANT_HYPOTHESIS = "consultant_hypothesis"


class QuestionFrameStaleReason(StrEnum):
    DOCUMENT_TARGET_CHANGED = "document_target_changed"
    SOURCE_EVIDENCE_CHANGED = "source_evidence_changed"
    ANSWER_NOT_IMMEDIATE = "answer_not_immediate"
    MANUAL_INVALIDATION = "manual_invalidation"


# Claim dimensions map one-to-one onto EvidenceKind; qualifier dimensions describe
# the qualifier a target introduces. Slot kinds map onto the dimension they fill.
_SLOT_KIND_TO_DIMENSION: dict[QuestionSlotKind, QuestionDimension] = {
    QuestionSlotKind.FREQUENCY: QuestionDimension.FREQUENCY,
    QuestionSlotKind.RECIPIENT: QuestionDimension.RECIPIENT,
    QuestionSlotKind.OUTPUT: QuestionDimension.OUTPUT,
    QuestionSlotKind.STANDARD: QuestionDimension.STANDARD,
    QuestionSlotKind.TOOL: QuestionDimension.TOOL,
    QuestionSlotKind.CONDITION: QuestionDimension.CONDITION,
    QuestionSlotKind.PURPOSE: QuestionDimension.PURPOSE,
    QuestionSlotKind.OWNERSHIP: QuestionDimension.OWNERSHIP,
    QuestionSlotKind.IMPORTANCE: QuestionDimension.IMPORTANCE,
    QuestionSlotKind.TIME_SCOPE: QuestionDimension.TIME_SCOPE,
    QuestionSlotKind.TYPICALITY: QuestionDimension.TYPICALITY,
}


class QuestionSourceRef(DomainModel):
    source_kind: QuestionSourceKind
    source_ref: NonEmptyText
    source_hash: Sha256


def _source_ref_sort_key(ref: QuestionSourceRef) -> tuple[str, str, str]:
    return (ref.source_kind.value, ref.source_ref, ref.source_hash)


def _validate_source_refs(refs: tuple[QuestionSourceRef, ...]) -> tuple[QuestionSourceRef, ...]:
    keys = [_source_ref_sort_key(ref) for ref in refs]
    if len(keys) != len(set(keys)):
        raise ValueError("source refs must be unique")
    if keys != sorted(keys):
        raise ValueError("source refs must be sorted by (source_kind, source_ref, source_hash)")
    return refs


class QuestionProposition(DomainModel):
    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    qualifiers: EvidenceQualifiers = Field(default_factory=EvidenceQualifiers)
    source_refs: tuple[QuestionSourceRef, ...]
    supersedes_evidence_ids: tuple[UUID, ...] = ()

    @field_validator("source_refs")
    @classmethod
    def source_refs_sorted_unique(
        cls, value: tuple[QuestionSourceRef, ...]
    ) -> tuple[QuestionSourceRef, ...]:
        return _validate_source_refs(value)

    @field_validator("supersedes_evidence_ids")
    @classmethod
    def supersedes_ids_unique(cls, value: tuple[UUID, ...]) -> tuple[UUID, ...]:
        if len(value) != len(set(value)):
            raise ValueError("supersedes_evidence_ids must be unique")
        return value


def _sealed_hash(model: DomainModel, field: str) -> str:
    """Compute a self-referential hash over every field except ``field``."""

    return canonical_hash_excluding(model, exclude=field)


class PropositionQuestionTarget(DomainModel):
    target_kind: Literal[QuestionTargetKind.PROPOSITION] = QuestionTargetKind.PROPOSITION
    target_ordinal: TargetOrdinal
    proposition: QuestionProposition
    introduced_dimensions: tuple[QuestionDimension, ...]
    target_hash: Sha256

    @model_validator(mode="after")
    def hash_is_sealed(self) -> "PropositionQuestionTarget":
        if self.target_kind is not QuestionTargetKind.PROPOSITION:
            raise ValueError("proposition target requires target_kind=proposition")
        if self.target_hash != _sealed_hash(self, "target_hash"):
            raise ValueError("proposition target_hash mismatch")
        return self


class SlotQuestionTarget(DomainModel):
    target_kind: Literal[QuestionTargetKind.SLOT] = QuestionTargetKind.SLOT
    target_ordinal: TargetOrdinal
    slot_kind: QuestionSlotKind
    subject: EvidenceSubject
    evidence_kind: EvidenceKind
    base_claim: NonEmptyText
    claim_template: NonEmptyText
    base_qualifiers: EvidenceQualifiers = Field(default_factory=EvidenceQualifiers)
    source_refs: tuple[QuestionSourceRef, ...]
    supersedes_evidence_ids: tuple[UUID, ...] = ()
    introduced_dimension: QuestionDimension
    target_hash: Sha256

    @field_validator("source_refs")
    @classmethod
    def source_refs_sorted_unique(
        cls, value: tuple[QuestionSourceRef, ...]
    ) -> tuple[QuestionSourceRef, ...]:
        return _validate_source_refs(value)

    @field_validator("claim_template")
    @classmethod
    def claim_template_has_single_value_placeholder(cls, value: str) -> str:
        if value.count("{value}") != 1:
            raise ValueError("claim_template must contain exactly one {value}")
        if value.replace("{value}", "").count("{") or value.replace("{value}", "").count("}"):
            raise ValueError("claim_template must not contain other braces")
        return value

    @model_validator(mode="after")
    def slot_is_coherent(self) -> "SlotQuestionTarget":
        if self.target_kind is not QuestionTargetKind.SLOT:
            raise ValueError("slot target requires target_kind=slot")
        if self.introduced_dimension is not _SLOT_KIND_TO_DIMENSION[self.slot_kind]:
            raise ValueError("introduced_dimension must match slot_kind")
        if len(self.supersedes_evidence_ids) != len(set(self.supersedes_evidence_ids)):
            raise ValueError("supersedes_evidence_ids must be unique")
        if self.target_hash != _sealed_hash(self, "target_hash"):
            raise ValueError("slot target_hash mismatch")
        return self


class ChoiceOption(DomainModel):
    option_ordinal: TargetOrdinal
    label: NonEmptyText
    proposition: QuestionProposition
    option_hash: Sha256

    @model_validator(mode="after")
    def hash_is_sealed(self) -> "ChoiceOption":
        if self.option_hash != _sealed_hash(self, "option_hash"):
            raise ValueError("choice option_hash mismatch")
        return self


class ChoiceQuestionTarget(DomainModel):
    target_kind: Literal[QuestionTargetKind.CHOICE] = QuestionTargetKind.CHOICE
    target_ordinal: TargetOrdinal
    multi_select: bool
    introduced_dimension: QuestionDimension
    options: tuple[ChoiceOption, ...]
    target_hash: Sha256

    @model_validator(mode="after")
    def choice_is_coherent(self) -> "ChoiceQuestionTarget":
        if self.target_kind is not QuestionTargetKind.CHOICE:
            raise ValueError("choice target requires target_kind=choice")
        if not (2 <= len(self.options) <= 8):
            raise ValueError("choice target requires between 2 and 8 options")
        expected = tuple(range(1, len(self.options) + 1))
        if tuple(option.option_ordinal for option in self.options) != expected:
            raise ValueError("choice option ordinals must be contiguous from 1")
        if self.target_hash != _sealed_hash(self, "target_hash"):
            raise ValueError("choice target_hash mismatch")
        return self


QuestionTarget = Annotated[
    PropositionQuestionTarget | SlotQuestionTarget | ChoiceQuestionTarget,
    Field(discriminator="target_kind"),
]


def build_proposition_target(
    *,
    target_ordinal: int,
    proposition: QuestionProposition,
    introduced_dimensions: tuple[QuestionDimension, ...],
) -> PropositionQuestionTarget:
    fields = dict(
        target_kind=QuestionTargetKind.PROPOSITION,
        target_ordinal=target_ordinal,
        proposition=proposition,
        introduced_dimensions=tuple(introduced_dimensions),
    )
    target_hash = canonical_hash_excluding(
        PropositionQuestionTarget.model_construct(target_hash="", **fields),
        exclude="target_hash",
    )
    return PropositionQuestionTarget(target_hash=target_hash, **fields)


def build_slot_target(
    *,
    target_ordinal: int,
    slot_kind: QuestionSlotKind,
    subject: EvidenceSubject,
    evidence_kind: EvidenceKind,
    base_claim: str,
    claim_template: str,
    base_qualifiers: EvidenceQualifiers,
    source_refs: tuple[QuestionSourceRef, ...],
    supersedes_evidence_ids: tuple[UUID, ...] = (),
) -> SlotQuestionTarget:
    fields = dict(
        target_kind=QuestionTargetKind.SLOT,
        target_ordinal=target_ordinal,
        slot_kind=slot_kind,
        subject=subject,
        evidence_kind=evidence_kind,
        base_claim=base_claim,
        claim_template=claim_template,
        base_qualifiers=base_qualifiers,
        source_refs=tuple(source_refs),
        supersedes_evidence_ids=tuple(supersedes_evidence_ids),
        introduced_dimension=_SLOT_KIND_TO_DIMENSION[slot_kind],
    )
    target_hash = canonical_hash_excluding(
        SlotQuestionTarget.model_construct(target_hash="", **fields),
        exclude="target_hash",
    )
    return SlotQuestionTarget(target_hash=target_hash, **fields)


def build_choice_option(
    *, option_ordinal: int, label: str, proposition: QuestionProposition
) -> ChoiceOption:
    fields = dict(option_ordinal=option_ordinal, label=label, proposition=proposition)
    option_hash = canonical_hash_excluding(
        ChoiceOption.model_construct(option_hash="", **fields), exclude="option_hash"
    )
    return ChoiceOption(option_hash=option_hash, **fields)


def build_choice_target(
    *,
    target_ordinal: int,
    multi_select: bool,
    introduced_dimension: QuestionDimension,
    options: tuple[ChoiceOption, ...],
) -> ChoiceQuestionTarget:
    fields = dict(
        target_kind=QuestionTargetKind.CHOICE,
        target_ordinal=target_ordinal,
        multi_select=multi_select,
        introduced_dimension=introduced_dimension,
        options=tuple(options),
    )
    target_hash = canonical_hash_excluding(
        ChoiceQuestionTarget.model_construct(target_hash="", **fields),
        exclude="target_hash",
    )
    return ChoiceQuestionTarget(target_hash=target_hash, **fields)


class QuestionFrameDefinition(DomainModel):
    schema_version: Literal["question_frame_definition.v1"] = "question_frame_definition.v1"
    mode: QuestionMode
    question_text_hash: Sha256
    targets: tuple[QuestionTarget, ...]
    definition_hash: Sha256

    @model_validator(mode="after")
    def mode_matrix_holds(self) -> "QuestionFrameDefinition":
        target = self.targets[0] if len(self.targets) == 1 else None
        if self.mode is QuestionMode.OPEN_NARRATIVE:
            if self.targets:
                raise ValueError("open_narrative frames must have no targets")
        elif target is None:
            raise ValueError(f"{self.mode.value} requires exactly one target")
        elif self.mode is QuestionMode.ATOMIC_CONFIRMATION:
            if not isinstance(target, PropositionQuestionTarget):
                raise ValueError("atomic_confirmation requires a proposition target")
            if len(target.introduced_dimensions) != 1:
                raise ValueError("atomic_confirmation introduces exactly one dimension")
        elif self.mode is QuestionMode.SLOT_REQUEST:
            if not isinstance(target, SlotQuestionTarget):
                raise ValueError("slot_request requires a slot target")
        elif self.mode is QuestionMode.CHOICE:
            if not isinstance(target, ChoiceQuestionTarget):
                raise ValueError("choice requires a choice target")
        elif self.mode is QuestionMode.CORRECTION_CHECK:
            if not isinstance(target, PropositionQuestionTarget):
                raise ValueError("correction_check requires a proposition target")
            if target.introduced_dimensions != (QuestionDimension.POLARITY,):
                raise ValueError("correction_check introduces only polarity")
            if not target.proposition.supersedes_evidence_ids:
                raise ValueError("correction_check must supersede active evidence")
        if self.definition_hash != _sealed_hash(self, "definition_hash"):
            raise ValueError("definition_hash mismatch")
        return self


QuestionFrameDefinition.model_rebuild()


def build_question_frame_definition(
    *,
    mode: QuestionMode,
    question_text: str,
    targets: tuple[QuestionTarget, ...],
) -> QuestionFrameDefinition:
    fields = dict(
        mode=mode,
        question_text_hash=sha256_utf8_text(question_text),
        targets=tuple(targets),
    )
    definition_hash = canonical_hash_excluding(
        QuestionFrameDefinition.model_construct(definition_hash="", **fields),
        exclude="definition_hash",
    )
    return QuestionFrameDefinition(definition_hash=definition_hash, **fields)


class QuestionFrame(DomainModel):
    schema_version: Literal["question_frame.v1"] = "question_frame.v1"
    question_frame_id: UUID
    session_id: UUID
    consultant_turn_id: UUID
    definition: QuestionFrameDefinition
    status: QuestionFrameStatus
    opened_state_version: Annotated[int, Field(ge=1)]
    opened_at: UtcDatetime
    answer_turn_id: UUID | None = None
    consumed_operation_id: UUID | None = None
    superseded_by_frame_id: UUID | None = None
    stale_reason: QuestionFrameStaleReason | None = None
    closed_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def lifecycle_is_coherent(self) -> "QuestionFrame":
        consumed = self.consumed_operation_id is not None
        superseded = self.superseded_by_frame_id is not None
        stale = self.stale_reason is not None
        closed = self.closed_at is not None
        answered = self.answer_turn_id is not None

        if self.status is QuestionFrameStatus.ACTIVE:
            if consumed or superseded or stale or closed:
                raise ValueError("active frame must not set closure fields")
        elif self.status is QuestionFrameStatus.CONSUMED:
            if not (answered and consumed and closed):
                raise ValueError("consumed frame requires answer, operation, and closed_at")
            if superseded or stale:
                raise ValueError("consumed frame must not be superseded or stale")
        elif self.status is QuestionFrameStatus.SUPERSEDED:
            if not (superseded and closed):
                raise ValueError("superseded frame requires superseded_by and closed_at")
            if answered:
                raise ValueError("superseded frame must not bind an answer")
            if consumed or stale:
                raise ValueError("superseded frame must not be consumed or stale")
        elif self.status is QuestionFrameStatus.STALE:
            if not (stale and closed):
                raise ValueError("stale frame requires stale_reason and closed_at")
            if consumed or superseded:
                raise ValueError("stale frame must not be consumed or superseded")
        return self


QuestionFrame.model_rebuild()
