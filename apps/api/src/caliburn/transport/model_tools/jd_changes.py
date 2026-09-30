"""Canonical read_jd_changes: fixed manual and source comparisons, never confirmation."""

import json
import re
from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import JsonValue, ValidationError

from caliburn.features.executions.history_models import HistoryConflictError
from caliburn.features.executions.models import ExecutionNotFoundError, ExecutionStateError
from caliburn.features.interviews.models import (
    InterviewScopeError,
    InterviewSourceNotAvailableError,
)
from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.capabilities import Capability
from caliburn.features.job_description.change_queries import (
    JdChangeHistoryUnavailableError,
    JdChangeSnapshot,
    ManualJdOperation,
)
from caliburn.features.job_description.collaborators import Collaborator
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.navigation import (
    JdReadTarget,
    JdReadTargetNotFoundError,
    jd_read_ref,
)
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import TaskDetail, WorkTask
from caliburn.features.work_memory.candidates import (
    MemoryCandidateStateError,
    MemoryPermissionError,
)
from caliburn.features.work_memory.edit_preparation import describe_body_change
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.jd_source_markdown import (
    project_jd_source_changes as project_jd_source_changes,
)
from caliburn.transport.model_tools.contracts import function_definition
from caliburn.transport.model_tools.jd_changes_wire import parse_jd_changes
from caliburn.transport.model_tools.jd_detail_projection import (
    jd_read_source_targets,
    project_jd_item,
    select_jd_items,
)
from caliburn.workflows.jd_changes import (
    AllManualChanges,
    AreaManualChanges,
    ItemManualChanges,
    JdChangesWorkflow,
    JdManualChanges,
    ManualChangeScope,
    ManualJdArea,
    ProfileManualChanges,
    SourceChangeQuery,
    UnsupportedJdSourceKindError,
)
from caliburn.workflows.memory_reads import PublishedMemoryRead


def jd_changes_definitions() -> list[FunctionToolParam]:
    """Definitions are independent of a Turn binding and tool handler construction."""
    return [
        function_definition(
            "read_jd_changes",
            (
                "按需讀 JD 差異。manual：上一成功 Turn 正式 JD 到本 Turn 起始正式 JD，"
                "讀人工操作與淨差異；"
                "source：JD citation_ref 固定舊 Memory 到本 Turn 固定版同身分來源的相關差異。"
                "來源引用只可取 diff，不可任意讀舊全文；不可變訪談用 read_interview，"
                "current_input 沿本輪原話。"
                "只讀，不表示核對或解除待核對；scope 與比較版本由 App 固定。"
            ),
            "read-jd-changes-arguments",
        )
    ]


class JdChangesTools:
    def __init__(
        self,
        reader: JdChangesWorkflow,
        binding: PublishedMemoryRead,
        *,
        manual_jd_start_revision_id: UUID,
        max_result_characters: int = 1_000_000,
    ) -> None:
        if max_result_characters < 1:
            raise ValueError("Tool result character limit must be positive")
        self.reader = reader
        self.binding = binding
        self.manual_jd_start_revision_id = manual_jd_start_revision_id
        self.max_result_characters = max_result_characters

    @property
    def names(self) -> tuple[str, ...]:
        return ("read_jd_changes",)

    def definitions(self) -> list[FunctionToolParam]:
        return jd_changes_definitions()

    async def invoke(self, name: str, arguments: str) -> str:
        if name not in self.names:
            return "rejected: scope_not_allowed；使用 read_jd_changes。"
        try:
            query = parse_jd_changes(arguments)
        except ValidationError, ValueError:
            return (
                "rejected: invalid_arguments；選 manual 的合法 scope "
                "或 source 的 citation_ref，不帶版本。"
            )
        if isinstance(query, SourceChangeQuery):
            return await read_jd_source_changes(
                self.reader,
                self.binding,
                query.citation_ref,
                max_result_characters=self.max_result_characters,
            )
        try:
            result = await self.reader.read_manual(
                self.binding,
                manual_jd_start_revision_id=self.manual_jd_start_revision_id,
                scope=query.scope,
            )
        except ExecutionNotFoundError, ExecutionStateError:
            return "rejected: scope_not_allowed；目前 Turn 或固定人工差異範圍不允許讀取。"
        except CandidateStateError:
            return "rejected: target_stale；本 Turn 已無有效 JD 候選。"
        except JdReadTargetNotFoundError:
            return (
                "rejected: target_not_found；項目已不在目前 JD；已刪項目改用 all／area 讀人工差異。"
            )
        except HistoryConflictError, JdChangeHistoryUnavailableError:
            return (
                "rejected: source_not_available；固定人工比較基底或原操作不可取回，"
                "不回退成初始／空差異。"
            )
        output = project_jd_manual_changes(result)
        if len(output) > self.max_result_characters:
            return (
                "rejected: read_limit_exceeded；完整人工差異超量，未截斷；"
                "請選合法 area／item／profile_field。"
            )
        return output


