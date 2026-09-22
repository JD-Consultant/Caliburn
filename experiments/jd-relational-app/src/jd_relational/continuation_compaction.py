"""Non-destructive context compaction shared by the A, B1, and B2 loops.

The Saver's canonical messages remain untouched.  This middleware keeps one
validated continuation summary beside them and substitutes a request-only
view when calling the model.  It does not update consultant Memory, treat a
summary as employee evidence, select a provider, or grant business tools to
the summary call.
"""

from collections.abc import Callable
from hashlib import sha256
import json
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, ModelRequest
from langchain.agents.middleware.types import ExtendedModelResponse, ModelResponse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.config import get_config
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .openai_responses import accepted


SUMMARY_SYSTEM_PROMPT = """你只整理 agent 的工作上下文，不更新工作理解 Memory，也不改 JD。
請根據既有摘要與這次新完成的互動，產出可讓同一 agent 繼續工作的精簡摘要。
保留：目前目標、使用者更正、已完成動作與工具結果、仍未解問題、衝突或失敗、下一步。
只記錄受控輸入明確支持的狀態。某項動作、衝突、未知或下一步沒有出現在輸入時，直接省略；
不得把「未提及」推論或寫成「未完成」、「沒有發生」、「沒有待辦」或「已確認」。
不得把模型分析冒充成使用者原話；不得補寫輸入沒有的事實；不要輸出 JSON。"""

GENERIC_SUMMARY_INSTRUCTIONS = "保留完成進度、未解事項與下一個可執行步驟。"
A_SUMMARY_INSTRUCTIONS = """你正在替 A 主顧問延續訪談與 JD 工作。
優先保留訪談焦點、完整工作覆蓋缺口、員工已確認事實、更正、未知或衝突、尚缺資訊、最近問答進度，以及已完成 JD、Working State、來源讀取與背景通知的真實結果。
背景通知只能記為已通知或已取得 receipt，不能宣稱 B1／B2 或 Memory 更新已完成。不要複製完整 Working State、JD 或 Memory。"""
B1_SUMMARY_INSTRUCTIONS = """你正在替 B1 案例維護 Agent 延續工作。
優先保留來源或窗口處理位置、案例身分與差異、觸發與輸入、本人行動、判斷、成果、分工、條件、例外、更正、時間範圍、未知、已讀 evidence keys、staged 案例變更、驗證結果與下一步。
不要把案例直接抽象成穩定工作理解，也不要把摘要當成 canonical 訪談或引用。"""
B2_SUMMARY_INSTRUCTIONS = """你正在替 B2 工作理解 Agent 延續工作。
優先保留固定任務與 base orientation、B1 change set、已讀案例與理解、跨案例支持、反證與差異、共同穩定任務、責任、條件、例外、未知、staged 理解變更、case rework、衝突與下一步。
不要修改案例，不要把單一案例條件誤寫成共同模式，也不要因一個案例改變就假定其他案例一起改變。
固定任務與 base orientation 只用來判斷哪些進度相關；摘要只能寫相對於它們的新進度、差異與未解事項，
不得另列「目前目標」來重述、改寫或概括固定任務本身。"""

SUMMARY_REQUEST_LABEL = "【對話延續摘要｜不是員工原話，也不是工作理解 Memory】"


class ContinuationCompactionError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ContinuationCompaction(BaseModel):
    """One checkpointed summary, source boundary, and optional exact orientation.

    Format v1 covers a contiguous prefix. Format v2 is A-only and keeps the
    latest employee HumanMessage in that prefix verbatim beside the summary.
    Both IDs and the digest are derived and checked by the Runtime, never the
    model.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    format_version: int = Field(ge=1, le=2)
    summary_text: str = Field(min_length=1, max_length=65536)
    covered_through_message_id: str = Field(min_length=1, max_length=512)
    covered_prefix_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    protected_message_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
    )

    @model_validator(mode="after")
    def valid_format(self):
        if ((self.format_version == 1 and self.protected_message_id is not None)
                or (self.format_version == 2 and self.protected_message_id is None)):
            raise ValueError("invalid_compaction_format")
        return self


class ContinuationCompactionState(AgentState):
    continuation_compaction: dict[str, Any] | None


class CompactionProfile(BaseModel):
    """Role-specific policy; provider limits are supplied only at assembly."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    summary_instructions: str = Field(
        default=GENERIC_SUMMARY_INSTRUCTIONS,
        min_length=1,
        max_length=8192,
    )
    trigger_input_tokens: int = Field(default=16000, ge=1)
    keep_messages: int = Field(default=8, ge=1)
    summary_max_output_tokens: int = Field(default=2048, ge=1)
    preserve_initial_messages: int = Field(default=0, ge=0)
    protect_latest_human_turn: bool = True
    preserve_latest_human_message: bool = False
    hard_input_tokens: int | None = Field(default=None, ge=1)
    main_output_reserve_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def valid_limits(self):
        if (
            self.hard_input_tokens is not None
            and self.trigger_input_tokens + self.main_output_reserve_tokens
            >= self.hard_input_tokens
        ):
            raise ValueError("invalid_compaction_limits")
        if self.preserve_latest_human_message and (
            self.protect_latest_human_turn or self.preserve_initial_messages
        ):
            raise ValueError("invalid_compaction_protection")
        return self


