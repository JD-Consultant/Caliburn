"""六個內容寫工具；LangGraph 保存業務結果後，才配置並呈現模型定位。"""

import asyncio
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Annotated, Literal, TypedDict
from uuid import UUID

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool, ToolException
from langgraph.func import task
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from pydantic.v1 import ValidationError as ValidationErrorV1

from caliburn.bundles.job_description import write_inputs as wire
from caliburn.bundles.job_description import writing
from caliburn.bundles.job_description.projection import reference_targets
from caliburn.bundles.job_description.services import (
    JD_MEMORY_QUERIES,
    JD_QUERIES,
    JD_REFERENCES,
    JD_UOW_FACTORY,
)
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.job_description.application import errors as application
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain import errors as domain
from caliburn.modules.model_references.contracts import (
    ModelReferenceError,
    ReferenceTarget,
    ResourceKind,
)


class _CreatedReference(TypedDict):
    kind: ResourceKind
    id: str


class _SavedWrite(TypedDict):
    version: int
    status: str
    created: list[_CreatedReference]
    detached_task_count: int
    unlinked_task_count: int


def _rejection(code: str, message: str, next_action: str) -> str:
    return json.dumps(
        {
            "status": "rejected",
            "code": code,
            "message": message,
            "next_action": next_action,
        },
        ensure_ascii=False,
    )


_INVALID_INPUT = (
    domain.InvalidCitationError,
    application.InvalidJobDescriptionInputError,
    domain.InvalidTextError,
    domain.InvalidCompetencyLevelError,
    domain.InvalidCollaborationNameError,
    domain.InvalidTaskOrderError,
    domain.InvalidDefinitionOrderError,
    domain.InvalidJobDescriptionRecordOrderError,
)
_INVALID_TARGET = (
    application.InvalidTaskReferenceError,
    application.JobDescriptionNotFoundError,
    application.TaskNotFoundError,
    application.DutyNotFoundError,
    application.KnowledgeNotFoundError,
    application.SkillNotFoundError,
    domain.InvalidTaskReferenceError,
    domain.TaskOutcomeNotFoundError,
    domain.TaskRequirementNotFoundError,
    domain.CollaborationNotFoundError,
    domain.JobConditionNotFoundError,
)


