"""The only pure functions allowed to transition vNext domain state."""

from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from .base import DomainModel
from .commands import (
    ApplyCandidateProposalsCommand,
    ApplyEvidenceCommand,
    ApplyGapProposalsCommand,
    ApplyInferenceProposalsCommand,
    ApplyReviewDecisionCommand,
    AppendTranscriptTurnCommand,
    CommandBase,
    DecideInferenceCommand,
    OpenEpisodeCommand,
    SupersedeInferenceCommand,
    TransitionCandidateCommand,
    TransitionEpisodeCommand,
    TransitionGapCommand,
    TransitionSessionCommand,
    WithdrawEvidenceCommand,
)
from .errors import DomainViolation
from .events import (
    CandidateAppliedEvent,
    CandidateTransitionedEvent,
    DomainEvent,
    EvidenceObservedEvent,
    EvidenceSupersededEvent,
    EvidenceWithdrawnEvent,
    EpisodeOpenedEvent,
    EpisodeTransitionedEvent,
    GapProposedEvent,
    GapTransitionedEvent,
    InferenceAppliedEvent,
    InferenceSupersededEvent,
    InferenceTransitionedEvent,
    ReviewDecisionAppliedEvent,
    SessionTransitionedEvent,
    TranscriptTurnAppendedEvent,
)
from .episode import EpisodeState, EpisodeStatus, GapStatus, Sensitivity
from .evidence import Evidence, EvidenceStatus, InferenceMethod, InferenceStatus
from .hashing import canonical_hash
from .invariants import (
    assert_candidate_lineage,
    assert_candidate_projectable,
    assert_evidence_matches_turn,
    assert_model_may_replace_candidate,
)
from .job_model import CandidateStatus
from .reason_codes import ReasonCode
from .review import ReviewAction
from .session import (
    LEGAL_SESSION_TRANSITIONS,
    TERMINAL_SESSION_STATUSES,
    InterviewSession,
    SessionStatus,
)
from .state import InterviewState
from .transcript import TranscriptRole


class ReductionResult(DomainModel):
    state: InterviewState
    events: tuple[DomainEvent, ...] = ()
    reason_code: ReasonCode
    idempotent: bool = False
    state_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


def _replace(model: DomainModel, **changes: Any):
    payload = model.model_dump(mode="python")
    payload.update(changes)
    return type(model).model_validate(payload)


def _event_id(command_id: UUID, event_type: str, ordinal: int) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn:{command_id}:{event_type}:{ordinal}")


def _preflight(
    state: InterviewState,
    command: CommandBase,
    *,
    allow_terminal: bool = False,
) -> ReductionResult | None:
    if command.command_id in state.processed_command_ids:
        return ReductionResult(
            state=state,
            events=(),
            reason_code=ReasonCode.DUPLICATE_COMMAND,
            idempotent=True,
            state_hash=canonical_hash(state),
        )
    if command.expected_state_version != state.session.state_version:
        raise DomainViolation(
            ReasonCode.STATE_VERSION_CONFLICT,
            "expected_state_version does not match current state",
            details={
                "expected": command.expected_state_version,
                "actual": state.session.state_version,
            },
        )
    if command.occurred_at < state.session.updated_at:
        raise DomainViolation(
            ReasonCode.COMMAND_TIME_REGRESSION,
            "command occurred_at precedes the materialized state",
            details={
                "command_occurred_at": command.occurred_at.isoformat(),
                "state_updated_at": state.session.updated_at.isoformat(),
            },
        )
    if not allow_terminal and state.session.status in TERMINAL_SESSION_STATUSES:
        raise DomainViolation(
            ReasonCode.TERMINAL_SESSION,
            "terminal session cannot accept new commands",
        )
    return None


def _result(state: InterviewState, events: tuple[DomainEvent, ...]) -> ReductionResult:
    return ReductionResult(
        state=state,
        events=events,
        reason_code=ReasonCode.APPLIED,
        state_hash=canonical_hash(state),
    )


def _commit_state(
    state: InterviewState,
    command: CommandBase,
    *,
    session_changes: dict[str, Any] | None = None,
    **state_changes: Any,
) -> tuple[InterviewState, int]:
    next_version = state.session.state_version + 1
    session = _replace(
        state.session,
        state_version=next_version,
        updated_at=command.occurred_at,
        **(session_changes or {}),
    )
    next_state = _replace(
        state,
        session=session,
        processed_command_ids=state.processed_command_ids + (command.command_id,),
        **state_changes,
    )
    return next_state, next_version


