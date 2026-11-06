"""先核對正文修改與工具回傳容量，再直接執行 Memory 用例。"""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime

from caliburn.bundles.interview.services import MODEL_REFERENCES
from caliburn.bundles.memory.projections import (
    ToolRejection,
    select_item,
    source_unavailable,
)
from caliburn.bundles.memory.reads import analyst_scope
from caliburn.bundles.memory.services import MEMORY_SERVICE
from caliburn.bundles.memory.tool_contracts import (
    AddInterviewReferences,
    AddSituationReferences,
    ChangeBody,
    ChangeInterviewReferences,
    ChangeSituationReferences,
    ChangeText,
    CreateSituation,
    CreateUnderstanding,
    RemoveInterviewReferences,
    RemoveSituationReferences,
    TargetArguments,
    UpdateSituation,
    UpdateUnderstanding,
)
from caliburn.bundles.memory.tool_output import bounded_output
from caliburn.bundles.memory.tool_registration import memory_tool
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.items import MemoryKind, WorkSituation
from caliburn.shared.domain.text_editing.body_edits import (
    EditLimits,
    apply_body_diff,
    describe_body_change,
)
from caliburn.shared.domain.text_editing.errors import TextEditError

_LIMITS = EditLimits(
    max_body_characters=2_000_000,
    max_patch_characters=64_000,
    max_hunks=128,
    max_scan_characters=20_000_000,
)

type WriteArguments = (
    CreateSituation
    | CreateUnderstanding
    | UpdateSituation
    | UpdateUnderstanding
    | TargetArguments
)
type WriteEffect = Literal["created", "updated", "unchanged", "deleted"]


@dataclass(frozen=True, slots=True)
class _PreparedWrite:
    context: MemoryWriteContext
    item_id: UUID | None
    content: MemoryContent | None
    source_ids: tuple[UUID, ...]
    output: str


class _Sources:
    def __init__(self, keys: dict[str, UUID]) -> None:
        self.keys = keys
        self.labels = {source: key for key, source in keys.items()}

    def resolve(self, keys: Sequence[str]) -> tuple[UUID, ...]:
        try:
            return tuple(sorted({self.keys[key] for key in keys}))
        except KeyError:
            raise source_unavailable() from None

    def change(
        self,
        existing: tuple[UUID, ...],
        *,
        add: Sequence[str],
        remove: Sequence[str],
    ) -> tuple[tuple[UUID, ...], dict[str, object]]:
        additions, removals = set(self.resolve(add)), set(self.resolve(remove))
        prior = set(existing)
        if additions & removals:
            raise ToolRejection(
                "invalid_arguments",
                "不能同時新增及移除同一來源。",
                "只提交需要的單一方向。",
            )
        if removals - prior:
            raise ToolRejection(
                "reference_not_found",
                "至少一個來源並非目前引用。",
                "先讀取項目目前來源，再移除確切關係。",
            )
        effects: dict[str, object] = {}
        if added := additions - prior:
            effects["added"] = sorted(self.labels[source] for source in added)
        if removals:
            effects["removed"] = sorted(self.labels[source] for source in removals)
        return tuple(sorted(prior - removals | additions)), effects


def _interview_refs(arguments: WriteArguments) -> list[str]:
    if isinstance(arguments, CreateSituation):
        return arguments.interview_references
    refs: list[str] = []
    if isinstance(arguments, UpdateSituation):
        for change in arguments.changes:
            if isinstance(change, AddInterviewReferences):
                refs.extend(change.add)
            if isinstance(change, RemoveInterviewReferences):
                refs.extend(change.remove)
    return refs


