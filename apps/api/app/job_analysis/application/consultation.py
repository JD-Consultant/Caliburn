"""One synchronous, durable consultant turn with provider-before-replay.

一次 `/turns` 最多跑**主顧問 ＋ 一個 OPKS specialist**(ADR 0054 決定 34):員工只
看到一個「分析中」。哪個 Task 值得分析由 `commit_verified_turn()` 在同一筆交易內
凍結,這裡只負責執行它。
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.job_analysis.providers import OpenRouterAdapter

from .context import ConversationTurn
from .durable_turn import StaleAuthoritySnapshot, commit_verified_turn, prepare_turn
from .errors import IdempotencyConflict, JobAnalysisApplicationError
from .operation import run_task_analysis_operation
from .opks_digest import ScheduledOpks, scheduled_opks_operation_id
from .opks_generation import generate_opks_proposals
from .persistence import (
    CompletedTurnPayload,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
)
from .verifier import TurnSpeaker


logger = logging.getLogger(__name__)


def _employee_turn(operation_id: str, text: str) -> ConversationTurn:
    return ConversationTurn(
        turn_id=f"{operation_id}-employee",
        speaker=TurnSpeaker.EMPLOYEE,
        text=text,
    )


def _require_same_employee_replay(
    entry: JournalEntry,
    *,
    operation_id: str,
    employee_turn: ConversationTurn,
) -> None:
    if entry.kind != "employee_turn" or not isinstance(
        entry.payload, CompletedTurnPayload
    ):
        raise IdempotencyConflict(
            f"entry {operation_id!r} already belongs to another operation"
        )
    if (
        entry.payload.operation_id != operation_id
        or entry.payload.employee_turn != employee_turn
    ):
        raise IdempotencyConflict(
            f"operation {operation_id!r} was replayed with different employee text"
        )


async def _committed_replay(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    operation_id: str,
    employee_turn: ConversationTurn,
) -> CompletedTurnPayload | None:
    """已提交過就交回**既凍結**的 payload,而不是只回一個布林。

    replay 必須拿得到 `scheduled_opks`:主回合 commit 之後、child 執行之前崩潰時,
    這是唯一的恢復點(ADR 0054 決定 9)。**沒有 background worker,單純 reload／GET
    不會自行補跑**;恢復只發生在同一個 `/turns` 以相同 Idempotency-Key 重播,
    或後續回合的 scheduler 再次選到同一個 child ID。
    """

    async with uow_factory() as uow:
        existing = await uow.journal.get(document_id, operation_id)
        if existing is None:
            return None
        _require_same_employee_replay(
            existing,
            operation_id=operation_id,
            employee_turn=employee_turn,
        )
        return existing.payload


async def submit_employee_turn(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    adapter: OpenRouterAdapter,
    document_id: UUID,
    operation_id: str,
    text: str,
) -> None:
    """Run at most one provider call for a not-yet-committed sequential request.

    This intentionally does not deduplicate two requests that are already in flight.
    The local Web disables duplicate submission while its mutation is pending.
    """

    employee_turn = _employee_turn(operation_id, text)
    replay = await _committed_replay(
        uow_factory,
        document_id=document_id,
        operation_id=operation_id,
        employee_turn=employee_turn,
    )
    if replay is not None:
        scheduled = replay.scheduled_opks
    else:
        snapshot = await prepare_turn(
            uow_factory,
            document_id=document_id,
            employee_turn=employee_turn,
        )
        operation_result = await run_task_analysis_operation(
            packet=snapshot.packet,
            adapter=adapter,
        )
        committed = await commit_verified_turn(
            uow_factory,
            snapshot=snapshot,
            operation_id=operation_id,
            employee_turn=employee_turn,
            operation_result=operation_result,
        )
        scheduled = committed.scheduled_opks

    if scheduled is not None:
        await _run_scheduled_opks(
            uow_factory,
            adapter=adapter,
            document_id=document_id,
            scheduled=scheduled,
        )


async def _run_scheduled_opks(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    adapter: OpenRouterAdapter,
    document_id: UUID,
    scheduled: ScheduledOpks,
) -> None:
    """執行主回合凍結的那一個 child(ADR 0054 決定 32、34)。

    **OPKS 的失敗不得牽連已提交的 Task Analysis。** 主回合已經寫進資料庫,員工的話
    已經留下;child 這裡出什麼事都不該讓 `/turns` 變成錯誤回應,員工也只看到一個
    「分析中」。四種終端失敗會由 `generate_opks_proposals()` 自己寫下 `failed`
    receipt,不會回到這裡。

    唯一走到 except 的是 `StaleAuthoritySnapshot`:輸入漂移了——可能在 provider 呼叫
    期間,也可能早在 child 開始之前(主回合 commit 之後員工又直接編輯了那個 Task)。
    後者由 `expected_digest` 在 prepare 擋下,所以連 provider 都不會打。兩者都是
    **abandon**——不寫 receipt、不擋下次(決定 10),由更新的那一輪排定自己的 child。
    `generate_opks_proposals()` 內部已先查 receipt,所以 replay 時若 child 早就跑完,
    這裡不會再花錢。
    """

    try:
        await generate_opks_proposals(
            uow_factory,
            adapter=adapter,
            document_id=document_id,
            task_id=scheduled.task_id,
            operation_id=scheduled_opks_operation_id(scheduled),
            expected_digest=scheduled.analysis_input_digest,
        )
    except StaleAuthoritySnapshot:
        logger.info(
            "scheduled OPKS analysis was abandoned because its input drifted: %s",
            scheduled.task_id,
        )
    except JobAnalysisApplicationError:
        logger.warning(
            "scheduled OPKS analysis could not run for task %s",
            scheduled.task_id,
            exc_info=True,
        )