A_COMPACTION_PROFILE = CompactionProfile(
    summary_instructions=A_SUMMARY_INSTRUCTIONS,
    protect_latest_human_turn=False,
    preserve_latest_human_message=True,
)
B1_COMPACTION_PROFILE = CompactionProfile(
    summary_instructions=B1_SUMMARY_INSTRUCTIONS,
    preserve_initial_messages=0,
    protect_latest_human_turn=True,
)
B2_COMPACTION_PROFILE = CompactionProfile(
    summary_instructions=B2_SUMMARY_INSTRUCTIONS,
    preserve_initial_messages=1,
    protect_latest_human_turn=False,
)


def _json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_prefix_digest(messages: list[BaseMessage]) -> str:
    """Bind a summary to the exact immutable canonical prefix it covers."""
    payload = [message.model_dump(mode="json") for message in messages]
    return "sha256:" + sha256(_json(payload).encode("utf-8")).hexdigest()


def _checked_compaction(
    value: Any,
    messages: list[BaseMessage],
    profile: CompactionProfile,
) -> tuple[ContinuationCompaction | None, int]:
    if value is None:
        return None, profile.preserve_initial_messages
    try:
        state = ContinuationCompaction.model_validate(value, strict=True)
        matches = [
            index
            for index, message in enumerate(messages)
            if message.id == state.covered_through_message_id
        ]
        if len(matches) != 1:
            raise ValueError()
        boundary = matches[0] + 1
        if boundary <= profile.preserve_initial_messages:
            raise ValueError()
        if canonical_prefix_digest(messages[:boundary]) != state.covered_prefix_digest:
            raise ValueError()
        if state.format_version == 2:
            if not profile.preserve_latest_human_message:
                raise ValueError()
            protected = [
                index for index, message in enumerate(messages[:boundary])
                if message.id == state.protected_message_id
            ]
            if (len(protected) != 1
                    or not isinstance(messages[protected[0]], HumanMessage)):
                raise ValueError()
            latest_human = next(
                (index for index in range(boundary - 1, -1, -1)
                 if isinstance(messages[index], HumanMessage)),
                None,
            )
            if latest_human != protected[0]:
                raise ValueError()
        return state, boundary
    except (ValidationError, ValueError, TypeError, AttributeError):
        raise ContinuationCompactionError("invalid_compaction_boundary") from None


def _summary_message(state: ContinuationCompaction) -> AIMessage:
    suffix = state.covered_prefix_digest.removeprefix("sha256:")[:16]
    return AIMessage(
        id=f"continuation-summary:{suffix}",
        content=f"{SUMMARY_REQUEST_LABEL}\n{state.summary_text}",
    )


def build_request_view(
    messages: list[BaseMessage],
    state: ContinuationCompaction | dict[str, Any] | None,
    profile: CompactionProfile,
) -> list[BaseMessage]:
    """Return a detached request view; never mutate canonical messages."""
    checked, boundary = _checked_compaction(state, messages, profile)
    if checked is None:
        return [message.model_copy(deep=True) for message in messages]
    if checked.format_version == 2:
        protected = next(
            message for message in messages[:boundary]
            if message.id == checked.protected_message_id
        )
        return [
            protected.model_copy(deep=True),
            _summary_message(checked),
            *(message.model_copy(deep=True) for message in messages[boundary:]),
        ]
    return [
        *(message.model_copy(deep=True)
          for message in messages[:profile.preserve_initial_messages]),
        _summary_message(checked),
        *(message.model_copy(deep=True) for message in messages[boundary:]),
    ]


