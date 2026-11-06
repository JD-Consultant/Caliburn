"""單 worker 的輪次受理、執行所有權與有界訂閱；持久證據留在 Core。"""

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence
from contextlib import aclosing, asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from uuid import UUID

from langgraph.errors import GraphDrained
from langgraph.runtime import RunControl
from langgraph.types import Command, Interrupt, StateSnapshot

from caliburn.modules.agent.agent import Agent, has_pending_work, turn_cancel_status
from caliburn.modules.agent.application.errors import (
    AgentUnavailable,
    TurnConflict,
    TurnNotFound,
)
from caliburn.modules.agent.application.events import (
    CancellationData,
    CancellationEvent,
    ResyncRequiredData,
    ResyncRequiredEvent,
    TurnEvent,
    TurnStatusEvent,
    model_event,
)
from caliburn.modules.agent.application.turn_history import (
    TurnExecution,
    applied_snapshot,
    step_views,
    turn_view,
)
from caliburn.modules.agent.application.views import (
    StepView,
    TurnSubmission,
    TurnView,
)
from caliburn.modules.agent.interrupts import (
    ConfirmedInterrupts,
    InterruptResume,
    ResumePoint,
    can_resume_interrupt,
    confirmed_interrupts,
)

logger = logging.getLogger(__name__)


@dataclass
class ActiveTurn:
    turn_id: UUID
    fingerprint: str
    accepted: asyncio.Future[bool]
    task: asyncio.Task[None] | None = None
    subscribers: set[asyncio.Queue[TurnEvent | None]] = field(default_factory=set)
    request_key: str | None = None
    saved_result: Callable[[Sequence[StateSnapshot]], bool] | None = None
    control: RunControl = field(default_factory=RunControl)
    cancel_task: asyncio.Task[TurnConflict | AgentUnavailable | None] | None = None

    def is_saved(self, snapshots: list[StateSnapshot]) -> bool:
        if self.saved_result is not None:
            return self.saved_result(snapshots)
        return any(applied_snapshot(s, self.turn_id) for s in snapshots)