def transition_session(
    state: InterviewState,
    command: TransitionSessionCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate

    current = state.session.status
    if command.target_status not in LEGAL_SESSION_TRANSITIONS[current]:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            f"cannot transition session from {current} to {command.target_status}",
        )
    if command.target_status in TERMINAL_SESSION_STATUSES and command.stop_reason is None:
        raise DomainViolation(
            ReasonCode.STOP_REASON_REQUIRED,
            "terminal transition requires stop_reason",
        )
    if (
        command.target_status == SessionStatus.COMPLETED
        and state.session.active_episode_id is not None
    ):
        raise DomainViolation(
            ReasonCode.ACTIVE_EPISODE_MUST_CLOSE,
            "active episode must close before session completion",
        )

    next_version = state.session.state_version + 1
    stop_reason = (
        command.stop_reason if command.target_status in TERMINAL_SESSION_STATUSES else None
    )
    session = _replace(
        state.session,
        status=command.target_status,
        state_version=next_version,
        stop_reason=stop_reason,
        updated_at=command.occurred_at,
    )
    next_state = _replace(
        state,
        session=session,
        processed_command_ids=state.processed_command_ids + (command.command_id,),
    )
    event = SessionTransitionedEvent(
        event_id=_event_id(command.command_id, "session.transitioned", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        previous_status=current,
        target_status=command.target_status,
        stop_reason=stop_reason,
    )
    return _result(next_state, (event,))


def append_transcript_turn(
    state: InterviewState,
    command: AppendTranscriptTurnCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status != SessionStatus.ACTIVE:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "transcript turns may only be appended to an active session",
        )

    turn = command.turn
    if turn.session_id != state.session.session_id:
        raise DomainViolation(ReasonCode.SESSION_ID_MISMATCH, "turn belongs to another session")
    if any(existing.turn_id == turn.turn_id for existing in state.turns):
        raise DomainViolation(ReasonCode.TURN_ID_DUPLICATE, "turn_id already exists")
    if any(existing.client_turn_id == turn.client_turn_id for existing in state.turns):
        raise DomainViolation(
            ReasonCode.CLIENT_TURN_ID_DUPLICATE,
            "client_turn_id already exists under a different command",
        )
    expected_sequence = len(state.turns) + 1
    if turn.sequence != expected_sequence:
        raise DomainViolation(
            ReasonCode.TURN_SEQUENCE_INVALID,
            "turn sequence must be contiguous",
            details={"expected": expected_sequence, "actual": turn.sequence},
        )
    expected_previous = state.turns[-1].turn_id if state.turns else None
    if turn.previous_turn_id != expected_previous:
        raise DomainViolation(
            ReasonCode.PREVIOUS_TURN_MISMATCH,
            "previous_turn_id does not match the transcript tail",
        )

    next_version = state.session.state_version + 1
    session = _replace(
        state.session,
        state_version=next_version,
        turn_count=expected_sequence,
        updated_at=command.occurred_at,
    )
    next_state = _replace(
        state,
        session=session,
        turns=state.turns + (turn,),
        processed_command_ids=state.processed_command_ids + (command.command_id,),
    )
    event = TranscriptTurnAppendedEvent(
        event_id=_event_id(command.command_id, "transcript.turn_appended", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        turn_id=turn.turn_id,
        turn_sequence=turn.sequence,
    )
    return _result(next_state, (event,))


def apply_evidence(
    state: InterviewState,
    command: ApplyEvidenceCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "evidence may only be applied to an active or finishing session",
        )

    turn_by_id = {turn.turn_id: turn for turn in state.turns}
    turn = turn_by_id.get(command.turn_id)
    if turn is None:
        raise DomainViolation(ReasonCode.TURN_NOT_FOUND, "evidence source turn does not exist")
    if turn.role != TranscriptRole.EMPLOYEE:
        raise DomainViolation(
            ReasonCode.EVIDENCE_REQUIRES_EMPLOYEE_TURN,
            "evidence source turn must be employee-authored",
        )

    existing_by_id = {item.evidence_id: item for item in state.evidence}
    batch_ids = [item.evidence_id for item in command.observations]
    if len(batch_ids) != len(set(batch_ids)) or set(batch_ids) & existing_by_id.keys():
        raise DomainViolation(ReasonCode.EVIDENCE_ID_DUPLICATE, "evidence_id is duplicated")

    superseded_targets: dict[UUID, UUID] = {}
    for item in command.observations:
        if item.status != EvidenceStatus.ACTIVE or item.superseded_by is not None:
            raise DomainViolation(
                ReasonCode.EVIDENCE_PROPOSAL_STATUS_INVALID,
                "new evidence proposals must be active",
            )
        if item.session_id != state.session.session_id or item.turn_id != command.turn_id:
            raise DomainViolation(
                ReasonCode.EVIDENCE_TURN_MISMATCH,
                "evidence does not belong to the command source turn",
            )
        if item.episode_id is not None:
            episode = next(
                (
                    episode
                    for episode in state.episodes
                    if episode.episode_id == item.episode_id
                ),
                None,
            )
            if episode is None:
                raise DomainViolation(
                    ReasonCode.EPISODE_NOT_FOUND,
                    "evidence episode does not exist",
                )
            opened_turn = turn_by_id[episode.opened_turn_id]
            if (
                state.session.active_episode_id != episode.episode_id
                or episode.status == EpisodeStatus.CLOSED
                or turn.sequence < opened_turn.sequence
            ):
                raise DomainViolation(
                    ReasonCode.EVIDENCE_EPISODE_INVALID,
                    "evidence must belong to the active episode and follow its opening",
                )
        assert_evidence_matches_turn(item, turn)
        for target_id in item.supersedes:
            target = existing_by_id.get(target_id)
            if target is None:
                raise DomainViolation(
                    ReasonCode.SUPERSEDE_TARGET_NOT_FOUND,
                    "superseded evidence target does not exist",
                )
            if target.status != EvidenceStatus.ACTIVE:
                raise DomainViolation(
                    ReasonCode.SUPERSEDE_TARGET_NOT_ACTIVE,
                    "only active evidence may be superseded",
                )
            target_turn = turn_by_id[target.turn_id]
            if turn.sequence <= target_turn.sequence:
                raise DomainViolation(
                    ReasonCode.EVIDENCE_TURN_MISMATCH,
                    "replacement evidence must follow the superseded evidence turn",
                )
            if target_id in superseded_targets:
                raise DomainViolation(
                    ReasonCode.SUPERSEDE_TARGET_DUPLICATE,
                    "one evidence item cannot be superseded twice in one command",
                )
            superseded_targets[target_id] = item.evidence_id

    updated_existing: list[Evidence] = []
    for item in state.evidence:
        replacement_id = superseded_targets.get(item.evidence_id)
        if replacement_id is None:
            updated_existing.append(item)
        else:
            updated_existing.append(
                _replace(item, status=EvidenceStatus.SUPERSEDED, superseded_by=replacement_id)
            )

    episodes = list(state.episodes)
    for index, episode in enumerate(episodes):
        additions = tuple(
            item.evidence_id
            for item in command.observations
            if item.episode_id == episode.episode_id
        )
        if additions:
            episodes[index] = _replace(
                episode,
                evidence_ids=episode.evidence_ids + additions,
                updated_at=command.occurred_at,
            )

    next_version = state.session.state_version + 1
    session: InterviewSession = _replace(
        state.session,
        state_version=next_version,
        updated_at=command.occurred_at,
    )
    next_state = _replace(
        state,
        session=session,
        evidence=tuple(updated_existing) + command.observations,
        episodes=tuple(episodes),
        processed_command_ids=state.processed_command_ids + (command.command_id,),
    )

    events: list[DomainEvent] = []
    ordinal = 0
    for item in command.observations:
        events.append(
            EvidenceObservedEvent(
                event_id=_event_id(command.command_id, "evidence.observed", ordinal),
                session_id=state.session.session_id,
                command_id=command.command_id,
                ordinal=ordinal,
                state_version=next_version,
                occurred_at=command.occurred_at,
                evidence_id=item.evidence_id,
                turn_id=item.turn_id,
            )
        )
        ordinal += 1
        for target_id in item.supersedes:
            events.append(
                EvidenceSupersededEvent(
                    event_id=_event_id(command.command_id, "evidence.superseded", ordinal),
                    session_id=state.session.session_id,
                    command_id=command.command_id,
                    ordinal=ordinal,
                    state_version=next_version,
                    occurred_at=command.occurred_at,
                    previous_evidence_id=target_id,
                    replacement_evidence_id=item.evidence_id,
                )
            )
            ordinal += 1
    return _result(next_state, tuple(events))


def withdraw_evidence(
    state: InterviewState,
    command: WithdrawEvidenceCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "evidence may only be withdrawn while active or finishing",
        )

    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    target = evidence_by_id.get(command.evidence_id)
    if target is None:
        raise DomainViolation(ReasonCode.EVIDENCE_NOT_FOUND, "evidence does not exist")
    if target.status != EvidenceStatus.ACTIVE:
        raise DomainViolation(
            ReasonCode.EVIDENCE_NOT_ACTIVE,
            "only active evidence may be withdrawn",
        )

    turn = next(
        (item for item in state.turns if item.turn_id == command.source_turn_id),
        None,
    )
    if turn is None or turn.role != TranscriptRole.EMPLOYEE:
        raise DomainViolation(
            ReasonCode.EVIDENCE_WITHDRAW_TURN_INVALID,
            "withdrawal requires an employee-authored source turn",
        )
    target_turn = next(item for item in state.turns if item.turn_id == target.turn_id)
    if turn.sequence <= target_turn.sequence:
        raise DomainViolation(
            ReasonCode.EVIDENCE_WITHDRAW_TURN_INVALID,
            "withdrawal source turn must follow the original evidence turn",
        )

    evidence = tuple(
        _replace(
            item,
            status=EvidenceStatus.WITHDRAWN,
            withdrawn_reason=command.reason,
            withdrawn_by_turn_id=command.source_turn_id,
        )
        if item.evidence_id == target.evidence_id
        else item
        for item in state.evidence
    )
    active_after = {
        item.evidence_id
        for item in evidence
        if item.status == EvidenceStatus.ACTIVE
    }

    gaps = list(state.gaps)
    gap_transitions: list[tuple[UUID, GapStatus, GapStatus, UUID | None]] = []
    for index, item in enumerate(gaps):
        if target.evidence_id in item.resolution_evidence_ids:
            gap_transitions.append(
                (
                    item.gap_id,
                    item.status,
                    GapStatus.DEFERRED,
                    item.resolution_turn_id,
                )
            )
            gaps[index] = _replace(
                item,
                status=GapStatus.DEFERRED,
                resolution_evidence_ids=(),
                unresolved_reason="resolution evidence withdrawn",
            )

    inferences = list(state.inferences)
    inference_transitions: list[tuple[UUID, InferenceStatus, InferenceStatus]] = []
    for index, item in enumerate(inferences):
        active_support_remains = bool(set(item.supporting_evidence_ids) & active_after)
        decision_withdrawn = item.decision_evidence_id == target.evidence_id
        should_invalidate = decision_withdrawn or (
            target.evidence_id in item.supporting_evidence_ids
            and not active_support_remains
            and item.status
            in {
                InferenceStatus.CANDIDATE,
                InferenceStatus.CONFIRMED_BY_EMPLOYEE,
                InferenceStatus.REJECTED,
            }
        )
        if should_invalidate:
            inference_transitions.append(
                (item.inference_id, item.status, InferenceStatus.INSUFFICIENT)
            )
            inferences[index] = _replace(
                item,
                status=InferenceStatus.INSUFFICIENT,
                decision_evidence_id=None,
                uncertainty_reason="supporting evidence withdrawn",
            )

    candidates = list(state.candidates)
    candidate_transitions: list[tuple[UUID, CandidateStatus, CandidateStatus]] = []
    for index, item in enumerate(candidates):
        if (
            target.evidence_id in item.evidence_ids
            and item.status
            in {
                CandidateStatus.DRAFT,
                CandidateStatus.VERIFIED,
                CandidateStatus.PROJECTED,
            }
        ):
            candidate_transitions.append(
                (item.candidate_id, item.status, CandidateStatus.INSUFFICIENT)
            )
            candidates[index] = _replace(item, status=CandidateStatus.INSUFFICIENT)

    next_state, next_version = _commit_state(
        state,
        command,
        evidence=evidence,
        gaps=tuple(gaps),
        inferences=tuple(inferences),
        candidates=tuple(candidates),
    )
    events: list[DomainEvent] = [
        EvidenceWithdrawnEvent(
            event_id=_event_id(command.command_id, "evidence.withdrawn", 0),
            session_id=state.session.session_id,
            command_id=command.command_id,
            ordinal=0,
            state_version=next_version,
            occurred_at=command.occurred_at,
            evidence_id=target.evidence_id,
            source_turn_id=command.source_turn_id,
            reason=command.reason,
        )
    ]
    ordinal = 1
    for gap_id, previous, target_status, source_turn_id in gap_transitions:
        events.append(
            GapTransitionedEvent(
                event_id=_event_id(command.command_id, "gap.transitioned", ordinal),
                session_id=state.session.session_id,
                command_id=command.command_id,
                ordinal=ordinal,
                state_version=next_version,
                occurred_at=command.occurred_at,
                gap_id=gap_id,
                previous_status=previous,
                target_status=target_status,
                source_turn_id=source_turn_id,
                cause="evidence_withdrawn",
            )
        )
        ordinal += 1
    for inference_id, previous, target_status in inference_transitions:
        events.append(
            InferenceTransitionedEvent(
                event_id=_event_id(command.command_id, "inference.transitioned", ordinal),
                session_id=state.session.session_id,
                command_id=command.command_id,
                ordinal=ordinal,
                state_version=next_version,
                occurred_at=command.occurred_at,
                inference_id=inference_id,
                previous_status=previous,
                target_status=target_status,
                cause="evidence_withdrawn",
            )
        )
        ordinal += 1
    for candidate_id, previous, target_status in candidate_transitions:
        events.append(
            CandidateTransitionedEvent(
                event_id=_event_id(command.command_id, "candidate.transitioned", ordinal),
                session_id=state.session.session_id,
                command_id=command.command_id,
                ordinal=ordinal,
                state_version=next_version,
                occurred_at=command.occurred_at,
                candidate_id=candidate_id,
                previous_status=previous,
                target_status=target_status,
                cause="evidence_withdrawn",
            )
        )
        ordinal += 1
    return _result(next_state, tuple(events))


def open_episode(
    state: InterviewState,
    command: OpenEpisodeCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status != SessionStatus.ACTIVE:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "episode may only open in an active session",
        )
    if state.session.active_episode_id is not None:
        raise DomainViolation(
            ReasonCode.ACTIVE_EPISODE_EXISTS,
            "close the active episode before opening another",
        )
    if any(item.episode_id == command.episode_id for item in state.episodes):
        raise DomainViolation(ReasonCode.EPISODE_ID_DUPLICATE, "episode_id already exists")
    if not state.turns or state.turns[-1].turn_id != command.opened_turn_id:
        raise DomainViolation(
            ReasonCode.EPISODE_OPEN_TURN_INVALID,
            "episode must open at the current transcript tail",
        )

    episode = EpisodeState(
        episode_id=command.episode_id,
        session_id=state.session.session_id,
        target=command.target,
        opened_turn_id=command.opened_turn_id,
        created_at=command.occurred_at,
        updated_at=command.occurred_at,
    )
    next_state, next_version = _commit_state(
        state,
        command,
        session_changes={"active_episode_id": episode.episode_id},
        episodes=state.episodes + (episode,),
    )
    event = EpisodeOpenedEvent(
        event_id=_event_id(command.command_id, "episode.opened", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        episode_id=episode.episode_id,
        opened_turn_id=episode.opened_turn_id,
    )
    return _result(next_state, (event,))


def transition_episode(
    state: InterviewState,
    command: TransitionEpisodeCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "episode may only transition while active or finishing",
        )

    episode = next(
        (item for item in state.episodes if item.episode_id == command.episode_id),
        None,
    )
    if episode is None:
        raise DomainViolation(ReasonCode.EPISODE_NOT_FOUND, "episode does not exist")
    if state.session.active_episode_id != episode.episode_id:
        raise DomainViolation(
            ReasonCode.EPISODE_TRANSITION_INVALID,
            "only the active episode may transition",
        )
    legal = {
        EpisodeStatus.OPEN: {EpisodeStatus.CLOSING},
        EpisodeStatus.CLOSING: {EpisodeStatus.CLOSED},
        EpisodeStatus.CLOSED: set(),
    }
    if command.target_status not in legal[episode.status]:
        raise DomainViolation(
            ReasonCode.EPISODE_TRANSITION_INVALID,
            f"cannot transition episode from {episode.status} to {command.target_status}",
        )

    if command.target_status == EpisodeStatus.CLOSED:
        unresolved = {
            GapStatus.OPEN,
            GapStatus.ASKED,
        }
        episode_gaps = {
            item.status for item in state.gaps if item.episode_id == episode.episode_id
        }
        if episode_gaps & unresolved:
            raise DomainViolation(
                ReasonCode.EPISODE_HAS_UNRESOLVED_GAPS,
                "episode cannot close with open or unanswered gaps",
            )
        close_turn = next(
            (item for item in state.turns if item.turn_id == command.closed_turn_id),
            None,
        )
        if close_turn is None:
            raise DomainViolation(
                ReasonCode.EPISODE_OPEN_TURN_INVALID,
                "closed_turn_id does not exist",
            )

    updated = _replace(
        episode,
        status=command.target_status,
        closed_turn_id=command.closed_turn_id,
        updated_at=command.occurred_at,
    )
    episodes = tuple(
        updated if item.episode_id == episode.episode_id else item
        for item in state.episodes
    )
    session_changes = (
        {"active_episode_id": None}
        if command.target_status == EpisodeStatus.CLOSED
        else None
    )
    next_state, next_version = _commit_state(
        state,
        command,
        session_changes=session_changes,
        episodes=episodes,
    )
    event = EpisodeTransitionedEvent(
        event_id=_event_id(command.command_id, "episode.transitioned", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        episode_id=episode.episode_id,
        previous_status=episode.status,
        target_status=command.target_status,
        closed_turn_id=command.closed_turn_id,
    )
    return _result(next_state, (event,))


def apply_gap_proposals(
    state: InterviewState,
    command: ApplyGapProposalsCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status != SessionStatus.ACTIVE:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "gap proposals may only be applied in an active session",
        )

    episode = next(
        (item for item in state.episodes if item.episode_id == command.episode_id),
        None,
    )
    if episode is None:
        raise DomainViolation(ReasonCode.EPISODE_NOT_FOUND, "episode does not exist")
    if (
        state.session.active_episode_id != episode.episode_id
        or episode.status != EpisodeStatus.OPEN
    ):
        raise DomainViolation(
            ReasonCode.GAP_PROPOSAL_INVALID,
            "gaps may only be proposed for the open active episode",
        )

    existing_ids = {item.gap_id for item in state.gaps}
    batch_ids = [item.gap_id for item in command.gaps]
    if len(batch_ids) != len(set(batch_ids)) or set(batch_ids) & existing_ids:
        raise DomainViolation(ReasonCode.GAP_ID_DUPLICATE, "gap_id is duplicated")
    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    for gap in command.gaps:
        if (
            gap.session_id != state.session.session_id
            or gap.episode_id != episode.episode_id
            or gap.status != GapStatus.OPEN
            or gap.asked_turn_ids
            or gap.resolution_turn_id is not None
            or gap.resolution_evidence_ids
            or gap.unresolved_reason is not None
        ):
            raise DomainViolation(
                ReasonCode.GAP_PROPOSAL_INVALID,
                "new gap proposal has invalid identity or lifecycle fields",
            )
        for evidence_id in gap.supporting_evidence_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None or evidence.status != EvidenceStatus.ACTIVE:
                raise DomainViolation(
                    ReasonCode.GAP_PROPOSAL_INVALID,
                    "gap supporting evidence must exist and be active",
                    details={"evidence_id": str(evidence_id)},
                )

    updated_episode = _replace(
        episode,
        gap_ids=episode.gap_ids + tuple(batch_ids),
        updated_at=command.occurred_at,
    )
    episodes = tuple(
        updated_episode if item.episode_id == episode.episode_id else item
        for item in state.episodes
    )
    next_state, next_version = _commit_state(
        state,
        command,
        episodes=episodes,
        gaps=state.gaps + command.gaps,
    )
    events = tuple(
        GapProposedEvent(
            event_id=_event_id(command.command_id, "gap.proposed", ordinal),
            session_id=state.session.session_id,
            command_id=command.command_id,
            ordinal=ordinal,
            state_version=next_version,
            occurred_at=command.occurred_at,
            gap_id=gap.gap_id,
            episode_id=episode.episode_id,
        )
        for ordinal, gap in enumerate(command.gaps)
    )
    return _result(next_state, events)


def transition_gap(
    state: InterviewState,
    command: TransitionGapCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "gap may only transition while active or finishing",
        )

    gap = next((item for item in state.gaps if item.gap_id == command.gap_id), None)
    if gap is None:
        raise DomainViolation(ReasonCode.GAP_NOT_FOUND, "gap does not exist")
    episode = next(
        (item for item in state.episodes if item.episode_id == gap.episode_id),
        None,
    )
    if episode is None or episode.status == EpisodeStatus.CLOSED:
        raise DomainViolation(
            ReasonCode.GAP_TRANSITION_INVALID,
            "gap cannot transition after its episode is closed",
        )

    legal = {
        GapStatus.OPEN: {
            GapStatus.ASKED,
            GapStatus.NOT_APPLICABLE,
            GapStatus.DEFERRED,
        },
        GapStatus.ASKED: {
            GapStatus.ANSWERED,
            GapStatus.DECLINED,
            GapStatus.NOT_APPLICABLE,
            GapStatus.DEFERRED,
        },
        GapStatus.ANSWERED: set(),
        GapStatus.DECLINED: set(),
        GapStatus.NOT_APPLICABLE: set(),
        GapStatus.DEFERRED: {GapStatus.ASKED},
    }
    if command.target_status not in legal[gap.status]:
        raise DomainViolation(
            ReasonCode.GAP_TRANSITION_INVALID,
            f"cannot transition gap from {gap.status} to {command.target_status}",
        )
    if command.target_status == GapStatus.ASKED:
        if episode.status != EpisodeStatus.OPEN:
            raise DomainViolation(
                ReasonCode.GAP_TRANSITION_INVALID,
                "closing episode cannot ask a new gap question",
            )
        if gap.priority_features.sensitivity == Sensitivity.PROHIBITED:
            raise DomainViolation(
                ReasonCode.GAP_TRANSITION_INVALID,
                "prohibited gap may not be asked",
            )

    source_turn = None
    if command.source_turn_id is not None:
        source_turn = next(
            (item for item in state.turns if item.turn_id == command.source_turn_id),
            None,
        )
        if source_turn is None:
            raise DomainViolation(ReasonCode.GAP_TURN_INVALID, "gap source turn does not exist")
        opened_sequence = next(
            item.sequence for item in state.turns if item.turn_id == episode.opened_turn_id
        )
        if source_turn.sequence < opened_sequence:
            raise DomainViolation(
                ReasonCode.GAP_TURN_INVALID,
                "gap source turn precedes episode opening",
            )

    if command.target_status == GapStatus.ASKED:
        if source_turn is None or source_turn.role != TranscriptRole.CONSULTANT:
            raise DomainViolation(
                ReasonCode.GAP_TURN_INVALID,
                "asked gap requires a consultant turn",
            )
        changes: dict[str, Any] = {
            "status": GapStatus.ASKED,
            "asked_turn_ids": gap.asked_turn_ids + (source_turn.turn_id,),
            "resolution_turn_id": None,
            "resolution_evidence_ids": (),
            "unresolved_reason": None,
        }
    else:
        if source_turn is not None and source_turn.role != TranscriptRole.EMPLOYEE:
            raise DomainViolation(
                ReasonCode.GAP_TURN_INVALID,
                "gap resolution source must be employee-authored",
            )
        if command.target_status in {GapStatus.ANSWERED, GapStatus.NOT_APPLICABLE}:
            evidence_by_id = {item.evidence_id: item for item in state.evidence}
            for evidence_id in command.resolution_evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if (
                    evidence is None
                    or evidence.status != EvidenceStatus.ACTIVE
                    or evidence.turn_id != command.source_turn_id
                ):
                    raise DomainViolation(
                        ReasonCode.GAP_TRANSITION_INVALID,
                        "gap resolution evidence must be active and from the source turn",
                        details={"evidence_id": str(evidence_id)},
                    )
        changes = {
            "status": command.target_status,
            "resolution_turn_id": command.source_turn_id,
            "resolution_evidence_ids": command.resolution_evidence_ids,
            "unresolved_reason": command.unresolved_reason,
        }

    updated = _replace(gap, **changes)
    gaps = tuple(updated if item.gap_id == gap.gap_id else item for item in state.gaps)
    next_state, next_version = _commit_state(state, command, gaps=gaps)
    event = GapTransitionedEvent(
        event_id=_event_id(command.command_id, "gap.transitioned", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        gap_id=gap.gap_id,
        previous_status=gap.status,
        target_status=command.target_status,
        source_turn_id=command.source_turn_id,
    )
    return _result(next_state, (event,))


def apply_inference_proposals(
    state: InterviewState,
    command: ApplyInferenceProposalsCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "inference proposals may only be applied while active or finishing",
        )

    batch_ids = [item.inference_id for item in command.inferences]
    if len(batch_ids) != len(set(batch_ids)):
        raise DomainViolation(
            ReasonCode.INFERENCE_ID_DUPLICATE,
            "inference_id is duplicated in proposal batch",
        )
    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    existing_by_id = {item.inference_id: item for item in state.inferences}
    for item in command.inferences:
        if (
            item.session_id != state.session.session_id
            or item.status not in {InferenceStatus.CANDIDATE, InferenceStatus.INSUFFICIENT}
            or item.method == InferenceMethod.HUMAN
            or item.decision_evidence_id is not None
        ):
            raise DomainViolation(
                ReasonCode.INFERENCE_PROPOSAL_INVALID,
                "inference proposal crosses identity, status, or authority boundary",
            )
        linked_ids = set(item.supporting_evidence_ids) | set(
            item.contradicting_evidence_ids
        )
        for evidence_id in linked_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                raise DomainViolation(
                    ReasonCode.INFERENCE_EVIDENCE_NOT_FOUND,
                    "inference evidence does not exist",
                    details={"evidence_id": str(evidence_id)},
                )
            if evidence.status != EvidenceStatus.ACTIVE:
                raise DomainViolation(
                    ReasonCode.INFERENCE_PROPOSAL_INVALID,
                    "new inference may only link active evidence",
                    details={"evidence_id": str(evidence_id)},
                )
        existing = existing_by_id.get(item.inference_id)
        if existing is not None and existing.status in {
            InferenceStatus.CONFIRMED_BY_EMPLOYEE,
            InferenceStatus.REJECTED,
        }:
            raise DomainViolation(
                ReasonCode.HUMAN_DECISION_PROTECTED,
                "model proposal cannot replace employee-decided inference",
            )
        if existing is not None and existing.status == InferenceStatus.SUPERSEDED:
            raise DomainViolation(
                ReasonCode.INFERENCE_PROPOSAL_INVALID,
                "superseded inference ID cannot be reused",
            )
        if existing is not None and existing.supersedes != item.supersedes:
            raise DomainViolation(
                ReasonCode.INFERENCE_PROPOSAL_INVALID,
                "inference revision must preserve established lineage",
            )

    inferences = list(state.inferences)
    index_by_id = {item.inference_id: index for index, item in enumerate(inferences)}
    previous_statuses: list[InferenceStatus | None] = []
    for proposal in command.inferences:
        index = index_by_id.get(proposal.inference_id)
        if index is None:
            previous_statuses.append(None)
            index_by_id[proposal.inference_id] = len(inferences)
            inferences.append(proposal)
        else:
            previous_statuses.append(inferences[index].status)
            inferences[index] = proposal

    next_state, next_version = _commit_state(
        state,
        command,
        inferences=tuple(inferences),
    )
    events = tuple(
        InferenceAppliedEvent(
            event_id=_event_id(command.command_id, "inference.applied", ordinal),
            session_id=state.session.session_id,
            command_id=command.command_id,
            ordinal=ordinal,
            state_version=next_version,
            occurred_at=command.occurred_at,
            inference_id=item.inference_id,
            previous_status=previous_statuses[ordinal],
            target_status=item.status,
        )
        for ordinal, item in enumerate(command.inferences)
    )
    return _result(next_state, events)


def decide_inference(
    state: InterviewState,
    command: DecideInferenceCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "inference may only be decided while active or finishing",
        )

    inference = next(
        (item for item in state.inferences if item.inference_id == command.inference_id),
        None,
    )
    if inference is None:
        raise DomainViolation(ReasonCode.INFERENCE_NOT_FOUND, "inference does not exist")
    if inference.status not in {InferenceStatus.CANDIDATE, InferenceStatus.INSUFFICIENT}:
        raise DomainViolation(
            ReasonCode.INFERENCE_DECISION_INVALID,
            "only undecided inference may receive an employee decision",
        )

    evidence = next(
        (
            item
            for item in state.evidence
            if item.evidence_id == command.decision_evidence_id
        ),
        None,
    )
    if evidence is None or evidence.status != EvidenceStatus.ACTIVE:
        raise DomainViolation(
            ReasonCode.INFERENCE_DECISION_INVALID,
            "decision evidence must exist and be active",
        )
    source_turn = next(
        (item for item in state.turns if item.turn_id == evidence.turn_id),
        None,
    )
    if source_turn is None or source_turn.role != TranscriptRole.EMPLOYEE:
        raise DomainViolation(
            ReasonCode.INFERENCE_DECISION_INVALID,
            "decision evidence must come from an employee turn",
        )

    supporting = inference.supporting_evidence_ids
    contradicting = inference.contradicting_evidence_ids
    if command.target_status == InferenceStatus.CONFIRMED_BY_EMPLOYEE:
        if evidence.evidence_id in contradicting:
            raise DomainViolation(
                ReasonCode.INFERENCE_DECISION_INVALID,
                "confirmation evidence is already classified as contradicting",
            )
        if evidence.evidence_id not in supporting:
            supporting = supporting + (evidence.evidence_id,)
    else:
        if evidence.evidence_id in supporting:
            raise DomainViolation(
                ReasonCode.INFERENCE_DECISION_INVALID,
                "rejection evidence must be distinct from supporting evidence",
            )
        if evidence.evidence_id not in contradicting:
            contradicting = contradicting + (evidence.evidence_id,)

    decided = _replace(
        inference,
        status=command.target_status,
        supporting_evidence_ids=supporting,
        contradicting_evidence_ids=contradicting,
        decision_evidence_id=evidence.evidence_id,
        uncertainty_reason=None,
    )
    inferences = tuple(
        decided if item.inference_id == inference.inference_id else item
        for item in state.inferences
    )

    candidates = list(state.candidates)
    candidate_transitions: list[tuple[UUID, CandidateStatus, CandidateStatus]] = []
    if command.target_status == InferenceStatus.REJECTED:
        for index, item in enumerate(candidates):
            if (
                inference.inference_id in item.inference_ids
                and item.status in {CandidateStatus.VERIFIED, CandidateStatus.PROJECTED}
            ):
                candidate_transitions.append(
                    (item.candidate_id, item.status, CandidateStatus.CONFLICTED)
                )
                candidates[index] = _replace(item, status=CandidateStatus.CONFLICTED)

    next_state, next_version = _commit_state(
        state,
        command,
        inferences=inferences,
        candidates=tuple(candidates),
    )
    events: list[DomainEvent] = [
        InferenceTransitionedEvent(
            event_id=_event_id(command.command_id, "inference.transitioned", 0),
            session_id=state.session.session_id,
            command_id=command.command_id,
            ordinal=0,
            state_version=next_version,
            occurred_at=command.occurred_at,
            inference_id=inference.inference_id,
            previous_status=inference.status,
            target_status=command.target_status,
            cause="employee_decision",
            decision_evidence_id=evidence.evidence_id,
        )
    ]
    for ordinal, (candidate_id, previous, target_status) in enumerate(
        candidate_transitions,
        start=1,
    ):
        events.append(
            CandidateTransitionedEvent(
                event_id=_event_id(command.command_id, "candidate.transitioned", ordinal),
                session_id=state.session.session_id,
                command_id=command.command_id,
                ordinal=ordinal,
                state_version=next_version,
                occurred_at=command.occurred_at,
                candidate_id=candidate_id,
                previous_status=previous,
                target_status=target_status,
                cause="inference_rejected",
            )
        )
    return _result(next_state, tuple(events))


def supersede_inference(
    state: InterviewState,
    command: SupersedeInferenceCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "inference may only be superseded while active or finishing",
        )

    previous = next(
        (item for item in state.inferences if item.inference_id == command.inference_id),
        None,
    )
    if previous is None:
        raise DomainViolation(ReasonCode.INFERENCE_NOT_FOUND, "inference does not exist")
    if previous.status not in {InferenceStatus.CANDIDATE, InferenceStatus.INSUFFICIENT}:
        raise DomainViolation(
            ReasonCode.HUMAN_DECISION_PROTECTED,
            "only model-owned undecided inference may be superseded",
        )

    replacement = command.replacement
    if any(item.inference_id == replacement.inference_id for item in state.inferences):
        raise DomainViolation(
            ReasonCode.INFERENCE_ID_DUPLICATE,
            "replacement inference_id already exists",
        )
    if (
        replacement.session_id != state.session.session_id
        or replacement.status
        not in {InferenceStatus.CANDIDATE, InferenceStatus.INSUFFICIENT}
        or replacement.method == InferenceMethod.HUMAN
        or replacement.decision_evidence_id is not None
        or replacement.superseded_by is not None
        or replacement.supersedes != (previous.inference_id,)
    ):
        raise DomainViolation(
            ReasonCode.INFERENCE_PROPOSAL_INVALID,
            "replacement inference has invalid identity, authority, or lineage",
        )
    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    for evidence_id in set(replacement.supporting_evidence_ids) | set(
        replacement.contradicting_evidence_ids
    ):
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None or evidence.status != EvidenceStatus.ACTIVE:
            raise DomainViolation(
                ReasonCode.INFERENCE_PROPOSAL_INVALID,
                "replacement inference may only link active evidence",
                details={"evidence_id": str(evidence_id)},
            )

    superseded = _replace(
        previous,
        status=InferenceStatus.SUPERSEDED,
        superseded_by=replacement.inference_id,
        uncertainty_reason=None,
    )
    inferences = tuple(
        superseded if item.inference_id == previous.inference_id else item
        for item in state.inferences
    ) + (replacement,)

    candidates = list(state.candidates)
    candidate_transitions: list[tuple[UUID, CandidateStatus, CandidateStatus]] = []
    for index, item in enumerate(candidates):
        if (
            previous.inference_id in item.inference_ids
            and item.status in {CandidateStatus.VERIFIED, CandidateStatus.PROJECTED}
        ):
            candidate_transitions.append(
                (item.candidate_id, item.status, CandidateStatus.CONFLICTED)
            )
            candidates[index] = _replace(item, status=CandidateStatus.CONFLICTED)

    next_state, next_version = _commit_state(
        state,
        command,
        inferences=inferences,
        candidates=tuple(candidates),
    )
    events: list[DomainEvent] = [
        InferenceSupersededEvent(
            event_id=_event_id(command.command_id, "inference.superseded", 0),
            session_id=state.session.session_id,
            command_id=command.command_id,
            ordinal=0,
            state_version=next_version,
            occurred_at=command.occurred_at,
            previous_inference_id=previous.inference_id,
            replacement_inference_id=replacement.inference_id,
        )
    ]
    for ordinal, (candidate_id, previous_status, target_status) in enumerate(
        candidate_transitions,
        start=1,
    ):
        events.append(
            CandidateTransitionedEvent(
                event_id=_event_id(command.command_id, "candidate.transitioned", ordinal),
                session_id=state.session.session_id,
                command_id=command.command_id,
                ordinal=ordinal,
                state_version=next_version,
                occurred_at=command.occurred_at,
                candidate_id=candidate_id,
                previous_status=previous_status,
                target_status=target_status,
                cause="inference_superseded",
            )
        )
    return _result(next_state, tuple(events))


def apply_candidate_proposals(
    state: InterviewState,
    command: ApplyCandidateProposalsCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "candidate proposals may only be applied while active or finishing",
        )

    batch_ids = [item.candidate_id for item in command.candidates]
    if len(batch_ids) != len(set(batch_ids)):
        raise DomainViolation(
            ReasonCode.CANDIDATE_ID_DUPLICATE,
            "candidate_id is duplicated in proposal batch",
        )
    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    inference_by_id = {item.inference_id: item for item in state.inferences}
    existing_by_id = {item.candidate_id: item for item in state.candidates}
    allowed_statuses = {
        CandidateStatus.DRAFT,
        CandidateStatus.INSUFFICIENT,
        CandidateStatus.CONFLICTED,
    }
    for item in command.candidates:
        if (
            item.session_id != state.session.session_id
            or item.status not in allowed_statuses
            or item.review_decision_id is not None
        ):
            raise DomainViolation(
                ReasonCode.CANDIDATE_PROPOSAL_INVALID,
                "candidate proposal crosses identity, status, or review boundary",
            )
        assert_candidate_lineage(item, evidence_by_id)
        for inference_id in item.inference_ids:
            if inference_id not in inference_by_id:
                raise DomainViolation(
                    ReasonCode.CANDIDATE_INFERENCE_NOT_FOUND,
                    "candidate inference does not exist",
                    details={"inference_id": str(inference_id)},
                )
        has_rejected_inference = any(
            inference_by_id[inference_id].status == InferenceStatus.REJECTED
            for inference_id in item.inference_ids
        )
        if has_rejected_inference and item.status != CandidateStatus.CONFLICTED:
            raise DomainViolation(
                ReasonCode.CANDIDATE_PROPOSAL_INVALID,
                "candidate using a rejected inference must be conflicted",
            )
        existing = existing_by_id.get(item.candidate_id)
        if existing is not None:
            assert_model_may_replace_candidate(existing)

    candidates = list(state.candidates)
    index_by_id = {item.candidate_id: index for index, item in enumerate(candidates)}
    previous_statuses: list[CandidateStatus | None] = []
    for proposal in command.candidates:
        index = index_by_id.get(proposal.candidate_id)
        if index is None:
            previous_statuses.append(None)
            index_by_id[proposal.candidate_id] = len(candidates)
            candidates.append(proposal)
        else:
            previous_statuses.append(candidates[index].status)
            candidates[index] = proposal

    next_state, next_version = _commit_state(
        state,
        command,
        candidates=tuple(candidates),
    )
    events = tuple(
        CandidateAppliedEvent(
            event_id=_event_id(command.command_id, "candidate.applied", ordinal),
            session_id=state.session.session_id,
            command_id=command.command_id,
            ordinal=ordinal,
            state_version=next_version,
            occurred_at=command.occurred_at,
            candidate_id=item.candidate_id,
            previous_status=previous_statuses[ordinal],
            target_status=item.status,
        )
        for ordinal, item in enumerate(command.candidates)
    )
    return _result(next_state, events)


def transition_candidate(
    state: InterviewState,
    command: TransitionCandidateCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.ACTIVE, SessionStatus.FINISHING}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "candidate may only transition while active or finishing",
        )

    candidate = next(
        (item for item in state.candidates if item.candidate_id == command.candidate_id),
        None,
    )
    if candidate is None:
        raise DomainViolation(ReasonCode.CANDIDATE_NOT_FOUND, "candidate does not exist")
    assert_model_may_replace_candidate(candidate)
    if command.target_status in {CandidateStatus.ACCEPTED, CandidateStatus.REJECTED}:
        raise DomainViolation(
            ReasonCode.HUMAN_DECISION_PROTECTED,
            "accepted/rejected status requires ApplyReviewDecisionCommand",
        )

    legal = {
        CandidateStatus.DRAFT: {
            CandidateStatus.VERIFIED,
            CandidateStatus.INSUFFICIENT,
            CandidateStatus.CONFLICTED,
        },
        CandidateStatus.VERIFIED: {
            CandidateStatus.PROJECTED,
            CandidateStatus.DRAFT,
            CandidateStatus.INSUFFICIENT,
            CandidateStatus.CONFLICTED,
        },
        CandidateStatus.INSUFFICIENT: {CandidateStatus.DRAFT},
        CandidateStatus.CONFLICTED: {
            CandidateStatus.DRAFT,
            CandidateStatus.INSUFFICIENT,
        },
        CandidateStatus.PROJECTED: {
            CandidateStatus.DRAFT,
            CandidateStatus.INSUFFICIENT,
            CandidateStatus.CONFLICTED,
        },
        CandidateStatus.ACCEPTED: set(),
        CandidateStatus.REJECTED: set(),
    }
    if command.target_status not in legal[candidate.status]:
        raise DomainViolation(
            ReasonCode.CANDIDATE_TRANSITION_INVALID,
            f"cannot transition candidate from {candidate.status} to {command.target_status}",
        )

    inference_by_id = {item.inference_id: item for item in state.inferences}
    if command.target_status in {CandidateStatus.VERIFIED, CandidateStatus.PROJECTED}:
        if any(
            inference_by_id[inference_id].status
            in {InferenceStatus.REJECTED, InferenceStatus.INSUFFICIENT}
            for inference_id in candidate.inference_ids
        ):
            raise DomainViolation(
                ReasonCode.CANDIDATE_TRANSITION_INVALID,
                "candidate cannot verify/project with rejected or insufficient inference",
            )
        candidate_for_validation = _replace(candidate, status=command.target_status)
        assert_candidate_projectable(
            candidate_for_validation,
            {item.evidence_id: item for item in state.evidence},
        )
    else:
        candidate_for_validation = _replace(candidate, status=command.target_status)

    candidates = tuple(
        candidate_for_validation if item.candidate_id == candidate.candidate_id else item
        for item in state.candidates
    )
    next_state, next_version = _commit_state(
        state,
        command,
        candidates=candidates,
    )
    event = CandidateTransitionedEvent(
        event_id=_event_id(command.command_id, "candidate.transitioned", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        candidate_id=candidate.candidate_id,
        previous_status=candidate.status,
        target_status=command.target_status,
        cause="verifier",
    )
    return _result(next_state, (event,))


def apply_review_decision(
    state: InterviewState,
    command: ApplyReviewDecisionCommand,
) -> ReductionResult:
    duplicate = _preflight(state, command, allow_terminal=True)
    if duplicate is not None:
        return duplicate
    if state.session.status not in {SessionStatus.FINISHING, SessionStatus.COMPLETED}:
        raise DomainViolation(
            ReasonCode.INVALID_SESSION_TRANSITION,
            "human review is only accepted while finishing or after completion",
        )

    decision = command.decision
    if decision.session_id != state.session.session_id:
        raise DomainViolation(
            ReasonCode.REVIEW_DECISION_INVALID,
            "review belongs to another session",
        )
    if any(item.review_id == decision.review_id for item in state.reviews):
        raise DomainViolation(ReasonCode.REVIEW_ID_DUPLICATE, "review_id already exists")
    if (
        decision.decided_at < state.session.created_at
        or decision.decided_at > command.occurred_at
    ):
        raise DomainViolation(
            ReasonCode.REVIEW_DECISION_INVALID,
            "review decided_at is outside the session/command timeline",
        )

    candidate = next(
        (item for item in state.candidates if item.candidate_id == decision.candidate_id),
        None,
    )
    if candidate is None:
        raise DomainViolation(ReasonCode.CANDIDATE_NOT_FOUND, "review candidate does not exist")
    if candidate.status != CandidateStatus.PROJECTED or candidate.review_decision_id is not None:
        raise DomainViolation(
            ReasonCode.REVIEW_CANDIDATE_NOT_REVIEWABLE,
            "only an unreviewed projected candidate may receive a decision",
        )

    target_status = (
        CandidateStatus.REJECTED
        if decision.action == ReviewAction.REJECT
        else CandidateStatus.ACCEPTED
    )
    statement = (
        decision.edited_statement
        if decision.action == ReviewAction.EDIT
        else candidate.statement
    )
    thresholds = (
        decision.edited_thresholds
        if decision.action == ReviewAction.EDIT and decision.edited_thresholds
        else candidate.thresholds
    )
    reviewed_candidate = _replace(
        candidate,
        statement=statement,
        thresholds=thresholds,
        status=target_status,
        review_decision_id=decision.review_id,
    )
    if decision.action != ReviewAction.REJECT:
        assert_candidate_projectable(
            reviewed_candidate,
            {item.evidence_id: item for item in state.evidence},
        )
    candidates = tuple(
        reviewed_candidate if item.candidate_id == candidate.candidate_id else item
        for item in state.candidates
    )
    next_state, next_version = _commit_state(
        state,
        command,
        candidates=candidates,
        reviews=state.reviews + (decision,),
    )
    event = ReviewDecisionAppliedEvent(
        event_id=_event_id(command.command_id, "review.applied", 0),
        session_id=state.session.session_id,
        command_id=command.command_id,
        ordinal=0,
        state_version=next_version,
        occurred_at=command.occurred_at,
        review_id=decision.review_id,
        candidate_id=candidate.candidate_id,
        action=decision.action,
    )
    return _result(next_state, (event,))
