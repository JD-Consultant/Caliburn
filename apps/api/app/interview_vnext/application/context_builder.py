"""Pure deterministic projection from persisted interview state to model context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.interview_vnext.domain.episode import GapDimension, GapStatus
from app.interview_vnext.domain.evidence import (
    EvidenceStatus,
    EvidenceSubject,
    Ownership,
    Polarity,
    TimeScope,
)
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.job_model import CandidateStatus
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
    ContextReferenceItem,
    ContextSectionBudget,
    ContextSelectionManifest,
    ContextSourceRef,
    ContextSourceType,
    EpisodeCodeContextPacket,
    EpisodeCodeContextPolicy,
    ReferenceSnapshot,
    TurnInterpretContextPacket,
    TurnInterpretContextPolicy,
)


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


def _decision(draft: _DecisionDraft) -> ContextItemDecision:
    content_hash, byte_size, code_points = _metrics(draft.content)
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
) -> ContextSourceRef:
    return ContextSourceRef(
        source_type=source_type,
        source_id=str(source_id),
        state_hash=state_hash,
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
    packet: ContextPacket,
    manifest: ContextSelectionManifest,
    policy,
    item_caps: dict[str, int | None],
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
    sections = tuple(
        ContextSectionBudget(
            section=section,
            selected_items=len(selected_by_section[section]),
            item_cap=item_caps.get(section),
            within_item_cap=(
                item_caps.get(section) is None
                or len(selected_by_section[section]) <= item_caps[section]
            ),
            utf8_bytes=sum(item.utf8_bytes for item in selected_by_section[section]),
            unicode_code_points=sum(
                item.unicode_code_points for item in selected_by_section[section]
            ),
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
        limitations=(TOKEN_ESTIMATE_LIMITATION,),
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


def _turn_sequence_by_evidence(state: InterviewState) -> dict[UUID, int]:
    turn_sequences = {turn.turn_id: turn.sequence for turn in state.turns}
    return {
        evidence.evidence_id: turn_sequences[evidence.turn_id]
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
            ContextSourceType.EVIDENCE, evidence.evidence_id, state_hash
        ),
        turn_sequence=turn_sequences[evidence.turn_id],
        evidence=evidence,
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
                key=lambda item: (turn_sequences[item.turn_id], str(item.evidence_id)),
            )
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
            reference_snapshot_hash=None,
        )
        packet = TurnInterpretContextPacket(
            **identity,
            preceding_consultant_turn=preceding,
            current_employee_turn=current_turn,
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
                    ContextSourceType.EVIDENCE, evidence.evidence_id, state_hash
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
                "active_episode": 1,
                "contradictions": policy.contradiction_cap,
                "correction_candidates": correction_cap,
                "recent_active_evidence": policy.recent_active_evidence_cap,
            },
        )
        return _result_or_raise(packet=packet, manifest=manifest, budget=budget)

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
                key=lambda item: (turn_sequences[item.turn_id], str(item.evidence_id)),
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
                    ContextSourceType.EVIDENCE, evidence.evidence_id, state_hash
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
