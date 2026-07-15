"""The only pure functions allowed to transition vNext domain state."""

from __future__ import annotations

from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from .base import DomainModel
from .commands import (
    ApplyEvidenceCommand,
    AppendTranscriptTurnCommand,
    CommandBase,
    TransitionSessionCommand,
)
from .errors import DomainViolation
from .events import (
    DomainEvent,
    EvidenceObservedEvent,
    EvidenceSupersededEvent,
    SessionTransitionedEvent,
    TranscriptTurnAppendedEvent,
)
from .evidence import Evidence, EvidenceStatus
from .hashing import canonical_hash
from .invariants import assert_evidence_matches_turn
from .reason_codes import ReasonCode
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


def _preflight(state: InterviewState, command: CommandBase) -> ReductionResult | None:
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
    if state.session.status in TERMINAL_SESSION_STATUSES:
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
        if item.episode_id is not None and all(
            episode.episode_id != item.episode_id for episode in state.episodes
        ):
            raise DomainViolation(ReasonCode.EPISODE_NOT_FOUND, "evidence episode does not exist")
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
