"""主要職責分組節點：把已確認任務整理成可確認的主要職責骨架。"""
import logging

from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState

logger = logging.getLogger("jobintel")

_PURE_CONFIRM_KEYWORDS = frozenset({"確認", "好", "對", "沒問題", "ok", "OK", "可以", "繼續", "正確", "yes", "Yes"})

_GROUPING_PROMPT = """你是職務分析顧問。請根據「已確認的工作任務」整理主要職責分組。
這一階段只整理「主要職責 → 工作任務」骨架，不新增任務，不改寫行為指標。

職稱：{job_title}
部門：{department}
職務摘要：{job_summary}
iCAP 參考狀態：{icap_context}

已確認工作任務：
{tasks_context}

{previous_groups_context}

規則：
1. 產出 2 到 5 個主要職責；若任務很少，可只產出 1 個
2. 每個任務必須且只能出現在一個主要職責
3. task_ids 只能使用上方已列出的 task_id，不得新增任務
4. 主要職責名稱要像職務說明書中的單元名稱，例如「後端服務與 API 開發」
5. 若 iCAP 有參考基準，只能作為命名風格參考，不可硬套官方職類
6. 如果使用者正在修正上一版分組，請依照最新對話更新

輸出 JSON（只輸出 JSON，不要其他文字）：
[
  {{
    "title": "主要職責名稱",
    "description": "這個職責範圍的簡短說明",
    "task_ids": ["task_001", "task_002"]
  }}
]

最新對話：
{conversation}
"""


def _is_pure_confirmation(text: str) -> bool:
    cleaned = text.strip().rstrip("！!。，, ")
    return cleaned in _PURE_CONFIRM_KEYWORDS or cleaned.lower() in {"ok", "yes"}


def _tasks_context(tasks: list[dict]) -> str:
    lines = []
    for task in tasks:
        detail = [
            f"task_id={task.get('task_id', '')}",
            f"task_name={task.get('task_name', '')}",
            f"category={task.get('category', '待確認')}",
            f"frequency={task.get('frequency', '待確認')}",
            f"responsibility_type={task.get('responsibility_type', '待確認')}",
        ]
        if task.get("description"):
            detail.append(f"description={task['description']}")
        lines.append("- " + "；".join(detail))
    return "\n".join(lines) or "（無任務）"


def _previous_groups_context(groups: list[dict], tasks: list[dict]) -> str:
    if not groups:
        return ""
    task_name_by_id = {task.get("task_id"): task.get("task_name", "") for task in tasks}
    lines = ["上一版主要職責分組（若使用者提出修正，請在此基礎上更新）："]
    for group in groups:
        task_names = [
            task_name_by_id.get(task_id, task_id)
            for task_id in group.get("task_ids", [])
        ]
        lines.append(f"- {group.get('title', '')}：{'、'.join(task_names)}")
    return "\n".join(lines) + "\n"


def _conversation_context(state: InterviewState) -> str:
    return "\n".join(
        f"{'工作者' if m.get('role') == 'user' else 'AI'}：{m.get('content', '')}"
        for m in state.get("messages", [])
        if isinstance(m, dict)
    )


def _icap_context(state: InterviewState) -> str:
    if state.get("icap_mode") == "company_defined":
        return "未採用 iCAP 主要參考"
    candidates = state.get("icap_candidates") or []
    if not candidates:
        return "無 iCAP 候選"
    c0 = candidates[0]
    return f"{c0.get('icap_title', '')}（{c0.get('confidence_label', c0.get('confidence', ''))}，僅作命名參考）"


def _fallback_groups(tasks: list[dict]) -> list[dict]:
    if not tasks:
        return []
    return [{
        "responsibility_id": "resp_001",
        "title": "主要工作任務",
        "description": "根據已確認任務整理的主要職責。",
        "task_ids": [task["task_id"] for task in tasks if task.get("task_id")],
    }]


def _ensure_task_ids(tasks: list[dict]) -> list[dict]:
    updated = []
    for index, task in enumerate(tasks, 1):
        task_copy = dict(task)
        task_copy.setdefault("task_id", f"task_{index:03d}")
        updated.append(task_copy)
    return updated


