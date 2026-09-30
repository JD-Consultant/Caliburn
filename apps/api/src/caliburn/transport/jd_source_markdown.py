"""Shared read-only source-difference rendering; comparison ownership stays in workflows."""

import re

from caliburn.features.work_memory.edit_preparation import describe_body_change
from caliburn.workflows.jd_source_queries import JdSourceChanges, MemorySourceChange


def project_jd_source_changes(
    result: JdSourceChanges, *, comparison_label: str | None = None
) -> str:
    """Only relevant deltas; old unchanged bodies and raw Memory IDs stay private."""
    root, *related = result.changes
    assert root.before is not None
    comparison = comparison_label or "本 Turn pinned Memory"
    unavailable_scope = comparison_label or "本 Turn 固定 Memory"
    lines = [
        "## JD 來源差異",
        f"比較：此 JD 引用固定舊來源 → {comparison} 的同一物件。",
        f"citation_ref: citation_{result.reference.citation_id.hex}",
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
            fence = "`" * max(3, max(map(len, re.findall(r"`+", diff)), default=0) + 1)
            lines.extend([f"{field}：", f"{fence}diff", diff, fence])
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
        lines.append("來源修訂已更新；沒有淨文字差異也不代表已核對，仍須檢查相關依據。")
    return lines