def project_jd_manual_changes(result: JdManualChanges) -> str:
    interval, snapshots, scope = result.interval, result.snapshots, result.scope
    before, after = snapshots[interval.base_revision_id], snapshots[interval.start_revision_id]
    operations: list[list[str]] = []
    for operation in interval.operations:
        old, new = snapshots[operation.before_revision_id], snapshots[operation.after_revision_id]
        delta = _manual_delta(old, new, scope)
        if delta or _operation_touches(operation, old, new, scope):
            labels = _operation_labels(operation, old, new, scope)
            operations.append(
                [
                    *([f"受影響範圍：{', '.join(labels)}"] if labels else []),
                    *(delta or ["原操作已成立，但結果未改變（no-op）。"]),
                ]
            )
    lines = [
        "## JD 人工差異",
        f"比較：{'初始空 JD' if interval.initial_base else '上一成功 A 正式 JD'}"
        " → 本 Turn 起點正式 JD。",
        "只讀；未確認內容，也未解除來源待核對。本 Turn 候選修改不在此範圍。",
        f"本範圍人工操作：{len(operations)}",
    ]
    if not operations:
        lines.append("沒有人工操作。")
    else:
        lines.append("### 原操作的實際效果（歷史定位不保證仍存活；可編定位重讀 read_jd）")
        for index, delta in enumerate(operations, 1):
            lines.extend([f"#### 操作 {index}", *delta])
    net = _manual_delta(before, after, scope)
    lines.extend(
        [
            "### 淨差異",
            *(net or ["淨差異：無；有操作不等於有淨改動。" if operations else "淨差異：無。"]),
        ]
    )
    return "\n".join(lines)


def _selected_items(
    snapshot: JdChangeSnapshot, scope: ManualChangeScope
) -> tuple[JdReadTarget, ...]:
    work = snapshot.work
    if isinstance(scope, AllManualChanges):
        return (*work.areas, *work.tasks, *work.capabilities, *work.collaborators, *work.conditions)
    if isinstance(scope, ProfileManualChanges) or (
        isinstance(scope, AreaManualChanges) and scope.view == ManualJdArea.PROFILE
    ):
        return ()
    if isinstance(scope, ItemManualChanges):
        try:
            return select_jd_items(work, "item", scope.read_ref)
        except JdReadTargetNotFoundError:
            return ()  # This historical endpoint lacks the currently validated identity.
    return select_jd_items(work, scope.view.value, None)


def _profile_fields(scope: ManualChangeScope) -> tuple[ProfileField, ...]:
    if isinstance(scope, ProfileManualChanges):
        return (scope.field,)
    if isinstance(scope, AllManualChanges) or (
        isinstance(scope, AreaManualChanges) and scope.view == ManualJdArea.PROFILE
    ):
        return tuple(ProfileField)
    return ()


def _snapshot_values(
    snapshot: JdChangeSnapshot, scope: ManualChangeScope
) -> dict[str, dict[str, JsonValue]]:
    values: dict[str, dict[str, JsonValue]] = {}
    for field in _profile_fields(scope):
        text = getattr(snapshot.profile, field.value)
        if text is not None:
            values[f"profile.{field.value}"] = {field.value: text}
    work = snapshot.work
    for item in _selected_items(snapshot, scope):
        value = project_jd_item(item, work, ())
        value.pop("supporting_sources")
        value.pop("read_ref")
        siblings: tuple[JdReadTarget, ...]
        match item:
            case ResponsibilityArea():
                siblings = work.areas
                value["task_read_refs"] = [
                    jd_read_ref(task) for task in work.tasks if task.area_id == item.area_id
                ]
            case WorkTask():
                siblings = tuple(task for task in work.tasks if task.area_id == item.area_id)
                value["area_read_ref"] = f"area_{item.area_id.hex}" if item.area_id else "未歸屬"
            case TaskDetail():
                task = next(task for task in work.tasks if item in task.details)
                siblings = tuple(detail for detail in task.details if detail.kind == item.kind)
                value["task_read_ref"] = jd_read_ref(task)
            case Capability():
                siblings = tuple(
                    capability for capability in work.capabilities if capability.kind == item.kind
                )
            case Collaborator():
                siblings = work.collaborators
            case JobCondition():
                siblings = tuple(
                    condition for condition in work.conditions if condition.kind == item.kind
                )
        value["position"] = siblings.index(item) + 1
        values[jd_read_ref(item)] = value
    return values


def _selected_sources(
    snapshot: JdChangeSnapshot, scope: ManualChangeScope
) -> dict[UUID, JdSourceReference]:
    targets = {
        *jd_read_source_targets(snapshot.work, _selected_items(snapshot, scope)),
        *(
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field)
            for field in _profile_fields(scope)
        ),
    }
    return {
        reference.citation_id: reference
        for reference in snapshot.sources
        if reference.target in targets
    }