def _prepare(
    arguments: WriteArguments,
    runtime: ToolRuntime[AgentContext, AgentState],
    *,
    role: MemoryKind,
    limit: int,
) -> _PreparedWrite:
    state = runtime.state
    root, analysis = analyst_scope(runtime, role)
    context = MemoryWriteContext(
        workspace_id=state["workspace_id"],
        analysis_id=analysis.analysis_id,
        expected_version=root.version,
    )

    source_keys: dict[str, UUID] = {}
    if role == "situation":
        # 既有但已撤回的來源仍可移除；新增來源由 Application 檢查合法範圍。
        targets = runtime.context.services.require(MODEL_REFERENCES).resolve_refs(
            state["workspace_id"], _interview_refs(arguments)
        )
        for ref, referenced in targets.items():
            if referenced.resource_kind != "message":
                raise ToolRejection(
                    "invalid_arguments",
                    f"interview_references 的 {ref} 不是訪談訊息。",
                    "使用材料提供的 message_* ref，不要改前綴或傳 UUID。",
                )
            source_keys[ref] = referenced.resource_id
    else:
        source_keys.update((s.content.title, s.id) for s in root.situations)
    sources = _Sources(source_keys)

    item_id = None
    content = None
    source_ids: tuple[UUID, ...] = ()
    effects: list[dict[str, object]] = []
    effect: WriteEffect
    if isinstance(arguments, (CreateSituation, CreateUnderstanding)):
        if len(arguments.body) > _LIMITS.max_body_characters:
            raise TextEditError("patch_limit_exceeded", "Initial body exceeds limit")
        effect = "created"
        content = MemoryContent(
            title=arguments.title,
            description=arguments.description,
            body=arguments.body,
        )
        source_ids = sources.resolve(
            arguments.interview_references
            if isinstance(arguments, CreateSituation)
            else arguments.work_situation_references
        )
    else:
        target = select_item(root.items, role, arguments.target_title)
        item_id = target.id
        if isinstance(arguments, (UpdateSituation, UpdateUnderstanding)):
            source_ids = (
                target.interview_message_ids
                if isinstance(target, WorkSituation)
                else target.situation_ids
            )
            updated = target.content.model_dump()
            for change in arguments.changes:
                if isinstance(change, ChangeText):
                    if updated[change.field] != change.value:
                        updated[change.field] = change.value
                        effects.append({"field": change.field})
                elif isinstance(change, ChangeBody):
                    before = target.content.body
                    after = apply_body_diff(before, change.diff, limits=_LIMITS)
                    if before != after:
                        updated["body"] = after
                        effects.append(
                            {
                                "field": "body",
                                "diff": describe_body_change(before, after),
                            }
                        )
                else:
                    add: Sequence[str] = ()
                    remove: Sequence[str] = ()
                    if isinstance(
                        change,
                        (
                            AddInterviewReferences,
                            AddSituationReferences,
                            ChangeInterviewReferences,
                            ChangeSituationReferences,
                        ),
                    ):
                        add = change.add
                    if isinstance(
                        change,
                        (
                            RemoveInterviewReferences,
                            RemoveSituationReferences,
                            ChangeInterviewReferences,
                            ChangeSituationReferences,
                        ),
                    ):
                        remove = change.remove
                    source_ids, applied = sources.change(
                        source_ids, add=add, remove=remove
                    )
                    if applied:
                        effects.append({"field": change.field, **applied})
            content = MemoryContent.model_validate(updated)
            effect = "updated" if effects else "unchanged"
        else:
            effect = "deleted"

    preview: dict[str, object] = {"status": effect}
    if effect == "updated":
        assert content is not None
        preview.update(
            title=content.title,
            description=content.description,
            applied_changes=effects,
        )
    return _PreparedWrite(
        context,
        item_id,
        content,
        source_ids,
        bounded_output(preview, limit=limit, writing=True),
    )


def _apply(service: MemoryService, role: MemoryKind, plan: _PreparedWrite) -> None:
    context, item_id, content, source_ids = (
        plan.context,
        plan.item_id,
        plan.content,
        plan.source_ids,
    )
    if role == "situation":
        if item_id is None:
            assert content is not None
            service.create_situation(
                context, content=content, interview_message_ids=source_ids
            )
        elif content is None:
            service.delete_situation(context, item_id=item_id)
        else:
            service.revise_situation(
                context,
                item_id=item_id,
                content=content,
                interview_message_ids=source_ids,
            )
    elif item_id is None:
        assert content is not None
        service.create_understanding(context, content=content, situation_ids=source_ids)
    elif content is None:
        service.delete_understanding(context, item_id=item_id)
    else:
        service.revise_understanding(
            context, item_id=item_id, content=content, situation_ids=source_ids
        )


def create_write_tools(role: MemoryKind, *, limit: int) -> tuple[StructuredTool, ...]:
    async def write(
        arguments: WriteArguments, runtime: ToolRuntime[AgentContext, AgentState]
    ) -> str:
        service = runtime.context.services.require(MEMORY_SERVICE)

        def save() -> str:
            prepared = _prepare(arguments, runtime, role=role, limit=limit)
            _apply(service, role, prepared)
            return prepared.output

        return await asyncio.to_thread(save)

    label = "工作情境" if role == "situation" else "工作理解"
    create_schema: type[WriteArguments] = (
        CreateSituation if role == "situation" else CreateUnderstanding
    )
    update_schema: type[WriteArguments] = (
        UpdateSituation if role == "situation" else UpdateUnderstanding
    )
    return (
        memory_tool(
            f"create_work_{role}",
            f"建立一項完整{label}候選。提供正文與實際支持的來源，無來源傳 []。",
            create_schema,
            write,
        ),
        memory_tool(
            f"update_work_{role}",
            f"修改一項{label}候選。指定精確 target_title，changes 每欄一次，"
            "未列保留。來源按需 add／remove；正文使用 V4A。全成或全拒。"
            "成功回傳的展示 diff 是實際前後差異，不能直接作為下一次 V4A。",
            update_schema,
            write,
        ),
        memory_tool(
            f"delete_work_{role}",
            f"刪除精確 target_title 指定的{label}候選。歷史發布版維持原樣。"
            + (
                "同時解除指向它的理解來源關係，不刪理解。"
                if role == "situation"
                else "同時移除它自己的來源關係，不刪上游情境。"
            ),
            TargetArguments,
            write,
        ),
    )
