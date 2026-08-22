"""Assembly of one professional consultant with progressively loaded methods."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from deepagents.backends import BackendProtocol
from deepagents.backends.utils import validate_path
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
from app.consultant.model_output import ConsultantModelOutput
from app.consultant.workspace_backend import ConsultantWorkspaceBackendBinding
from app.consultant.workspace_tools import (
    WORKSPACE_FILESYSTEM_TOOL_NAMES,
    WORKSPACE_TOOL_DESCRIPTIONS,
    CandidateCheckToolBinding,
    WorkspaceToolWaveMiddleware,
    build_check_candidate_document_tool,
)
from app.consultant.skill_backend import PackageSkillBackend


SKILLS_SYSTEM_PROMPT = """## Caliburn 專業分析方法

你是同一位專業職務分析顧問；下列 Skills 是可按需載入的方法，不是多個人格或固定階段。
本輪只有列出的 Skills 可用。每個實際用來形成結果的 Skill，都必須先用 read_file 完整讀取一次；只能讀取列出的 /skills/<skill-id>/SKILL.md。
先判斷現有 context 是否已足夠；足夠時不要為了展示而呼叫 Tool。/skills、/sources、/approved、/pending 是唯讀 workspace；/workspace 是同一份跨 turn 保留、non-authoritative 且唯一可編輯的工作草稿。只有前一波結果產生新的資料依賴時才使用第二波 lookup wave。

{skills_locations}{skills_load_warnings}

**本輪可用 Skills：**
{skills_list}

讀完本輪實際選用的方法後，把它們共同整合成一份結構化顧問結果。員工畫面只呈現一位顧問、必要的待審文件變更與至多一個主要問題；不得把 Skill 編排暴露成員工要操作的流程。