async def _execute(
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
    *,
    operation: Callable[[writing.WriteContext], JobDescriptionResult],
    reference_paths: Mapping[str, tuple[str, ...]] | None = None,
    effect: Literal["created", "updated", "moved", "deleted"],
    created_kinds: Sequence[ResourceKind] = (),
    memory_sources: bool = False,
) -> Command[object]:
    job_description_id = runtime.state["jd_id"]
    expected_version = runtime.state["jd_version"]
    if job_description_id is None or expected_version is None:
        raise ToolException(
            _rejection(
                "source_not_available",
                "尚未提供可供修改的 JD。",
                "先呼叫 read_jd 讀取目前 JD。",
            )
        )
    workspace_id = runtime.state["workspace_id"]
    references = runtime.context.services.require(JD_REFERENCES)
    reference_paths = reference_paths or {}

    @task
    def save_content() -> _SavedWrite:
        context = writing.load_write_context(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            expected_version=expected_version,
            turn_id=runtime.state["turn_id"],
            queries=runtime.context.services.require(JD_QUERIES),
            references=references,
            uow_factory=runtime.context.services.require(JD_UOW_FACTORY),
            refs=tuple(reference_paths),
            memory_published_version=runtime.state.get("memory_published_version"),
            memory_queries=runtime.context.services.require(JD_MEMORY_QUERIES)
            if memory_sources
            and runtime.state.get("memory_published_version") is not None
            else None,
        )
        result = operation(context)
        previous = set(reference_targets(context.snapshot))
        added = [
            target
            for target in reference_targets(result)
            if target not in previous
            and target.resource_kind not in ("message", "occupation")
        ]
        ordered: list[ReferenceTarget] = []
        for kind in created_kinds:
            target = next(
                (target for target in added if target.resource_kind == kind), None
            )
            if target is not None:
                ordered.append(target)
                added.remove(target)
        ordered.extend(added)
        old_tasks = {task.id: task for task in context.snapshot.tasks}
        return {
            "version": result.version,
            "status": effect if result.version != expected_version else "unchanged",
            "created": [
                {"kind": target.resource_kind, "id": str(target.resource_id)}
                for target in ordered
            ],
            "detached_task_count": sum(
                1
                for task in result.tasks
                if task.id in old_tasks
                and old_tasks[task.id].duty_id is not None
                and task.duty_id is None
            ),
            "unlinked_task_count": sum(
                1
                for task in result.tasks
                if task.id in old_tasks
                and (
                    set(old_tasks[task.id].knowledge_ids) - set(task.knowledge_ids)
                    or set(old_tasks[task.id].skill_ids) - set(task.skill_ids)
                )
            ),
        }

    try:
        saved = await save_content()
    except application.JobDescriptionConcurrencyError as error:
        raise ToolException(
            _rejection(
                "target_stale",
                "JD 已變動或本次並行修改遭拒絕。",
                "呼叫 read_jd 重新讀取，再依目前內容決定修改。",
            )
        ) from error
    except (
        application.JobDescriptionNameConflictError,
        domain.DuplicateNameError,
    ) as error:
        raise ToolException(
            _rejection(
                "name_conflict",
                "同種類已有相同名稱。",
                "讀取 JD 核對既有項目；修改既有項目或選擇正確名稱。",
            )
        ) from error
    except application.InvalidCitationSourceError as error:
        raise ToolException(
            _rejection(
                "source_not_available",
                "來源不在本輪可引用的有效範圍。",
                "核對已讀訪談短碼或本輪固定 Memory 的完整標題；"
                "不要改用未讀或無關來源。",
            )
        ) from error
    except application.CitationNotFoundError as error:
        raise ToolException(
            _rejection(
                "target_not_found",
                "引用不屬於此目標。",
                "讀取此目標的引用並使用提供的 citation_ref。",
            )
        ) from error
    except ModelReferenceError as error:
        locations = reference_paths.get(error.reference)
        if locations is None:
            raise
        next_action = (
            "核對已讀訪談或本輪原話提供的 ref，原樣填入 message_ref；"
            "沒有可用來源時先釐清，不猜碼或引用無關材料。"
            if any(location.endswith(".message_ref") for location in locations)
            else "呼叫 read_jd map 取得目前 JD 短碼，再核對目標與所屬範圍。"
        )
        raise ToolException(
            _rejection(
                "target_not_found",
                f"{'、'.join(locations)} 的短碼 {error.reference} 在此工作區不可用。",
                next_action,
            )
        ) from error
    except writing.ReferenceKindError as error:
        locations = reference_paths.get(error.reference)
        if locations is None:
            raise
        raise ToolException(
            _rejection(
                "target_not_found",
                f"短碼 {error.reference} 種類不適用此操作；"
                f"此碼出現於 {'、'.join(locations)}。",
                "呼叫 read_jd map，使用其中種類為 "
                f"{'、'.join(error.allowed_kinds)} 的短碼。",
            )
        ) from error
    except _INVALID_TARGET as error:
        raise ToolException(
            _rejection(
                "target_not_found",
                "指定短碼、種類或所屬範圍不適用此操作。",
                "讀取 JD 並使用其中的目標及同集合定位；不要猜碼或使用 UUID。",
            )
        ) from error
    except writing.RevisionFieldError as error:
        if error.reason == "unsupported_field":
            message = f"{error.location}：欄位 {error.field} 不適用此目標。"
            next_action = (
                f"此目標的欄位為 {'、'.join(error.allowed_fields)}；"
                "set_field 設定文字，clear_field 只清空工具允許的可空欄位。"
            )
        else:
            message = f"{error.location}：欄位 {error.field} 重複修改。"
            next_action = "同一欄位只能修改一次；保留一個設定或清空動作後再送出。"
        raise ToolException(
            _rejection("invalid_arguments", message, next_action)
        ) from error
    except domain.InvalidNameError as error:
        raise ToolException(
            _rejection(
                "invalid_arguments",
                "條目名稱不符合長度規則。",
                "名稱去除頭尾空白後須有內容，且不可超過 255 字元；縮短名稱後再送出。",
            )
        ) from error
    except _INVALID_INPUT as error:
        raise ToolException(
            _rejection(
                "invalid_arguments",
                "本次修改不符合欄位、排序或組合規則。",
                "核對適用欄位、必要文字及同集合錨點；同欄或同一目標不可重複或矛盾修改。",
            )
        ) from error

    # 映射與業務是不同交易。此處失敗必須向外傳遞；重入可重用已保存 Task 結果。
    targets = tuple(
        ReferenceTarget(item["kind"], UUID(item["id"])) for item in saved["created"]
    )
    assigned = await asyncio.to_thread(
        references.get_or_create_refs, workspace_id, targets
    )
    output: dict[str, object] = {"status": saved["status"]}
    if targets:
        created_refs = [assigned[target] for target in targets]
        if effect == "created":
            output["read_ref"] = created_refs[0]
            if len(created_refs) > 1:
                output["created_refs"] = created_refs[1:]
        else:
            output["created_refs"] = created_refs
    if saved["detached_task_count"]:
        output["detached_task_count"] = saved["detached_task_count"]
    if saved["unlinked_task_count"]:
        output["unlinked_task_count"] = saved["unlinked_task_count"]
    assert runtime.tool_call_id is not None
    return Command(
        update={
            "jd_version": saved["version"],
            "messages": [
                ToolMessage(
                    content=json.dumps(output, ensure_ascii=False),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


async def create_jd_task(
    name: Annotated[wire.Text, Field(description="可辨認此項工作的簡明名稱。")],
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
    parent_read_ref: Annotated[
        wire.ReadRef | None, Field(description="所屬職責的已讀短碼；null 表示未分類。")
    ] = None,
    description: Annotated[
        wire.Text | None,
        Field(
            description="本人行動、工作對象及必要的範圍、條件或權限；"
            "不需補述時填 null。"
        ),
    ] = None,
    competency_level: Annotated[
        wire.Level | None,
        Field(
            description="有已確認定級依據才填；未知填 null，"
            "不由職稱、年資或權限自行換算。"
        ),
    ] = None,
    outcomes: Annotated[
        tuple[wire.TaskDetail, ...],
        Field(
            max_length=64,
            description="本任務形成、交付或維持的結果，必要時交代接收用途；"
            "無已知成果填 []。",
        ),
    ] = (),
    requirements: Annotated[
        tuple[wire.TaskDetail, ...],
        Field(
            max_length=64,
            description="執行中或完成時已確認的品質、期限、條件及異常處理；不把單次做法升為固定要求。"
            "與成果分列、不逐項配對；無已知要求填 []。",
        ),
    ] = (),
    required_knowledge: Annotated[
        tuple[wire.Capability, ...],
        Field(
            max_length=64,
            description="本任務須理解的特性、概念、規則、程序與適用條件；"
            "沿用已讀定義或新建後連結，無已知項目填 []。",
        ),
    ] = (),
    required_skills: Annotated[
        tuple[wire.Capability, ...],
        Field(
            max_length=64,
            description="本任務須運用方法、工具進行操作、判斷或解題的能力；"
            "沿用已讀定義或新建後連結，無已知項目填 []。",
        ),
    ] = (),
    supporting_sources: Annotated[
        tuple[wire.Source, ...],
        Field(
            max_length=64,
            description="支持本任務、其 O/P 及 K/S 用途；"
            "不代替共用 K/S 定義自身的依據。無來源填 []。",
        ),
    ] = (),
) -> Command[object]:
    """一次建立任務、成果 O、要求 P，連結既有或新建共用 K/S；全成或全拒。

    existing 使用已讀短碼，new 明示新建定義；
    新 K/S 自身的來源可沿 created_refs 另行編修。
    成功回 created、任務 read_ref 及 O/P/新 K/S 的 created_refs，不回全文。
    """
    kinds: list[ResourceKind] = ["task"]
    kinds.extend("outcome" for _ in outcomes)
    kinds.extend("requirement" for _ in requirements)
    kinds.extend(
        "knowledge"
        for item in required_knowledge
        if isinstance(item, wire.NewCapability)
    )
    kinds.extend(
        "skill" for item in required_skills if isinstance(item, wire.NewCapability)
    )
    return await _execute(
        runtime,
        effect="created",
        created_kinds=kinds,
        reference_paths=writing.collect_reference_paths(
            parent_read_ref=parent_read_ref,
            required_knowledge=required_knowledge,
            required_skills=required_skills,
            supporting_sources=supporting_sources,
        ),
        memory_sources=writing.needs_memory(supporting_sources),
        operation=lambda context: writing.create_task(
            context,
            name=name,
            description=description,
            parent_read_ref=parent_read_ref,
            competency_level=competency_level,
            outcomes=outcomes,
            requirements=requirements,
            required_knowledge=required_knowledge,
            required_skills=required_skills,
            supporting_sources=supporting_sources,
        ),
    )


async def create_jd_item(
    item: wire.NewItem, runtime: ToolRuntime[AgentContext, JobDescriptionToolState]
) -> Command[object]:
    """建立單一職責、共用知識／技能、協作或條件；成功回 created 與 read_ref。

    kind 選擇對應欄位。共用 K/S 不會自動連結任務；完整任務使用 create_jd_task。
    來源使用已讀有效訪談或本輪固定 Memory。
    """
    return await _execute(
        runtime,
        effect="created",
        reference_paths=writing.collect_reference_paths(item=item),
        memory_sources=writing.needs_memory([item]),
        operation=lambda context: writing.create_item(context, item),
    )


async def revise_jd_profile(
    changes: wire.ProfileChanges,
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
) -> Command[object]:
    """一次更正基本資料；未列欄位保留，clear_field 清空，級別可設 1–6 或 null。

    同欄不可重複設定或清空。全成或全拒；成功回 updated 或 unchanged。
    add_source/remove_source/confirm_reference_alignment 操作整組基本資訊的引用。
    引用確認須先核清目前內容；Memory 保留原物件並對齊本輪固定發布版。
    """
    return await _execute(
        runtime,
        effect="updated",
        reference_paths=writing.collect_reference_paths(changes=changes),
        memory_sources=writing.needs_memory(changes),
        operation=lambda context: writing.revise_profile(context, changes),
    )


async def revise_jd_item(
    read_ref: wire.ReadRef,
    changes: wire.ItemChanges,
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
) -> Command[object]:
    """以有界 changes 一次更正同一項目；全成或全拒，未列內容保留。

    Task 可同次改名／說明／級別、增改刪 O/P、連結／解除／排序 K/S 或新建並連結 K/S。
    共用定義的文字須選該 knowledge/skill 修改。其他項目只接受自身欄位；條件可改分類。
    同欄與同明細不可重複或矛盾操作；link 後 reorder 同一能力合法。
    reorder_capability 的 before_read_ref=null 表示組末；錨點須為同任務同類能力。
    add_source/remove_source/confirm_reference_alignment 只操作此目標的引用。
    O/P 共用所屬 Task 來源。改字、排序或移動保留既有引用；確認前須核清目前內容。
    成功回 updated/unchanged；新建項目的 created_refs 依新增動作順序提供。
    """
    kinds = [
        change.kind
        for change in changes
        if isinstance(change, (wire.AddDetail, wire.CreateCapability))
    ]
    return await _execute(
        runtime,
        effect="updated",
        reference_paths=writing.collect_reference_paths(
            read_ref=read_ref, changes=changes
        ),
        memory_sources=writing.needs_memory(changes),
        created_kinds=kinds,
        operation=lambda context: writing.revise_item(context, read_ref, changes),
    )


async def move_jd_item(
    read_ref: wire.ReadRef,
    destination: wire.Destination,
    before_read_ref: wire.ReadRef | None,
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
    content_changes: Annotated[
        tuple[wire.MovementChange, ...], Field(max_length=64)
    ] = (),
) -> Command[object]:
    """排序既有項目，或把任務移到另一職責／未分類；保留物件短碼與內容。

    before_read_ref 是目的同集合的鄰項，null 表示組末；首項用目的集合目前首項作錨點。
    current_container 保留歸屬；task_parent 只適用 Task；
    parent_read_ref=null 表示未分類。
    任務實際更換職責時可同次修改任務文字／級別及新增或修改自己的 O/P。
    set_duty_scope 可同次設定原或目的職責範圍，scope=null 清空；純排序填 []。
    全成或全拒；回 moved/unchanged，轉未分類時附 detached_task_count。
    """
    kinds = [
        change.kind for change in content_changes if isinstance(change, wire.AddDetail)
    ]
    return await _execute(
        runtime,
        effect="moved",
        reference_paths=writing.collect_reference_paths(
            read_ref=read_ref,
            before_read_ref=before_read_ref,
            destination=destination,
            content_changes=content_changes,
        ),
        created_kinds=kinds,
        operation=lambda context: writing.move_item(
            context, read_ref, destination, before_read_ref, content_changes
        ),
    )


async def delete_jd_item(
    read_ref: wire.ReadRef, runtime: ToolRuntime[AgentContext, JobDescriptionToolState]
) -> Command[object]:
    """刪除單一職責、任務、共用 K/S、協作或條件。

    刪職責保留任務並轉未分類；刪 Task 清自有 O/P 與引用，保留共用 K/S。
    刪共用 K/S 會解除所有任務對它的引用。只解除關係用 Task 的 set_capability unlink。
    O/P 請以所屬 Task 的 remove_detail 刪除。成功回 deleted 及必要連帶影響數。
    """
    return await _execute(
        runtime,
        effect="deleted",
        reference_paths=writing.collect_reference_paths(read_ref=read_ref),
        operation=lambda context: writing.delete_item(context, read_ref),
    )


def _validation_error(error: ValidationError | ValidationErrorV1) -> str:
    details = (
        error.errors(include_input=False, include_context=False, include_url=False)
        if isinstance(error, ValidationError)
        else error.errors()
    )
    # 普通 union 也回報不適用分支；只呈現 action/kind 相符分支的本機值驗證。
    mismatched = {
        tuple(detail["loc"][:-1])
        for detail in details
        if detail["type"] == "literal_error"
        and detail["loc"]
        and detail["loc"][-1] in ("action", "kind")
    }
    for detail in details:
        location = tuple(detail["loc"])
        if detail["type"] != "value_error" or any(
            location[: len(prefix)] == prefix for prefix in mismatched
        ):
            continue
        path = ""
        for part in location:
            if isinstance(part, int):
                path += f"[{part}]"
            elif part.isidentifier() and part[:1].islower():
                path += ("." if path else "") + part
        if path:
            return _rejection(
                "invalid_arguments",
                f"{path}：{detail['msg'].removeprefix('Value error, ')}",
                "修正指出的欄位後再送出；其餘內容保持原意。",
            )
    message = "工具參數不符合格式。"
    if details and details[0]["type"] not in ("extra_forbidden", "value_error.extra"):
        location = details[0]["loc"]
        if location and isinstance(location[0], str):
            path = location[0]
            for part in location[1:]:
                if not isinstance(part, int):
                    break
                path += f"[{part}]"
            message = f"{path} 不符合工具參數格式。"
    return _rejection(
        "invalid_arguments",
        message,
        "依工具欄位傳入明確種類與內容；定位使用 JD 短碼，不填 UUID、Workspace 或版本。",
    )


def create_write_tools() -> tuple[StructuredTool, ...]:
    result = []
    for handler in (
        create_jd_task,
        create_jd_item,
        revise_jd_profile,
        revise_jd_item,
        move_jd_item,
        delete_jd_item,
    ):
        tool = StructuredTool.from_function(
            coroutine=handler,
            handle_tool_error=True,
            handle_validation_error=_validation_error,
        )
        schema = tool.get_input_schema()
        assert issubclass(schema, BaseModel)
        tool.args_schema = create_model(
            schema.__name__, __base__=schema, __config__=ConfigDict(extra="forbid")
        )
        result.append(tool)
    return tuple(result)
