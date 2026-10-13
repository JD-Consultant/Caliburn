"""框架擁有 model/tool 路由；App 擁有原件、准入與效果交易。"""

from asyncio import CancelledError, Condition
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, TypedDict, cast
from uuid import UUID, uuid4, uuid5

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain.agents.middleware.types import ExtendedModelResponse, ModelRequest, ModelResponse
from langchain.tools import ToolRuntime
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, RemoveMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command, StateSnapshot, interrupt
from openai.types.responses import FunctionToolParam, ResponseFunctionToolCall
from pydantic import Field, ValidationError

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import (
    NativeSnapshot,
    function_result_item,
    require_result_order,
    response_input_items,
    restore_response,
    snapshot_response,
)
from caliburn.agent_execution.request_capacity import (
    MAX_FIRST_REQUEST_FITS,
    CompactionRequiredError,
    RequestCapacityError,
    RequestOverCapacityError,
    RequestOverflow,
    allowed_input_tokens,
    require_request_capacity,
    require_request_limits,
    validate_capacity_limits,
)
from caliburn.agent_execution.response_runtime import (
    HeldInputCount,
    HeldModelResponse,
    InputCountSaveError,
    ModelStepLimitError,
    PausedResponseLoop,
    ReceivedModelResponse,
    ReceivedModelResponseCancelledError,
    ResponseLoopControls,
    ResponseStepRuntime,
    ResponseStepSaveError,
    ResponseStepState,
)
from caliburn.agent_execution.response_steps import ResponseAction, inspect_response_step
from caliburn.agent_execution.result_save_retries import (
    ResultSaveCancelledError,
    ResultSaveRetryPolicy,
    retry_result_save,
)


class NativeAgentState(AgentState, ResponseStepState):
    boundary_response_id: str | None
    agent_completed: bool


class ToolEffectState(TypedDict, total=False):
    request_id: UUID
    call: NativeSnapshot
    operation_id: UUID
    prepared: object
    output: str


@dataclass(frozen=True, slots=True)
class NativeToolBinding:
    prepare: Callable[[ResponseFunctionToolCall, UUID], Awaitable[object]]
    execute: Callable[[object], Awaitable[str]]


def project_native_response(snapshot: NativeSnapshot) -> AIMessage:
    """已保存原件才建立 name/id 路由；參數只由正式准入讀原件。"""
    response = restore_response(snapshot)
    calls = []
    for call in inspect_response_step(response).calls:
        calls.append({"name": call.name, "id": call.call_id, "args": {}, "type": "tool_call"})
    # raw 僅存在 response_snapshot；messages 不再保存整份 provider 結果。
    return AIMessage(id=response.id, content="", tool_calls=calls)


def completed_step_update(state: NativeAgentState) -> ResponseStepState:
    response = state["response_snapshot"]
    step = inspect_response_step(restore_response(response))
    observations = _current_tool_observations(state)
    results = [
        function_result_item(call, cast(str, observations[call.call_id].content))
        for call in step.calls
        if call.call_id in observations
    ]
    require_result_order(step.calls, results)
    if len(results) != len(step.calls):
        raise ValueError("A Step cannot finish with unresolved tool calls")
    return {
        "tool_results": results,
        "completed_steps": state["completed_steps"]
        + (state.get("boundary_response_id") != response["id"]),
        "next_action": "deliver_answer"
        if step.action == ResponseAction.DELIVER_ANSWER
        else "continue",
    }


def _current_tool_observations(state: NativeAgentState) -> dict[str, ToolMessage]:
    messages = state["messages"]
    last = max(i for i, message in enumerate(messages) if isinstance(message, AIMessage))
    if messages[last].id != state["response_snapshot"]["id"]:
        raise ValueError("Tool observations require the current model response")
    return {m.tool_call_id: m for m in messages[last + 1 :] if isinstance(m, ToolMessage)}