class AgentService:
    """由 lifespan 共用；關閉前收束 invocation，查讀不啟動執行。"""

    def __init__(
        self,
        agent: Agent,
        *,
        ensure_workspace: Callable[[UUID], Awaitable[None]],
        max_active_turns: int = 8,
        on_turn_completed: Callable[[UUID, UUID], None] | None = None,
    ):
        self._agent = agent
        self._ensure_workspace = ensure_workspace
        self._max_active_turns = max_active_turns
        self._on_turn_completed = on_turn_completed
        self._admission = asyncio.Lock()
        self._active: dict[UUID, ActiveTurn] = {}
        self._confirmed_interrupts: dict[UUID, ConfirmedInterrupts] = {}
        self._suspended_workspaces: set[UUID] = set()
        self._closed = False

    async def _require_admission(self, workspace_id: UUID) -> None:
        """准入鎖內核對，避免刪除與先前通過的存在檢查交錯。"""
        if self._closed:
            raise AgentUnavailable("Agent 正在關閉")
        if workspace_id in self._suspended_workspaces:
            raise TurnConflict("Workspace 正在停止工作")
        await self._ensure_workspace(workspace_id)

    @asynccontextmanager
    async def suspend_workspace(self, workspace_id: UUID) -> AsyncIterator[None]:
        """Host 刪除期間封鎖新執行，等待在途 Node 與取消收尾安全結束。"""
        async with self._admission:
            if workspace_id in self._suspended_workspaces:
                raise TurnConflict("Workspace 正在停止工作")
            self._suspended_workspaces.add(workspace_id)
            active = self._active.get(workspace_id)
            tasks = []
            if active is not None:
                active.control.request_drain("workspace_deleted")
                tasks = [
                    task
                    for task in (active.task, active.cancel_task)
                    if task is not None
                ]
        try:
            await asyncio.gather(*tasks)
            yield
            self._confirmed_interrupts.pop(workspace_id, None)
        finally:
            async with self._admission:
                self._suspended_workspaces.discard(workspace_id)

    async def _history(self, workspace_id: UUID, turn_id: UUID) -> list[StateSnapshot]:
        return [
            s
            async for s in self._agent.aget_state_history(
                workspace_id=workspace_id, turn_id=turn_id
            )
        ]

    async def submit_turn(
        self, *, workspace_id: UUID, turn_id: UUID, input: str
    ) -> TurnSubmission:
        fingerprint = sha256(input.encode("utf-8")).hexdigest()
        created = False
        async with self._admission:
            await self._require_admission(workspace_id)
            active = self._active.get(workspace_id)
            if active and active.cancel_task is not None:
                raise TurnConflict("對話正在取消收尾")
            if active and active.turn_id == turn_id:
                if active.fingerprint != fingerprint:
                    raise TurnConflict("同一輪次不得變更輸入")
            else:
                saved = await self._history(workspace_id, turn_id)
                if saved:
                    if turn_cancel_status(saved[0]) is not None:
                        raise TurnConflict("已取消輪次不得重新受理")
                    if (
                        not saved[0].metadata
                        or saved[0].metadata.get("input_fingerprint") != fingerprint
                    ):
                        raise TurnConflict("輪次原輸入不同或無法核對")
                    return TurnSubmission(
                        await self.get_turn(workspace_id=workspace_id, turn_id=turn_id),
                        False,
                    )
                live = await self._agent.aget_state(workspace_id=workspace_id)
                if active or (
                    turn_cancel_status(live) != "completed"
                    and (
                        has_pending_work(live) or turn_cancel_status(live) == "pending"
                    )
                ):
                    raise TurnConflict("對話仍有未完成工作")
                if len(self._active) >= self._max_active_turns:
                    raise AgentUnavailable("活動輪次已達上限")
                active = ActiveTurn(
                    turn_id, fingerprint, asyncio.get_running_loop().create_future()
                )
                self._active[workspace_id] = active
                active.task = asyncio.create_task(
                    self._run(workspace_id, active, input)
                )
                created = True
        if not await asyncio.shield(active.accepted):
            raise AgentUnavailable("無法確認受理保存；請查讀或以同一輪次重送")
        return TurnSubmission(
            await self.get_turn(workspace_id=workspace_id, turn_id=turn_id), created
        )

    async def _run(
        self,
        workspace_id: UUID,
        active: ActiveTurn,
        input: str | None,
        resume_command: Command[Any] | None = None,
        expected: ResumePoint | None = None,
    ) -> None:
        self._confirmed_interrupts.pop(workspace_id, None)
        emitted: tuple[Interrupt, ...] = ()
        completed = False
        try:
            invocation = (
                self._agent.aresume(
                    workspace_id=workspace_id,
                    turn_id=active.turn_id,
                    input_fingerprint=active.fingerprint,
                    include_checkpoints=True,
                    resume_command=resume_command,
                    expected=expected,
                    control=active.control,
                )
                if input is None
                else self._agent.astream(
                    workspace_id=workspace_id,
                    turn_id=active.turn_id,
                    input=input,
                    input_fingerprint=active.fingerprint,
                    include_checkpoints=True,
                    control=active.control,
                )
            )
            async with aclosing(invocation) as stream:
                async for part in stream:
                    if part.get("interrupts"):
                        emitted += deepcopy(tuple(part["interrupts"]))
                    event = model_event(part)
                    if event is not None:
                        self._publish(active, event)
                    if part["type"] == "checkpoints" and not active.accepted.done():
                        data = part["data"]
                        if (
                            data["metadata"].get("source") != "input"
                            and data["values"].get("turn_id") == active.turn_id
                        ):
                            saved = await self._agent.aget_state(
                                workspace_id=workspace_id,
                                checkpoint_id=data["config"]["configurable"][
                                    "checkpoint_id"
                                ],
                            )
                            if (
                                saved.metadata
                                and saved.metadata.get("source") != "input"
                                and saved.metadata.get("turn_id") == str(active.turn_id)
                                and saved.values.get("turn_id") == active.turn_id
                                # 結果與原中斷可能分屬不同保存點；確認沿本輪
                                # 完整歷史，與恢復准入及故障收尾採同一證據。
                                and active.is_saved(
                                    [
                                        saved,
                                        *await self._history(
                                            workspace_id, active.turn_id
                                        ),
                                    ]
                                )
                            ):
                                active.accepted.set_result(True)
            if emitted:
                saved = await self._agent.aget_state(workspace_id=workspace_id)
                if confirmed := confirmed_interrupts(saved, emitted):
                    self._confirmed_interrupts[workspace_id] = confirmed
            if self._on_turn_completed is not None:
                saved = await self._agent.aget_state(workspace_id=workspace_id)
                completed = (
                    turn_view(
                        workspace_id=workspace_id,
                        turn_id=active.turn_id,
                        history=await self._history(workspace_id, active.turn_id),
                        current=saved,
                        running=False,
                        confirmed_waiting=self._is_confirmed_waiting(
                            workspace_id, saved
                        ),
                    ).status
                    == "completed"
                )
        except GraphDrained:
            pass
        except Exception as error:
            try:
                logger.error(
                    "Agent 執行中斷",
                    extra={
                        "event": "agent.turn.failed",
                        "workspace_id": str(workspace_id),
                        "turn_id": str(active.turn_id),
                        "error_type": type(error).__name__,
                    },
                )
            except Exception:
                pass
        finally:
            if not active.accepted.done():
                # 初次確認前可能故障；最後只核保存，不把未知當成未執行。
                try:
                    saved_history = await self._history(workspace_id, active.turn_id)
                    live = await self._agent.aget_state(workspace_id=workspace_id)
                    active.accepted.set_result(active.is_saved([live, *saved_history]))
                except Exception:
                    if not active.accepted.done():
                        active.accepted.set_result(False)
            if active.cancel_task is None:
                if self._active.get(workspace_id) is active:
                    self._active.pop(workspace_id)
                self._publish(active, None)
            if completed and self._on_turn_completed is not None:
                # 同步通知只交給 Host 排程；不在輪次內等待其他業務或網路。
                try:
                    self._on_turn_completed(workspace_id, active.turn_id)
                except Exception as error:
                    logger.error(
                        "輪次完成通知失敗",
                        extra={
                            "event": "agent.turn.completion_notification_failed",
                            "workspace_id": str(workspace_id),
                            "turn_id": str(active.turn_id),
                            "error_type": type(error).__name__,
                        },
                    )

    async def get_turn(self, *, workspace_id: UUID, turn_id: UUID) -> TurnView:
        execution = await self.read_turn_execution(
            workspace_id=workspace_id, turn_id=turn_id
        )
        active = self._active.get(workspace_id)
        return turn_view(
            workspace_id=workspace_id,
            turn_id=turn_id,
            history=execution.history,
            current=execution.current,
            running=active is not None and active.turn_id == turn_id,
            confirmed_waiting=execution.confirmed_interrupts is not None,
        )

    async def cancel_turn(self, *, workspace_id: UUID, turn_id: UUID) -> None:
        """等待安全停止及插件撤回；重送共用工作，失敗可沿同入口收尾。"""
        async with self._admission:
            await self._require_admission(workspace_id)
            history = await self._history(workspace_id, turn_id)
            active = self._active.get(workspace_id)
            if history and turn_cancel_status(history[0]) == "completed":
                return
            if active is not None and active.turn_id != turn_id:
                raise TurnConflict("只能取消目前輪次")
            if not history and active is None:
                raise TurnNotFound("查無輪次")
            if active is None:
                live = await self._agent.aget_state(workspace_id=workspace_id)
                if not live.metadata or live.metadata.get("turn_id") != str(turn_id):
                    raise TurnConflict("只能取消目前輪次")
                if turn_cancel_status(live) is None and not has_pending_work(live):
                    raise TurnConflict("正常完成輪次不能取消")
                if len(self._active) >= self._max_active_turns:
                    raise AgentUnavailable("活動輪次已達上限")
                active = ActiveTurn(
                    turn_id, "", asyncio.get_running_loop().create_future()
                )
                active.accepted.set_result(False)
                self._active[workspace_id] = active
            if active.cancel_task is None:
                active.control.request_drain("turn_cancelled")
                active.cancel_task = asyncio.create_task(
                    self._cancel(workspace_id, active)
                )
            cancellation = active.cancel_task
        error = await asyncio.shield(cancellation)
        if error is not None:
            raise error

    async def _cancel(
        self, workspace_id: UUID, active: ActiveTurn
    ) -> TurnConflict | AgentUnavailable | None:
        try:
            if active.task is not None:
                await active.task
            live = await self._agent.aget_state(workspace_id=workspace_id)
            if not live.metadata or live.metadata.get("turn_id") != str(active.turn_id):
                raise TurnConflict("無法定位目前輪次")
            if turn_cancel_status(live) is None and not has_pending_work(live):
                raise TurnConflict("輪次已正常完成")
            # writer 已停止；移除排隊的舊正文，收尾期間不再輸出取消輪內容。
            for queue in active.subscribers:
                while not queue.empty():
                    queue.get_nowait()
            await self._agent.acancel_turn(
                workspace_id=workspace_id, turn_id=active.turn_id
            )
            return None
        except TurnConflict as error:
            return error
        except Exception as error:
            try:
                logger.error(
                    "輪次取消尚未完成",
                    extra={
                        "event": "agent.turn.cancellation_failed",
                        "workspace_id": str(workspace_id),
                        "turn_id": str(active.turn_id),
                        "error_type": type(error).__name__,
                    },
                )
            except Exception:
                pass
            # 背景工作返回安全結果，由仍連線的入口拋出；斷線時不讓
            # asyncio shield 的例外通知輸出插件原始錯誤／cause。
            return AgentUnavailable("取消尚未完成；請以同一輪次重試")
        finally:
            self._confirmed_interrupts.pop(workspace_id, None)
            if self._active.get(workspace_id) is active:
                self._active.pop(workspace_id)
            self._publish(active, None)

    def _is_confirmed_waiting(
        self, workspace_id: UUID, snapshot: StateSnapshot
    ) -> bool:
        confirmed = self._confirmed_interrupts.get(workspace_id)
        return confirmed is not None and confirmed.matches(snapshot)

    async def resume_interrupt(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID,
        request_key: str,
        prepare: Callable[[StateSnapshot], InterruptResume],
        is_saved: Callable[[Sequence[StateSnapshot]], bool],
    ) -> TurnSubmission:
        """鎖內準備原生恢復；同步純 callback 不得 I/O、改快照或重入服務。

        request_key 只合併活動工作；受理仍須 is_saved 確認本次結果。
        is_saved 的輸入包含本輪完整歷史，保留原中斷與結果的共同證據。
        """
        created = False
        async with self._admission:
            await self._require_admission(workspace_id)
            history = await self._history(workspace_id, turn_id)
            if not history:
                raise TurnNotFound("查無輪次")
            live = await self._agent.aget_state(workspace_id=workspace_id)
            active = self._active.get(workspace_id)
            if turn_cancel_status(history[0]) is not None or (
                active is not None and active.cancel_task is not None
            ):
                raise TurnConflict("取消輪次不得回答或恢復")
            if is_saved([live, *history]):
                return TurnSubmission(
                    await self.get_turn(workspace_id=workspace_id, turn_id=turn_id),
                    False,
                )
            active = self._active.get(workspace_id)
            if active is not None:
                if active.turn_id != turn_id or active.request_key != request_key:
                    raise TurnConflict("對話正在執行其他工作或不同恢復請求")
            else:
                if live.values.get("turn_id") != turn_id:
                    raise TurnConflict("只能繼續目前輪次的待續工作")
                self._require_resume_version(live, turn_id)
                fingerprint = (
                    live.metadata.get("input_fingerprint") if live.metadata else None
                )
                if not isinstance(fingerprint, str):
                    raise TurnConflict("無法核對原始輸入")
                if len(self._active) >= self._max_active_turns:
                    raise AgentUnavailable("活動輪次已達上限")
                prepared = deepcopy(prepare(live))
                if not prepared.point.matches(live):
                    raise TurnConflict("指定的保存點或中斷已變更")
                confirmed = self._confirmed_interrupts.get(workspace_id)
                if not can_resume_interrupt(live, prepared.point.interrupt, confirmed):
                    raise TurnConflict(
                        "執行曾中斷；請先恢復原輪，勿覆寫可能已保存的輸入"
                    )
                active = ActiveTurn(
                    turn_id,
                    fingerprint,
                    asyncio.get_running_loop().create_future(),
                    request_key=request_key,
                    saved_result=is_saved,
                )
                self._active[workspace_id] = active
                active.task = asyncio.create_task(
                    self._run(
                        workspace_id,
                        active,
                        None,
                        Command(resume={prepared.point.interrupt.id: prepared.value}),
                        prepared.point,
                    )
                )
                created = True
        if not await asyncio.shield(active.accepted):
            raise AgentUnavailable("無法確認恢復結果保存；請查讀原輪狀態")
        return TurnSubmission(
            await self.get_turn(workspace_id=workspace_id, turn_id=turn_id), created
        )

    async def read_turn_execution(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> TurnExecution:
        """提供能力投影所需原生原件；查讀不啟動執行。"""
        await self._ensure_workspace(workspace_id)
        live = await self._agent.aget_state(workspace_id=workspace_id)
        history = await self._history(workspace_id, turn_id)
        if not history:
            raise TurnNotFound("查無輪次")
        current = _latest_snapshot(live, history[0])
        if turn_cancel_status(current) is not None:
            raise TurnNotFound("查無輪次")
        confirmed = self._confirmed_interrupts.get(workspace_id)
        return TurnExecution(
            current,
            history,
            confirmed if confirmed is not None and confirmed.matches(current) else None,
        )

    def _require_resume_version(self, snapshot: StateSnapshot, turn_id: UUID) -> None:
        if (
            not snapshot.metadata
            or snapshot.metadata.get("turn_id") != str(turn_id)
            or snapshot.metadata.get("resume_version") != self._agent.resume_version
        ):
            raise TurnConflict("目前 Agent 配置不相容於本輪恢復版本")

    async def resume_turn(self, *, workspace_id: UUID, turn_id: UUID) -> TurnView:
        async with self._admission:
            await self._require_admission(workspace_id)
            history = await self._history(workspace_id, turn_id)
            if not history:
                raise TurnNotFound("查無輪次")
            if turn_cancel_status(history[0]) is not None:
                raise TurnConflict("取消輪次不得恢復")
            saved = await self._agent.aget_state(workspace_id=workspace_id)
            if (
                workspace_id in self._active
                or not has_pending_work(saved)
                or not saved.metadata
                or saved.metadata.get("turn_id") != str(turn_id)
            ):
                raise TurnConflict("只能恢復目前未完成的輪次")
            self._require_resume_version(saved, turn_id)
            if saved.interrupts and (
                self._is_confirmed_waiting(workspace_id, saved)
                or not any(task.error is not None for task in saved.tasks)
            ):
                raise TurnConflict("輪次正在等待回答")
            fingerprint = saved.metadata.get("input_fingerprint")
            if not isinstance(fingerprint, str):
                raise TurnConflict("無法核對原始輸入")
            if len(self._active) >= self._max_active_turns:
                raise AgentUnavailable("活動輪次已達上限")
            active = ActiveTurn(
                turn_id, fingerprint, asyncio.get_running_loop().create_future()
            )
            self._active[workspace_id] = active
            active.task = asyncio.create_task(self._run(workspace_id, active, None))
        if not await asyncio.shield(active.accepted):
            raise AgentUnavailable("無法確認恢復受理")
        return await self.get_turn(workspace_id=workspace_id, turn_id=turn_id)

    async def list_turns(self, *, workspace_id: UUID) -> list[TurnView]:
        await self._ensure_workspace(workspace_id)
        live = await self._agent.aget_state(workspace_id=workspace_id)
        history = [
            s async for s in self._agent.aget_state_history(workspace_id=workspace_id)
        ]
        grouped: dict[UUID, list[StateSnapshot]] = {}
        for saved in history:
            saved_turn_id = saved.metadata.get("turn_id") if saved.metadata else None
            if isinstance(saved_turn_id, str):
                grouped.setdefault(UUID(saved_turn_id), []).append(saved)
        active = self._active.get(workspace_id)
        # History 由新到舊；每輪最早保存時間決定公開建立順序。
        ordered = sorted(grouped.items(), key=lambda item: item[1][-1].created_at or "")
        return [
            turn_view(
                workspace_id=workspace_id,
                turn_id=turn_id,
                history=snapshots,
                current=_latest_snapshot(live, snapshots[0]),
                running=active is not None and active.turn_id == turn_id,
                confirmed_waiting=(
                    live.values.get("turn_id") == turn_id
                    and self._is_confirmed_waiting(workspace_id, live)
                ),
            )
            for turn_id, snapshots in ordered
            if turn_cancel_status(snapshots[0]) is None
        ]

    async def list_steps(self, *, workspace_id: UUID, turn_id: UUID) -> list[StepView]:
        execution = await self.read_turn_execution(
            workspace_id=workspace_id, turn_id=turn_id
        )
        return step_views([execution.current, *execution.history], turn_id)

    @staticmethod
    def _publish(active: ActiveTurn, event: TurnEvent | None) -> None:
        for queue in tuple(active.subscribers):
            if queue.full():
                active.subscribers.remove(queue)
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(
                    ResyncRequiredEvent(
                        event="resync_required",
                        data=ResyncRequiredData(reason="slow_subscriber"),
                    )
                )
                queue.put_nowait(None)
            else:
                queue.put_nowait(event)

    async def stream_turn(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> AsyncGenerator[TurnEvent]:
        active: ActiveTurn | None = None
        queue: asyncio.Queue[TurnEvent | None] = asyncio.Queue(maxsize=64)
        try:
            # 與恢復共用准入鎖，訂閱與初次狀態不可分屬兩次執行。
            async with self._admission:
                active = self._active.get(workspace_id)
                if active and active.turn_id != turn_id:
                    active = None
                if active:
                    if len(active.subscribers) >= 64:
                        raise AgentUnavailable("訂閱數已達上限")
                    active.subscribers.add(queue)
                # 執行收尾不取鎖；讀取期間完成仍會留下終局通知。
                current = await self.get_turn(
                    workspace_id=workspace_id, turn_id=turn_id
                )
            yield TurnStatusEvent(event="status", data=current)
            if current.status != "running" or active is None:
                return
            while True:
                event = await queue.get()
                if event is None:
                    history = await self._history(workspace_id, turn_id)
                    if history and (status := turn_cancel_status(history[0])):
                        yield CancellationEvent(
                            event="cancellation",
                            data=CancellationData(turn_id=turn_id, status=status),
                        )
                        return
                    current = await self.get_turn(
                        workspace_id=workspace_id, turn_id=turn_id
                    )
                    yield TurnStatusEvent(event="status", data=current)
                    return
                yield event
                if event.event == "resync_required":
                    return
        finally:
            if active:
                active.subscribers.discard(queue)

    async def aclose(self) -> None:
        """停止准入後等待自有工作，不強制取消原生保存收尾。"""
        async with self._admission:
            self._closed = True
            tasks = [
                task
                for active in self._active.values()
                for task in (active.task, active.cancel_task)
                if task is not None
            ]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._confirmed_interrupts.clear()


def _latest_snapshot(live: StateSnapshot, latest: StateSnapshot) -> StateSnapshot:
    # history 在 live 後讀取；同一保存點才採用 live 合併的 pending writes，
    # 否則沿較新的目標輪歷史，避免取消或換輪交錯時回傳舊正文。
    if live.config["configurable"].get("checkpoint_id") == latest.config[
        "configurable"
    ].get("checkpoint_id"):
        return live
    return latest