def _manual_delta(
    before: JdChangeSnapshot, after: JdChangeSnapshot, scope: ManualChangeScope
) -> list[str]:
    old, new = _snapshot_values(before, scope), _snapshot_values(after, scope)
    lines = []
    for key in dict.fromkeys((*old, *new)):
        left, right = old.get(key), new.get(key)
        if left == right:
            continue
        effect = (
            "新增"
            if left is None
            else "刪除（歷史定位，不可編輯）"
            if right is None
            else "變更（文字／順序／歸屬／關聯）"
        )
        lines.append(f"{effect} · {key}")
        diff = describe_body_change(
            json.dumps(left, ensure_ascii=False, indent=2) if left is not None else "",
            json.dumps(right, ensure_ascii=False, indent=2) if right is not None else "",
        )
        fence = "`" * max(3, max(map(len, re.findall(r"`+", diff)), default=0) + 1)
        lines.extend([f"{fence}diff", diff, fence])
    old_sources, new_sources = _selected_sources(before, scope), _selected_sources(after, scope)
    for citation_id in dict.fromkeys((*old_sources, *new_sources)):
        left_source, right_source = old_sources.get(citation_id), new_sources.get(citation_id)
        if left_source is None:
            effect = "新增來源引用"
        elif right_source is None:
            effect = "移除來源引用"
        elif left_source.source != right_source.source:
            effect = "來源依據位置已改綁"
        elif left_source.needs_review != right_source.needs_review:
            effect = "來源改為待核對" if right_source.needs_review else "原操作已核對來源"
        else:
            continue
        selected = right_source or left_source
        assert selected is not None
        kind = (
            "interview"
            if isinstance(selected.source, InterviewSource)
            else selected.source.layer.value
        )
        target_label = _source_target_label(after if right_source else before, selected.target)
        lines.append(f"{effect} · {target_label} · citation_{citation_id.hex} · {kind}")
        if (
            left_source is not None
            and right_source is not None
            and left_source.source != right_source.source
            and left_source.needs_review != right_source.needs_review
        ):
            review = "待核對" if right_source.needs_review else "原操作已核對"
            lines.append(f"來源資格：{review} · {target_label} · citation_{citation_id.hex}")
    return lines


def _source_target_label(snapshot: JdChangeSnapshot, target: JdSourceTarget) -> str:
    if target.kind == SourceTargetKind.PROFILE_FIELD:
        assert target.field is not None
        return f"profile.{target.field.value}"
    if target.kind == SourceTargetKind.TASK_CAPABILITY:
        capability = next(
            item for item in snapshot.work.capabilities if item.capability_id == target.item_id
        )
        assert target.task_id is not None
        return f"task_{target.task_id.hex} → {jd_read_ref(capability)}"
    items = (
        *_selected_items(snapshot, AllManualChanges()),
        *(detail for task in snapshot.work.tasks for detail in task.details),
    )
    return next(
        jd_read_ref(item)
        for item in items
        if jd_read_source_targets(snapshot.work, (item,))[0] == target
    )


def _operation_touches(
    operation: ManualJdOperation,
    before: JdChangeSnapshot,
    after: JdChangeSnapshot,
    scope: ManualChangeScope,
) -> bool:
    if isinstance(scope, AllManualChanges):
        return True
    return bool(_operation_labels(operation, before, after, scope))


def _operation_labels(
    operation: ManualJdOperation,
    before: JdChangeSnapshot,
    after: JdChangeSnapshot,
    scope: ManualChangeScope,
) -> tuple[str, ...]:
    fields = [
        f"profile.{field.value}"
        for field in _profile_fields(scope)
        if field in operation.profile_fields
    ]
    refs = {
        jd_read_ref(item)
        for snapshot in (before, after)
        for item in _selected_items(snapshot, scope)
    }
    return (
        *fields,
        *sorted(
            ref
            for ref in refs
            if any(ref.rsplit("_", 1)[-1] == item_id.hex for item_id in operation.item_ids)
        ),
    )


async def read_jd_source_changes(
    reader: JdChangesWorkflow,
    binding: PublishedMemoryRead,
    citation_ref: str,
    *,
    max_result_characters: int = 1_000_000,
) -> str:
    """Source branch only; registration must also implement the manual branch."""
    if max_result_characters < 1:
        raise ValueError("Tool result character limit must be positive")
    try:
        result = await reader.read_source(binding, citation_ref)
    except UnsupportedJdSourceKindError as error:
        return f"rejected: source_kind_not_supported；{error}"
    except ExecutionNotFoundError, ExecutionStateError, MemoryPermissionError, InterviewScopeError:
        return (
            "rejected: scope_not_allowed；目前執行或固定來源範圍不允許讀取；由 App 恢復合法範圍。"
        )
    except CandidateStateError:
        return "rejected: target_stale；本 Turn 已無有效 JD 候選；不可重送舊定位。"
    except JdReadTargetNotFoundError:
        return (
            "rejected: target_not_found；目前 JD 找不到引用；用 read_jd 局部讀取取得 citation_ref。"
        )
    except MemoryRevisionNotFoundError, MemoryCandidateStateError, InterviewSourceNotAvailableError:
        return (
            "rejected: source_not_available；固定來源或比較端點無法完整取回，未回傳假空差異；"
            "請由 App 核對保存資料，不推論來源已刪除。"
        )
    output = project_jd_source_changes(result)
    if len(output) > max_result_characters:
        return (
            "rejected: read_limit_exceeded；完整相關差異超過容量，未截斷或視為已讀；"
            "單筆來源已是最小合法範圍，交 App 處理。"
        )
    return output
