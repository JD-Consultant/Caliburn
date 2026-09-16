"""JD-only model context using LangChain's native model-node middleware.

LangChain 1.4.0 ExtendedModelResponse/Command applies the response and this
binding in one model step. It does not make a SQL transaction or prove a root
checkpoint closed. The caller owns foreground admission, a fixed run ID and the
initial notice. This module never starts a provider, rewrites HumanMessages,
updates Memory, retries a model, or grants writer authority.
"""

from dataclasses import dataclass
from collections.abc import Callable
from hashlib import sha256
import json
from threading import Event
from typing import Any
from uuid import UUID, uuid4

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import ExtendedModelResponse, ModelResponse
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.config import get_config
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .continuation_compaction import ContinuationCompactionState
from .notice_history import NoticeBoundary, NoticeHistoryReader, NoticeMaterial
from .openai_responses import accepted
from .references import ReferenceCodec, SignedReference

MAX_NOTICE_BYTES = 65536
NOTICE_INSTRUCTION = (
    "這是App提供的已保存JD事件，不是員工原話，也不是已讀完JD的證明。"
    "工作以目前內容為準；需要文字與確切變更時使用jd_read或jd_change_read。"
    "事件改了又改回仍算修改；沒有列完的事件可依history_anchor讀原歷史。"
    "知道有改動不代表本輪必須修改JD；JD還原不代表撤回訪談或Memory。"
    "標了took_back_an_ai_turn的事件，是員工把那一輪對JD的改動整輪取回；"
    "那一輪的對話、原話與工作理解都還在，不要當成沒發生過，也不要自行重做一次。"
)


class ConsultantContextError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value):
    return sha256(value.encode("utf-8")).hexdigest()


