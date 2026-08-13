"""Assembly of one professional consultant with progressively loaded methods."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.skills import SkillsMiddleware, SkillsState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, PrivateStateAttr
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired, override

from app.consultant.model_runtime import ResolvedExecution, build_consultant_agent
from app.consultant.results import ConsultantResult
from app.consultant.skill_backend import PackageSkillBackend


SKILLS_SYSTEM_PROMPT = """## Caliburn 專業分析方法

你是同一位專業職務分析顧問；下列 Skills 是可按需載入的方法，不是多個人格或固定階段。
本輪只有列出的 Skills 可用。每個實際用來形成結果的 Skill，都必須先用 read_file 完整讀取一次；不要重複讀取，也不要嘗試其他路徑。

{skills_locations}{skills_load_warnings}

**本輪可用 Skills：**
{skills_list}

完整閱讀後，把方法共同整合成一份 ConsultantResult。員工畫面只呈現一位顧問、必要的待審文件變更與至多一個主要問題；不得把 Skill 編排暴露成員工要操作的流程。
"""


@dataclass(frozen=True)
class ProfessionalConsultantAgent:
    graph: Any
    skill_backend: PackageSkillBackend

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return self.graph.invoke(*args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self.graph.ainvoke(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.graph, name)


class LookupWaveLimitExceeded(RuntimeError):
    pass


class LookupWaveState(AgentState):
    run_lookup_wave_count: NotRequired[
        Annotated[int, UntrackedValue, PrivateStateAttr]
    ]


class LookupWaveLimitMiddleware(AgentMiddleware[LookupWaveState, Any]):
    """Count one wave per model message, not one per parallel lookup call."""

    state_schema = LookupWaveState

    def __init__(self, *, tool_names: frozenset[str], run_limit: int) -> None:
        self.tool_names = tool_names
        self.run_limit = run_limit

    @override
    def after_model(
        self,
        state: LookupWaveState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del runtime
        last_ai = next(
            (
                message
                for message in reversed(state.get("messages", []))
                if isinstance(message, AIMessage)
            ),
            None,
        )
        if last_ai is None or not any(
            call["name"] in self.tool_names for call in last_ai.tool_calls
        ):
            return None
        count = state.get("run_lookup_wave_count", 0) + 1
        if count > self.run_limit:
            raise LookupWaveLimitExceeded(
                f"consultant run exceeded {self.run_limit} lookup waves"
            )
        return {"run_lookup_wave_count": count}

    async def aafter_model(
        self,
        state: LookupWaveState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)


class RunScopedSkillsMiddleware(SkillsMiddleware):
    """Refresh framework Skill metadata so a prior turn cannot leak eligibility."""

    def __init__(self, *, backend: PackageSkillBackend) -> None:
        super().__init__(
            backend=backend,
            sources=[("/skills", "Caliburn")],
            system_prompt=SKILLS_SYSTEM_PROMPT,
        )
        self._package_backend = backend

    @override
    def before_agent(
        self,
        state: SkillsState,
        runtime: Runtime,
        config: RunnableConfig,
    ) -> dict[str, Any] | None:
        _reject_stale_skill_results(state)
        self._package_backend.begin_run()
        clean = dict(state)
        clean.pop("skills_metadata", None)
        clean.pop("skills_load_errors", None)
        update = super().before_agent(clean, runtime, config) or {}
        update.setdefault("skills_load_errors", [])
        return update

    async def abefore_agent(
        self,
        state: SkillsState,
        runtime: Runtime,
        config: RunnableConfig,
    ) -> dict[str, Any] | None:
        _reject_stale_skill_results(state)
        self._package_backend.begin_run()
        clean = dict(state)
        clean.pop("skills_metadata", None)
        clean.pop("skills_load_errors", None)
        update = await super().abefore_agent(clean, runtime, config) or {}
        update.setdefault("skills_load_errors", [])
        return update


def _reject_stale_skill_results(state: SkillsState) -> None:
    if any(
        isinstance(message, ToolMessage) and message.name == "read_file"
        for message in state.get("messages", [])
    ):
        raise ValueError(
            "interactive consultant input contains a stale Skill tool result"
        )


def build_professional_consultant_agent(
    *,
    model: BaseChatModel,
    execution: ResolvedExecution,
    selected_skill_ids: tuple[str, ...],
    context_middleware: AgentMiddleware | None = None,
    context_schema: type[Any] | None = None,
) -> ProfessionalConsultantAgent:
    """Build the bounded agent using Deep Agents' Skill/read-file primitives."""

    if not selected_skill_ids:
        raise ValueError("an interactive consultant run requires at least one Skill")
    ineligible = set(selected_skill_ids) - set(execution.allowed_skill_ids)
    if ineligible:
        raise ValueError(f"agent requested ineligible Skills: {sorted(ineligible)}")
    if "read_file" not in execution.allowed_tool_ids:
        raise ValueError("resolved run policy must allow the read_file Skill tool")
    if execution.max_model_calls > 3:
        raise ValueError("interactive consultant runs allow at most three model calls")
    if execution.max_lookup_waves > 2:
        raise ValueError("interactive consultant runs allow at most two lookup waves")

    backend = PackageSkillBackend(selected_skill_ids)
    skills = RunScopedSkillsMiddleware(backend=backend)
    files = FilesystemMiddleware(
        backend=backend,
        tools=["read_file"],
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    lookup_cap = LookupWaveLimitMiddleware(
        tool_names=frozenset(
            {
                "read_file",
                "source_by_id",
                "source_lineage",
                "source_lexical_search",
                "source_semantic_search",
            }
            & set(execution.allowed_tool_ids)
        ),
        run_limit=execution.max_lookup_waves,
    )
    graph = build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ConsultantResult,
        additional_middleware=(skills, files, lookup_cap),
        context_middleware=context_middleware,
        context_schema=context_schema,
    )
    return ProfessionalConsultantAgent(graph=graph, skill_backend=backend)
