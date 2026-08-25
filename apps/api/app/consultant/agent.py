"""Assembly of one professional consultant with progressively loaded methods."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from deepagents.backends import BackendProtocol
from deepagents.backends.utils import validate_path
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.skills import SkillsMiddleware, SkillsState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from typing_extensions import override

from app.consultant.model_runtime import ResolvedExecution, build_consultant_agent
from app.consultant.model_output import ConsultantModelOutput
from app.consultant.workspace_backend import ConsultantWorkspaceBackendBinding
from app.consultant.workspace_tools import (
    WORKSPACE_FILESYSTEM_TOOL_NAMES,
    WORKSPACE_TOOL_DESCRIPTIONS,
    WorkspaceToolWaveMiddleware,
)
from app.consultant.workspace_validation import (
    WorkspaceValidationMiddleware,
    WorkspaceValidationService,
)
from app.consultant.skill_backend import PackageSkillBackend


SKILLS_SYSTEM_PROMPT = """## Caliburn 專業分析方法

你是同一位專業職務分析顧問；下列 Skills 是可按需載入的方法，不是多個人格或固定階段。
本輪只有列出的 Skills 可用。每個實際用來形成結果的 Skill，都必須先用 read_file 完整讀取一次；只能讀取列出的 /skills/<skill-id>/SKILL.md。
先判斷現有 context 是否已足夠；足夠時不要為了展示而呼叫 Tool。/skills、/sources、/approved、/review 是唯讀；/workspace 是同一份跨 turn 保留、non-authoritative 且唯一可編輯的工作草稿。只有既有結果產生新的明確資料依賴時才繼續讀取；彼此獨立的 reads 應在同一 model response 平行提出。

{skills_locations}{skills_load_warnings}

**本輪可用 Skills：**
{skills_list}

讀完本輪實際選用的方法後，把它們共同整合成一份結構化顧問結果。員工畫面只呈現一位顧問、必要的文件變更與至多一個主要問題；不得把 Skill 編排暴露成員工要操作的流程。

**提交前的最小契約：**
- 本輪最新員工原話已是 current HumanMessage，直接使用並以 context 給的 source handle 引用，不要再從 `/sources` 重讀；只有需要舊來源時才查 VFS。詳細 Current JD、/review 與方法內容仍從對應 VFS 路徑按需讀取，不要把整份資料複製到回覆或 context。
- 直接續編 /workspace 下既有的 canonical resources；不得從 approved 複製或重建另一份草稿。每一波編輯後 application 會自動驗證 workspace。
- Batch independent reads in the same model response. To see which existing resources already cite this turn, grep once for the current source handle under /workspace before enumerating entity files; matches are orientation, not proof that the source is fully processed. Before editing, decide one coherent current-turn delta; combine all changes to the same file into one enclosing edit and issue the remaining edits as one non-overlapping mutation wave. If validation is invalid, read only the reported paths and repair every listed diagnostic in that wave. Once your mutation is valid or conflicted and no new data dependency remains, do not reread /workspace or /review merely to confirm it; return the final structured response. If no document edit is needed, return the final response directly.
- Workspace JSON 的 Evidence 只填 `source_handle`、逐字 `quote`、`occurrence`（quote 唯一時填 null，重複時填 1-based 次序）與使用的 `skill_ids`。不要填 offset、stable source UUID、workspace revision、digest 或 action handle。
- /review 是 application 由 workspace 派生的 semantic review；只有員工決定後，authority 才能把內容整合進 approved。
- O／P／K／S 文件變更必須以 canonical resource 的 task handle 連到 Task；不得提交沒有 Task linkage 的 O／P／K／S。
- `question.kind=none` 時其他 question 欄位全為空、`basis_ordinal=0`。
- 一般下一題（next）只填 `text`、`answer_target`、`reason`、`basis_ordinal`；`current_understanding、choices、affected_work_ids、affected_branch 全部留空`。
- 必要澄清（required_clarification）才填 `current_understanding`、2–3 個 `choices`、既有 `affected_work_ids` 與 `affected_branch`，且 `answer_target` 留空。
- 只有員工明確取代一則唯一可辨識的較早原話時，`source_supersessions` 才填一個舊 source handle；補充或限定不填。
- 若多個舊來源都可能是目標，填 `required_clarification` 並讓 `source_supersessions` 保持空陣列；不要猜測或填 UUID。
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
    expected_tools = WORKSPACE_FILESYSTEM_TOOL_NAMES
    if set(execution.allowed_tool_ids) != expected_tools:
        raise ValueError("resolved run policy must allow exactly the workspace Tool surface")
    if workspace_binding.skill_backend.selected_skill_ids != selected_skill_ids:
        raise ValueError("workspace Skill binding must match selected Skills")

    backend: BackendProtocol = workspace_binding.composite_backend
    receipt_backend = workspace_binding.skill_backend
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
    async def load_document_sources() -> Sequence[Any]:
        return await workspace_binding.source_backend.lookup.runtime.list_sources(
            workspace_binding.document_id
        )

    validation = WorkspaceValidationMiddleware(
        validator=WorkspaceValidationService(
            workspace=workspace_binding.workspace,
            catalog=workspace_binding.catalog,
            source_loader=load_document_sources,
            selected_skill_ids=selected_skill_ids,
        ),
        skill_backend=receipt_backend,
    )
    graph = build_consultant_agent(
        model=model,
        execution=execution,
        response_schema=ConsultantModelOutput,
        tools=(),
        additional_middleware=(
            skills,
            files,
            WorkspaceToolWaveMiddleware(
                workspace_backend=workspace_binding.workspace_backend
            ),
            validation,
        ),
        context_middleware=context_middleware,
        context_schema=context_schema,
    )
    return ProfessionalConsultantAgent(
        graph=graph,
        skill_backend=receipt_backend,
        workspace_binding=workspace_binding,
    )