**提交前的最小契約：**
- 詳細 Current JD、pending review、員工來源與方法內容都從對應 VFS 路徑讀取；不要把整份資料複製到回覆或 context。
- 直接續編 /workspace 下既有的 canonical resources；不得從 approved 複製或重建另一份草稿。編輯後必須在獨立 wave 呼叫 check_candidate_document，依 compact observation 修復問題。
- Candidate JSON 的 Evidence 只填 `source_handle`、逐字 `quote`、`occurrence`（quote 唯一時填 null，重複時填 1-based 次序）與使用的 `skill_ids`；最終 structured output 才以 0 表示唯一 quote。不要填 offset、stable source UUID 或自行推導的位置。
- O／P／K／S 文件變更必須以 canonical resource 的 task handle 連到 Task；不得提交沒有 Task linkage 的 O／P／K／S。
- `question.kind=none` 時其他 question 欄位全為空、`basis_ordinal=0`。
- 一般下一題（next）只填 `text`、`answer_target`、`reason`、`basis_ordinal`；`current_understanding、choices、affected_work_ids、affected_branch 全部留空`。
- 必要澄清（required_clarification）才填 `current_understanding`、2–3 個 `choices`、既有 `affected_work_ids` 與 `affected_branch`，且 `answer_target` 留空。
"""


@dataclass(frozen=True)
class ProfessionalConsultantAgent:
    graph: Any
    skill_backend: PackageSkillBackend
    workspace_binding: ConsultantWorkspaceBackendBinding

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        raise WorkspaceAgentAsyncOnlyError(
            "workspace consultant agents are async-only; use ainvoke()"
        )

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self.graph.ainvoke(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.graph, name)


class WorkspaceAgentAsyncOnlyError(RuntimeError):
    """Raised when a workspace-backed consultant is invoked synchronously."""


class LookupWaveLimitExceeded(RuntimeError):
    pass


_LOOKUP_TOOL_NAMES = frozenset({"ls", "read_file", "grep"})
_EXTERNAL_DATA_LOOKUP_ROOTS = ("/sources", "/approved", "/pending")


class LookupWaveState(AgentState):
    run_lookup_wave_count: NotRequired[
        Annotated[int, UntrackedValue, PrivateStateAttr]
    ]


class LookupWaveLimitMiddleware(AgentMiddleware[LookupWaveState, Any]):
    """Count one wave for path-aware external document-data reads."""

    state_schema = LookupWaveState

    def __init__(self, *, tool_names: frozenset[str], run_limit: int) -> None:
        self.tool_names = tool_names
        self.run_limit = run_limit

    def _is_external_lookup(self, call: Mapping[str, Any]) -> bool:
        name = call.get("name")
        if name not in _LOOKUP_TOOL_NAMES or name not in self.tool_names:
            return False
        args = call.get("args")
        if not isinstance(args, Mapping):
            return False
        raw_path = args.get("file_path", args.get("path"))
        if name == "grep" and raw_path is None:
            return True
        if not isinstance(raw_path, str):
            return False
        try:
            path = validate_path(raw_path)
        except (TypeError, ValueError):
            return False
        if name == "grep" and path == "/":
            return True
        return any(
            path == root or path.startswith(root + "/")
            for root in _EXTERNAL_DATA_LOOKUP_ROOTS
        )

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
            self._is_external_lookup(call)
            for call in last_ai.tool_calls
            if isinstance(call, Mapping)
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

    def __init__(
        self,
        *,
        backend: BackendProtocol,
        receipt_backend: PackageSkillBackend | None = None,
        workspace_mode: bool = False,
    ) -> None:
        super().__init__(
            backend=backend,
            sources=[("/skills", "Caliburn")],
            system_prompt=SKILLS_SYSTEM_PROMPT,
        )
        self._package_backend = receipt_backend or backend
        self._workspace_mode = workspace_mode

    @override
    def before_agent(
        self,
        state: SkillsState,
        runtime: Runtime,
        config: RunnableConfig,
    ) -> dict[str, Any] | None:
        _reject_stale_skill_results(state, workspace_mode=self._workspace_mode)
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
        _reject_stale_skill_results(state, workspace_mode=self._workspace_mode)
        self._package_backend.begin_run()
        clean = dict(state)
        clean.pop("skills_metadata", None)
        clean.pop("skills_load_errors", None)
        update = await super().abefore_agent(clean, runtime, config) or {}
        update.setdefault("skills_load_errors", [])
        return update


def _reject_stale_skill_results(
    state: SkillsState,
    *,
    workspace_mode: bool = False,
) -> None:
    if workspace_mode:
        _reject_stale_workspace_read_receipts(state)
        return
    if any(
        isinstance(message, ToolMessage) and message.name == "read_file"
        for message in state.get("messages", [])
    ):
        raise ValueError(
            "interactive consultant input contains a stale Skill tool result"
        )


def _message_tool_calls(message: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(message, AIMessage):
        return tuple(call for call in message.tool_calls if isinstance(call, Mapping))
    if isinstance(message, Mapping) and message.get("type") == "ai":
        calls = message.get("tool_calls", ())
        if isinstance(calls, Sequence):
            return tuple(call for call in calls if isinstance(call, Mapping))
    return ()


def _read_file_receipt(message: Any) -> tuple[bool, str | None]:
    if isinstance(message, ToolMessage):
        return message.name == "read_file", message.tool_call_id
    if isinstance(message, Mapping) and message.get("type") == "tool":
        return message.get("name") == "read_file", message.get("tool_call_id")
    return False, None


def _reject_stale_workspace_read_receipts(state: SkillsState) -> None:
    messages = state.get("messages", [])
    if not isinstance(messages, Sequence):
        return
    for index, message in enumerate(messages):
        is_read_receipt, tool_call_id = _read_file_receipt(message)
        if not is_read_receipt:
            continue
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise ValueError("workspace read_file receipt is orphaned")
        matches = [
            call
            for prior in messages[:index]
            for call in _message_tool_calls(prior)
            if call.get("name") == "read_file" and call.get("id") == tool_call_id
        ]
        if not matches:
            raise ValueError("workspace read_file receipt is orphaned")
        if len(matches) != 1:
            raise ValueError("workspace read_file receipt is ambiguous")
        args = matches[0].get("args")
        path = args.get("file_path") if isinstance(args, Mapping) else None
        if not isinstance(path, str):
            raise ValueError("workspace read_file receipt has no valid path")
        try:
            canonical_path = validate_path(path)
        except (TypeError, ValueError) as error:
            raise ValueError("workspace read_file receipt has an invalid path") from error
        if canonical_path == "/skills" or canonical_path.startswith("/skills/"):
            raise ValueError("interactive consultant input contains a stale Skill tool result")


def build_professional_consultant_agent(
    *,
    model: BaseChatModel,
    execution: ResolvedExecution,
    selected_skill_ids: tuple[str, ...],
    context_middleware: AgentMiddleware | None = None,
    context_schema: type[Any] | None = None,
    workspace_binding: ConsultantWorkspaceBackendBinding,
    candidate_check_binding: CandidateCheckToolBinding,
) -> ProfessionalConsultantAgent:
    """Build the bounded agent using Deep Agents' Skill/read-file primitives."""

    if not selected_skill_ids:
        raise ValueError("an interactive consultant run requires at least one Skill")
    ineligible = set(selected_skill_ids) - set(execution.allowed_skill_ids)
    if ineligible:
        raise ValueError(f"agent requested ineligible Skills: {sorted(ineligible)}")
    if "read_file" not in execution.allowed_tool_ids:
        raise ValueError("resolved run policy must allow the read_file Skill tool")
    if execution.max_model_calls > 11:
        raise ValueError("interactive consultant runs allow at most eleven model calls")
    if execution.max_lookup_waves > 2:
        raise ValueError("interactive consultant runs allow at most two lookup waves")
    expected_tools = WORKSPACE_FILESYSTEM_TOOL_NAMES | {
        "check_candidate_document"
    }
    if set(execution.allowed_tool_ids) != expected_tools:
        raise ValueError("resolved run policy must allow exactly the workspace Tool surface")
    if workspace_binding.skill_backend.selected_skill_ids != selected_skill_ids:
        raise ValueError("workspace Skill binding must match selected Skills")
    if candidate_check_binding.workspace is not workspace_binding:
        raise ValueError("candidate check binding must use the agent workspace")

    backend: BackendProtocol = workspace_binding.composite_backend
    receipt_backend = workspace_binding.skill_backend
    check_tools = (
        build_check_candidate_document_tool(binding=candidate_check_binding),
    )
    skills = RunScopedSkillsMiddleware(
        backend=backend,
        receipt_backend=receipt_backend,
        workspace_mode=True,
    )
    files = FilesystemMiddleware(
        backend=backend,
        tools=sorted(WORKSPACE_FILESYSTEM_TOOL_NAMES),
        custom_tool_descriptions=WORKSPACE_TOOL_DESCRIPTIONS,
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    lookup_cap = LookupWaveLimitMiddleware(
        tool_names=frozenset({"ls", "read_file", "grep"}),
        run_limit=execution.max_lookup_waves,
    )
    graph = build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ConsultantModelOutput,
        tools=check_tools,
        additional_middleware=(
            skills,
            files,
            lookup_cap,
            WorkspaceToolWaveMiddleware(
                candidate_backend=workspace_binding.candidate_backend
            ),
        ),
        context_middleware=context_middleware,
        context_schema=context_schema,
    )
    return ProfessionalConsultantAgent(
        graph=graph,
        skill_backend=receipt_backend,
        workspace_binding=workspace_binding,
    )
