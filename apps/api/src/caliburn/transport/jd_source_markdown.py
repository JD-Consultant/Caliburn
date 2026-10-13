"""Shared read-only source-difference rendering; comparison ownership stays in workflows."""

import re

from caliburn.features.job_description.sources import SourceTargetKind, TaskSourceContents
from caliburn.features.work_memory.edit_preparation import describe_body_change
from caliburn.workflows.job_description.evidence import JdEvidenceChanges
from caliburn.workflows.job_description.source_queries import JdSourceChanges, MemorySourceChange


def project_jd_target_changes(result: JdEvidenceChanges) -> str:
    """Render only the exact target's reviewed/current values, never surrounding JD items."""
    lines = [
        "## JD 項目差異",
        "比較：此引用上次核對的 JD 項目 → 所選正式 JD 修訂的同一項目。",
        "只讀；未確認支持 JD，也未解除待核對。",
    ]
    if result.before == result.after:
        lines.append("此 JD 項目沒有淨差異。")
        if result.reference.needs_review:
            lines.append("人工曾修改此項，即使改回原文仍保留待核對。")
        return "\n".join(lines)
    if result.reference.target.kind == SourceTargetKind.TASK:
        if not isinstance(result.before, TaskSourceContents) or not isinstance(
            result.after, TaskSourceContents
        ):
            raise ValueError("Task evidence comparison requires complete task support")
        lines.extend(_task_changes(result.before, result.after))
        return "\n".join(lines)
    if isinstance(result.before, TaskSourceContents) or isinstance(
        result.after, TaskSourceContents
    ):
        raise ValueError("Task evidence comparison must use the same support shape")
    labels = {
        SourceTargetKind.PROFILE_FIELD: ("欄位內容",),
        SourceTargetKind.AREA: ("職責名稱", "職責範圍"),
        SourceTargetKind.CAPABILITY: ("能力類型", "能力名稱", "能力說明"),
        SourceTargetKind.COLLABORATOR: ("協作對象", "合作範圍"),
        SourceTargetKind.CONDITION: ("條件分類", "條件內容"),
    }[result.reference.target.kind]
    for label, before, after in zip(labels, result.before, result.after, strict=True):
        if before != after:
            lines.extend(
                [f"{label}：", *_fenced_diff(describe_body_change(before or "", after or ""))]
            )
    return "\n".join(lines)


def _task_changes(before: TaskSourceContents, after: TaskSourceContents) -> list[str]:
    lines = []
    for label, old, new in (
        ("任務名稱", before.title, after.title),
        ("工作內容", before.description, after.description),
    ):
        if old != new:
            lines.extend([f"{label}：", *_fenced_diff(describe_body_change(old or "", new or ""))])
    old_details = {detail.detail_id: detail for detail in before.details}
    new_details = {detail.detail_id: detail for detail in after.details}
    for identity in sorted(old_details.keys() | new_details.keys()):
        old_detail, new_detail = old_details.get(identity), new_details.get(identity)
        if old_detail == new_detail:
            continue
        selected = new_detail or old_detail
        assert selected is not None
        label = "工作成果" if selected.kind.value == "outcome" else "工作要求"
        effect = "新增" if old_detail is None else "移除" if new_detail is None else "修改"
        old = f"{old_detail.kind.value}: {old_detail.text}" if old_detail else ""
        new = f"{new_detail.kind.value}: {new_detail.text}" if new_detail else ""
        lines.extend([f"{effect}{label}：", *_fenced_diff(describe_body_change(old, new))])
    old_capabilities = {capability.capability_id: capability for capability in before.capabilities}
    new_capabilities = {capability.capability_id: capability for capability in after.capabilities}
    for identity in sorted(old_capabilities.keys() | new_capabilities.keys()):
        old_capability, new_capability = (
            old_capabilities.get(identity),
            new_capabilities.get(identity),
        )
        if old_capability == new_capability:
            continue
        effect = (
            "新增連結"
            if old_capability is None
            else "移除連結"
            if new_capability is None
            else "修改定義"
        )
        old = (
            "\n".join(
                (
                    old_capability.kind.value,
                    old_capability.name or "",
                    old_capability.description or "",
                )
            )
            if old_capability
            else ""
        )
        new = (
            "\n".join(
                (
                    new_capability.kind.value,
                    new_capability.name or "",
                    new_capability.description or "",
                )
            )
            if new_capability
            else ""
        )
        lines.extend([f"任務 K/S {effect}：", *_fenced_diff(describe_body_change(old, new))])
    return lines


def _fenced_diff(diff: str) -> list[str]:
    fence = "`" * max(3, max(map(len, re.findall(r"`+", diff)), default=0) + 1)
    return [f"{fence}diff", diff, fence]


def project_jd_source_changes(
    result: JdSourceChanges, *, comparison_label: str | None = None, citation_ref: str | None = None
) -> str:
    """Only relevant deltas; old unchanged bodies and raw Memory IDs stay private."""
    root, *related = result.changes
    assert root.before is not None
    comparison = comparison_label or "本 Turn pinned Memory"
    unavailable_scope = comparison_label or "本 Turn 固定 Memory"
    lines = [
        "## JD 來源差異",
        f"比較：此 JD 引用固定舊來源 → {comparison} 的同一物件。",
        f"citation_ref: {citation_ref or f'citation_{result.reference.citation_id.hex}'}",
        f"歷史名稱：{root.before.content.title}",
        (
            f"可讀 target_title：{root.after.content.title}"
            if root.after
            else f"來源可用性：同一物件已不在{unavailable_scope}；不按同名替代。"
        ),
        "只讀；未確認支持 JD，也未解除待核對。",
    ]
    root_delta = _memory_delta(root)
    lines.extend(root_delta or ["來源自身內容與訪談引用無變化。"])
    for change in related:
        delta = _memory_delta(change)
        if not delta:
            continue
        selected = change.after or change.before
        assert selected is not None
        lines.extend(["", f"### 直接情境依據：{selected.content.title}"])
        if change.before is None:
            lines.append("新增直接情境引用（不代表新建物件）。")
        elif change.after is None:
            lines.append("移除直接情境引用（不據此推論物件全域刪除）。")
        lines.extend(delta)
    if not root_delta and all(not _memory_delta(change) for change in related):
        lines.append("相關來源鏈亦無變化。")
    return "\n".join(lines)


def _memory_delta(change: MemorySourceChange) -> list[str]:
    before = change.before.content if change.before else None
    after = change.after.content if change.after else None
    lines = []
    for field in ("title", "description", "body"):
        old = getattr(before, field) if before else ""
        new = getattr(after, field) if after else ""
        if old != new:
            diff = describe_body_change(old, new)
            lines.extend([f"{field}：", *_fenced_diff(diff)])
    removed = sorted(set(change.before_interviews) - set(change.after_interviews))
    added = sorted(set(change.after_interviews) - set(change.before_interviews))
    if removed:
        lines.append(f"移除訪談引用序號：{', '.join(map(str, removed))}")
    if added:
        lines.append(f"新增訪談引用序號：{', '.join(map(str, added))}")
    if not lines and (change.before is None) != (change.after is None):
        lines.append("來源選擇已改變。")
    if (
        not lines
        and change.before is not None
        and change.after is not None
        and change.before.revision_id != change.after.revision_id
    ):
        lines.append("來源修訂已更新，沒有淨文字差異；依本輪正文判斷引用與 JD 是否需調整。")
    return lines