class ModelView(BaseModel):
    """Internal checkpoint binding; none of these fields are model parameters."""
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    format_version: int = Field(ge=1, le=1)
    dataset_id: str
    document_id: str
    run_id: str
    revision_id: str
    revision_number: int = Field(ge=1)
    response_message_id: str = Field(min_length=1, max_length=512)
    response_digest: str = Field(pattern="^[0-9a-f]{64}$")
    notice_json: str = Field(min_length=1, max_length=MAX_NOTICE_BYTES)
    notice_digest: str = Field(pattern="^[0-9a-f]{64}$")

    @field_validator("dataset_id", "document_id", "run_id", "revision_id")
    @classmethod
    def valid_uuid(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("invalid_context_identity")
        return value

    @property
    def boundary(self):
        return NoticeBoundary(UUID(self.revision_id), self.revision_number)


class ConsultantState(ContinuationCompactionState):
    jd_memory_view: dict[str, Any] | None
    jd_model_view: dict[str, Any] | None
    jd_ai_run: dict[str, Any] | None
    jd_ai_bindings: list[dict[str, Any]]
    jd_ai_read: dict[str, Any] | None
    jd_memory_repair_bindings: list[dict[str, Any]]


@dataclass(frozen=True)
class ConsultantContext:
    dataset_id: str
    document_id: str
    run_id: str
    history: NoticeHistoryReader
    codec: ReferenceCodec
    turn_notice: NoticeMaterial
    event_limit: int = 20
    tool_session: object | None = None
    stop_event: Event | None = None
    # Trusted, run-scoped source owner. It validates the actual request before
    # supplying metadata; original bodies remain in their original messages.
    source_notice: Callable | None = None
    memory_session: object | None = None
    memory_repair_session: object | None = None

    def __post_init__(self):
        try:
            if any(str(UUID(x)) != x for x in (self.dataset_id, self.document_id, self.run_id)):
                raise ValueError()
            if self.codec.dataset_id != self.dataset_id or self.turn_notice.document_id != self.document_id:
                raise ValueError()
            if type(self.event_limit) is not int or not 1 <= self.event_limit <= 20:
                raise ValueError()
            if self.stop_event is not None and not isinstance(self.stop_event, Event):
                raise ValueError()
            if self.source_notice is not None and not callable(self.source_notice):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ConsultantContextError("invalid_consultant_context") from None


def checked_model_view(value, *, dataset_id, document_id):
    if value is None:
        return None
    try:
        result = ModelView.model_validate(value, strict=True)
        if result.dataset_id != dataset_id or result.document_id != document_id:
            raise ValueError()
        if len(result.notice_json.encode("utf-8")) > MAX_NOTICE_BYTES or _digest(result.notice_json) != result.notice_digest:
            raise ValueError()
        notice = json.loads(result.notice_json)
        if notice["type"] != "jd_change_notice" or notice["current_revision_number"] != result.revision_number:
            raise ValueError()
        return result
    except (ValidationError, ValueError, TypeError, AttributeError, KeyError):
        raise ConsultantContextError("invalid_model_view") from None


def _material_notice(material, codec):
    def revision(boundary):
        return codec.issue(SignedReference(document_id=material.document_id,
            revision_id=str(boundary.revision_id), purpose="history", role="revision", kind="revision"))
    return {
        "first_notification": material.baseline is None,
        "baseline_revision_number": material.baseline.revision_number if material.baseline else None,
        "through_revision_number": material.head.revision_number,
        "history_anchor": revision(material.head),
        "manual_change_count": material.manual_count,
        "ai_change_count": material.ai_count,
        "omitted_count": material.omitted_count,
        "events": [{
            "origin": event.origin, "kind": event.command_kind,
            # A marker, not an identity: every other identity in this notice is
            # a signed reference, and the model has no tool that takes a run id.
            **({"took_back_an_ai_turn": True} if event.undone_ai_run_id else {}),
            "result_revision_number": event.result_revision_number,
            "change_ref": codec.issue(SignedReference(document_id=material.document_id,
                revision_id=str(event.result_revision_id), purpose="observation", role="change",
                kind="change", entity_id=str(event.operation_id))),
        } for event in material.events],
        "content_included": False,
    }


def _project(request):
    context = request.runtime.context
    if not isinstance(context, ConsultantContext):
        raise ConsultantContextError("invalid_consultant_context")
    # Runtime context and graph thread configuration are separate inputs.
    # Check the native runnable context before any document read/model call.
    if get_config().get("configurable", {}).get("thread_id") != context.document_id:
        raise ConsultantContextError("consultant_thread_mismatch")
    if context.stop_event is not None and context.stop_event.is_set():
        raise ConsultantContextError("consultant_cancelled")
    previous = checked_model_view(request.state.get("jd_model_view"),
        dataset_id=context.dataset_id, document_id=context.document_id)
    # The first notice remains reachable throughout this AI turn, even after
    # its first model response advanced the per-response boundary.
    if previous is None or previous.run_id != context.run_id:
        if context.turn_notice.baseline != (previous.boundary if previous else None):
            raise ConsultantContextError("turn_notice_mismatch")
    current = context.history.read(context.document_id,
        previous.boundary if previous else None, limit=context.event_limit)
    if current.head.revision_number < context.turn_notice.head.revision_number:
        raise ConsultantContextError("turn_notice_mismatch")
    notice = {"type": "jd_change_notice", "current_revision_number": current.head.revision_number,
        "instruction": NOTICE_INSTRUCTION, "turn_start": _material_notice(context.turn_notice, context.codec)}
    if current != context.turn_notice:
        notice["since_previous_response"] = _material_notice(current, context.codec)
    text = _json(notice)
    if len(text.encode("utf-8")) > MAX_NOTICE_BYTES:
        raise ConsultantContextError("notice_too_large")
    blocks = []
    if request.system_message:
        content = request.system_message.content
        blocks.extend([{"type": "text", "text": content}] if isinstance(content, str) else content)
    # Only trusted counts, command names and issued refs enter system context;
    # employee/task text stays in original messages or actual tool results.
    settings = dict(request.model_settings)
    if request.tools:
        settings["parallel_tool_calls"] = False
        settings["strict"] = True
    blocks.append({"type": "text", "text": text})
    if context.source_notice is not None:
        try:
            source = _json(context.source_notice(request.messages))
            if len(source.encode("utf-8")) > MAX_NOTICE_BYTES:
                raise ValueError()
        except Exception:
            raise ConsultantContextError("source_not_available") from None
        blocks.append({"type": "text", "text": source})
    if context.memory_session is not None:
        from .memory_context import memory_session
        # ModelRequest state is the native step state, not a model parameter.
        from types import SimpleNamespace
        memory = memory_session(SimpleNamespace(context=context, state=request.state,
                                                store=request.runtime.store))
        blocks.append({"type": "text", "text": _json(memory.notice())})
    projected = request.override(system_message=SystemMessage(content=blocks),
        model_settings=settings)
    return projected, context, current.head, text


def _bound_response(response, context, head, notice):
    if not isinstance(response, ModelResponse) or len(response.result) != 1:
        raise ConsultantContextError("invalid_consultant_response")
    message = response.result[0]
    # The same terminal rule every role uses: a reply cut off at the output
    # ceiling arrives as `incomplete`, never as a short success, and a refusal
    # is not an answer. HTTP 200 alone proves neither.
    if (not isinstance(message, AIMessage) or message.type != "ai"
            or message.invalid_tool_calls or not accepted(message)):
        raise ConsultantContextError("incomplete_consultant_response")
    if not message.id:
        message = message.model_copy(update={"id": str(uuid4())})
        response = ModelResponse(result=[message], structured_response=response.structured_response)
    view = ModelView(format_version=1, dataset_id=context.dataset_id,
        document_id=context.document_id, run_id=context.run_id, revision_id=str(head.revision_id),
        revision_number=head.revision_number, response_message_id=message.id,
        response_digest=_digest(_json(message.model_dump(mode="json"))),
        notice_json=notice, notice_digest=_digest(notice))
    return ExtendedModelResponse(model_response=response,
        command=Command(update={"jd_model_view": view.model_dump(mode="json")}))


class JdNoticeMiddleware(AgentMiddleware):
    state_schema = ConsultantState

    def wrap_model_call(self, request, handler):
        projected, context, head, notice = _project(request)
        return _bound_response(handler(projected), context, head, notice)

    async def awrap_model_call(self, request, handler):
        # The existing SQL reader is synchronous; keep it off the async loop.
        import asyncio
        projected, context, head, notice = await asyncio.to_thread(_project, request)
        return _bound_response(await handler(projected), context, head, notice)


def read_closed_model_view(graph, *, document_id, dataset_id, run_id):
    """Observe a CLOSED pinned root, never replay/promote an unfinished child.

    LangGraph latest get_state may overlay pending writes. Re-read its exact
    checkpoint ID and require no tasks/next before calling it a closed root.
    Caller still owns host/run exclusion; this read is not admission or a lock.
    """
    latest = graph.get_state({"configurable": {"thread_id": document_id}}, subgraphs=True)
    location = latest.config.get("configurable", {}) if latest.config else {}
    if (not location.get("checkpoint_id") or location.get("thread_id") != document_id
            or location.get("checkpoint_ns", "") != ""):
        raise ConsultantContextError("consultant_checkpoint_unconfirmed")
    pinned = graph.get_state(latest.config, subgraphs=True)
    if pinned.next or pinned.tasks or pinned.interrupts:
        raise ConsultantContextError("consultant_checkpoint_unconfirmed")
    pinned_location = pinned.config.get("configurable", {}) if pinned.config else {}
    if (pinned_location.get("thread_id") != document_id
            or pinned_location.get("checkpoint_ns", "") != ""
            or pinned_location.get("checkpoint_id") != location["checkpoint_id"]):
        raise ConsultantContextError("consultant_checkpoint_unconfirmed")
    view = checked_model_view(pinned.values.get("jd_model_view"), dataset_id=dataset_id, document_id=document_id)
    if view is None or view.run_id != run_id:
        raise ConsultantContextError("consultant_checkpoint_unconfirmed")
    messages = [m for m in pinned.values.get("messages", ()) if isinstance(m, AIMessage) and m.id == view.response_message_id]
    if len(messages) != 1 or _digest(_json(messages[0].model_dump(mode="json"))) != view.response_digest:
        raise ConsultantContextError("consultant_checkpoint_unconfirmed")
    return view


def build_consultant_node(model, *, tools, guidance: str, extra_middleware=(),
                          context_middleware=None):
    """Build the native child; the host injects owned tools/run context later.

    No checkpointer, provider configuration or document is created here. Scope
    and tool-call execution stay with the App, not generated model parameters.
    """
    from langchain.agents import create_agent
    from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
    from .consultant_model import (
        MAX_MODEL_STEPS, MAX_TOOL_CALLS, OPENROUTER_PROVIDER, ReceiptChatOpenRouter,
    )
    from .inspection_model import InspectionOnly, InspectionGuard
    inspection = type(model) is InspectionOnly
    # One provider, checked by what the assembly actually configured. A model
    # that stores the conversation server-side, retries on its own or answers
    # with parallel tool calls is not this role's model.
    route = {"only": [OPENROUTER_PROVIDER], "order": [OPENROUTER_PROVIDER],
             "allow_fallbacks": False, "require_parameters": True}
    provider_valid = (isinstance(model, ReceiptChatOpenRouter)
        and model.openrouter_provider == route and model.max_retries == 0
        and model.model_kwargs.get("parallel_tool_calls") is False
        and (model.reasoning or {}).get("effort") == "high")
    if ((not provider_valid and not inspection)
            or not isinstance(extra_middleware, (list, tuple))
            or any(not isinstance(value, AgentMiddleware) for value in extra_middleware)
            or (context_middleware is not None
                and not isinstance(context_middleware, AgentMiddleware))
            or not isinstance(guidance, str) or not guidance.strip()):
        raise ConsultantContextError("invalid_consultant_configuration")
    # This role's verified budgets, declared where the agent is assembled.
    middleware = [JdNoticeMiddleware(),
                  *extra_middleware,
                  ModelCallLimitMiddleware(thread_limit=MAX_MODEL_STEPS, exit_behavior="end"),
                  ToolCallLimitMiddleware(thread_limit=MAX_TOOL_CALLS, exit_behavior="end"),
                  # Request-only context projection must run after every
                  # middleware that appends Skills or App notices, otherwise
                  # its budget is not the request that reaches the model.
                  *([context_middleware] if context_middleware is not None else [])]
    if inspection:
        from .consultant_tools import AiToolMiddleware
        # Only this known layout has its non-wrap hook guarded. Unknown hooks
        # cannot be made inspection-only by wrapping model/tool execution.
        if (context_middleware is not None or len(extra_middleware) != 1
                or type(extra_middleware[0]) is not AiToolMiddleware):
            raise ConsultantContextError("invalid_consultant_configuration")
        middleware = [InspectionGuard(), JdNoticeMiddleware(), AiToolMiddleware(inspection_only=True)]
    return create_agent(model, tools=tools, system_prompt=guidance,
        middleware=middleware, state_schema=ConsultantState,
        context_schema=ConsultantContext)
