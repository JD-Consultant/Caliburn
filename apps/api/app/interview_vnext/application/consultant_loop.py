"""Minimal application-owned control loop after one interpreted employee turn.

Only deterministic workflow decisions live here. The model selects the next
question inside ``question.select``; it never decides session or episode state
transitions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid5

from app.interview_vnext.domain.commands import (
    CommandBase,
    TransitionEpisodeCommand,
    TransitionGapCommand,
    TransitionSessionCommand,
)
from app.interview_vnext.domain.episode import EpisodeStatus, GapStatus
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.session import SessionStatus
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.port import LlmPort
from app.job_authoring.contracts import JobStateDigest

from .durable_commands import apply_durable_command
from .persistence import VNextUnitOfWork
from .question_select_executor import (
    QuestionSelectExecutionOutcome,
    execute_question_select,
)


CONTROL_STAGE = "consultant.loop_control"
EXPLICIT_SHIFT_REASON = "employee explicitly shifted to another work topic"


class LoopDisposition(StrEnum):
    ASK_NEXT = "ask_next"
    FINISHING = "finishing"


@dataclass(frozen=True)
class LoopControlPlan:
    disposition: LoopDisposition
    commands: tuple[CommandBase, ...]


@dataclass(frozen=True)
class ConsultantLoopOutcome:
    disposition: LoopDisposition
    state: InterviewState
    question: QuestionSelectExecutionOutcome | None = None


def _command_id(operation_id: UUID, label: str) -> UUID:
    return uuid5(operation_id, f"consultant-loop/{label}")


def _require_latest_receipt(
    state: InterviewState,
    receipt: TurnInterpretationRecord,
) -> None:
    if not state.turn_interpretations:
        raise ValueError("interview state has no interpretation receipt")
    if state.turn_interpretations[-1] != receipt:
        raise ValueError("loop control requires the latest interpretation receipt")


def plan_loop_control(
    state: InterviewState,
    latest_receipt: TurnInterpretationRecord,
    *,
    operation_id: UUID,
    occurred_at: datetime,
) -> LoopControlPlan:
    """Plan only certain control transitions; ambiguous signals do nothing."""

    state = InterviewState.model_validate(state.model_dump())
    latest_receipt = TurnInterpretationRecord.model_validate(
        latest_receipt.model_dump()
    )
    _require_latest_receipt(state, latest_receipt)
    version = state.session.state_version
    commands: list[CommandBase] = []

    if latest_receipt.dialogue_act == DialogueAct.STOP:
        if state.session.status in {SessionStatus.ACTIVE, SessionStatus.PAUSED}:
            commands.append(
                TransitionSessionCommand(
                    command_id=_command_id(operation_id, "finish-session"),
                    expected_state_version=version,
                    occurred_at=occurred_at,
                    target_status=SessionStatus.FINISHING,
                )
            )
        elif state.session.status != SessionStatus.FINISHING:
            raise ValueError("stop receipt cannot control a terminal/planned session")
        return LoopControlPlan(
            disposition=LoopDisposition.FINISHING,
            commands=tuple(commands),
        )

    if latest_receipt.episode_signal != EpisodeSignal.EXPLICIT_SHIFT:
        return LoopControlPlan(
            disposition=LoopDisposition.ASK_NEXT,
            commands=(),
        )

    active_id = state.session.active_episode_id
    if active_id is None:
        return LoopControlPlan(
            disposition=LoopDisposition.ASK_NEXT,
            commands=(),
        )
    episode = next(
        item for item in state.episodes if item.episode_id == active_id
    )
    for gap in state.gaps:
        if (
            gap.episode_id == active_id
            and gap.status in {GapStatus.OPEN, GapStatus.ASKED}
        ):
            commands.append(
                TransitionGapCommand(
                    command_id=_command_id(
                        operation_id, f"defer-gap/{gap.gap_id}"
                    ),
                    expected_state_version=version,
                    occurred_at=occurred_at,
                    gap_id=gap.gap_id,
                    target_status=GapStatus.DEFERRED,
                    unresolved_reason=EXPLICIT_SHIFT_REASON,
                )
            )
            version += 1

    if episode.status == EpisodeStatus.OPEN:
        commands.append(
            TransitionEpisodeCommand(
                command_id=_command_id(operation_id, "close-episode/closing"),
                expected_state_version=version,
                occurred_at=occurred_at,
                episode_id=active_id,
                target_status=EpisodeStatus.CLOSING,
            )
        )
        version += 1
    if episode.status in {EpisodeStatus.OPEN, EpisodeStatus.CLOSING}:
        commands.append(
            TransitionEpisodeCommand(
                command_id=_command_id(operation_id, "close-episode/closed"),
                expected_state_version=version,
                occurred_at=occurred_at,
                episode_id=active_id,
                target_status=EpisodeStatus.CLOSED,
                closed_turn_id=latest_receipt.employee_turn_id,
            )
        )

    return LoopControlPlan(
        disposition=LoopDisposition.ASK_NEXT,
        commands=tuple(commands),
    )


async def _apply_control_plan(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    session_id: UUID,
    run_id: UUID,
    operation_id: UUID,
    plan: LoopControlPlan,
    initial_state: InterviewState,
) -> InterviewState:
    state = initial_state
    for ordinal, command in enumerate(plan.commands, start=1):
        outcome = await apply_durable_command(
            uow_factory,
            tenant_id=tenant_id,
            session_id=session_id,
            run_id=run_id,
            command=command,
            stage=CONTROL_STAGE,
            event_id=uuid5(
                operation_id, f"consultant-loop/event/{ordinal}"
            ),
            command_artifact_id=uuid5(
                operation_id, f"consultant-loop/command/{ordinal}"
            ),
            reduction_artifact_id=uuid5(
                operation_id, f"consultant-loop/reduction/{ordinal}"
            ),
            committed_at=command.occurred_at,
            request_idempotency_key=(
                f"consultant-loop:{operation_id}:{ordinal}"
            ),
        )
        state = outcome.result.state
    return state


async def continue_after_interpretation(
    uow_factory: Callable[[], VNextUnitOfWork],
    *,
    tenant_id: UUID,
    session_id: UUID,
    run_id: UUID,
    latest_receipt: TurnInterpretationRecord,
    control_operation_id: UUID,
    question_operation_id: UUID,
    job_digest: JobStateDigest,
    llm: LlmPort,
    question_binding: ProviderBinding,
    provider_config: object,
    occurred_at: datetime,
    contains_test_data: bool = False,
) -> ConsultantLoopOutcome:
    """Apply control, then ask exactly one verified next question when allowed."""

    async with uow_factory() as uow:
        state = await uow.sessions.get(
            tenant_id=tenant_id,
            session_id=session_id,
        )
    plan = plan_loop_control(
        state,
        latest_receipt,
        operation_id=control_operation_id,
        occurred_at=occurred_at,
    )
    state = await _apply_control_plan(
        uow_factory,
        tenant_id=tenant_id,
        session_id=session_id,
        run_id=run_id,
        operation_id=control_operation_id,
        plan=plan,
        initial_state=state,
    )
    if plan.disposition == LoopDisposition.FINISHING:
        return ConsultantLoopOutcome(
            disposition=plan.disposition,
            state=state,
        )

    question = await execute_question_select(
        uow_factory,
        tenant_id=tenant_id,
        run_id=run_id,
        session_id=session_id,
        operation_id=question_operation_id,
        idempotency_key=f"question-select:{question_operation_id}",
        job_digest=job_digest,
        llm=llm,
        binding=question_binding,
        provider_config=provider_config,
        started_at=occurred_at,
        now=occurred_at,
        contains_test_data=contains_test_data,
    )
    async with uow_factory() as uow:
        state = await uow.sessions.get(
            tenant_id=tenant_id,
            session_id=session_id,
        )
    return ConsultantLoopOutcome(
        disposition=LoopDisposition.ASK_NEXT,
        state=state,
        question=question,
    )
