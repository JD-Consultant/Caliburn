from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, NotRequired

from deepagents.backends import StateBackend
from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware import FilesystemMiddleware, SkillsMiddleware
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
    ModelResponse,
    ToolCallLimitMiddleware,
)
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import AIMessage, SystemMessage
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_openrouter import ChatOpenRouter
from langgraph.runtime import Runtime
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ConsultantModelProfile:
    profile_id: str
    model_id: str
    temperature: float | None
    max_completion_tokens: int | None
    reasoning: dict[str, Any] | None
    provider_order: tuple[str, ...]
    allow_fallbacks: bool
    require_parameters: bool

    def build(self, *, api_key: str) -> ChatOpenRouter:
        return ChatOpenRouter(
            model=self.model_id,
            api_key=api_key,
            temperature=self.temperature,
            max_completion_tokens=self.max_completion_tokens,
            reasoning=self.reasoning,
            openrouter_provider={
                "order": list(self.provider_order),
                "allow_fallbacks": self.allow_fallbacks,
                "require_parameters": self.require_parameters,
            },
        )


@dataclass(frozen=True)
class ConsultantRunContext:
    operation_id: str
    document_id: str
    focus: dict[str, Any]
    progress: dict[str, Any]
    current_jd: dict[str, Any]
    effective_source_ids: tuple[str, ...]
    available_source_ids: tuple[str, ...]
    eligible_skill_names: tuple[str, ...]
    source_token_budget: int


class ConsultantTurn(BaseModel):
    visible_message: str
    used_skill_names: list[str]
    used_source_ids: list[str]
    next_focus: str


class ConsultantContractViolation(ValueError):
    pass


def verify_consultant_turn(
    turn: ConsultantTurn,
    context: ConsultantRunContext,
) -> None:
    ineligible_skills = set(turn.used_skill_names) - set(context.eligible_skill_names)
    if ineligible_skills:
        raise ConsultantContractViolation(
            f"ineligible skills used: {sorted(ineligible_skills)}"
        )
    unavailable_sources = set(turn.used_source_ids) - set(
        context.available_source_ids
    )
    if unavailable_sources:
        raise ConsultantContractViolation(
            f"unavailable sources used: {sorted(unavailable_sources)}"
        )


class ConsultantAgentState(AgentState[ConsultantTurn]):
    context_pack: NotRequired[str]
    context_manifest: NotRequired[dict[str, Any]]


def _message_text(message: BaseMessage) -> str:
    content = message.content
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)


class ScriptedChatModel(BaseChatModel):
    """Deterministic tool-capable model used only by the conformance probe."""

    responses: list[AIMessage]
    response_index: int = 0
    call_count: int = 0
    system_prompts: list[str] = Field(default_factory=list, exclude=True)
    captured_text: list[list[str]] = Field(default_factory=list, exclude=True)
    bound_tool_names: list[str] = Field(default_factory=list, exclude=True)

    @property
    def _llm_type(self) -> str:
        return "caliburn-scripted-chat-model"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable[..., Any] | Any],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        del tool_choice, kwargs
        self.bound_tool_names = [
            convert_to_openai_tool(tool)["function"]["name"] for tool in tools
        ]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.system_prompts.append(
            "\n".join(
                _message_text(message)
                for message in messages
                if isinstance(message, SystemMessage)
            )
        )
        self.captured_text.append([_message_text(message) for message in messages])
        response = self.responses[min(self.response_index, len(self.responses) - 1)]
        self.response_index += 1
        self.call_count += 1
        return ChatResult(generations=[ChatGeneration(message=response)])


