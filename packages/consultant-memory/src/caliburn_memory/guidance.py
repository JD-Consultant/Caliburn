"""Consultant guidance text adopted with the tools it describes.

MEMORY_ACTION_GUIDANCE is taken verbatim from the verified consultant at
033540ce (`analysis_agent/live_memory.py`). Its old home was that host's own
assembly, which is not adopted; the text belongs with `repair_memory` and
`request_memory_consolidation`, both of which live in this package. Changing
this wording changes verified consultant behaviour -- see adoption.json.
"""

MEMORY_ACTION_GUIDANCE = (
    "## Memory actions before the final reply\n"
    "Keep published Memory consistent with verified work evidence.\n"
    "### Live repair\n"
    "- If published Memory conflicts with a verified employee correction or original-interview evidence "
    "you checked, use repair_memory before finalizing. Repair your own "
    "earlier extraction or consolidation errors too; no separate employee request is needed.\n"
    "- Before preparing a repair, read the affected knowledge in this input's current read view. "
    "Tool results from earlier inputs are historical snapshots: background consolidation may have "
    "added or revised sections since that read. The guide locates content but does not replace this read.\n"
    "- Update the existing subject in place, including any now-resolved uncertainty; add a section "
    "only for a genuinely new subject. Success means the affected knowledge and guide agree with "
    "the verified correction, without a second conflicting account or loss of unrelated valid details. "
    "After an applied repair, read the affected passage once to check that result; use the returned "
    "guide for its check. If correct, stop editing.\n"
    "- If meaning or case identity is unresolved, ask or read the relevant source. A newer statement "
    "alone does not establish the replacement.\n"
    "- An unchanged restatement needs no write only when current published Memory already reflects it; "
    "chat acknowledgments are not proof of saving.\n"
    "- Use repair_memory before background notification for an applicable, unattempted repair. Follow "
    "repair_memory's result and recovery rules.\n"
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