class NativeModel(BaseChatModel):
    policy: object = Field(exclude=True)

    @property
    def _llm_type(self) -> str:
        return "caliburn-native-responses"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self.bind(**kwargs)

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        raise RuntimeError("The native agent requires async execution")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        policy = cast(NativePolicy, self.policy)
        state: NativeAgentState = kwargs["native_state"]
        held = policy.held
        if isinstance(held, HeldModelResponse) and held.request_id == state["request_id"]:
            if held.request_snapshot != state["request_snapshot"]:
                raise ValueError("The held response belongs to another original request")
            update = held.update
        else:
            await policy.io.ensure_active()
            count = state["input_count"]
            if count is None:
                raise ValueError("The exact request needs a saved input count")
            try:
                received = await policy.io.request_model(
                    ResponseRequest.from_snapshot(state["request_snapshot"]),
                    state["request_id"],
                    count["input_tokens"],
                )
            except ReceivedModelResponseCancelledError as error:
                policy.interruption = error
                policy.cancelled_response = True
                received = error.received
            update = {
                "response_snapshot": snapshot_response(received.response),
                "response_attempt_id": received.attempt_id,
                "operation_seed": uuid4(),
                "tool_results": [],
                "next_action": None,
            }
            # 在任何 routing view／framework message 建構之前，先持有已收到原件。
            policy.held = HeldModelResponse(
                policy.thread_id,
                state["request_id"],
                deepcopy(state["request_snapshot"]),
                deepcopy(update),
            )
        policy.model_update = update
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        id=update["response_snapshot"]["id"],
                        content="",
                    )
                )
            ]
        )