class ContextPackMiddleware(
    AgentMiddleware[ConsultantAgentState, ConsultantRunContext, ConsultantTurn]
):
    state_schema = ConsultantAgentState

    async def abefore_agent(
        self,
        state: ConsultantAgentState,
        runtime: Runtime[ConsultantRunContext],
    ) -> dict[str, Any]:
        del state
        context = runtime.context
        if runtime.store is None:
            raise RuntimeError("ContextPack requires a LangGraph Store")

        included: list[str] = []
        omitted: list[str] = []
        source_lines: list[str] = []
        used_tokens = 0
        namespace = ("job-analysis", context.document_id, "sources")
        for source_id in context.effective_source_ids:
            item = await runtime.store.aget(namespace, source_id)
            if item is None:
                omitted.append(source_id)
                continue
            line = f"- [{source_id}] {item.value['text']}"
            # A stable conservative approximation is enough for the mechanism
            # probe; production can delegate to the selected model tokenizer.
            estimated_tokens = max(1, len(line) // 4)
            if used_tokens + estimated_tokens > context.source_token_budget:
                omitted.append(source_id)
                continue
            source_lines.append(line)
            included.append(source_id)
            used_tokens += estimated_tokens

        pack = "\n".join(
            [
                "你是 AI 專業職務分析顧問。只提出候選，不得直接修改 Current JD。",
                f"operation_id: {context.operation_id}",
                f"focus: {json.dumps(context.focus, ensure_ascii=False, sort_keys=True)}",
                f"progress: {json.dumps(context.progress, ensure_ascii=False, sort_keys=True)}",
                f"current_jd: {json.dumps(context.current_jd, ensure_ascii=False, sort_keys=True)}",
                "available_source_ids: " + ", ".join(context.available_source_ids),
                "selected_employee_sources:",
                *(source_lines or ["- none"]),
            ]
        )
        manifest = {
            "operation_id": context.operation_id,
            "included_source_ids": included,
            "omitted_source_ids": omitted,
            "available_source_ids": list(context.available_source_ids),
            "eligible_skill_names": list(context.eligible_skill_names),
            "estimated_source_tokens": used_tokens,
            "source_token_budget": context.source_token_budget,
        }
        return {"context_pack": pack, "context_manifest": manifest}

    async def awrap_model_call(
        self,
        request: ModelRequest[ConsultantRunContext],
        handler: Callable[
            [ModelRequest[ConsultantRunContext]],
            Any,
        ],
    ) -> ModelResponse[ConsultantTurn]:
        existing = (
            _message_text(request.system_message)
            if request.system_message is not None
            else ""
        )
        context_pack = request.state.get("context_pack", "")
        system_message = SystemMessage(
            content="\n\n".join(part for part in (existing, context_pack) if part)
        )
        return await handler(request.override(system_message=system_message))


class EligibleSkillsMiddleware(SkillsMiddleware):
    """Reuse Deep Agents discovery/read mechanics, filter metadata per run."""

    def modify_request(
        self,
        request: ModelRequest[ConsultantRunContext],
    ) -> ModelRequest[ConsultantRunContext]:
        eligible = set(request.runtime.context.eligible_skill_names)
        filtered_state = dict(request.state)
        filtered_state["skills_metadata"] = [
            skill
            for skill in request.state.get("skills_metadata", [])
            if skill["name"] in eligible
        ]
        return super().modify_request(request.override(state=filtered_state))


@tool
async def lookup_source(
    source_id: str,
    runtime: ToolRuntime[ConsultantRunContext],
) -> str:
    """Read one employee Source that the current ContextManifest exposes."""
    context = runtime.context
    if source_id not in context.available_source_ids:
        return "SOURCE_NOT_AVAILABLE_IN_THIS_OPERATION"
    if runtime.store is None:
        return "SOURCE_STORE_UNAVAILABLE"
    item = await runtime.store.aget(
        ("job-analysis", context.document_id, "sources"), source_id
    )
    if item is None:
        return "SOURCE_NOT_FOUND"
    return json.dumps(
        {"source_id": source_id, "text": item.value["text"]},
        ensure_ascii=False,
        sort_keys=True,
    )


_SKILLS_PROMPT = """## Eligible Skills

Only the skills listed below are eligible for this operation. Their descriptions
are discovery metadata, not the full instructions. Read a SKILL.md only when its
method is needed, and never claim a skill was used unless you read it.

{skills_locations}
{skills_load_warnings}
{skills_list}
"""


def build_consultant_agent(
    *,
    model: BaseChatModel,
    backend: BackendProtocol | None = None,
    checkpointer: Any,
    store: Any,
) -> Any:
    skill_backend = backend or StateBackend()
    middleware = [
        ContextPackMiddleware(),
        FilesystemMiddleware(backend=skill_backend, tools=["read_file"]),
        EligibleSkillsMiddleware(
            backend=skill_backend,
            sources=["/skills/"],
            system_prompt=_SKILLS_PROMPT,
        ),
        ModelCallLimitMiddleware(run_limit=3, exit_behavior="error"),
        ToolCallLimitMiddleware(
            tool_name="read_file", run_limit=1, exit_behavior="end"
        ),
        ToolCallLimitMiddleware(
            tool_name="lookup_source", run_limit=2, exit_behavior="end"
        ),
    ]
    return create_agent(
        model=model,
        tools=[lookup_source],
        middleware=middleware,
        response_format=ToolStrategy(ConsultantTurn),
        state_schema=ConsultantAgentState,
        context_schema=ConsultantRunContext,
        checkpointer=checkpointer,
        store=store,
        name="caliburn-consultant-runtime-spike",
    )
