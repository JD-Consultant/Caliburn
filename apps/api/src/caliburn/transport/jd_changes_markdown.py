"""完整人工 net 與人用完成輪差異；判變由 JD owner 決定。"""

import json
import re
from collections.abc import Callable
from difflib import unified_diff

from pydantic import JsonValue

from caliburn.features.job_description.areas import ResponsibilityArea
from caliburn.features.job_description.capabilities import Capability
from caliburn.features.job_description.change_comparison import JdChangeSnapshot, JdNetChanges
from caliburn.features.job_description.conditions import JobCondition
from caliburn.features.job_description.navigation import JdReadTarget, jd_read_ref
from caliburn.features.job_description.sources import (
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    SourceTargetKind,
)
from caliburn.features.job_description.tasks import TaskDetail, WorkTask
from caliburn.transport.jd_full_text import project_jd_full_text
from caliburn.transport.model_tools.jd_detail_projection import project_jd_item
from caliburn.transport.model_tools.jd_reference_fields import map_jd_reference_fields
from caliburn.workflows.job_description.reads import JdSourceReading


def project_manual_jd_changes(
    changes: JdNetChanges,
    *,
    format_ref: Callable[[str], str],
    format_source: Callable[[JdSourceReference], str],
) -> str:
    lines = [
        "## JD 人工最終差異",
        "比較上一成功 A 採用的正式 JD（尚無成功 A 時為建檔初稿）與本輪起始正式 JD。",
        "以下全部是最後留下的差異；從改後 JD 繼續分析，"
        "不當待套用 patch、工作事實或全部來源已核清。",
    ]
    for field in changes.profile_fields:
        lines.extend(
            [
                f"### profile.{field.value}",
                _endpoint("改前", getattr(changes.before.profile, field.value)),
                _endpoint("改後", getattr(changes.after.profile, field.value)),
            ]
        )
    old, new = _item_values(changes.before), _item_values(changes.after)
    for ref in changes.item_refs:
        effect = (
            "新增" if ref not in old else "刪除（歷史定位，不可編輯）" if ref not in new else "修改"
        )
        lines.extend(
            [
                f"### {format_ref(ref)}：{effect}",
                _endpoint("改前", map_jd_reference_fields(old.get(ref), format_ref)),
                _endpoint("改後", map_jd_reference_fields(new.get(ref), format_ref)),
            ]
        )
    before = {item.citation_id: item for item in changes.before.sources}
    after = {item.citation_id: item for item in changes.after.sources}
    for citation in changes.citation_ids:
        left, right = before.get(citation), after.get(citation)
        effect = (
            "新增" if left is None else "移除（歷史定位，不可編輯）" if right is None else "修改"
        )
        lines.append(f"### {format_ref(f'citation_{citation.hex}')}：來源引用{effect}")
        for label, reference, snapshot in (
            ("改前", left, changes.before),
            ("改後", right, changes.after),
        ):
            if reference is None:
                lines.append(f"{label}：無。")
            else:
                locator = _source_locator(reference.target, snapshot, format_ref)
                review = "待核對" if reference.needs_review else "已核對"
                lines.append(
                    f"{label}：target={locator}；{format_source(reference)}；JD 核對狀態={review}。"
                )
        if left is not None and right is not None:
            if left.source != right.source:
                lines.append("固定來源身分或依據版本已變更。")
            if left.reviewed_revision_id != right.reviewed_revision_id:
                lines.append("JD 核對基底已變更。")
    return "\n\n".join(lines)


def _source_locator(
    target: JdSourceTarget, snapshot: JdChangeSnapshot, format_ref: Callable[[str], str]
) -> str:
    if target.field is not None:
        return f"profile.{target.field.value}"
    if target.item_id is None:
        raise ValueError("The source target has no item identity")
    if target.kind == SourceTargetKind.CAPABILITY:
        capability = next(
            item for item in snapshot.work.capabilities if item.capability_id == target.item_id
        )
        return format_ref(jd_read_ref(capability))
    return format_ref(f"{target.kind.value}_{target.item_id.hex}")


def _endpoint(label: str, value: JsonValue) -> str:
    return f"{label}：{json.dumps(value, ensure_ascii=False)}"


def project_manual_source(reading: JdSourceReading) -> str:
    if reading.interview_sequence is not None:
        return f"訪談序號 {reading.interview_sequence}"
    if reading.source_version is None or not isinstance(reading.reference.source, MemorySource):
        raise ValueError("The fixed Memory source has no readable version metadata")
    title = reading.historical_title or reading.target_title
    if title is None:
        raise ValueError("The fixed Memory source has no readable title")
    return (
        f"Memory {reading.reference.source.layer.value}：{title}；"
        f"涵蓋訪談至 {reading.source_version.covered_through_sequence}"
    )


def _item_values(snapshot: JdChangeSnapshot) -> dict[str, dict[str, JsonValue]]:
    work = snapshot.work
    values = {}
    items: tuple[JdReadTarget, ...] = (
        *work.areas,
        *work.tasks,
        *(detail for task in work.tasks for detail in task.details),
        *work.capabilities,
        *work.collaborators,
        *work.conditions,
    )
    for item in items:
        value = project_jd_item(item, work, ())
        value.pop("supporting_sources")
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
            case JobCondition():
                siblings = tuple(
                    condition for condition in work.conditions if condition.kind == item.kind
                )
            case _:
                siblings = work.collaborators
        value["position"] = siblings.index(item) + 1
        values[jd_read_ref(item)] = value
    return values


def project_turn_jd_changes(before: JdChangeSnapshot, after: JdChangeSnapshot) -> str:
    old = project_jd_full_text(before.profile, before.work)
    new = project_jd_full_text(after.profile, after.work)
    diff = "".join(
        unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile="本輪開始的正式 JD",
            tofile="本輪完成採用的 JD",
        )
    )
    lines = [
        "## 這輪 JD 變更",
        "比較本輪開始與完成採用的兩份 JD，不包含後續修改或撤回；不是目前 JD。",
        "以下為淨差異，不是逐步操作紀錄；閱讀不表示已核對來源，也不決定是否可撤回。",
        "### 正文",
    ]
    if diff:
        fence = "`" * max(3, max(map(len, re.findall(r"`+", diff)), default=0) + 1)
        lines.extend(["`-` 表示移除，`+` 表示加入。", f"{fence}diff", diff, fence])
    else:
        lines.append("正文淨差異：無。")
    old_sources = {item.citation_id: item for item in before.sources}
    new_sources = {item.citation_id: item for item in after.sources}
    added = len(new_sources.keys() - old_sources.keys())
    removed = len(old_sources.keys() - new_sources.keys())
    updated = sum(
        old_sources[key] != new_sources[key] for key in old_sources.keys() & new_sources.keys()
    )
    lines.append("### 來源依據摘要")
    if added or removed or updated:
        lines.append(f"新增 {added} 筆、移除 {removed} 筆、調整 {updated} 筆來源依據。")
        lines.append("調整包含依據位置或核對狀態變化；本檢視不展開來源全文。")
    else:
        lines.append("來源依據淨差異：無。")
    return "\n\n".join(lines)