def select_safe_boundary(
    messages: list[BaseMessage],
    profile: CompactionProfile,
) -> int | None:
    """Choose the latest completed old interaction without splitting tools."""
    if len(messages) <= profile.keep_messages + profile.preserve_initial_messages:
        return None
    maximum = len(messages) - profile.keep_messages
    if profile.protect_latest_human_turn:
        latest_human = next(
            (index for index in range(len(messages) - 1, -1, -1)
             if isinstance(messages[index], HumanMessage)),
            None,
        )
        if latest_human is not None:
            maximum = min(maximum, latest_human)
    if maximum <= profile.preserve_initial_messages:
        return None

    candidates: list[int] = []
    pending_tool_calls: set[str] = set()
    for index, message in enumerate(messages):
        boundary = index + 1
        if boundary > maximum:
            break
        if isinstance(message, AIMessage):
            if pending_tool_calls:
                continue
            call_ids = {
                call.get("id") for call in message.tool_calls
                if isinstance(call, dict) and isinstance(call.get("id"), str)
            }
            if message.tool_calls and len(call_ids) != len(message.tool_calls):
                pending_tool_calls = {"__invalid_tool_call__"}
            elif call_ids:
                pending_tool_calls = call_ids
            else:
                candidates.append(boundary)
        elif isinstance(message, ToolMessage):
            if message.tool_call_id in pending_tool_calls:
                pending_tool_calls.remove(message.tool_call_id)
                if not pending_tool_calls:
                    candidates.append(boundary)

    candidates = [
        boundary for boundary in candidates
        if boundary > profile.preserve_initial_messages
    ]
    return candidates[-1] if candidates else None


def _default_token_counter(request: ModelRequest, view: list[BaseMessage]) -> int:
    messages: list[BaseMessage] = []
    if request.system_message is not None:
        messages.append(request.system_message)
    messages.extend(view)
    return count_tokens_approximately(messages, tools=request.tools)


def _cancelled(request: ModelRequest) -> bool:
    stop_event = getattr(getattr(request.runtime, "context", None), "stop_event", None)
    return bool(stop_event is not None and stop_event.is_set())


def _summary_prompt(
    previous: ContinuationCompaction | None,
    incremental: list[BaseMessage],
    *,
    protected_orientation: list[BaseMessage] | tuple[()] = (),
) -> str:
    payload = {
        "protected_orientation": [
            _summary_input(message) for message in protected_orientation
        ],
        "existing_summary": previous.summary_text if previous else None,
        "new_completed_messages": [_summary_input(message) for message in incremental],
    }
    return "請更新對話延續摘要。以下是受控輸入：\n" + _json(payload)


def _summary_system_prompt(profile: CompactionProfile) -> str:
    return (
        f"{SUMMARY_SYSTEM_PROMPT}\n\n"
        "【本角色續作重點】\n"
        f"{profile.summary_instructions}\n\n"
        "protected_orientation 只供判斷相關性，仍會逐字留在主請求；"
        "摘要輸出不得包含它本身，也不得以目標、限制或下一步的形式重抄、"
        "改寫、概括或宣稱已由摘要取代；請直接從相對進度開始。"
    )


