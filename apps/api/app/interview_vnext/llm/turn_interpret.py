"""Provider-neutral turn interpretation and verification contracts.

Nothing here carries a UUID, hash, or artifact ref toward the provider: the model
sees ordinals and text, and the application maps those back to domain identity
(amendment plan §8.5, §9). The dialogue/insufficiency vocabularies are owned by
the domain so the receipt and the provider schema cannot drift apart.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.episode import EpisodeStatus, GapStatus
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceSubject,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import (
    Locale,
    NonEmptyText,
    SemVer,
    Sha256,
    StableName,
)
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInsufficiencyCode,
)
from app.interview_vnext.domain.question_frame import (
    QuestionMode,
    QuestionSlotKind,
    QuestionTargetKind,
)
from app.interview_vnext.domain.support import QuoteSpan
from app.interview_vnext.domain.turn_identity import (
    contextual_evidence_id,
    derive_binding_ref,
    derive_proposal_ref,
    literal_evidence_id,
)
from app.interview_vnext.llm.context import INJECTION_BOUNDARY


def _unique_sorted_codes(
    value: tuple[TurnInsufficiencyCode, ...],
) -> tuple[TurnInsufficiencyCode, ...]:
    if len(value) != len(set(value)):
        raise ValueError("insufficiency codes must be unique")
    order = {code: index for index, code in enumerate(TurnInsufficiencyCode)}
    if list(value) != sorted(value, key=order.__getitem__):
        raise ValueError("insufficiency codes must follow domain enum order")
    return value


class TurnInputTurn(DomainModel):
    sequence: int
    locale: Locale
    text: NonEmptyText


class TurnInputEpisode(DomainModel):
    target: NonEmptyText
    status: EpisodeStatus


class TurnInputContradiction(DomainModel):
    contradiction_ordinal: int = Field(ge=1)
    status: GapStatus
    question_goal: NonEmptyText


class TurnInputEvidence(DomainModel):
    """Flat portable projection of one prior Evidence.

    ``support_kind`` is load-bearing: for a contextual answer, ``quote`` is the
    short answer the employee gave (「是」), not a verbatim statement of ``claim``.
    Every consumer must branch on it before presenting the quote as support
    (ADR 0037 §4; plan §3.1).
    """

    ordinal: int = Field(ge=1)
    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    support_kind: Literal["literal_employee_span", "contextual_answer"]
    quote: NonEmptyText
    qualifiers: EvidenceQualifiers


class TurnInputChoiceOption(DomainModel):
    option_ordinal: int = Field(ge=1)
    label: NonEmptyText


class TurnInputQuestionTarget(DomainModel):
    target_ordinal: int = Field(ge=1)
    target_kind: QuestionTargetKind
    claim: NonEmptyText | None = None
    slot_kind: QuestionSlotKind | None = None
    claim_template: NonEmptyText | None = None
    options: tuple[TurnInputChoiceOption, ...] = ()

    @model_validator(mode="after")
    def target_shape_matches_kind(self) -> "TurnInputQuestionTarget":
        if self.target_kind == QuestionTargetKind.PROPOSITION:
            if self.claim is None or self.slot_kind is not None or self.options:
                raise ValueError("proposition target projects only a claim")
        elif self.target_kind == QuestionTargetKind.SLOT:
            if self.slot_kind is None or self.claim_template is None or self.options:
                raise ValueError("slot target projects slot_kind and claim_template")
        elif not self.options or self.claim is not None:
            raise ValueError("choice target projects only options")
        return self


class TurnInputQuestionFrame(DomainModel):
    mode: QuestionMode
    question_text: NonEmptyText
    targets: tuple[TurnInputQuestionTarget, ...] = ()

    @model_validator(mode="after")
    def target_ordinals_are_contiguous(self) -> "TurnInputQuestionFrame":
        ordinals = tuple(item.target_ordinal for item in self.targets)
        if ordinals != tuple(range(1, len(ordinals) + 1)):
            raise ValueError("frame target ordinals must be contiguous from 1")
        return self


class TurnInterpretInput(DomainModel):
    schema_version: Literal["turn_interpret_input.v2"] = "turn_interpret_input.v2"
    input_boundary: Literal[INJECTION_BOUNDARY]
    preceding_question: TurnInputTurn | None
    current_turn: TurnInputTurn
    question_frame: TurnInputQuestionFrame | None = None
    active_episode: TurnInputEpisode | None
    contradictions: tuple[TurnInputContradiction, ...]
    correction_candidates: tuple[TurnInputEvidence, ...]
    recent_active_evidence: tuple[TurnInputEvidence, ...]

    @model_validator(mode="after")
    def ordinals_and_frame_text_are_canonical(self) -> "TurnInterpretInput":
        groups = (
            (tuple(item.contradiction_ordinal for item in self.contradictions),
             "contradiction"),
            (tuple(item.ordinal for item in self.correction_candidates),
             "correction candidate"),
            (tuple(item.ordinal for item in self.recent_active_evidence),
             "recent evidence"),
        )
        for ordinals, label in groups:
            if ordinals != tuple(range(1, len(ordinals) + 1)):
                raise ValueError(f"{label} ordinals must be contiguous from 1")
        if self.question_frame is not None:
            if self.preceding_question is None:
                raise ValueError("a question frame requires the preceding question")
            if self.question_frame.question_text != self.preceding_question.text:
                raise ValueError("frame question_text must equal the preceding question")
        return self


class FrequencyQualifierProposal(DomainModel):
    """Provider-facing frequency with decimal text preserved losslessly."""

    value: str | None
    unit: FrequencyUnit
    verbatim: str | None


class EvidenceQualifiersProposal(DomainModel):
    time_scope: TimeScope
    time_scope_support: NonEmptyText | None = None
    typicality: Typicality
    typicality_support: NonEmptyText | None = None
    polarity: Polarity
    polarity_support: NonEmptyText | None = None
    frequency: FrequencyQualifierProposal
    importance: Importance
    importance_support: NonEmptyText | None = None
    ownership: Ownership
    ownership_support: NonEmptyText | None = None


class CorrectionProposal(DomainModel):
    target_candidate_ordinals: tuple[int, ...] = ()
    target_unknown: bool = False

    @field_validator("target_candidate_ordinals")
    @classmethod
    def ordinals_are_positive_and_unique(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(item < 1 for item in value):
            raise ValueError("correction target ordinals must be 1-based")
        if len(value) != len(set(value)):
            raise ValueError("correction target ordinals must be unique")
        return value


class ObservationProposal(DomainModel):
    """A claim the employee stated literally in this turn.

    Identity is the proposal's original position in the output tuple — the model
    never names an Evidence ID or a proposal key (amendment plan §9.2).
    """

    subject: EvidenceSubject
    kind: EvidenceKind
    claim: NonEmptyText
    quote: NonEmptyText
    quote_occurrence: int = Field(ge=1)
    qualifiers: EvidenceQualifiersProposal
    correction: CorrectionProposal = Field(default_factory=CorrectionProposal)
    insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()

    @field_validator("insufficiency_codes")
    @classmethod
    def codes_are_canonical(
        cls, value: tuple[TurnInsufficiencyCode, ...]
    ) -> tuple[TurnInsufficiencyCode, ...]:
        return _unique_sorted_codes(value)


class AnswerBindingKind(StrEnum):
    PROPOSITION = "proposition"
    SLOT = "slot"
    CHOICE = "choice"


class AnswerBindingResolution(StrEnum):
    AFFIRMED = "affirmed"
    DENIED = "denied"
    SUPPLIED = "supplied"
    SELECTED = "selected"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class AnswerBindingProposal(DomainModel):
    """A short answer bound to one QuestionFrame target.

    Deliberately flat rather than a discriminated union: a provider-portable
    schema projection must not have to reproduce union branches (§9.3).
    """

    target_ordinal: int = Field(ge=1)
    binding_kind: AnswerBindingKind
    resolution: AnswerBindingResolution
    answer_quote: NonEmptyText
    answer_quote_occurrence: int = Field(ge=1)
    value_text: NonEmptyText | None = None
    selected_choice_ordinals: tuple[int, ...] = ()
    insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()

    @field_validator("insufficiency_codes")
    @classmethod
    def codes_are_canonical(
        cls, value: tuple[TurnInsufficiencyCode, ...]
    ) -> tuple[TurnInsufficiencyCode, ...]:
        return _unique_sorted_codes(value)

    @model_validator(mode="after")
    def binding_matrix_holds(self) -> "AnswerBindingProposal":
        unresolved = self.resolution in {
            AnswerBindingResolution.AMBIGUOUS,
            AnswerBindingResolution.UNKNOWN,
        }
        if unresolved:
            if self.value_text is not None or self.selected_choice_ordinals:
                raise ValueError("ambiguous/unknown binding carries no value or choices")
            return self
        if self.binding_kind == AnswerBindingKind.PROPOSITION:
            if self.resolution not in {
                AnswerBindingResolution.AFFIRMED,
                AnswerBindingResolution.DENIED,
            }:
                raise ValueError("proposition binding resolves affirmed or denied")
            if self.value_text is not None or self.selected_choice_ordinals:
                raise ValueError("proposition binding carries no value or choices")
        elif self.binding_kind == AnswerBindingKind.SLOT:
            if self.resolution != AnswerBindingResolution.SUPPLIED:
                raise ValueError("slot binding resolves supplied")
            if self.value_text is None or self.selected_choice_ordinals:
                raise ValueError("slot binding requires value_text and no choices")
        else:
            if self.resolution != AnswerBindingResolution.SELECTED:
                raise ValueError("choice binding resolves selected")
            if self.value_text is not None or not self.selected_choice_ordinals:
                raise ValueError("choice binding requires selected choices and no value")
            ordinals = self.selected_choice_ordinals
            if any(item < 1 for item in ordinals):
                raise ValueError("choice ordinals must be 1-based")
            if len(ordinals) != len(set(ordinals)) or list(ordinals) != sorted(ordinals):
                raise ValueError("choice ordinals must be unique and sorted")
        return self


class EmergentTopicProposal(DomainModel):
    topic: NonEmptyText
    quote: NonEmptyText
    quote_occurrence: int = Field(ge=1)


class TurnInterpretOutput(DomainModel):
    schema_version: Literal["turn_interpret_output.v2"]
    dialogue_act: DialogueAct
    episode_signal: EpisodeSignal
    literal_observations: tuple[ObservationProposal, ...] = ()
    answer_bindings: tuple[AnswerBindingProposal, ...] = ()
    emergent_topics: tuple[EmergentTopicProposal, ...] = ()
    turn_insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()

    @field_validator("turn_insufficiency_codes")
    @classmethod
    def codes_are_canonical(
        cls, value: tuple[TurnInsufficiencyCode, ...]
    ) -> tuple[TurnInsufficiencyCode, ...]:
        return _unique_sorted_codes(value)


class TurnInterpretRejectCode(StrEnum):
    """Canonical reject vocabulary — two namespaces, one enum (amendment §10.3).

    Declaration order *is* the verifier ``reject_order``: literal-observation
    codes first (roughly the amendment §10.2 gate order), then answer-binding
    codes. A literal decision may only carry observation codes and a binding
    decision only binding codes; the split is enforced per decision below. No WIP
    aliases survive this atomic hard cut.
    """

    # --- literal observation namespace -------------------------------------
    QUOTE_NOT_FOUND = "quote_not_found"
    QUOTE_OCCURRENCE_OUT_OF_RANGE = "quote_occurrence_out_of_range"
    INVALID_QUALIFIER = "invalid_qualifier"
    QUALIFIER_SUPPORT_NOT_IN_QUOTE = "qualifier_support_not_in_quote"
    FALSE_SPECIFIC_QUALIFIER = "false_specific_qualifier"
    FOREIGN_CORRECTION_TARGET = "foreign_correction_target"
    INACTIVE_CORRECTION_TARGET = "inactive_correction_target"
    INCOHERENT_CORRECTION = "incoherent_correction"
    UNSUPPORTED_QUANTIFICATION = "unsupported_quantification"
    REFERENCE_LEAKAGE = "reference_leakage"
    NON_ATOMIC_CLAIM = "non_atomic_claim"
    DUPLICATE_OBSERVATION = "duplicate_observation"
    INSUFFICIENCY_INCOHERENT = "insufficiency_incoherent"
    DOMAIN_INVARIANT_FAILED = "domain_invariant_failed"

    # --- answer binding namespace ------------------------------------------
    BINDING_WITHOUT_QUESTION_FRAME = "binding_without_question_frame"
    BINDING_TARGET_OUT_OF_RANGE = "binding_target_out_of_range"
    BINDING_KIND_MISMATCH = "binding_kind_mismatch"
    BINDING_RESOLUTION_INCOHERENT = "binding_resolution_incoherent"
    BINDING_QUOTE_NOT_FOUND = "binding_quote_not_found"
    BINDING_QUOTE_OCCURRENCE_OUT_OF_RANGE = "binding_quote_occurrence_out_of_range"
    BINDING_VALUE_NOT_SUPPORTED = "binding_value_not_supported"
    CHOICE_SELECTION_INVALID = "choice_selection_invalid"
    DUPLICATE_BINDING_TARGET = "duplicate_binding_target"
    QUESTION_FRAME_NOT_ELIGIBLE = "question_frame_not_eligible"
    QUESTION_FRAME_HASH_MISMATCH = "question_frame_hash_mismatch"
    CONTEXTUAL_MATERIALIZATION_FAILED = "contextual_materialization_failed"


_OBSERVATION_REJECT_CODES: frozenset[TurnInterpretRejectCode] = frozenset(
    {
        TurnInterpretRejectCode.QUOTE_NOT_FOUND,
        TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE,
        TurnInterpretRejectCode.INVALID_QUALIFIER,
        TurnInterpretRejectCode.QUALIFIER_SUPPORT_NOT_IN_QUOTE,
        TurnInterpretRejectCode.FALSE_SPECIFIC_QUALIFIER,
        TurnInterpretRejectCode.FOREIGN_CORRECTION_TARGET,
        TurnInterpretRejectCode.INACTIVE_CORRECTION_TARGET,
        TurnInterpretRejectCode.INCOHERENT_CORRECTION,
        TurnInterpretRejectCode.UNSUPPORTED_QUANTIFICATION,
        TurnInterpretRejectCode.REFERENCE_LEAKAGE,
        TurnInterpretRejectCode.NON_ATOMIC_CLAIM,
        TurnInterpretRejectCode.DUPLICATE_OBSERVATION,
        TurnInterpretRejectCode.INSUFFICIENCY_INCOHERENT,
        TurnInterpretRejectCode.DOMAIN_INVARIANT_FAILED,
    }
)
_BINDING_REJECT_CODES: frozenset[TurnInterpretRejectCode] = frozenset(
    {
        TurnInterpretRejectCode.BINDING_WITHOUT_QUESTION_FRAME,
        TurnInterpretRejectCode.BINDING_TARGET_OUT_OF_RANGE,
        TurnInterpretRejectCode.BINDING_KIND_MISMATCH,
        TurnInterpretRejectCode.BINDING_RESOLUTION_INCOHERENT,
        TurnInterpretRejectCode.BINDING_QUOTE_NOT_FOUND,
        TurnInterpretRejectCode.BINDING_QUOTE_OCCURRENCE_OUT_OF_RANGE,
        TurnInterpretRejectCode.BINDING_VALUE_NOT_SUPPORTED,
        TurnInterpretRejectCode.CHOICE_SELECTION_INVALID,
        TurnInterpretRejectCode.DUPLICATE_BINDING_TARGET,
        TurnInterpretRejectCode.QUESTION_FRAME_NOT_ELIGIBLE,
        TurnInterpretRejectCode.QUESTION_FRAME_HASH_MISMATCH,
        TurnInterpretRejectCode.CONTEXTUAL_MATERIALIZATION_FAILED,
    }
)
_EMERGENT_TOPIC_REJECT_CODES: frozenset[TurnInterpretRejectCode] = frozenset(
    {
        TurnInterpretRejectCode.QUOTE_NOT_FOUND,
        TurnInterpretRejectCode.QUOTE_OCCURRENCE_OUT_OF_RANGE,
    }
)


def compile_marker(pattern: str) -> re.Pattern[str]:
    """Compile one sealed marker pattern with the amendment §7.3 flag rule.

    ASCII English patterns fold case; any pattern with a non-ASCII code point is
    Unicode and matched verbatim — the employee's text is never case-folded,
    trimmed, or NFKC-normalized before matching.
    """

    return re.compile(pattern, re.IGNORECASE) if pattern.isascii() else re.compile(pattern)


# Marker keys that carry no positive evidence: an "unknown"/"not_stated" value is
# the *absence* of a marker, never something a pattern proves (amendment §7.3).
_MARKERLESS_VALUES = frozenset({"unknown", "not_stated"})

_REQUIRED_MARKER_KEYS = (
    ("time_scope", frozenset(TimeScope) - {TimeScope.UNKNOWN}),
    ("frequency", frozenset(FrequencyUnit) - {FrequencyUnit.UNKNOWN}),
    ("typicality", frozenset(Typicality) - {Typicality.UNKNOWN}),
    ("polarity", frozenset({Polarity.DENIED, Polarity.UNCERTAIN})),
    (
        "importance",
        frozenset({Importance.EXPLICIT_CORE, Importance.EXPLICIT_SUPPORTING}),
    ),
    ("ownership", frozenset(Ownership) - {Ownership.UNKNOWN}),
)


class TurnInterpretVerifierPolicyDefinition(DomainModel):
    schema_version: Literal["turn_interpret_verifier_policy.v2"] = (
        "turn_interpret_verifier_policy.v2"
    )
    name: StableName
    version: SemVer
    quote_match: Literal["exact"]
    span_unit: Literal["unicode_code_point"]
    duplicate_correction_target_policy: Literal["reject_all"]
    number_pattern: NonEmptyText
    non_atomic_pattern: NonEmptyText
    reference_markers: tuple[NonEmptyText, ...]
    reject_order: tuple[TurnInterpretRejectCode, ...]
    # The single runtime authority for qualifier markers: application verifier and
    # slot parser read these, prompts/adapters/graders never keep a second copy
    # (amendment §7.3). JSON keys are the domain enum serialized values; values are
    # ordered regex tuples.
    time_scope_markers: dict[TimeScope, tuple[NonEmptyText, ...]]
    frequency_markers: dict[FrequencyUnit, tuple[NonEmptyText, ...]]
    typicality_markers: dict[Typicality, tuple[NonEmptyText, ...]]
    polarity_markers: dict[Polarity, tuple[NonEmptyText, ...]]
    importance_markers: dict[Importance, tuple[NonEmptyText, ...]]
    ownership_markers: dict[Ownership, tuple[NonEmptyText, ...]]

    @model_validator(mode="after")
    def policy_is_canonical(self) -> "TurnInterpretVerifierPolicyDefinition":
        if tuple(sorted(set(self.reference_markers))) != self.reference_markers:
            raise ValueError("verifier reference markers must be unique and sorted")
        if self.reject_order != tuple(TurnInterpretRejectCode):
            raise ValueError("verifier reject order must include the exact enum order")
        for value in (self.number_pattern, self.non_atomic_pattern):
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError("verifier policy contains an invalid regex") from exc
        marker_maps = (
            ("time_scope", self.time_scope_markers),
            ("frequency", self.frequency_markers),
            ("typicality", self.typicality_markers),
            ("polarity", self.polarity_markers),
            ("importance", self.importance_markers),
            ("ownership", self.ownership_markers),
        )
        required_keys = dict(_REQUIRED_MARKER_KEYS)
        for label, mapping in marker_maps:
            if frozenset(mapping) != required_keys[label]:
                raise ValueError(f"{label} marker map must contain its exact active keys")
            for value, patterns in mapping.items():
                if value.value in _MARKERLESS_VALUES:
                    raise ValueError(f"{label} marker map cannot key {value.value}")
                if not patterns:
                    raise ValueError(f"{label} marker '{value.value}' needs a pattern")
                if len(patterns) != len(set(patterns)):
                    raise ValueError(
                        f"{label} marker '{value.value}' patterns must be unique"
                    )
                for pattern in patterns:
                    try:
                        compile_marker(pattern)
                    except re.error as exc:
                        raise ValueError(
                            f"{label} marker '{value.value}' has an invalid regex"
                        ) from exc
        return self


class TurnInterpretVerifierPolicy(TurnInterpretVerifierPolicyDefinition):
    policy_hash: Sha256

    @model_validator(mode="after")
    def hash_matches_definition(self) -> "TurnInterpretVerifierPolicy":
        definition = TurnInterpretVerifierPolicyDefinition.model_validate(
            self.model_dump(exclude={"policy_hash"})
        )
        if canonical_hash(definition) != self.policy_hash:
            raise ValueError("turn interpreter verifier policy hash mismatch")
        return self


def define_turn_interpret_verifier_policy(
    **values,
) -> TurnInterpretVerifierPolicy:
    definition = TurnInterpretVerifierPolicyDefinition(**values)
    return TurnInterpretVerifierPolicy(
        **definition.model_dump(), policy_hash=canonical_hash(definition)
    )


TURN_INTERPRET_VERIFIER_POLICY_V2 = define_turn_interpret_verifier_policy(
    name="turn-interpret-verifier",
    version="2.0.0",
    quote_match="exact",
    span_unit="unicode_code_point",
    duplicate_correction_target_policy="reject_all",
    number_pattern=r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?",
    non_atomic_pattern=(
        r"(?:[;；\n]|，(?:並且|並|以及|而且)|,\s*(?:and|also)\b)"
    ),
    reference_markers=tuple(
        sorted(
            (
                "according to the taxonomy",
                "job description",
                "o*net",
                "onet",
                "urn:",
                "依據職業分類",
                "標準職稱",
                "職務說明書",
            )
        )
    ),
    reject_order=tuple(TurnInterpretRejectCode),
    # Marker policy 2.0.0 (amendment plan §11) — the exact authority, copied here
    # rather than referenced from mother-plan prose. Owner markers deliberately
    # exclude bare 我/我自己: those are a slot-only exact allowance (§10.5), never a
    # general ownership marker.
    time_scope_markers={
        TimeScope.CURRENT: ("目前", "現在", "現階段", "當前", "currently", "right now", "at present"),
        TimeScope.PAST: ("曾經", "以前", "過去", "之前", "上一份工作", "當時", "previously", "used to"),
        TimeScope.FUTURE: ("未來", "預計", "計畫", "將會", "之後會"),
        TimeScope.HYPOTHETICAL: ("如果", "假如", "假設", "可能會", "會考慮"),
    },
    frequency_markers={
        FrequencyUnit.PER_DAY: ("每天", "每日", "daily"),
        FrequencyUnit.PER_WEEK: ("每週", "每周", "weekly"),
        FrequencyUnit.PER_MONTH: ("每月", "monthly"),
        FrequencyUnit.PER_QUARTER: ("每季", "每季度", "quarterly"),
        FrequencyUnit.PER_YEAR: ("每年", "每年度", "annually", "yearly"),
        FrequencyUnit.IRREGULAR: ("不定期", "視情況", "as needed"),
    },
    typicality_markers={
        Typicality.TYPICAL: ("通常", "平常", "一般來說", "多半", "日常"),
        Typicality.OCCASIONAL: ("偶爾", "有時", "不定期", "視情況"),
        Typicality.EXCEPTION: ("例外", "特殊情況", "只有.*才"),
    },
    polarity_markers={
        Polarity.DENIED: ("不負責", "不會", "沒有", "不是", "從不", "不需要", "並非"),
        Polarity.UNCERTAIN: ("不確定", "不清楚", "可能", "大概", "應該", "不一定"),
    },
    importance_markers={
        Importance.EXPLICIT_CORE: ("核心", "主要", "最重要", "首要", "關鍵職責"),
        Importance.EXPLICIT_SUPPORTING: ("協助性", "支援性", "次要", "輔助"),
    },
    ownership_markers={
        Ownership.OWNER: ("我負責", "由我負責", "我主責", "由我主導", "我決定"),
        Ownership.SHARED: ("共同負責", "一起負責", "我和.*共同", "與.*共同"),
        Ownership.ASSISTS: ("我協助", "幫忙", "支援.*處理"),
        Ownership.RECEIVES: ("交給我", "我接收", "我收到"),
        Ownership.NOT_RESPONSIBLE: ("我不負責", "不歸我", "不是我負責"),
    },
)


_REJECT_CODE_POSITION = {
    code: index for index, code in enumerate(TurnInterpretRejectCode)
}


def _reason_codes_are_canonical(
    reason_codes: tuple[TurnInterpretRejectCode, ...],
) -> None:
    if len(reason_codes) != len(set(reason_codes)):
        raise ValueError("verification reason codes must be unique")
    if reason_codes != tuple(
        sorted(reason_codes, key=_REJECT_CODE_POSITION.__getitem__)
    ):
        raise ValueError("verification reason codes must follow policy reject order")


class ObservationVerification(DomainModel):
    """One literal observation's decision plus its pre-derived identity.

    ``candidate_evidence_id`` is derived from the proposal's original position and
    kept whether or not the proposal is accepted, so a rejected neighbour never
    renumbers the survivors (amendment §10.1). When accepted it is exactly the
    materialized Evidence's id.
    """

    proposal_index: int = Field(ge=1)
    proposal_ref: str
    candidate_evidence_id: UUID
    accepted: bool
    reason_codes: tuple[TurnInterpretRejectCode, ...]
    computed_span: QuoteSpan | None
    evidence: Evidence | None

    @model_validator(mode="after")
    def outcome_is_coherent(self) -> "ObservationVerification":
        if self.proposal_ref != derive_proposal_ref(self.proposal_index):
            raise ValueError("proposal_ref must match its proposal index")
        if self.accepted:
            if self.reason_codes or self.computed_span is None or self.evidence is None:
                raise ValueError("accepted proposal requires span/evidence and no reasons")
            if self.evidence.evidence_id != self.candidate_evidence_id:
                raise ValueError("accepted evidence id must equal the candidate id")
        elif not self.reason_codes or self.evidence is not None:
            raise ValueError("rejected proposal requires reasons and no evidence")
        if not set(self.reason_codes) <= _OBSERVATION_REJECT_CODES:
            raise ValueError("observation carries a non-observation reason code")
        _reason_codes_are_canonical(self.reason_codes)
        return self


class AnswerBindingVerification(DomainModel):
    """One binding's decision plus every Evidence it materialized.

    A choice binding can materialize several Evidence (one per selected option),
    and an ambiguous binding legitimately materializes none while still being a
    semantic success (plan §11.3).
    """

    binding_index: int = Field(ge=1)
    binding_ref: str
    candidate_evidence_ids: tuple[UUID, ...] = ()
    accepted: bool
    reason_codes: tuple[TurnInterpretRejectCode, ...]
    computed_span: QuoteSpan | None
    materialized_evidence: tuple[Evidence, ...] = ()

    @model_validator(mode="after")
    def outcome_is_coherent(self) -> "AnswerBindingVerification":
        if self.binding_ref != derive_binding_ref(self.binding_index):
            raise ValueError("binding_ref must match its binding index")
        if len(self.candidate_evidence_ids) != len(set(self.candidate_evidence_ids)):
            raise ValueError("candidate evidence ids must be unique")
        if self.accepted:
            if self.reason_codes or self.computed_span is None:
                raise ValueError("accepted binding requires a span and no reasons")
            # Accepted means fully materialized: every candidate id became evidence
            # (an ambiguous/unknown binding accepts with no candidates at all).
            materialized_ids = tuple(item.evidence_id for item in self.materialized_evidence)
            if materialized_ids != self.candidate_evidence_ids:
                raise ValueError("accepted binding evidence must equal its candidate ids")
        elif not self.reason_codes or self.materialized_evidence:
            raise ValueError("rejected binding requires reasons and no evidence")
        if not set(self.reason_codes) <= _BINDING_REJECT_CODES:
            raise ValueError("binding carries a non-binding reason code")
        _reason_codes_are_canonical(self.reason_codes)
        return self


class EmergentTopicVerification(DomainModel):
    topic_index: int = Field(ge=1)
    proposal: EmergentTopicProposal
    accepted: bool
    reason_codes: tuple[TurnInterpretRejectCode, ...]
    computed_span: QuoteSpan | None

    @model_validator(mode="after")
    def outcome_is_coherent(self) -> "EmergentTopicVerification":
        if self.accepted != (not self.reason_codes and self.computed_span is not None):
            raise ValueError("emergent topic verification outcome is inconsistent")
        if not set(self.reason_codes) <= _EMERGENT_TOPIC_REJECT_CODES:
            raise ValueError("emergent topic has an invalid reason code")
        _reason_codes_are_canonical(self.reason_codes)
        return self


class TurnInterpretVerificationReport(DomainModel):
    schema_version: Literal["turn_interpret_verification_report.v2"] = (
        "turn_interpret_verification_report.v2"
    )
    operation_id: UUID
    operation_definition_hash: Sha256
    verifier_policy_name: StableName
    verifier_policy_version: SemVer
    verifier_policy_hash: Sha256
    session_id: UUID
    turn_id: UUID
    question_frame_id: UUID | None = None
    context_packet_hash: Sha256
    output_hash: Sha256
    dialogue_act: DialogueAct
    episode_signal: EpisodeSignal
    decisions: tuple[ObservationVerification, ...] = ()
    binding_decisions: tuple[AnswerBindingVerification, ...] = ()
    accepted_evidence_ids: tuple[UUID, ...] = ()
    emergent_topic_decisions: tuple[EmergentTopicVerification, ...] = ()
    model_insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()
    system_insufficiency_codes: tuple[TurnInsufficiencyCode, ...] = ()
    accepted_count: int = Field(ge=0)
    dropped_count: int = Field(ge=0)

    @model_validator(mode="after")
    def counts_identity_and_evidence_are_coherent(
        self,
    ) -> "TurnInterpretVerificationReport":
        policy = TURN_INTERPRET_VERIFIER_POLICY_V2
        if (
            self.verifier_policy_name != policy.name
            or self.verifier_policy_version != policy.version
            or self.verifier_policy_hash != policy.policy_hash
        ):
            raise ValueError("verification report has an unknown verifier policy identity")
        indices = tuple(item.proposal_index for item in self.decisions)
        if indices != tuple(range(1, len(indices) + 1)):
            raise ValueError("verification decisions must preserve proposal order")
        binding_indices = tuple(item.binding_index for item in self.binding_decisions)
        if binding_indices != tuple(range(1, len(binding_indices) + 1)):
            raise ValueError("binding decisions must preserve output order")

        # Candidate identities must be the deterministic derivations for this
        # operation — the report cannot smuggle in a foreign or hand-picked id.
        for item in self.decisions:
            if item.candidate_evidence_id != literal_evidence_id(
                self.operation_id, item.proposal_index
            ):
                raise ValueError("observation candidate id is not derived for this operation")
        for item in self.binding_decisions:
            expected_candidates = tuple(
                contextual_evidence_id(self.operation_id, item.binding_index, materialization)
                for materialization in range(1, len(item.candidate_evidence_ids) + 1)
            )
            if item.candidate_evidence_ids != expected_candidates:
                raise ValueError("binding candidate ids are not derived for this operation")
        topic_indices = tuple(
            item.topic_index for item in self.emergent_topic_decisions
        )
        if topic_indices != tuple(range(1, len(topic_indices) + 1)):
            raise ValueError("emergent topic decisions must preserve output order")

        accepted = tuple(item for item in self.decisions if item.accepted)
        accepted_bindings = tuple(
            item for item in self.binding_decisions if item.accepted
        )
        if self.accepted_count != len(accepted) + len(accepted_bindings):
            raise ValueError("accepted_count does not match decisions")
        dropped = (len(self.decisions) - len(accepted)) + (
            len(self.binding_decisions) - len(accepted_bindings)
        )
        if self.dropped_count != dropped:
            raise ValueError("dropped_count does not match decisions")

        # Accepted IDs are literal observations in output order, then bindings in
        # output order, then each binding's materializations by option ordinal
        # (plan §10.3).
        expected_ids = tuple(item.evidence.evidence_id for item in accepted) + tuple(
            evidence.evidence_id
            for item in accepted_bindings
            for evidence in item.materialized_evidence
        )
        if self.accepted_evidence_ids != expected_ids:
            raise ValueError("accepted evidence IDs do not match decisions")
        if len(self.accepted_evidence_ids) != len(set(self.accepted_evidence_ids)):
            raise ValueError("accepted evidence IDs must be unique")

        materialized = tuple(item.evidence for item in accepted) + tuple(
            evidence for item in accepted_bindings for evidence in item.materialized_evidence
        )
        for evidence in materialized:
            if (
                evidence.session_id != self.session_id
                or evidence.source_turn_id != self.turn_id
                or evidence.extractor_operation_id != self.operation_id
            ):
                raise ValueError("accepted evidence identity does not match report")
        for code_group in (self.model_insufficiency_codes, self.system_insufficiency_codes):
            _unique_sorted_codes(code_group)
        return self


def turn_interpret_output_schema() -> dict:
    """Return the local full schema before provider portability projection."""

    return TurnInterpretOutput.model_json_schema()


TURN_INTERPRET_REJECT_ORDER = TURN_INTERPRET_VERIFIER_POLICY_V2.reject_order
TURN_INTERPRET_REJECT_ORDER_INDEX = {
    code: index for index, code in enumerate(TURN_INTERPRET_REJECT_ORDER)
}


def canonical_reject_codes(
    values: set[TurnInterpretRejectCode],
) -> tuple[TurnInterpretRejectCode, ...]:
    return tuple(sorted(values, key=TURN_INTERPRET_REJECT_ORDER_INDEX.__getitem__))
