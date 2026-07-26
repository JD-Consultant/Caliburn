"""Pure deterministic projection from persisted interview state to model context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.interview_vnext.application.agenda import (
    QuestionAgenda,
    QuestionAgendaSource,
)
from app.interview_vnext.domain.episode import GapDimension, GapStatus
from app.interview_vnext.domain.evidence import (
    EvidenceStatus,
    EvidenceSubject,
    Ownership,
    Polarity,
    TimeScope,
)
from app.interview_vnext.domain.hashing import (
    canonical_hash,
    canonical_json,
    sha256_utf8_text,
)
from app.interview_vnext.domain.job_model import CandidateStatus
from app.interview_vnext.domain.question_frame import (
    PropositionQuestionTarget,
    QuestionFrameStatus,
    QuestionSourceKind,
    SlotQuestionTarget,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.transcript import TranscriptRole
from app.interview_vnext.llm.context import (
    EPISODE_AUTHORITY_RULES,
    INJECTION_BOUNDARY,
    ContextBudgetReport,
    ContextBuildResult,
    ContextCandidateItem,
    ContextContradiction,
    ContextEpisodeIdentity,
    ContextEvidenceItem,
    ContextIdentity,
    ContextItemDecision,
    ContextPacket,
    ContextQuestionFrame,
    QuestionFrameLimitation,
    ContextReferenceItem,
    ContextSectionBudget,
    ContextSelectionManifest,
    ContextSourceRef,
    ContextSourceType,
    EpisodeCodeContextPacket,
    EpisodeCodeContextPolicy,
    QuestionSelectContextBuildResult,
    QuestionSelectContextCandidate,
    QuestionSelectContextPacket,
    QuestionSelectContextPolicy,
    QuestionSelectDialogueLimits,
    ReferenceSnapshot,
    TurnInterpretContextPacket,
    TurnInterpretContextPolicy,
)
from app.job_authoring.contracts import JobStateDigest


UNRESOLVED_CONTRADICTION_STATUSES = frozenset(
    {GapStatus.OPEN, GapStatus.ASKED, GapStatus.DECLINED, GapStatus.DEFERRED}
)
EPISODE_CONTEXT_CANDIDATE_STATUSES = frozenset(
    {
        CandidateStatus.DRAFT,
        CandidateStatus.VERIFIED,
        CandidateStatus.INSUFFICIENT,
        CandidateStatus.CONFLICTED,
    }
)
TOKEN_ESTIMATE_LIMITATION = (
    "Estimated input tokens use a provider-neutral UTF-8/code-point heuristic; "
    "provider billing tokenization may differ."
)
# Stated in the budget report so a downstream reader can tell "no frame existed"
# from "a frame existed but was not usable" (plan §9.3).
QUESTION_FRAME_LIMITATIONS = {
    QuestionFrameLimitation.MISSING: (
        "No usable question frame: no active frame pointer exists."
    ),
    QuestionFrameLimitation.NOT_ACTIVE: (
        "No usable question frame: the active frame is no longer active."
    ),
    QuestionFrameLimitation.ANSWER_NOT_BOUND: (
        "No usable question frame: the active frame is not bound to this answer."
    ),
    QuestionFrameLimitation.NOT_IMMEDIATE: (
        "No usable question frame: the active frame is not the immediately "
        "preceding consultant question."
    ),
    QuestionFrameLimitation.TEXT_HASH_MISMATCH: (
        "No usable question frame: the frame definition does not describe the "
        "preceding consultant question."
    ),
    QuestionFrameLimitation.SOURCE_INVALID: (
        "No usable question frame: an employee_evidence source ref is not a UUID."
    ),
    QuestionFrameLimitation.SOURCE_NOT_ACTIVE: (
        "No usable question frame: an employee_evidence source is no longer active."
    ),
    QuestionFrameLimitation.SOURCE_HASH_MISMATCH: (
        "No usable question frame: an employee_evidence source hash no longer matches."
    ),
}


class ContextBuildError(ValueError):
    """Base class for deterministic context input/policy failures."""


class ContextBudgetExceeded(ContextBuildError):
    """The complete non-truncated packet violates a byte or hard item budget."""

    def __init__(
        self,
        *,
        packet: ContextPacket,
        manifest: ContextSelectionManifest,
        budget: ContextBudgetReport,
    ) -> None:
        super().__init__("context packet exceeds policy budget")
        self.packet = packet
        self.manifest = manifest
        self.budget = budget


@dataclass(frozen=True)
class _DecisionDraft:
    source: ContextSourceRef
    section: str
    selected: bool
    reasons: tuple[str, ...]
    selected_ordinal: int | None
    content: Any


def _metrics(value: Any) -> tuple[str, int, int]:
    content = canonical_json(value)
    return canonical_hash(value), len(content.encode("utf-8")), len(content)


def _authoritative_content(source: ContextSourceRef, content: Any) -> Any:
    """The object a frame/evidence decision hashes.

    Selection wraps the domain object (``ContextEvidenceItem`` /
    ``ContextQuestionFrame``) while exclusion carries the raw object; both must
    hash to the same authoritative value so a source's identity never depends on
    whether it made the cut (corrective §6.3 point 6).
    """

    if source.source_type == ContextSourceType.EVIDENCE:
        return content.evidence if isinstance(content, ContextEvidenceItem) else content
    if source.source_type == ContextSourceType.QUESTION_FRAME:
        return content.frame if isinstance(content, ContextQuestionFrame) else content
    return content


def _decision(draft: _DecisionDraft) -> ContextItemDecision:
    content_hash, byte_size, code_points = _metrics(
        _authoritative_content(draft.source, draft.content)
    )
    if draft.source.content_hash is not None and content_hash != draft.source.content_hash:
        raise ContextBuildError("context decision content hash disagrees with its source")
    return ContextItemDecision(
        source=draft.source,
        section=draft.section,
        selected=draft.selected,
        reason_codes=tuple(sorted(set(draft.reasons))),
        selected_ordinal=draft.selected_ordinal,
        content_hash=content_hash,
        utf8_bytes=byte_size,
        unicode_code_points=code_points,
    )


def _state_source(
    source_type: ContextSourceType,
    source_id: object,
    state_hash: str,
    content_hash: str | None = None,
) -> ContextSourceRef:
    return ContextSourceRef(
        source_type=source_type,
        source_id=str(source_id),
        state_hash=state_hash,
        content_hash=content_hash,
    )


def _policy_source(source_id: str) -> ContextSourceRef:
    return ContextSourceRef(
        source_type=ContextSourceType.POLICY,
        source_id=source_id,
    )


def _reference_source(urn: str, snapshot_hash: str) -> ContextSourceRef:
    return ContextSourceRef(
        source_type=ContextSourceType.REFERENCE,
        source_id=urn,
        reference_snapshot_hash=snapshot_hash,
    )


def _identity(
    *,
    operation_name: str,
    operation_definition_hash: str,
    policy,
    session_id: UUID,
    turn_id: UUID,
    operation_id: UUID,
    state_hash: str,
    state_version: int,
    reference_snapshot_hash: str | None,
) -> dict[str, Any]:
    return ContextIdentity(
        operation_name=operation_name,
        operation_definition_hash=operation_definition_hash,
        context_policy_name=policy.name,
        context_policy_version=policy.version,
        context_policy_hash=policy.policy_hash,
        session_id=session_id,
        turn_id=turn_id,
        operation_id=operation_id,
        state_hash=state_hash,
        state_version=state_version,
        reference_snapshot_hash=reference_snapshot_hash,
        section_order=policy.section_order,
    ).model_dump()


def _finalize_manifest(
    identity: dict[str, Any], drafts: list[_DecisionDraft]
) -> ContextSelectionManifest:
    decisions = tuple(
        sorted(
            (_decision(item) for item in drafts),
            key=lambda item: (item.source.source_type.value, item.source.source_id),
        )
    )
    return ContextSelectionManifest(**identity, decisions=decisions)


def _budget_report(
    *,
    identity: dict[str, Any],
    packet: Any,
    manifest: ContextSelectionManifest,
    policy,
    item_caps: dict[str, int | None],
    section_singletons: dict[str, tuple[Any, ...]] | None = None,
    limitations: tuple[str, ...] = (),
) -> ContextBudgetReport:
    packet_json = canonical_json(packet)
    actual_bytes = len(packet_json.encode("utf-8"))
    code_points = len(packet_json)
    estimated_tokens = max(code_points, (actual_bytes + 3) // 4)
    selected_by_section = {
        section: tuple(
            item
            for item in manifest.decisions
            if item.selected and item.section == section
        )
        for section in policy.section_order
    }
    section_singletons = section_singletons or {}

    def section_metrics(section: str) -> tuple[int, int, int]:
        decisions = selected_by_section[section]
        singletons = section_singletons.get(section, ())
        singleton_metrics = tuple(_metrics(item) for item in singletons)
        return (
            len(decisions) + len(singletons),
            sum(item.utf8_bytes for item in decisions)
            + sum(item[1] for item in singleton_metrics),
            sum(item.unicode_code_points for item in decisions)
            + sum(item[2] for item in singleton_metrics),
        )

    metrics = {
        section: section_metrics(section) for section in policy.section_order
    }
    sections = tuple(
        ContextSectionBudget(
            section=section,
            selected_items=metrics[section][0],
            item_cap=item_caps.get(section),
            within_item_cap=(
                item_caps.get(section) is None
                or metrics[section][0] <= item_caps[section]
            ),
            utf8_bytes=metrics[section][1],
            unicode_code_points=metrics[section][2],
        )
        for section in policy.section_order
    )
    within_budget = actual_bytes <= policy.max_utf8_bytes and all(
        section.within_item_cap for section in sections
    )
    return ContextBudgetReport(
        **identity,
        max_utf8_bytes=policy.max_utf8_bytes,
        actual_utf8_bytes=actual_bytes,
        unicode_code_points=code_points,
        reserved_output_tokens=policy.reserved_output_tokens,
        token_estimator=policy.token_estimator,
        estimated_input_tokens=estimated_tokens,
        sections=sections,
        within_budget=within_budget,
        limitations=tuple(sorted({TOKEN_ESTIMATE_LIMITATION, *limitations})),
    )


def _result_or_raise(
    *,
    packet: ContextPacket,
    manifest: ContextSelectionManifest,
    budget: ContextBudgetReport,
) -> ContextBuildResult:
    if not budget.within_budget:
        raise ContextBudgetExceeded(packet=packet, manifest=manifest, budget=budget)
    return ContextBuildResult(
        packet=packet,
        manifest=manifest,
        budget=budget,
        packet_hash=canonical_hash(packet),
        manifest_hash=canonical_hash(manifest),
        budget_hash=canonical_hash(budget),
    )


def _question_result_or_raise(
    *,
    packet: QuestionSelectContextPacket,
    manifest: ContextSelectionManifest,
    budget: ContextBudgetReport,
) -> QuestionSelectContextBuildResult:
    if not budget.within_budget:
        raise ContextBudgetExceeded(packet=packet, manifest=manifest, budget=budget)
    return QuestionSelectContextBuildResult(
        packet=packet,
        manifest=manifest,
        budget=budget,
        packet_hash=canonical_hash(packet),
        manifest_hash=canonical_hash(manifest),
        budget_hash=canonical_hash(budget),
    )


def _turn_sequence_by_evidence(state: InterviewState) -> dict[UUID, int]:
    turn_sequences = {turn.turn_id: turn.sequence for turn in state.turns}
    return {
        evidence.evidence_id: turn_sequences[evidence.source_turn_id]
        for evidence in state.evidence
    }


def _contradictions(
    *,
    state: InterviewState,
    episode_id: UUID,
    state_hash: str,
) -> tuple[ContextContradiction, ...]:
    evidence_sequences = _turn_sequence_by_evidence(state)
    items = []
    for gap in state.gaps:
        if (
            gap.episode_id != episode_id
            or gap.dimension != GapDimension.CONTRADICTION
            or gap.status not in UNRESOLVED_CONTRADICTION_STATUSES
        ):
            continue
        latest = max(
            (evidence_sequences[item] for item in gap.supporting_evidence_ids),
            default=0,
        )
        items.append(
            ContextContradiction(
                source=_state_source(
                    ContextSourceType.GAP, gap.gap_id, state_hash
                ),
                latest_supporting_turn_sequence=latest,
                gap=gap,
            )
        )
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.latest_supporting_turn_sequence,
                str(item.gap.gap_id),
            ),
        )
    )


def _evidence_item(state_hash: str, turn_sequences: dict[UUID, int], evidence):
    return ContextEvidenceItem(
        source=_state_source(
            ContextSourceType.EVIDENCE,
            evidence.evidence_id,
            state_hash,
            canonical_hash(evidence),
        ),
        turn_sequence=turn_sequences[evidence.source_turn_id],
        evidence=evidence,
    )


def _question_frame_source_refs(definition) -> tuple:
    refs: list = []
    for target in definition.targets:
        if isinstance(target, PropositionQuestionTarget):
            refs.extend(target.proposition.source_refs)
        elif isinstance(target, SlotQuestionTarget):
            refs.extend(target.source_refs)
        else:
            for option in target.options:
                refs.extend(option.proposition.source_refs)
    return tuple(refs)


def _eligible_question_frame(
    *,
    state: InterviewState,
    current_turn,
    preceding,
    state_hash: str,
) -> tuple[ContextQuestionFrame | None, QuestionFrameLimitation | None]:
    """Project the frame only when every closure condition holds.

    A frame that is stale, superseded, or not the immediately preceding question
    is deliberately withheld rather than repaired: the builder only observes
    state, and a short answer with no frame must fail to bind rather than bind
    to a stale question (plan §9.3).
    """

    if state.active_question_frame_id is None:
        return None, QuestionFrameLimitation.MISSING
    frame = next(
        (
            item
            for item in state.question_frames
            if item.question_frame_id == state.active_question_frame_id
        ),
        None,
    )
    if frame is None or frame.status != QuestionFrameStatus.ACTIVE:
        return None, QuestionFrameLimitation.NOT_ACTIVE
    if frame.answer_turn_id != current_turn.turn_id:
        return None, QuestionFrameLimitation.ANSWER_NOT_BOUND
    if preceding is None or frame.consultant_turn_id != preceding.turn_id:
        return None, QuestionFrameLimitation.NOT_IMMEDIATE
    if frame.definition.question_text_hash != sha256_utf8_text(preceding.text):
        return None, QuestionFrameLimitation.TEXT_HASH_MISMATCH

    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    for ref in _question_frame_source_refs(frame.definition):
        if ref.source_kind != QuestionSourceKind.EMPLOYEE_EVIDENCE:
            continue
        try:
            evidence_id = UUID(ref.source_ref)
        except ValueError:
            return None, QuestionFrameLimitation.SOURCE_INVALID
        source = evidence_by_id.get(evidence_id)
        if source is None or source.status != EvidenceStatus.ACTIVE:
            return None, QuestionFrameLimitation.SOURCE_NOT_ACTIVE
        if canonical_hash(source) != ref.source_hash:
            return None, QuestionFrameLimitation.SOURCE_HASH_MISMATCH

    return (
        ContextQuestionFrame(
            source=_state_source(
                ContextSourceType.QUESTION_FRAME,
                frame.question_frame_id,
                state_hash,
                canonical_hash(frame),
            ),
            frame=frame,
        ),
        None,
    )


class ContextBuilder:
    """Build operation-specific context without I/O, provider state, or environment."""

    def build_turn_interpret(
        self,
        *,
        state: InterviewState,
        employee_turn_id: UUID,
        operation_id: UUID,
        operation_definition_hash: str,
        policy: TurnInterpretContextPolicy,
    ) -> ContextBuildResult:
        state = InterviewState.model_validate(state.model_dump())
        policy = TurnInterpretContextPolicy.model_validate(policy.model_dump())
        state_hash = canonical_hash(state)
        turn_by_id = {turn.turn_id: turn for turn in state.turns}
        try:
            current_turn = turn_by_id[employee_turn_id]
        except KeyError as exc:
            raise ContextBuildError("employee turn does not exist in state") from exc
        if current_turn.role != TranscriptRole.EMPLOYEE:
            raise ContextBuildError("turn_interpret requires an employee turn")

        preceding = next(
            (
                turn
                for turn in reversed(state.turns[: current_turn.sequence - 1])
                if turn.role == TranscriptRole.CONSULTANT
            ),
            None,
        )
        episode = next(
            (
                item
                for item in state.episodes
                if item.episode_id == state.session.active_episode_id
            ),
            None,
        )
        episode_identity = (
            ContextEpisodeIdentity(
                episode_id=episode.episode_id,
                target=episode.target,
                status=episode.status,
            )
            if episode is not None
            else None
        )
        all_contradictions = (
            _contradictions(
                state=state, episode_id=episode.episode_id, state_hash=state_hash
            )
            if episode is not None
            else ()
        )
        selected_contradictions = all_contradictions[-policy.contradiction_cap :]

        turn_sequences = {turn.turn_id: turn.sequence for turn in state.turns}
        active_episode_evidence = tuple(
            sorted(
                (
                    item
                    for item in state.evidence
                    if episode is not None
                    and item.episode_id == episode.episode_id
                    and item.status == EvidenceStatus.ACTIVE
                ),
                key=lambda item: (
                    turn_sequences[item.source_turn_id],
                    str(item.evidence_id),
                ),
            )
        )
        question_frame_item, frame_limitation = _eligible_question_frame(
            state=state,
            current_turn=current_turn,
            preceding=preceding,
            state_hash=state_hash,
        )

        folded_text = current_turn.text.casefold()
        has_correction_cue = any(
            cue.casefold() in folded_text for cue in policy.correction_cues
        )
        correction_cap = (
            policy.correction_candidate_cap
            if has_correction_cue
            else policy.default_correction_candidate_cap
        )
        correction_evidence = active_episode_evidence[-correction_cap:]
        recent_window = active_episode_evidence[-policy.recent_active_evidence_cap :]
        correction_ids = {item.evidence_id for item in correction_evidence}
        recent_evidence = tuple(
            item for item in recent_window if item.evidence_id not in correction_ids
        )
        correction_items = tuple(
            _evidence_item(state_hash, turn_sequences, item)
            for item in correction_evidence
        )
        recent_items = tuple(
            _evidence_item(state_hash, turn_sequences, item) for item in recent_evidence
        )

        identity = _identity(
            operation_name=policy.operation_name,
            operation_definition_hash=operation_definition_hash,
            policy=policy,
            session_id=state.session.session_id,
            turn_id=current_turn.turn_id,
            operation_id=operation_id,
            state_hash=state_hash,
            state_version=state.session.state_version,
            reference_snapshot_hash=None,
        )
        packet = TurnInterpretContextPacket(
            **identity,
            preceding_consultant_turn=preceding,
            current_employee_turn=current_turn,
            question_frame=question_frame_item,
            question_frame_limitation=frame_limitation,
            active_episode=episode_identity,
            contradictions=selected_contradictions,
            correction_candidates=correction_items,
            recent_active_evidence=recent_items,
        )

        selected: dict[tuple[ContextSourceType, str], tuple[str, set[str], Any]] = {}

        def choose(source, section: str, reason: str, content: Any) -> None:
            key = (source.source_type, source.source_id)
            if key in selected:
                selected[key][1].add(reason)
            else:
                selected[key] = (section, {reason}, content)

        boundary_source = _policy_source(f"{policy.name}:injection-boundary")
        choose(boundary_source, "injection_boundary", "required_policy_boundary", INJECTION_BOUNDARY)
        if preceding is not None:
            choose(
                _state_source(ContextSourceType.TURN, preceding.turn_id, state_hash),
                "preceding_consultant_turn",
                "required_preceding_turn",
                preceding,
            )
        choose(
            _state_source(ContextSourceType.TURN, current_turn.turn_id, state_hash),
            "current_employee_turn",
            "required_current_turn",
            current_turn,
        )
        if question_frame_item is not None:
            # Mandatory when eligible: budget pressure may never drop or truncate
            # the frame, because a partial frame would silently change what the
            # short answer binds to (plan §9.2).
            choose(
                question_frame_item.source,
                "question_frame",
                "eligible_question_frame",
                question_frame_item,
            )
        if episode is not None:
            choose(
                _state_source(ContextSourceType.EPISODE, episode.episode_id, state_hash),
                "active_episode",
                "active_episode_identity",
                episode_identity,
            )
        for item in selected_contradictions:
            choose(
                item.source,
                "contradictions",
                "unresolved_contradiction",
                item,
            )
        recent_window_ids = {item.evidence_id for item in recent_window}
        for item in correction_items:
            choose(
                item.source,
                "correction_candidates",
                "correction_candidate",
                item,
            )
            if item.evidence.evidence_id in recent_window_ids:
                choose(
                    item.source,
                    "correction_candidates",
                    "recent_active_evidence",
                    item,
                )
        for item in recent_items:
            choose(
                item.source,
                "recent_active_evidence",
                "recent_active_evidence",
                item,
            )

        selected_order = sorted(
            selected.items(),
            key=lambda pair: (
                policy.section_order.index(pair[1][0]),
                _selected_content_order(pair[1][2]),
            ),
        )
        selected_ordinals = {
            key: ordinal for ordinal, (key, _value) in enumerate(selected_order, 1)
        }

        drafts: list[_DecisionDraft] = []

        def add(source, content, excluded_reason: str) -> None:
            key = (source.source_type, source.source_id)
            if key in selected:
                section, reasons, selected_content = selected[key]
                drafts.append(
                    _DecisionDraft(
                        source, section, True, tuple(reasons),
                        selected_ordinals[key], selected_content
                    )
                )
            else:
                drafts.append(
                    _DecisionDraft(
                        source, "excluded", False, (excluded_reason,), None, content
                    )
                )

        add(boundary_source, INJECTION_BOUNDARY, "not_selected")
        for turn in state.turns:
            add(
                _state_source(ContextSourceType.TURN, turn.turn_id, state_hash),
                turn,
                "outside_turn_window",
            )
        for item in state.episodes:
            add(
                _state_source(ContextSourceType.EPISODE, item.episode_id, state_hash),
                item,
                "not_active_episode",
            )
        for frame in state.question_frames:
            add(
                _state_source(
                    ContextSourceType.QUESTION_FRAME,
                    frame.question_frame_id,
                    state_hash,
                    canonical_hash(frame),
                ),
                frame,
                (frame_limitation or QuestionFrameLimitation.NOT_ACTIVE).value,
            )
        selected_contradiction_ids = {
            item.gap.gap_id for item in selected_contradictions
        }
        all_contradiction_ids = {item.gap.gap_id for item in all_contradictions}
        for gap in state.gaps:
            reason = (
                "section_cap_exceeded"
                if gap.gap_id in all_contradiction_ids
                and gap.gap_id not in selected_contradiction_ids
                else "not_unresolved_contradiction"
            )
            add(
                _state_source(ContextSourceType.GAP, gap.gap_id, state_hash),
                gap,
                reason,
            )
        selected_evidence_ids = correction_ids | {
            item.evidence_id for item in recent_evidence
        }
        for evidence in state.evidence:
            if evidence.evidence_id in selected_evidence_ids:
                reason = "not_selected"
            elif evidence.status != EvidenceStatus.ACTIVE:
                reason = "inactive_evidence"
            elif episode is None or evidence.episode_id != episode.episode_id:
                reason = "outside_active_episode"
            else:
                reason = "section_cap_exceeded"
            add(
                _state_source(
                    ContextSourceType.EVIDENCE,
                    evidence.evidence_id,
                    state_hash,
                    canonical_hash(evidence),
                ),
                evidence,
                reason,
            )
        for inference in state.inferences:
            add(
                _state_source(
                    ContextSourceType.INFERENCE, inference.inference_id, state_hash
                ),
                inference,
                "forbidden_inference",
            )
        for candidate in state.candidates:
            add(
                _state_source(
                    ContextSourceType.CANDIDATE, candidate.candidate_id, state_hash
                ),
                candidate,
                "forbidden_candidate",
            )
        for review in state.reviews:
            add(
                _state_source(ContextSourceType.REVIEW, review.review_id, state_hash),
                review,
                "forbidden_review",
            )

        manifest = _finalize_manifest(identity, drafts)
        budget = _budget_report(
            identity=identity,
            packet=packet,
            manifest=manifest,
            policy=policy,
            item_caps={
                "injection_boundary": 1,
                "preceding_consultant_turn": 1,
                "current_employee_turn": 1,
                "question_frame": 1,
                "active_episode": 1,
                "contradictions": policy.contradiction_cap,
                "correction_candidates": correction_cap,
                "recent_active_evidence": policy.recent_active_evidence_cap,
            },
            limitations=(
                (QUESTION_FRAME_LIMITATIONS[frame_limitation],)
                if frame_limitation is not None
                else ()
            ),
        )
        return _result_or_raise(packet=packet, manifest=manifest, budget=budget)

    def build_question_select(
        self,
        *,
        state: InterviewState,
        agenda: QuestionAgenda,
        job_digest: JobStateDigest,
        operation_id: UUID,
        operation_definition_hash: str,
        policy: QuestionSelectContextPolicy,
    ) -> QuestionSelectContextBuildResult:
        """Build the bounded state used to choose one next consultant question."""

        state = InterviewState.model_validate(state.model_dump())
        agenda = QuestionAgenda.model_validate(agenda.model_dump())
        job_digest = JobStateDigest.model_validate(job_digest.model_dump())
        policy = QuestionSelectContextPolicy.model_validate(policy.model_dump())
        if (
            agenda.session_id != state.session.session_id
            or agenda.state_version != state.session.state_version
        ):
            raise ContextBuildError("question agenda is stale or belongs to another session")
        if job_digest.session_id != state.session.session_id:
            raise ContextBuildError("job digest belongs to another interview session")
        if agenda.active_episode_id != state.session.active_episode_id:
            raise ContextBuildError("question agenda active episode is stale")
        if not state.turns or state.turns[-1].role != TranscriptRole.EMPLOYEE:
            raise ContextBuildError(
                "question.select requires an employee turn at the transcript tail"
            )

        latest_employee = state.turns[-1]
        if latest_employee.turn_id not in {
            item.employee_turn_id for item in state.turn_interpretations
        }:
            raise ContextBuildError(
                "question.select requires the latest employee turn to be interpreted"
            )
        recent_consultant = next(
            (
                turn
                for turn in reversed(state.turns[:-1])
                if turn.role == TranscriptRole.CONSULTANT
            ),
            None,
        )
        episode = next(
            (
                item
                for item in state.episodes
                if item.episode_id == state.session.active_episode_id
            ),
            None,
        )
        episode_identity = (
            ContextEpisodeIdentity(
                episode_id=episode.episode_id,
                target=episode.target,
                status=episode.status,
            )
            if episode is not None
            else None
        )
        state_hash = canonical_hash(state)
        active_evidence = {
            item.evidence_id: item
            for item in state.evidence
            if item.status == EvidenceStatus.ACTIVE
            and (
                episode is None
                or item.episode_id == episode.episode_id
            )
        }
        requested_support_ids = tuple(
            sorted(
                {
                    evidence_id
                    for candidate in agenda.candidates
                    for evidence_id in candidate.supporting_evidence_ids
                    if evidence_id in active_evidence
                },
                key=str,
            )
        )
        selected_support_ids = requested_support_ids[: policy.max_evidence_items]
        turn_sequences = {turn.turn_id: turn.sequence for turn in state.turns}
        evidence_items = tuple(
            _evidence_item(
                state_hash, turn_sequences, active_evidence[evidence_id]
            )
            for evidence_id in selected_support_ids
        )
        selected_support_set = set(selected_support_ids)

        context_candidates: list[QuestionSelectContextCandidate] = []
        for candidate in agenda.candidates[: policy.max_candidate_items]:
            source = (
                _state_source(
                    ContextSourceType.GAP,
                    candidate.existing_gap_id,
                    state_hash,
                )
                if candidate.source == QuestionAgendaSource.EXISTING_GAP
                else _policy_source(f"question-agenda:{candidate.stable_key}")
            )
            context_candidates.append(
                QuestionSelectContextCandidate(
                    source=source,
                    ordinal=candidate.ordinal,
                    stable_key=candidate.stable_key,
                    dimension=candidate.dimension,
                    question_goal=candidate.question_goal,
                    supporting_evidence_ids=tuple(
                        evidence_id
                        for evidence_id in candidate.supporting_evidence_ids
                        if evidence_id in selected_support_set
                    ),
                    existing_gap_id=candidate.existing_gap_id,
                )
            )

        identity = _identity(
            operation_name=policy.operation_name,
            operation_definition_hash=operation_definition_hash,
            policy=policy,
            session_id=state.session.session_id,
            turn_id=latest_employee.turn_id,
            operation_id=operation_id,
            state_hash=state_hash,
            state_version=state.session.state_version,
            reference_snapshot_hash=None,
        )
        dialogue_limits = QuestionSelectDialogueLimits(
            allow_broaden_coverage=agenda.allow_broaden_coverage,
            allow_offer_finish=agenda.allow_offer_finish,
            remaining_high_value_questions=agenda.remaining_high_value_questions,
        )
        packet = QuestionSelectContextPacket(
            **identity,
            latest_employee_turn=latest_employee,
            recent_consultant_question=recent_consultant,
            active_episode=episode_identity,
            agenda_candidates=tuple(context_candidates),
            supporting_evidence=evidence_items,
            job_state_digest=job_digest,
            dialogue_limits=dialogue_limits,
        )

        selected: dict[
            tuple[ContextSourceType, str], tuple[str, set[str], Any]
        ] = {}

        def choose(source, section: str, reason: str, content: Any) -> None:
            key = (source.source_type, source.source_id)
            if key in selected:
                selected[key][1].add(reason)
            else:
                selected[key] = (section, {reason}, content)

        boundary_source = _policy_source(f"{policy.name}:injection-boundary")
        choose(
            boundary_source,
            "injection_boundary",
            "required_policy_boundary",
            INJECTION_BOUNDARY,
        )
        choose(
            _state_source(
                ContextSourceType.TURN, latest_employee.turn_id, state_hash
            ),
            "latest_employee_turn",
            "required_latest_employee_turn",
            latest_employee,
        )
        if recent_consultant is not None:
            choose(
                _state_source(
                    ContextSourceType.TURN, recent_consultant.turn_id, state_hash
                ),
                "recent_consultant_question",
                "recent_question_for_repetition_control",
                recent_consultant,
            )
        if episode is not None:
            choose(
                _state_source(
                    ContextSourceType.EPISODE, episode.episode_id, state_hash
                ),
                "active_episode",
                "active_episode_identity",
                episode_identity,
            )
        for item in context_candidates:
            choose(
                item.source,
                "agenda_candidates",
                "eligible_question_candidate",
                item,
            )
        for item in evidence_items:
            choose(
                item.source,
                "supporting_evidence",
                "candidate_supporting_evidence",
                item,
            )

        selected_order = sorted(
            selected.items(),
            key=lambda pair: (
                policy.section_order.index(pair[1][0]),
                _selected_content_order(pair[1][2]),
            ),
        )
        selected_ordinals = {
            key: ordinal for ordinal, (key, _value) in enumerate(selected_order, 1)
        }
        drafts: list[_DecisionDraft] = []
        drafted: set[tuple[ContextSourceType, str]] = set()

        def add(source, content, excluded_reason: str) -> None:
            key = (source.source_type, source.source_id)
            if key in drafted:
                return
            drafted.add(key)
            if key in selected:
                section, reasons, selected_content = selected[key]
                drafts.append(
                    _DecisionDraft(
                        source,
                        section,
                        True,
                        tuple(reasons),
                        selected_ordinals[key],
                        selected_content,
                    )
                )
            else:
                drafts.append(
                    _DecisionDraft(
                        source,
                        "excluded",
                        False,
                        (excluded_reason,),
                        None,
                        content,
                    )
                )

        add(boundary_source, INJECTION_BOUNDARY, "not_selected")
        for turn in state.turns:
            add(
                _state_source(ContextSourceType.TURN, turn.turn_id, state_hash),
                turn,
                "outside_recent_question_window",
            )
        for item in state.episodes:
            add(
                _state_source(
                    ContextSourceType.EPISODE, item.episode_id, state_hash
                ),
                item,
                "not_active_episode",
            )
        context_candidate_by_key = {
            item.stable_key: item for item in context_candidates
        }
        for candidate in agenda.candidates:
            item = context_candidate_by_key.get(candidate.stable_key)
            source = (
                item.source
                if item is not None
                else (
                    _state_source(
                        ContextSourceType.GAP,
                        candidate.existing_gap_id,
                        state_hash,
                    )
                    if candidate.source == QuestionAgendaSource.EXISTING_GAP
                    else _policy_source(
                        f"question-agenda:{candidate.stable_key}"
                    )
                )
            )
            add(
                source,
                item or candidate,
                "candidate_cap_exceeded",
            )
        for evidence in state.evidence:
            if evidence.evidence_id in selected_support_set:
                reason = "not_selected"
            elif evidence.status != EvidenceStatus.ACTIVE:
                reason = "inactive_evidence"
            elif episode is None or evidence.episode_id != episode.episode_id:
                reason = "outside_active_episode"
            elif evidence.evidence_id in requested_support_ids:
                reason = "section_cap_exceeded"
            else:
                reason = "not_candidate_support"
            add(
                _state_source(
                    ContextSourceType.EVIDENCE,
                    evidence.evidence_id,
                    state_hash,
                    canonical_hash(evidence),
                ),
                evidence,
                reason,
            )
        for gap in state.gaps:
            add(
                _state_source(ContextSourceType.GAP, gap.gap_id, state_hash),
                gap,
                "not_eligible_question_candidate",
            )
        for inference in state.inferences:
            add(
                _state_source(
                    ContextSourceType.INFERENCE,
                    inference.inference_id,
                    state_hash,
                ),
                inference,
                "inference_not_allowed_in_question_context",
            )
        for candidate in state.candidates:
            add(
                _state_source(
                    ContextSourceType.CANDIDATE,
                    candidate.candidate_id,
                    state_hash,
                ),
                candidate,
                "job_candidate_not_allowed_in_question_context",
            )
        for review in state.reviews:
            add(
                _state_source(
                    ContextSourceType.REVIEW, review.review_id, state_hash
                ),
                review,
                "review_not_allowed_in_question_context",
            )

        manifest = _finalize_manifest(identity, drafts)
        budget = _budget_report(
            identity=identity,
            packet=packet,
            manifest=manifest,
            policy=policy,
            item_caps={
                "injection_boundary": 1,
                "latest_employee_turn": 1,
                "recent_consultant_question": 1,
                "active_episode": 1,
                "agenda_candidates": policy.max_candidate_items,
                "supporting_evidence": policy.max_evidence_items,
                "job_state_digest": 1,
                "dialogue_limits": 1,
            },
            section_singletons={
                "job_state_digest": (job_digest,),
                "dialogue_limits": (dialogue_limits,),
            },
            limitations=(
                (
                    "Question agenda supporting Evidence was capped; candidate "
                    "support ordinals include only selected Evidence."
                ,)
                if len(requested_support_ids) > len(selected_support_ids)
                else ()
            ),
        )
        return _question_result_or_raise(
            packet=packet, manifest=manifest, budget=budget
        )

    def build_episode_code(
        self,
        *,
        state: InterviewState,
        episode_id: UUID,
        reference_snapshot: ReferenceSnapshot,
        operation_id: UUID,
        operation_definition_hash: str,
        policy: EpisodeCodeContextPolicy,
    ) -> ContextBuildResult:
        state = InterviewState.model_validate(state.model_dump())
        policy = EpisodeCodeContextPolicy.model_validate(policy.model_dump())
        reference_snapshot = ReferenceSnapshot.model_validate(
            reference_snapshot.model_dump()
        )
        if reference_snapshot.snapshot_id != state.session.reference_snapshot_id:
            raise ContextBuildError("reference snapshot does not match session")
        try:
            episode = next(
                item for item in state.episodes if item.episode_id == episode_id
            )
        except StopIteration as exc:
            raise ContextBuildError("episode does not exist in state") from exc

        state_hash = canonical_hash(state)
        boundary_turn_id = episode.closed_turn_id or state.turns[-1].turn_id
        turn_sequences = {turn.turn_id: turn.sequence for turn in state.turns}
        episode_evidence = tuple(
            sorted(
                (
                    evidence
                    for evidence in state.evidence
                    if evidence.episode_id == episode_id
                    and evidence.status == EvidenceStatus.ACTIVE
                ),
                key=lambda item: (
                    turn_sequences[item.source_turn_id],
                    str(item.evidence_id),
                ),
            )
        )

        def is_positive(evidence) -> bool:
            return (
                evidence.subject
                in {EvidenceSubject.EMPLOYEE, EvidenceSubject.EMPLOYEE_TEAM}
                and evidence.qualifiers.time_scope == TimeScope.CURRENT
                and evidence.qualifiers.polarity != Polarity.DENIED
                and evidence.qualifiers.ownership != Ownership.NOT_RESPONSIBLE
            )

        positive = tuple(item for item in episode_evidence if is_positive(item))
        excluded = tuple(item for item in episode_evidence if not is_positive(item))
        positive_items = tuple(
            _evidence_item(state_hash, turn_sequences, item) for item in positive
        )
        excluded_items = tuple(
            _evidence_item(state_hash, turn_sequences, item) for item in excluded
        )
        contradictions = _contradictions(
            state=state, episode_id=episode_id, state_hash=state_hash
        )
        episode_evidence_ids = set(episode.evidence_ids)
        candidates = tuple(
            sorted(
                (
                    candidate
                    for candidate in state.candidates
                    if candidate.status in EPISODE_CONTEXT_CANDIDATE_STATUSES
                    and bool(set(candidate.evidence_ids) & episode_evidence_ids)
                ),
                key=lambda item: (item.kind.value, str(item.candidate_id)),
            )
        )
        candidate_items = tuple(
            ContextCandidateItem(
                source=_state_source(
                    ContextSourceType.CANDIDATE, item.candidate_id, state_hash
                ),
                candidate=item,
            )
            for item in candidates
        )
        reference_items = tuple(
            ContextReferenceItem(
                source=_reference_source(
                    item.urn, reference_snapshot.snapshot_hash
                ),
                snippet=item,
            )
            for item in reference_snapshot.snippets
        )
        episode_identity = ContextEpisodeIdentity(
            episode_id=episode.episode_id,
            target=episode.target,
            status=episode.status,
        )
        identity = _identity(
            operation_name=policy.operation_name,
            operation_definition_hash=operation_definition_hash,
            policy=policy,
            session_id=state.session.session_id,
            turn_id=boundary_turn_id,
            operation_id=operation_id,
            state_hash=state_hash,
            state_version=state.session.state_version,
            reference_snapshot_hash=reference_snapshot.snapshot_hash,
        )
        packet = EpisodeCodeContextPacket(
            **identity,
            episode=episode_identity,
            positive_evidence=positive_items,
            excluded_or_negative_evidence=excluded_items,
            contradictions=contradictions,
            existing_candidates=candidate_items,
            reference_snippets=reference_items,
        )

        selected: dict[tuple[ContextSourceType, str], tuple[str, set[str], Any]] = {}

        def choose(source, section: str, reason: str, content: Any) -> None:
            selected[(source.source_type, source.source_id)] = (
                section,
                {reason},
                content,
            )

        boundary_source = _policy_source(f"{policy.name}:injection-boundary")
        authority_source = _policy_source(f"{policy.name}:authority-rules")
        episode_source = _state_source(
            ContextSourceType.EPISODE, episode.episode_id, state_hash
        )
        choose(boundary_source, "injection_boundary", "required_policy_boundary", INJECTION_BOUNDARY)
        choose(episode_source, "episode_identity", "required_episode_identity", episode_identity)
        for item in positive_items:
            choose(item.source, "positive_evidence", "eligible_episode_evidence", item)
        for item in excluded_items:
            choose(
                item.source,
                "excluded_or_negative_evidence",
                "negative_or_noncurrent_evidence",
                item,
            )
        for item in contradictions:
            choose(item.source, "contradictions", "unresolved_contradiction", item)
        for item in candidate_items:
            choose(item.source, "existing_candidates", "existing_episode_candidate", item)
        for item in reference_items:
            choose(item.source, "reference_snippets", "fixture_selected_reference", item)
        choose(authority_source, "authority_rules", "required_authority_boundary", EPISODE_AUTHORITY_RULES)

        selected_order = sorted(
            selected.items(),
            key=lambda pair: (
                policy.section_order.index(pair[1][0]),
                _selected_content_order(pair[1][2]),
            ),
        )
        selected_ordinals = {
            key: ordinal for ordinal, (key, _value) in enumerate(selected_order, 1)
        }
        drafts: list[_DecisionDraft] = []

        def add(source, content, excluded_reason: str) -> None:
            key = (source.source_type, source.source_id)
            if key in selected:
                section, reasons, selected_content = selected[key]
                drafts.append(
                    _DecisionDraft(
                        source, section, True, tuple(reasons),
                        selected_ordinals[key], selected_content
                    )
                )
            else:
                drafts.append(
                    _DecisionDraft(
                        source, "excluded", False, (excluded_reason,), None, content
                    )
                )

        add(boundary_source, INJECTION_BOUNDARY, "not_selected")
        add(authority_source, EPISODE_AUTHORITY_RULES, "not_selected")
        for turn in state.turns:
            add(
                _state_source(ContextSourceType.TURN, turn.turn_id, state_hash),
                turn,
                "turn_text_not_allowed_for_episode_code",
            )
        for item in state.episodes:
            add(
                _state_source(ContextSourceType.EPISODE, item.episode_id, state_hash),
                item,
                "not_target_episode",
            )
        for evidence in state.evidence:
            if evidence.status != EvidenceStatus.ACTIVE:
                reason = "inactive_evidence"
            elif evidence.episode_id != episode_id:
                reason = "outside_target_episode"
            else:
                reason = "not_selected"
            add(
                _state_source(
                    ContextSourceType.EVIDENCE,
                    evidence.evidence_id,
                    state_hash,
                    canonical_hash(evidence),
                ),
                evidence,
                reason,
            )
        for gap in state.gaps:
            add(
                _state_source(ContextSourceType.GAP, gap.gap_id, state_hash),
                gap,
                "not_unresolved_contradiction",
            )
        for inference in state.inferences:
            add(
                _state_source(
                    ContextSourceType.INFERENCE, inference.inference_id, state_hash
                ),
                inference,
                "inference_not_allowed_in_episode_context",
            )
        for candidate in state.candidates:
            reason = (
                "candidate_status_not_allowed"
                if candidate.status not in EPISODE_CONTEXT_CANDIDATE_STATUSES
                else "candidate_outside_target_episode"
            )
            add(
                _state_source(
                    ContextSourceType.CANDIDATE, candidate.candidate_id, state_hash
                ),
                candidate,
                reason,
            )
        for review in state.reviews:
            add(
                _state_source(ContextSourceType.REVIEW, review.review_id, state_hash),
                review,
                "review_not_allowed_in_episode_context",
            )
        for item in reference_snapshot.snippets:
            add(
                _reference_source(item.urn, reference_snapshot.snapshot_hash),
                item,
                "reference_not_selected",
            )

        manifest = _finalize_manifest(identity, drafts)
        remaining_evidence_cap = max(
            0, policy.max_evidence_items - len(positive_items)
        )
        budget = _budget_report(
            identity=identity,
            packet=packet,
            manifest=manifest,
            policy=policy,
            item_caps={
                "injection_boundary": 1,
                "episode_identity": 1,
                "positive_evidence": policy.max_evidence_items,
                "excluded_or_negative_evidence": remaining_evidence_cap,
                "contradictions": policy.max_contradiction_items,
                "existing_candidates": policy.max_candidate_items,
                "reference_snippets": policy.max_reference_snippets,
                "authority_rules": 1,
            },
        )
        return _result_or_raise(packet=packet, manifest=manifest, budget=budget)


def _selected_content_order(content: Any) -> tuple[Any, ...]:
    if isinstance(content, ContextEvidenceItem):
        return (content.turn_sequence, str(content.evidence.evidence_id))
    if isinstance(content, ContextContradiction):
        return (
            content.latest_supporting_turn_sequence,
            str(content.gap.gap_id),
        )
    if isinstance(content, ContextCandidateItem):
        return (content.candidate.kind.value, str(content.candidate.candidate_id))
    if isinstance(content, ContextReferenceItem):
        return (content.snippet.urn,)
    if hasattr(content, "sequence") and hasattr(content, "turn_id"):
        return (content.sequence, str(content.turn_id))
    if isinstance(content, ContextEpisodeIdentity):
        return (str(content.episode_id),)
    return (canonical_hash(content),)