class NativePolicy(AgentMiddleware[NativeAgentState, None]):
    state_schema = NativeAgentState

    def __init__(
        self,
        thread_id: str,
        io: ResponseStepRuntime,
        controls: ResponseLoopControls | None,
        held: HeldModelResponse | HeldInputCount | None,
        unknown_tool_output: str,
    ) -> None:
        self.thread_id, self.io, self.controls, self.held = thread_id, io, controls, held
        self.unknown_tool_output = unknown_tool_output
        self.model_update: ResponseStepState = {}
        self.interruption: ReceivedModelResponseCancelledError | None = None
        self.cancelled_response = False
        self.limits: tuple[int, int] | None = None
        self.capacity = self._capacity_graph()
        self._tool_condition = Condition()
        self._completed_tool_calls: set[tuple[UUID, str]] = set()

    def _capacity_graph(
        self,
    ) -> CompiledStateGraph[ResponseStepState, None, ResponseStepState, ResponseStepState]:
        async def count(state: ResponseStepState) -> ResponseStepState:
            await self.io.ensure_active()
            request = ResponseRequest.from_snapshot(state["request_snapshot"])
            require_request_limits(request, self.io.capacity_limits)
            held = self.held
            if isinstance(held, HeldInputCount) and held.request_id == state["request_id"]:
                if held.request_snapshot != state["request_snapshot"]:
                    raise ValueError("The held count belongs to another original request")
                return held.update
            received = await self.io.count_input(
                request, uuid5(state["request_id"], "input_tokens")
            )
            update: ResponseStepState = {
                "input_count": received,
            }
            self.held = HeldInputCount(
                self.thread_id,
                state["request_id"],
                deepcopy(state["request_snapshot"]),
                update,
            )
            return update

        async def admit(state: ResponseStepState) -> Command[Any]:
            self.held = None  # 前一 sync 節點已確認 count 原件。
            await self.io.ensure_active()
            request = ResponseRequest.from_snapshot(state["request_snapshot"])
            count = state["input_count"]
            if count is None:
                raise ValueError("The exact request needs a saved input count")
            try:
                require_request_capacity(
                    request,
                    count,
                    self.io.capacity_limits,
                    completed_steps=state["completed_steps"],
                )
            except CompactionRequiredError:
                if state.get("compacted_request_id") == state["request_id"]:
                    raise RequestCapacityError(
                        "The compacted window still requires compaction"
                    ) from None
                return Command(goto="compact")
            except RequestOverCapacityError:
                if (
                    self.io.fit_first_request is None
                    or state["completed_steps"] != 0
                    or state.get("first_request_fits", 0) >= MAX_FIRST_REQUEST_FITS
                ):
                    raise
                return Command(goto="fit")
            return Command(goto=END)

        async def fit(state: ResponseStepState) -> ResponseStepState:
            request = ResponseRequest.from_snapshot(state["request_snapshot"])
            count, reduce = state["input_count"], self.io.fit_first_request
            if count is None or reduce is None:
                raise ValueError("The counted first request has no fit policy")
            attempt = state.get("first_request_fits", 0) + 1
            items = reduce(
                request,
                RequestOverflow(
                    count["input_tokens"],
                    allowed_input_tokens(request, self.io.capacity_limits),
                    attempt,
                ),
            )
            return {
                "request_id": uuid5(state["request_id"], "fitted"),
                "request_snapshot": {**deepcopy(state["request_snapshot"]), "input": items},
                "input_count": None,
                "first_request_fits": attempt,
            }

        async def compact(state: ResponseStepState) -> ResponseStepState:
            count = state["input_count"]
            if self.io.compact_window is None or count is None:
                raise CompactionRequiredError("The next request requires boundary compaction")
            items = await self.io.compact_window(
                ResponseRequest.from_snapshot(state["request_snapshot"]),
                count,
                state["request_id"],
            )
            request_id = uuid5(state["request_id"], "compacted")
            return {
                "request_id": request_id,
                "compacted_request_id": request_id,
                "request_snapshot": {**deepcopy(state["request_snapshot"]), "input": items},
                "input_count": None,
            }

        graph = StateGraph(ResponseStepState)
        for name, node in (("count", count), ("admit", admit), ("fit", fit), ("compact", compact)):
            graph.add_node(name, node)
        graph.add_edge(START, "count").add_edge("count", "admit")
        graph.add_edge("fit", "count").add_edge("compact", "count")
        return graph.compile()

    async def boundary(self, state: NativeAgentState) -> ResponseStepState:
        response = state.get("response_snapshot")
        if not response:
            return {}
        update = completed_step_update(state)
        if self.controls is not None:
            requested = await self.controls.read_pause_requested()
            if type(requested) is not bool:
                raise ValueError("The pause request must be a definite boolean")
            if (
                requested
                and interrupt({"kind": "step_pause", "completed_steps": update["completed_steps"]})
                is not True
            ):
                raise ValueError("Only explicit original-loop resume can release this pause")
        return update

    async def abefore_model(
        self, state: NativeAgentState, runtime: Runtime[None]
    ) -> dict[str, Any]:
        if self.limits is not None and self.limits != (
            state["tool_call_limit"],
            state["model_step_limit"],
        ):
            raise ValueError("Resume with the original execution mode and limits")
        inherited = get_config()
        config: RunnableConfig = {
            **inherited,
            "configurable": {
                key: value
                for key, value in inherited["configurable"].items()
                if key != "checkpoint_id"
            },
        }
        if state.get("response_snapshot"):
            try:
                await self.io.ensure_active()
            except self.io.inactive_errors:
                # 僅已知資格失效可結清已存 C；控制查詢失敗不授權重入。
                pending = await self.capacity.aget_state(config)
                if pending.next == ("compact",):
                    await self.capacity.ainvoke(None, config, durability="sync")
                raise
        update = await self.boundary(state)
        current = cast(NativeAgentState, {**state, **update})
        limit = current["model_step_limit"]
        if limit is None or current["completed_steps"] >= limit:
            return dict(update)
        if state.get("response_snapshot"):
            payload = deepcopy(state["request_snapshot"])
            payload["input"] = [
                *payload["input"],
                *response_input_items(restore_response(state["response_snapshot"])),
                *update["tool_results"],
            ]
            next_id = uuid5(state["request_id"], "next")
            unchanged = (
                state.get("compacted_request_id") == state["request_id"]
                and payload["input"] == state["request_snapshot"]["input"]
            )
            current.update(
                {
                    "request_id": next_id,
                    "request_snapshot": payload,
                    "input_count": None,
                    "compacted_request_id": next_id if unchanged else None,
                }
            )
        capacity_input = {
            key: current[key]
            for key in (
                "request_id",
                "request_snapshot",
                "completed_steps",
                "input_count",
                "first_request_fits",
                "compacted_request_id",
            )
            if key in current
        }
        counted = await self.capacity.ainvoke(
            cast(ResponseStepState, capacity_input), config, durability="sync"
        )
        return {
            **update,
            **{
                key: counted[key]
                for key in (
                    "request_id",
                    "request_snapshot",
                    "input_count",
                    "first_request_fits",
                    "compacted_request_id",
                )
                if key in counted
            },
            **({"response_snapshot": {}} if state.get("response_snapshot") else {}),
            "response_attempt_id": None,
            "operation_seed": None,
            "tool_results": [],
            "next_action": None,
            "boundary_response_id": state.get("response_snapshot", {}).get("id"),
        }

    async def awrap_model_call(
        self,
        request: ModelRequest[None],
        handler: Callable[[ModelRequest[None]], Awaitable[ModelResponse[object]]],
    ) -> ExtendedModelResponse[object]:
        state = cast(NativeAgentState, request.state)
        limit = state["model_step_limit"]
        if limit is None:
            raise ValueError("The saved work requires a model Step bound")
        if state["completed_steps"] >= limit:
            raise ModelStepLimitError("The saved model Step limit has been reached")
        result = await handler(request.override(model_settings={"native_state": request.state}))
        return ExtendedModelResponse(result, Command(update=self.model_update))

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state: NativeAgentState, runtime: Runtime[None]) -> dict[str, Any]:
        if self.interruption is not None:
            interruption, self.interruption = self.interruption, None
            self.cancelled_response = True
            raise interruption
        self.held = None  # raw R 已通過 model 的 sync 保存屏障。
        attempt = state["response_attempt_id"]
        if attempt is None:
            raise ValueError("The original response has no admitted attempt")
        response = restore_response(state["response_snapshot"])
        await self.io.account_response(ReceivedModelResponse(response, attempt))
        await self.io.ensure_active()
        step = inspect_response_step(response)
        if len(step.calls) > state["tool_call_limit"]:
            raise ValueError("The response exceeds the saved tool bound")
        view = project_native_response(state["response_snapshot"])
        return {
            "messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), view],
            **({"jump_to": "model"} if step.action == ResponseAction.CONTINUE else {}),
        }

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        state = cast(NativeAgentState, request.state)
        request_id, call_id = state["request_id"], request.tool_call["id"]
        if call_id is None:
            raise ValueError("The tool call requires its original identity")
        calls = [
            call.call_id
            for call in inspect_response_step(restore_response(state["response_snapshot"])).calls
        ]
        previous = calls[: calls.index(call_id)]
        async with self._tool_condition:
            await self._tool_condition.wait_for(
                lambda: all((request_id, prior) in self._completed_tool_calls for prior in previous)
            )
            # handler 返回前，工具子圖的 output 已通過 sync 保存屏障。
            # 普通 Exception 不放行後繼；原 Graph runner 取消等待中的 calls。
            # 外層取消整輪時，同樣由原 runner 取消所有 tools tasks。
            result: ToolMessage | Command[Any]
            if request.tool is None:
                result = ToolMessage(
                    content=self.unknown_tool_output,
                    name=request.tool_call["name"],
                    tool_call_id=call_id,
                )
            else:
                result = await handler(request)
            self._completed_tool_calls.add((request_id, call_id))
            self._tool_condition.notify_all()
            return result

    async def aafter_agent(self, state: NativeAgentState, runtime: Runtime[None]) -> dict[str, Any]:
        await self.io.ensure_active()
        update = await self.boundary(state)
        return {
            **update,
            "agent_completed": True,
            "boundary_response_id": state["response_snapshot"]["id"],
        }


