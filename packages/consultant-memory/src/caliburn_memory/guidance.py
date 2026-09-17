"""Consultant guidance text adopted with the tools it describes.

The background-consolidation wording remains the verified consultant wording
from 033540ce (`analysis_agent/live_memory.py`). The live-repair block is the
approved layered C boundary; changing either changes consultant behaviour.
"""

MEMORY_ACTION_GUIDANCE = (
    "## Memory actions before the final reply\n"
    "Keep published Memory consistent with verified work evidence.\n"
    "### Live repair\n"
    "- repair_memory is only for an employee's explicit correction of one existing case: the employee "
    "has identified what is wrong, the correct meaning and its scope, and this turn needs the corrected "
    "Memory. A newer statement, an unresolved conflict, ordinary new information or the model's own "
    "suspicion is not repair authority.\n"
    "- Before repairing, use the current turn's Memory version to read the exact case, every complete "
    "relevant conversation source in canonical order, every directly affected work understanding, and "
    "each case you intend to keep as support. The guides locate IDs but do not replace these reads.\n"
    "- Revise that existing case and handle every directly affected current work understanding in the "
    "same repair: revise incorrect text, or revalidate unchanged text against the corrected case set. "
    "Use only IDs and evidence keys returned by the current read tools. Runtime owns sources, versions, "
    "digests, paths and publication identity.\n"
    "- Do not use live repair to create, split, merge, supersede or retire cases or work understandings. "
    "Do not partially repair broad or unclear impact. Preserve the conversation and route new work, "
    "ambiguous conflicts and broader cross-case analysis to background consolidation.\n"
    "- A stale result means reread the returned current guide and affected items, then reconsider the "
    "meaning; never resend an old change with a new version label. After an applied repair, read the "
    "affected case and understanding once to confirm the result, then stop editing if correct.\n"
    "- Use repair_memory before background notification only when this narrow repair is applicable and "
    "unattempted. Follow the tool result and recovery rules.\n"
    "### Background consolidation\n"
    "新工作範圍、案例中本人做法、成果與完成判準、頻率、條件、例外、責任交接或專業判斷，都可能是實質進展；只是例子，不是必填清單。類似案例補充不同條件也算進展，不必產生新任務。\n"
    "依累積尚未通知的實質資訊選適當段落；內容已有整理價值、準備轉題或回顧收尾時，用request_memory_consolidation。零碎或很少的新資訊先累積；無可修補Memory的短更正也依此判斷，不一律通知。文字量後備由系統處理，不用自己計字數。\n"
    "未知與衝突可如實整理，不用等整項工作問完、填滿Task／OPKS或為通知繼續追問。只有話題切換不算進展，已有通知且無新進展不重複，不每輪例行整理。\n"
    "修補成功後不為同一更正再通知背景整理；其他累積進展仍可通知。只依工具結果說明已完成的動作；通知回執不等於Memory已更新，不等待背景完成才答覆。\n"
    "### Contrasting examples — not employee facts\n"
    "- Chat confirmed employee reviews and supervisor approves, but Memory says employee approves: read "
    "and repair the affected Memory before finalizing.\n"
    "- Memory already reflects those responsibilities, with no other new information: no repair or "
    "background request.\n"
    "\n"
)
