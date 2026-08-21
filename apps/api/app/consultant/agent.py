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
from langchain_core.tools import BaseTool
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired, override

from app.consultant.model_runtime import ResolvedExecution, build_consultant_agent
from app.consultant.model_output import ConsultantModelOutput
from app.consultant.candidate_tool import (
    CandidateEditToolBinding,
    build_job_document_candidate_edit_tool,
)
from app.consultant.workspace_backend import ConsultantWorkspaceBackendBinding
from app.consultant.workspace_tools import (
    WORKSPACE_FILESYSTEM_TOOL_NAMES,
    WORKSPACE_TOOL_DESCRIPTIONS,
    CandidateCheckToolBinding,
    WorkspaceToolWaveMiddleware,
    build_check_candidate_document_tool,
)
from app.consultant.skill_backend import (
    DirectPackageSkillBackendAdapter,
    PackageSkillBackend,
)


SKILL_READ_TOOL_DESCRIPTION = (
    "Read one eligible Caliburn analysis Skill in full. "
    "Use only the exact /skills/<skill-id>/SKILL.md path listed for this run. "
    "Omit offset and limit; the server scopes access and records the loaded Skill."
)


SKILLS_SYSTEM_PROMPT = """## Caliburn 專業分析方法

你是同一位專業職務分析顧問；下列 Skills 是可按需載入的方法，不是多個人格或固定階段。
本輪只有列出的 Skills 可用。每個實際用來形成結果的 Skill，都必須先用 read_file 完整讀取一次；不要重複讀取，也不要嘗試其他路徑。
先判斷現有 context 是否已足夠；足夠時不要為了展示而呼叫 Tool。彼此獨立的 Skill 與員工來源讀取可在同一波平行呼叫，不固定先後；只有前一波結果產生新的資料依賴時才使用第二波。

{skills_locations}{skills_load_warnings}

**本輪可用 Skills：**
{skills_list}

讀完本輪實際選用的方法後，把它們共同整合成一份結構化顧問結果。員工畫面只呈現一位顧問、必要的待審文件變更與至多一個主要問題；不得把 Skill 編排暴露成員工要操作的流程。

**提交前的最小契約：**
- 不得自行編造 UUID。只有 context 明列的既有 ID 才可引用；新理解、新焦點與新 Gap 的 ID 留空，由應用程式配置。
- 使用 candidate edit Tool 新增 Duty／Task／OPKS 時，每個新實體給同一 candidate batch 內唯一的 `entity_ref`；同批新實體之間以 `duty_ref`、`task_refs` 或 `indicator_refs` 關聯，正式 UUID 由應用程式配置。
- 新增 Duty／Task／OPKS 時 `display_order=-1`，由應用程式配置排序；每個 ADD 只提交一個實體。完整實體 ADD 使用 `field=whole_entity`；`field=top_level_value` 只用於 job_title／work_description。
- 每個 document change 只有 `field` 對應的 payload slot 可帶內容；未使用的 `text_value=""`、未使用的 `integer_value=-1`、未使用的 `uuid_value=""`，其餘未使用陣列一律為空。
- Task／Duty 的拆分或合併使用 ADD／REVISE／WITHDRAW／REASSIGN／REORDER 與 dependency／`atomic_group_ref` 組合；不要使用專用 split／merge operation。必須共同成立的 actions 放在同一原子群組供員工整組裁決。
- quote anchor 可留空；一般事實可只列 `source_ids`。若使用 anchor，`quote` 必須逐字存在於該來源，`start` 是 0-based 起點、`end` 是 exclusive 終點且等於 `start + len(quote)`；不得填 999 等占位值。
- O／P／K／S 文件變更必須以 `task_ids` 連到 context 已有 Task，或以 `task_refs` 連到同一 candidate batch 新增的 Task；不得提交沒有 Task linkage 的 O／P／K／S。
- `question.kind=none` 時其他 question 欄位全為空、`basis_ordinal=0`。
- 一般下一題（next）只填 `text`、`answer_target`、`reason`、`basis_ordinal`；`current_understanding、choices、affected_work_ids、affected_branch 全部留空`。
- 必要澄清（required_clarification）才填 `current_understanding`、2–3 個 `choices`、既有 `affected_work_ids` 與 `affected_branch`，且 `answer_target` 留空。
"""