async def run_native_agent(
    checkpointer: BaseCheckpointSaver[str],
    *,
    thread_id: str,
    request: ResponseRequest | None,
    runtime: ResponseStepRuntime,
    tools: Sequence[BaseTool],
    max_tool_calls: int,
    max_model_steps: int,
    controls: ResponseLoopControls | None = None,
    unknown_tool_output: str,
    recovery: HeldModelResponse | HeldInputCount | None = None,
    resume_interrupt_id: str | None = None,
    save_retry_policy: ResultSaveRetryPolicy | None = None,
) -> ResponseStepState | PausedResponseLoop:
    """完整原件優先補存；遺失 count 的重算與未知 R／C 的阻擋由外送准入負責。"""
    if (
        not thread_id
        or type(max_tool_calls) is not int
        or type(max_model_steps) is not int
        or min(max_tool_calls, max_model_steps) < 1
    ):
        raise ValueError("Configure an original thread and positive execution bounds")
    if recovery is not None and (request is not None or recovery.thread_id != thread_id):
        raise ValueError("The handoff requires its original Step with None")
    if recovery is not None:
        try:
            ResponseRequest.from_snapshot(recovery.request_snapshot)
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("The handoff must retain its saved request boundary") from error
    validate_capacity_limits(runtime.capacity_limits)
    policy = NativePolicy(thread_id, runtime, controls, recovery, unknown_tool_output)
    policy.limits = (max_tool_calls, max_model_steps)
    graph = create_agent(
        NativeModel(policy=policy),
        tools=list(tools),
        middleware=[policy],
        state_schema=NativeAgentState,
        checkpointer=checkpointer,
    )
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id, "checkpoint_ns": ""},
        "recursion_limit": (max_tool_calls * 2 + 20) * max_model_steps,
    }

    async def read_saved() -> StateSnapshot:
        try:
            saved = await graph.aget_state(config)
            if saved.values.get("response_snapshot"):
                # ToolRuntime 的同一 super-step 不含前任務的 pending writes；
                # 既有公開 snapshot 查詢已將其投影為可恢復的 ToolMessages。
                policy._completed_tool_calls.update(
                    (saved.values["request_id"], call_id)
                    for call_id in _current_tool_observations(cast(NativeAgentState, saved.values))
                )
            return saved
        except BaseException as error:
            if recovery is None:
                raise
            failure = (
                InputCountSaveError(recovery)
                if isinstance(recovery, HeldInputCount)
                else ResponseStepSaveError(recovery)
            )
            if isinstance(error, CancelledError):
                raise ResultSaveCancelledError(failure) from error
            raise failure from error

    initial: dict[str, Any] | Command[Any] | None = None
    initialized = False

    async def run_or_reconcile() -> ResponseStepState | PausedResponseLoop:
        nonlocal initial, initialized
        if not initialized:
            saved = await read_saved()
            if request is not None and saved.created_at is not None:
                raise ValueError("This work already exists; resume with None")
            if request is None and saved.created_at is None:
                raise ValueError("There is no saved work to resume")
            if "request_id" in saved.values:
                if recovery is not None and saved.values.get("request_id") == recovery.request_id:
                    if saved.values["request_snapshot"] != recovery.request_snapshot:
                        raise ValueError("The handoff must retain its saved request boundary")
                    original = saved.values.get("response_snapshot")
                    if (
                        isinstance(recovery, HeldModelResponse)
                        and original
                        and any(
                            saved.values.get(key) != recovery.update[key]
                            for key in (
                                "response_snapshot",
                                "response_attempt_id",
                                "operation_seed",
                            )
                        )
                    ):
                        raise ValueError("The saved Step contains a different model result")
                    if isinstance(recovery, HeldModelResponse) and original:
                        policy.held = None
                elif isinstance(recovery, HeldModelResponse):
                    raise ValueError("The handoff must retain its saved request boundary")
                if (
                    saved.values.get("model_step_limit") != max_model_steps
                    or saved.values.get("tool_call_limit") != max_tool_calls
                ):
                    raise ValueError("Resume with the original execution mode and limits")
                if saved.values.get("capacity_limits") != runtime.capacity_limits:
                    raise ValueError("Resume with the original capacity limits")
                if saved.values.get("pause_enabled") != (controls is not None):
                    raise ValueError("Resume with the original control configuration")
            if saved.interrupts:
                if controls is None or recovery is not None:
                    raise ValueError("A paused loop requires its original control binding")
                if resume_interrupt_id is None:
                    await controls.mark_paused()
                    paused = native_agent_pause(saved)
                    if paused is None:
                        raise ValueError("The complete Step pause was not saved")
                    return paused
                if len(saved.interrupts) != 1 or saved.interrupts[0].id != resume_interrupt_id:
                    raise ValueError("The resume identity does not match the current interrupt")
                initial = Command(resume={resume_interrupt_id: True})
            elif resume_interrupt_id is not None:
                raise ValueError("There is no current pause interrupt to resume")
            elif request is not None:
                initial = {
                    "messages": [],
                    "request_id": uuid4(),
                    "request_snapshot": request.create_payload(),
                    "completed_steps": 0,
                    "model_step_limit": max_model_steps,
                    "tool_call_limit": max_tool_calls,
                    "capacity_limits": runtime.capacity_limits,
                    "pause_enabled": controls is not None,
                    "agent_completed": False,
                    "boundary_response_id": None,
                }
            elif saved.values.get("agent_completed") and controls is not None:
                # 完成交易前仍可能有晚到 pause；只重入 final 的控制 successor。
                await graph.aupdate_state(
                    config, {"agent_completed": False}, as_node="NativePolicy.after_model"
                )

            initialized = True
        if isinstance(policy.held, HeldModelResponse):
            try:
                await runtime.ensure_active()
            except Exception:
                attempt_id = policy.held.update["response_attempt_id"]
                if attempt_id is None:
                    raise ValueError(
                        "The held model result requires its original attempt"
                    ) from None
                await runtime.account_response(
                    ReceivedModelResponse(
                        restore_response(policy.held.update["response_snapshot"]),
                        attempt_id,
                    )
                )
                raise
        elif isinstance(policy.held, HeldInputCount) or request is not None:
            await runtime.ensure_active()
        try:
            result = await graph.ainvoke(
                cast(Any, initial), config, durability="sync", version="v2"
            )
        except BaseException as error:
            held = policy.held
            if held is None:
                raise
            initial = None
            failure = (
                InputCountSaveError(held)
                if isinstance(held, HeldInputCount)
                else ResponseStepSaveError(held)
            )
            if isinstance(error, CancelledError) or policy.cancelled_response:
                raise ResultSaveCancelledError(failure) from error
            raise failure from error
        if result.interrupts:
            if controls is None:
                raise ValueError("Unexpected pause without a control binding")
            await controls.mark_paused()
            paused = native_agent_pause(await graph.aget_state(config))
            if paused is None:
                raise ValueError("The complete Step pause was not saved")
            return paused
        await runtime.ensure_active()
        return cast(ResponseStepState, result.value)

    return await retry_result_save(
        run_or_reconcile,
        errors=(InputCountSaveError, ResponseStepSaveError),
        policy=save_retry_policy or ResultSaveRetryPolicy(),
    )


