"""原生 Graph 的可信 Workspace 執行與查讀入口。"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import aclosing
from copy import deepcopy
from typing import Any, cast
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphDrained
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import RunControl
from langgraph.types import Command, StateSnapshot, StateUpdate
from openai.types.responses import ParsedResponse, Response
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.modules.agent.completed_turns import previous_turn_snapshots
from caliburn.modules.agent.infrastructure.openai.call_model import (
    ModelResponseError,
    classify_model_response,
    validate_response,
)
from caliburn.modules.agent.interrupts import ResumePoint
from caliburn.modules.agent.plugins.contracts import AgentContext, PluginCancelHook
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.agent.state import (
    AgentInput,
    AgentOutput,
    AgentState,
    CancelStatus,
)


class AgentExecutionError(RuntimeError):
    """目前生命週期或 thread 狀態不允許所要求的操作。"""


class Agent:
    def __init__(
        self,
        *,
        agent_id: str,
        resume_version: str,
        graph: CompiledStateGraph[AgentState, AgentContext, AgentInput, AgentOutput],
        context: AgentContext,
        recursion_limit: int | None = None,
        cancel_hooks: tuple[PluginCancelHook[Any], ...] = (),
    ):
        self._agent_id = agent_id
        self._resume_version = resume_version
        self._graph = graph
        self._context = context
        self._recursion_limit = recursion_limit
        self._cancel_hooks = cancel_hooks
        self._active: set[UUID] = set()
        self._closed = False

    @property
    def resume_version(self) -> str:
        """目前 Host 對恢復契約的明示版本。"""
        return self._resume_version

    @property
    def services(self) -> PluginServices:
        """供可信 Host 使用已組裝的公開服務；生命週期仍由 open_agent 管理。"""
        return self._context.services

    def close(self) -> None:
        """Host 必須先結束／等待所有 invocation，再退出啟動生命週期。"""
        self._closed = True

    def _config(
        self, workspace_id: UUID, checkpoint_id: str | None = None
    ) -> RunnableConfig:
        if self._closed:
            raise AgentExecutionError("Agent is closed")
        config: RunnableConfig = {
            "configurable": {"thread_id": f"{self._agent_id}:{workspace_id}"}
        }
        if checkpoint_id is not None:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        if self._recursion_limit is not None:
            config["recursion_limit"] = self._recursion_limit
        return config

    def astream(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID,
        input: str | ResponseInputParam,
        input_fingerprint: str | None = None,
        include_checkpoints: bool = False,
        control: RunControl | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """新輪可附受理指紋；checkpoint 事件仍須公開查讀確認保存。"""
        return self._execute(
            workspace_id,
            turn_id,
            deepcopy(input),
            input_fingerprint=input_fingerprint,
            include_checkpoints=include_checkpoints,
            control=control,
        )

    def aresume(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID,
        resume_command: Command[Any] | None = None,
        expected: ResumePoint | None = None,
        input_fingerprint: str | None = None,
        include_checkpoints: bool = False,
        control: RunControl | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """恢復原輪；未明示指紋時沿用該輪已保存 metadata。"""
        return self._execute(
            workspace_id,
            turn_id,
            resume_command,
            expected=deepcopy(expected),
            input_fingerprint=input_fingerprint,
            include_checkpoints=include_checkpoints,
            control=control,
        )

    async def _execute(
        self,
        workspace_id: UUID,
        turn_id: UUID,
        input: str | ResponseInputParam | Command[Any] | None,
        *,
        expected: ResumePoint | None = None,
        input_fingerprint: str | None = None,
        include_checkpoints: bool = False,
        control: RunControl | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        config = self._config(workspace_id)
        if workspace_id in self._active:
            raise AgentExecutionError("Thread already has an active execution")
        self._active.add(workspace_id)
        try:
            saved = await self._graph.aget_state(config)
            self._validate_workspace(saved, workspace_id)
            if expected is not None and not expected.matches(saved):
                raise AgentExecutionError("Prepared interrupt or checkpoint changed")
            config["metadata"] = {
                "workspace_id": str(workspace_id),
                "turn_id": str(turn_id),
                "resume_version": self._resume_version,
            }
            graph_input: AgentInput | Command[Any] | None
            if input is None or isinstance(input, Command):
                graph_input = _prepare_resume_input(
                    saved, turn_id=turn_id, resume_command=input
                )
                if saved.metadata:
                    config["metadata"]["resume_version"] = saved.metadata.get(
                        "resume_version"
                    )
                if input_fingerprint is None and saved.metadata:
                    saved_fingerprint = saved.metadata.get("input_fingerprint")
                    if isinstance(saved_fingerprint, str):
                        input_fingerprint = saved_fingerprint
            else:
                async for previous in self.aget_state_history(
                    workspace_id=workspace_id, turn_id=turn_id, limit=1
                ):
                    if turn_cancel_status(previous) is not None:
                        raise AgentExecutionError("Cannot restart a cancelled turn")
                graph_input = _prepare_new_turn_input(
                    saved, workspace_id=workspace_id, turn_id=turn_id, input=input
                )
            config["run_id"] = uuid4()
            if input_fingerprint is not None:
                config["metadata"]["input_fingerprint"] = input_fingerprint
            # 官方 astream 實作為 async generator；其 overload 只註記
            # AsyncIterator。此處適配關閉契約及原生 v2 dict 的型別。
            try:
                async with aclosing(
                    cast(
                        AsyncGenerator[dict[str, Any]],
                        self._graph.astream(
                            graph_input,
                            config,
                            context=self._context,
                            stream_mode=["custom", "values", "checkpoints"]
                            if include_checkpoints
                            else ["custom", "values"],
                            output_keys=["turn_id", "model_response"],
                            durability="sync",
                            version="v2",
                            control=control,
                        ),
                    )
                ) as stream:
                    async for part in stream:
                        if (
                            part["type"] == "values"
                            and part["data"].get("turn_id") != turn_id
                        ):
                            if part.get("interrupts"):
                                yield {**part, "data": {}}
                            continue
                        yield part
            except GraphDrained:
                drained = await self._graph.aget_state(config)
                if drained.next != ("finish_turn",):
                    raise
                # 全部模型／工具／插件已完成，只剩 Core 完成標記；停止請求
                # 不把這個純保存接點改判為取消，也不重跑任何業務 Node。
                await self._graph.aupdate_state(
                    config, {"turn_completed": True}, as_node="finish_turn"
                )
            final = await self._graph.aget_state(config)
            if final.interrupts:
                return
            if (
                has_pending_work(final)
                or final.values.get("turn_id") != turn_id
                or not final.values.get("model_step")
                or final.values.get("model_response") is None
            ):
                raise AgentExecutionError("Agent stopped with pending work")
        finally:
            self._active.remove(workspace_id)

    async def acancel_turn(self, *, workspace_id: UUID, turn_id: UUID) -> None:
        """writer 已停止後保存整輪取消；失敗可沿同一入口重試。"""
        config = self._config(workspace_id)
        if workspace_id in self._active:
            raise AgentExecutionError("Thread already has an active execution")
        self._active.add(workspace_id)
        try:
            saved = await self.aget_state(workspace_id=workspace_id)
            if saved.metadata is None or saved.metadata.get("turn_id") != str(turn_id):
                async for previous in self.aget_state_history(
                    workspace_id=workspace_id, turn_id=turn_id, limit=1
                ):
                    if turn_cancel_status(previous) == "completed":
                        return
                raise AgentExecutionError("Cannot cancel a missing or different turn")
            status = turn_cancel_status(saved)
            if status == "completed":
                return
            if status is None and not has_pending_work(saved):
                raise AgentExecutionError("Cannot cancel a completed turn")
            config["metadata"] = {
                key: saved.metadata.get(key)
                for key in (
                    "workspace_id",
                    "turn_id",
                    "resume_version",
                    "input_fingerprint",
                )
                if key in saved.metadata
            }
            if status is None:
                # 公開 task.result 是尚未併入 checkpoint 的 channel 更新。
                # 同批套用保留 reducer 語意；START 的 None 不覆蓋本次 pending。
                updates = [
                    StateUpdate(
                        {
                            key: value
                            for key, value in task.result.items()
                            if key != "cancel_status"
                        },
                        task.name,
                        task.id,
                    )
                    for task in saved.tasks
                    if task.result is not None
                ]
                updates.append(StateUpdate({"cancel_status": "pending"}, "cancel_turn"))
                await self._graph.abulk_update_state(config, [updates])
                saved = await self.aget_state(workspace_id=workspace_id)
            state = saved.values if saved.values.get("turn_id") == turn_id else None
            for hook in self._cancel_hooks:
                await hook(
                    state,
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    context=self._context,
                )
            await self._graph.aupdate_state(
                config, {"cancel_status": "completed"}, as_node="cancel_turn"
            )
        finally:
            self._active.remove(workspace_id)

    async def aget_state(
        self,
        *,
        workspace_id: UUID,
        checkpoint_id: str | None = None,
        subgraphs: bool = False,
    ) -> StateSnapshot:
        snapshot = await self._graph.aget_state(
            self._config(workspace_id, checkpoint_id), subgraphs=subgraphs
        )
        self._validate_workspace(snapshot, workspace_id)
        return snapshot

    async def aget_state_history(
        self,
        *,
        workspace_id: UUID,
        limit: int | None = None,
        before: RunnableConfig | None = None,
        turn_id: UUID | None = None,
    ) -> AsyncIterator[StateSnapshot]:
        """以官方 metadata 篩選輪次，包含 State 尚未套入的 input 保存點。"""
        async for snapshot in self._graph.aget_state_history(
            self._config(workspace_id),
            limit=limit,
            before=before,
            filter={"turn_id": str(turn_id)} if turn_id is not None else None,
        ):
            self._validate_workspace(snapshot, workspace_id)
            yield snapshot

    async def aget_previous_completed_turn(
        self, *, workspace_id: UUID, before_turn_id: UUID
    ) -> StateSnapshot | None:
        """唯讀取得指定輪開始前的上一正常完成輪；無錨點或完成輪則 None。"""
        async for snapshot in previous_turn_snapshots(
            self.aget_state_history(workspace_id=workspace_id),
            before_turn_id=before_turn_id,
        ):
            if completed_turn_id(snapshot) is not None:
                return snapshot
        return None

    @staticmethod
    def _validate_workspace(snapshot: StateSnapshot, workspace_id: UUID) -> None:
        # 原生 input checkpoint 在 __start__ 套用前可只有 reducer 初值；
        # 其新輸入在 pending task，不能誤當成另一個 Workspace。
        if (
            "workspace_id" in snapshot.values
            and snapshot.values["workspace_id"] != workspace_id
        ):
            raise AgentExecutionError("Checkpoint Workspace ownership does not match")


def _prepare_new_turn_input(
    snapshot: StateSnapshot,
    *,
    workspace_id: UUID,
    turn_id: UUID,
    input: str | ResponseInputParam,
) -> AgentInput:
    status = turn_cancel_status(snapshot)
    if status == "pending":
        raise AgentExecutionError("Cancellation is pending")
    if status is None:
        if snapshot.interrupts:
            raise AgentExecutionError(
                "Cannot start a new turn while waiting for an answer"
            )
        if has_pending_work(snapshot):
            raise AgentExecutionError("Cannot start a new turn while work is pending")
    return {
        "workspace_id": workspace_id,
        "turn_id": turn_id,
        "turn_input": input,
        "model_response": None,
        "compaction_response": None,
        "model_step": 0,
        "cancel_status": None,
        "turn_completed": False,
    }


def _prepare_resume_input(
    snapshot: StateSnapshot,
    *,
    turn_id: UUID,
    resume_command: Command[Any] | None,
) -> Command[Any] | None:
    if turn_cancel_status(snapshot) is not None:
        raise AgentExecutionError("Cannot resume a cancelled turn")
    if not has_pending_work(snapshot):
        raise AgentExecutionError("Cannot resume a missing or completed thread")
    if snapshot.metadata is None or snapshot.metadata.get("turn_id") != str(turn_id):
        raise AgentExecutionError("Cannot resume a different turn")
    if resume_command is None:
        # 同一 Node 回答後故障，原生快照仍可同時保留 interrupt 與 error。
        # 交給框架復用已保存答案；若遇未回答問題，仍會再次 interrupt。
        if snapshot.interrupts and not any(
            task.error is not None for task in snapshot.tasks
        ):
            raise AgentExecutionError("Waiting turn requires a resume answer")
        return None
    if (
        resume_command.resume is None
        or resume_command.update is not None
        or resume_command.goto
        or resume_command.graph is not None
    ):
        raise AgentExecutionError("Only a resume-only Command is allowed")
    if not snapshot.interrupts:
        raise AgentExecutionError("Resume answer requires a waiting turn")
    # 以 ID 指定問題，避免無 ID 答案在重試時被後續問題再次取用。
    answers = resume_command.resume
    interrupt_ids = {item.id for item in snapshot.interrupts}
    if (
        not isinstance(answers, dict)
        or not answers
        or not answers.keys() <= interrupt_ids
    ):
        raise AgentExecutionError("回答須以目前的 interrupt ID 對應答案")
    return resume_command


def completed_turn_id(snapshot: StateSnapshot) -> UUID | None:
    """正常完成且已無待續工作的輪次；回應資格與 Core 模型收尾相同。"""
    turn_id = snapshot.values.get("turn_id")
    response = snapshot.values.get("model_response")
    if (
        snapshot.values.get("turn_completed") is not True
        or not isinstance(turn_id, UUID)
        or (snapshot.metadata or {}).get("turn_id") != str(turn_id)
        or turn_cancel_status(snapshot) is not None
        or has_pending_work(snapshot)
        or not isinstance(response, Response)
    ):
        return None
    # ParsedResponse 只增加解析輔助欄位；此兩個 Core 判讀只讀 Response 欄位。
    parsed = cast(ParsedResponse[None], response)
    try:
        validate_response(parsed)
    except ModelResponseError, ValueError:
        return None
    return (
        turn_id
        if classify_model_response({"model_response": parsed}) == "finish"
        else None
    )


def has_pending_work(snapshot: StateSnapshot) -> bool:
    """公開保存點是否仍有待續工作，包含尚未套入 State 的新輸入。"""
    # 最新查讀可先合併 START pending writes，使 next 暫時為空；tasks 與
    # input 保存位置仍指出需要原生 None 續作，不能誤判前輪 Response 已完成。
    return bool(
        snapshot.next
        or snapshot.tasks
        or snapshot.interrupts
        # 停用插件會移除其 Node；新 Graph 的空排程不是舊輪完成證據。
        or snapshot.values.get("turn_completed") is False
        or (snapshot.metadata and snapshot.metadata.get("source") == "input")
    )


def turn_cancel_status(snapshot: StateSnapshot) -> CancelStatus | None:
    """讀取此保存點所屬輪的取消狀態；新輪 input 可仍帶前輪 values。"""
    if snapshot.metadata and snapshot.metadata.get("source") == "input":
        return None
    return cast(CancelStatus | None, snapshot.values.get("cancel_status"))