@dataclass(frozen=True)
class ProfessionalConsultantAgent:
    graph: Any
    skill_backend: DirectPackageSkillBackendAdapter | PackageSkillBackend
    workspace_binding: ConsultantWorkspaceBackendBinding | None = None

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        if self.workspace_binding is not None:
            raise WorkspaceAgentAsyncOnlyError(
                "workspace consultant agents are async-only; use ainvoke()"
            )
        return self.graph.invoke(*args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self.graph.ainvoke(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.graph, name)


class WorkspaceAgentAsyncOnlyError(RuntimeError):
    """Raised when a workspace-backed consultant is invoked synchronously."""


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

    def __init__(
        self,
        *,
        backend: BackendProtocol,
        receipt_backend: DirectPackageSkillBackendAdapter | PackageSkillBackend | None = None,
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
    source_tools: Sequence[BaseTool] = (),
    candidate_edit_binding: CandidateEditToolBinding | None = None,
    context_middleware: AgentMiddleware | None = None,
    context_schema: type[Any] | None = None,
    workspace_binding: ConsultantWorkspaceBackendBinding | None = None,
    candidate_check_binding: CandidateCheckToolBinding | None = None,
) -> ProfessionalConsultantAgent:
    """Build the bounded agent using Deep Agents' Skill/read-file primitives."""

    if not selected_skill_ids:
        raise ValueError("an interactive consultant run requires at least one Skill")
    ineligible = set(selected_skill_ids) - set(execution.allowed_skill_ids)
    if ineligible:
        raise ValueError(f"agent requested ineligible Skills: {sorted(ineligible)}")
    if "read_file" not in execution.allowed_tool_ids:
        raise ValueError("resolved run policy must allow the read_file Skill tool")
    if execution.max_model_calls > 5:
        raise ValueError("interactive consultant runs allow at most five model calls")
    if execution.max_lookup_waves > 2:
        raise ValueError("interactive consultant runs allow at most two lookup waves")

    if workspace_binding is not None and source_tools:
        raise ValueError("workspace agents cannot receive legacy source Tools")
    if workspace_binding is not None and candidate_edit_binding is not None:
        raise ValueError("workspace agents cannot receive the legacy candidate Tool")
    if workspace_binding is not None and candidate_check_binding is None:
        raise ValueError("workspace agents require a candidate check Tool binding")

    if workspace_binding is None:
        legacy_backend = DirectPackageSkillBackendAdapter(
            PackageSkillBackend(selected_skill_ids)
        )
        backend: BackendProtocol = legacy_backend
        receipt_backend: DirectPackageSkillBackendAdapter | PackageSkillBackend = (
            legacy_backend
        )
    else:
        if workspace_binding.skill_backend.selected_skill_ids != selected_skill_ids:
            raise ValueError("workspace Skill binding must match selected Skills")
        if candidate_check_binding is not None and (
            candidate_check_binding.workspace is not workspace_binding
        ):
            raise ValueError("candidate check binding must use the agent workspace")
        backend = workspace_binding.composite_backend
        receipt_backend = workspace_binding.skill_backend

    candidate_tools: tuple[BaseTool, ...] = ()
    check_tools: tuple[BaseTool, ...] = ()
    if workspace_binding is not None:
        if not WORKSPACE_FILESYSTEM_TOOL_NAMES.issubset(
            set(execution.allowed_tool_ids)
        ) or "check_candidate_document" not in execution.allowed_tool_ids:
            raise ValueError(
                "resolved run policy must allow the complete workspace Tool surface"
            )
        check_binding = candidate_check_binding
        assert check_binding is not None
        check_tools = (
            build_check_candidate_document_tool(
                binding=check_binding,
            ),
        )
    elif candidate_edit_binding is not None:
        if "job_document_candidate_edit" not in execution.allowed_tool_ids:
            raise ValueError(
                "resolved run policy must allow the candidate document edit Tool"
            )
        if candidate_edit_binding.selected_skill_ids != selected_skill_ids:
            raise ValueError("candidate Tool binding must match selected Skills")
        candidate_tools = (
            build_job_document_candidate_edit_tool(
                binding=candidate_edit_binding,
                loaded_skill_ids=lambda: backend.loaded_skill_ids,
            ),
        )
    skills = RunScopedSkillsMiddleware(
        backend=backend,
        receipt_backend=(receipt_backend if workspace_binding is not None else None),
        workspace_mode=workspace_binding is not None,
    )
    files = FilesystemMiddleware(
        backend=backend,
        tools=(
            sorted(WORKSPACE_FILESYSTEM_TOOL_NAMES)
            if workspace_binding is not None
            else ["read_file"]
        ),
        custom_tool_descriptions=(
            WORKSPACE_TOOL_DESCRIPTIONS
            if workspace_binding is not None
            else {"read_file": SKILL_READ_TOOL_DESCRIPTION}
        ),
        system_prompt=None,
        tool_token_limit_before_evict=None,
        human_message_token_limit_before_evict=None,
    )
    lookup_cap = LookupWaveLimitMiddleware(
        tool_names=frozenset(
            {
                "read_file",
                "employee_source_get",
                "employee_source_lineage",
                "employee_source_search",
            }
            & set(execution.allowed_tool_ids)
        ),
        run_limit=execution.max_lookup_waves,
    )
    graph = build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ConsultantModelOutput,
        tools=(*source_tools, *candidate_tools, *check_tools),
        additional_middleware=(
            (skills, files, lookup_cap, WorkspaceToolWaveMiddleware())
            if workspace_binding is not None
            else (skills, files, lookup_cap)
        ),
        context_middleware=context_middleware,
        context_schema=context_schema,
    )
    return ProfessionalConsultantAgent(
        graph=graph,
        skill_backend=receipt_backend,
        workspace_binding=workspace_binding,
    )
