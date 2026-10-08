"""Human-readable net changes; original fixed endpoints are selected by the workflow."""

import re
from difflib import unified_diff

from caliburn.features.job_description.change_queries import JdChangeSnapshot
from caliburn.transport.jd_full_text import project_jd_full_text


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