def _summary_input(message: BaseMessage) -> dict[str, Any]:
    """Project one canonical message to the semantics visible to the model."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": str(message.text)}
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": str(message.text)}
    if isinstance(message, AIMessage):
        value: dict[str, Any] = {
            "role": "assistant",
            "content": str(message.text),
        }
        if message.tool_calls:
            value["tool_calls"] = [{
                "name": call["name"],
                "args": call["args"],
                "id": call["id"],
            } for call in message.tool_calls]
        return value
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "content": str(message.text),
            "name": message.name,
            "tool_call_id": message.tool_call_id,
            "status": message.status,
        }
    return {"role": message.type, "content": str(message.text)}


class ContinuationCompactionMiddleware(AgentMiddleware):
    """Create one summary call at most, then atomically publish with main output."""

    state_schema = ContinuationCompactionState

    def __init__(
        self,
        *,
        summary_model: BaseChatModel,
        profile: CompactionProfile,
        token_counter: Callable[[ModelRequest, list[BaseMessage]], int] | None = None,
    ):
        self.summary_model = summary_model
        self.profile = profile
        self.token_counter = token_counter or _default_token_counter

    def _count(self, request: ModelRequest, view: list[BaseMessage]) -> int:
        try:
            count = self.token_counter(request, view)
        except Exception:
            raise ContinuationCompactionError("compaction_budget_unavailable") from None
        if type(count) is not int or count < 0:
            raise ContinuationCompactionError("compaction_budget_unavailable")
        return count

    def _over_hard_limit(self, tokens: int) -> bool:
        limit = self.profile.hard_input_tokens
        return (
            limit is not None
            and tokens + self.profile.main_output_reserve_tokens >= limit
        )

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        canonical = request.messages
        raw_state = request.state.get("continuation_compaction")
        try:
            previous, previous_boundary = _checked_compaction(
                raw_state, canonical, self.profile
            )
            current_view = build_request_view(canonical, previous, self.profile)
        except ContinuationCompactionError:
            canonical_view = [message.model_copy(deep=True) for message in canonical]
            canonical_tokens = self._count(request, canonical_view)
            if self._over_hard_limit(canonical_tokens):
                raise
            previous = None
            previous_boundary = self.profile.preserve_initial_messages
            current_view = canonical_view

        input_tokens = self._count(request, current_view)
        if input_tokens < self.profile.trigger_input_tokens:
            return handler(request.override(messages=current_view))
        if _cancelled(request):
            raise ContinuationCompactionError("compaction_cancelled")

        boundary = select_safe_boundary(canonical, self.profile)
        if boundary is None or boundary <= previous_boundary:
            if self._over_hard_limit(input_tokens):
                raise ContinuationCompactionError("compaction_no_safe_boundary")
            return handler(request.override(messages=current_view))
        boundary_message_id = canonical[boundary - 1].id
        if not boundary_message_id:
            raise ContinuationCompactionError("compaction_boundary_missing_id")

        protected_message: HumanMessage | None = None
        if self.profile.preserve_latest_human_message:
            latest_human = next(
                (index for index in range(len(canonical) - 1, -1, -1)
                 if isinstance(canonical[index], HumanMessage)),
                None,
            )
            if latest_human is not None and latest_human < boundary:
                protected_message = canonical[latest_human]

        incremental_start = max(
            previous_boundary,
            self.profile.preserve_initial_messages,
        )
        incremental: list[BaseMessage] = []
        if previous is not None and previous.format_version == 2:
            # A v2 summaries deliberately excluded this exact employee input.
            # Once a newer employee input takes over, fold the former protected
            # message into the cumulative summary so it cannot disappear.
            previous_protected = next(
                message for message in canonical[:previous_boundary]
                if message.id == previous.protected_message_id
            )
            if (protected_message is None
                    or previous_protected.id != protected_message.id):
                incremental.append(previous_protected)
        incremental.extend(
            message
            for message in canonical[incremental_start:boundary]
            if protected_message is None or message.id != protected_message.id
        )
        protected_orientation = list(
            canonical[:self.profile.preserve_initial_messages]
        )
        if protected_message is not None:
            protected_orientation.append(protected_message)
        prompt = _summary_prompt(
            previous,
            incremental,
            protected_orientation=protected_orientation,
        )
        summary_reply = self.summary_model.invoke(
            [
                SystemMessage(content=_summary_system_prompt(self.profile)),
                HumanMessage(content=prompt),
            ],
            config=get_config(),
            max_tokens=self.profile.summary_max_output_tokens,
        )
        if (
            not isinstance(summary_reply, AIMessage)
            or summary_reply.tool_calls
            or summary_reply.invalid_tool_calls
            or not accepted(summary_reply)
            or not summary_reply.text.strip()
        ):
            raise ContinuationCompactionError("invalid_compaction_summary")
        if _cancelled(request):
            raise ContinuationCompactionError("compaction_cancelled")

        published = ContinuationCompaction(
            format_version=2 if protected_message is not None else 1,
            summary_text=summary_reply.text.strip(),
            covered_through_message_id=boundary_message_id,
            covered_prefix_digest=canonical_prefix_digest(canonical[:boundary]),
            protected_message_id=(
                protected_message.id if protected_message is not None else None
            ),
        )
        compacted_view = build_request_view(canonical, published, self.profile)
        response = handler(request.override(messages=compacted_view))
        if (
            not isinstance(response, ModelResponse)
            or len(response.result) != 1
            or not isinstance(response.result[0], AIMessage)
            or response.result[0].invalid_tool_calls
            or not accepted(response.result[0])
        ):
            raise ContinuationCompactionError("incomplete_compacted_model_response")
        return ExtendedModelResponse(
            model_response=response,
            command=Command(update={
                "continuation_compaction": published.model_dump(mode="json")
            }),
        )