async def read_native_agent_state(
    checkpointer: BaseCheckpointSaver[str],
    config: RunnableConfig,
    values: dict[str, Any],
) -> StateSnapshot:
    """以相同 factory topology 只讀已存 task/interrupt，不執行任何 callback。"""
    from langchain_core.tools import StructuredTool

    async def unavailable(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("A native history reader cannot execute effects or controls")

    io = ResponseStepRuntime(
        request_model=unavailable,
        ensure_active=unavailable,
        account_response=unavailable,
        count_input=unavailable,
        capacity_limits=values["capacity_limits"],
    )
    controls = ResponseLoopControls(unavailable, unavailable) if values["pause_enabled"] else None
    policy = NativePolicy(config["configurable"]["thread_id"], io, controls, None, "")
    tools = [
        StructuredTool.from_function(
            coroutine=unavailable,
            name=definition["name"],
            description=definition.get("description", ""),
            args_schema=definition["parameters"],
        )
        for definition in values["request_snapshot"]["tools"]
    ]
    graph = create_agent(
        NativeModel(policy=policy),
        tools=tools,
        middleware=[policy],
        state_schema=NativeAgentState,
        checkpointer=checkpointer,
    )
    return await graph.aget_state(config)


def native_agent_pause(snapshot: StateSnapshot) -> PausedResponseLoop | None:
    if not snapshot.interrupts:
        return None
    state = snapshot.values
    update = completed_step_update(cast(NativeAgentState, state))
    count = update["completed_steps"]
    interrupts = snapshot.interrupts
    if (
        len(interrupts) != 1
        or interrupts[0].value != {"kind": "step_pause", "completed_steps": count}
        or count < 1
    ):
        raise ValueError("The saved interrupt is not a complete Step pause")
    return PausedResponseLoop(
        interrupts[0].id,
        cast(
            ResponseStepState,
            {
                **deepcopy(state),
                **update,
            },
        ),
    )


def native_tool(
    definition: FunctionToolParam,
    binding: NativeToolBinding,
    ensure_active: Callable[[], Awaitable[None]],
) -> BaseTool:
    """標準 registry 配對 calls；固定命令跨 sync prepare 屏障才執行。"""
    from langchain_core.tools import StructuredTool

    async def prepare(state: ToolEffectState) -> ToolEffectState:
        await ensure_active()
        command = await binding.prepare(
            ResponseFunctionToolCall.model_validate(state["call"]), state["operation_id"]
        )
        if command is None:
            raise ValueError("A tool must return a command or a definite observation")
        return {"prepared": command}

    async def execute(state: ToolEffectState) -> ToolEffectState:
        await ensure_active()
        prepared = state["prepared"]
        output = prepared if isinstance(prepared, str) else await binding.execute(prepared)
        if not isinstance(output, str):
            raise TypeError("A tool must return a definite string observation")
        return {"output": output}

    graph = (
        StateGraph(ToolEffectState)
        .add_node("prepare", prepare)
        .add_node("execute", execute)
        .add_edge(START, "prepare")
        .add_edge("prepare", "execute")
        .add_edge("execute", END)
        .compile()
    )

    async def invoke(runtime: ToolRuntime, **kwargs: Any) -> str:
        try:
            state = runtime.state
            call = next(
                call
                for call in restore_response(state["response_snapshot"]).output
                if isinstance(call, ResponseFunctionToolCall)
                and call.call_id == runtime.tool_call_id
            )
            config: RunnableConfig = {
                **runtime.config,
                "configurable": {
                    key: value
                    for key, value in runtime.config["configurable"].items()
                    if key != "checkpoint_id"
                },
            }
            result = await graph.ainvoke(
                {
                    "request_id": state["request_id"],
                    "call": call.model_dump(mode="json", by_alias=True, exclude_unset=True),
                    "operation_id": uuid5(state["operation_seed"], call.call_id),
                },
                config,
                durability="sync",
            )
            return cast(str, result["output"])
        except ValidationError as error:
            # Owner 已回傳參數拒絕；漏出的驗證錯誤屬於內部失敗。
            raise RuntimeError("Internal tool validation failed") from error

    return StructuredTool.from_function(
        coroutine=invoke,
        name=definition["name"],
        description=definition.get("description", ""),
        args_schema=definition["parameters"],
    )