def _normalize_groups(raw_groups: list, tasks: list[dict]) -> list[dict]:
    if not isinstance(raw_groups, list):
        return _fallback_groups(tasks)

    valid_task_ids = [task["task_id"] for task in tasks if task.get("task_id")]
    valid_set = set(valid_task_ids)
    assigned: set[str] = set()
    groups: list[dict] = []

    for raw in raw_groups:
        if not isinstance(raw, dict):
            continue
        task_ids = []
        for task_id in raw.get("task_ids") or []:
            if task_id in valid_set and task_id not in assigned:
                task_ids.append(task_id)
                assigned.add(task_id)
        if not task_ids:
            continue
        groups.append({
            "responsibility_id": f"resp_{len(groups) + 1:03d}",
            "title": str(raw.get("title") or f"主要職責 {len(groups) + 1}").strip(),
            "description": str(raw.get("description") or "").strip(),
            "task_ids": task_ids,
        })

    unassigned = [task_id for task_id in valid_task_ids if task_id not in assigned]
    if unassigned:
        if groups:
            groups[-1]["task_ids"].extend(unassigned)
        else:
            groups = _fallback_groups(tasks)

    return groups or _fallback_groups(tasks)


def _build_grouping_summary(groups: list[dict], tasks: list[dict], is_revision: bool) -> str:
    task_name_by_id = {task.get("task_id"): task.get("task_name", "") for task in tasks}
    header = "根據你的補充，我更新了主要職責分組：\n" if is_revision else "我先把任務整理成以下主要職責，請確認是否合理：\n"
    lines = [header]
    for i, group in enumerate(groups, 1):
        lines.append(f"{i}. **{group['title']}**")
        if group.get("description"):
            lines.append(f"   {group['description']}")
        for task_id in group.get("task_ids", []):
            task_name = task_name_by_id.get(task_id, task_id)
            lines.append(f"   - {task_name}")
    lines.append("\n如果分組正確，請說「確認」。如果要調整，可以直接說例如「把 API 測試移到後端服務開發」。")
    return "\n".join(lines)


async def responsibility_grouping_node(state: InterviewState) -> dict:
    tasks = _ensure_task_ids(list(state.get("extracted_tasks") or []))
    existing_groups = list(state.get("responsibility_groups") or [])
    prev_round = state.get("responsibility_grouping_round", 0)

    if prev_round >= 1 and existing_groups:
        user_msgs = [m for m in state.get("messages", []) if isinstance(m, dict) and m.get("role") == "user"]
        if user_msgs and _is_pure_confirmation(user_msgs[-1]["content"]):
            logger.info("responsibility_grouping_node: confirmation detected")
            return {
                "extracted_tasks": tasks,
                "responsibility_groups": existing_groups,
                "current_stage": "responsibility_grouping",
                "ai_response": "",
                "responsibility_grouping_round": prev_round + 1,
            }

    if not tasks:
        return {
            "extracted_tasks": tasks,
            "responsibility_groups": [],
            "current_stage": "responsibility_grouping",
            "ai_response": "目前還沒有可分組的任務，請先補充工作內容。",
            "responsibility_grouping_round": prev_round + 1,
        }

    prompt = _GROUPING_PROMPT.format(
        job_title=state["job_title"],
        department=state.get("department", ""),
        job_summary=state.get("job_summary", ""),
        icap_context=_icap_context(state),
        tasks_context=_tasks_context(tasks),
        previous_groups_context=_previous_groups_context(existing_groups, tasks),
        conversation=_conversation_context(state),
    )
    raw_groups = await LLMGateway(temperature=0.0).invoke_json(prompt, default=[])
    groups = _normalize_groups(raw_groups, tasks)
    logger.info("responsibility_grouping_node: grouped %d tasks into %d groups", len(tasks), len(groups))

    return {
        "extracted_tasks": tasks,
        "responsibility_groups": groups,
        "current_stage": "responsibility_grouping",
        "ai_response": _build_grouping_summary(groups, tasks, is_revision=prev_round >= 1),
        "responsibility_grouping_round": prev_round + 1,
    }
