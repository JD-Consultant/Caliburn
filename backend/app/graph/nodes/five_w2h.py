"""5W2H 補洞節點：逐欄位追問缺漏，並把回答存回 extracted_tasks。"""
import logging

from app.graph.constants import FIVE_W2H_LIST_FIELDS, FIVE_W2H_REQUIRED
from app.graph.phase import Phase
from app.graph.state import InterviewState
from app.graph.task_loop import TaskLoopManager
from app.services.icap_ksa_rag import search_outputs

logger = logging.getLogger("jobintel")


def _prefill_from_star(task: dict) -> dict:
    """S → situation；A → workflow_steps（以「、」拆分）。"""
    star = task.get("star_case") or {}
    task = dict(task)

    if not task.get("situation") and star.get("situation"):
        task["situation"] = star["situation"]

    if not task.get("workflow_steps") and star.get("action"):
        action = star["action"]
        steps = [s.strip() for s in action.replace("；", "、").split("、") if s.strip()]
        task["workflow_steps"] = steps if len(steps) > 1 else [action]

    return task


def _store_answer(task: dict, field: str, answer: str) -> dict:
    task = dict(task)
    if field in FIVE_W2H_LIST_FIELDS:
        task[field] = [
            s.strip()
            for s in answer.replace("、", ",").replace("，", ",").split(",")
            if s.strip()
        ] or [answer]
    else:
        task[field] = answer
    return task


async def five_w2h_node(state: InterviewState) -> dict:
    tasks = list(state.get("extracted_tasks", []))
    loop = TaskLoopManager(tasks, state.get("current_task_index", 0))

    if loop.is_done:
        logger.warning("five_w2h: idx=%d >= len(tasks)=%d, routing to indicator as fallback", loop.index, len(tasks))
        return {
            "ai_response":   "所有任務的 5W2H 資訊已補齊，正在生成行為指標…",
            "current_stage": "indicator",
            "missing_fields": [],
        }

    idx = loop.index
    current_task = _prefill_from_star(dict(loop.current_task))
    task_name = current_task["task_name"]
    task_id   = loop.current_task_id()
    phase_key = Phase.five_w2h(task_id).to_str()
    prev_missing = state.get("missing_fields", [])

    if prev_missing:
        phase_msgs = [m for m in state["messages"] if isinstance(m, dict) and m.get("phase") == phase_key]
        last_user  = next((m for m in reversed(phase_msgs) if m.get("role") == "user"), None)
        if last_user is None:
            all_user = [m for m in state["messages"] if isinstance(m, dict) and m.get("role") == "user"]
            last_user = all_user[-1] if all_user else None
        if last_user:
            current_task = _store_answer(current_task, prev_missing[0], last_user["content"])
            logger.debug("five_w2h: stored '%s'='%s...' for task=%s",
                         prev_missing[0], last_user["content"][:40], task_name)
            tasks = list(tasks)
            tasks[idx] = current_task

    missing = [
        (field, label, question)
        for field, (label, question) in FIVE_W2H_REQUIRED.items()
        if not current_task.get(field)
    ]

    if not missing:
        logger.info("five_w2h: task '%s' complete → indicator", task_name)
        return {
            "extracted_tasks":    tasks,
            "current_task_index": idx,
            "ai_response":        f"「{task_name}」的資訊已補齊，正在為你生成行為指標…",
            "current_stage":      "five_w2h",
            "missing_fields":     [],
        }

    field, label, question = missing[0]

    icap_suggestion = ""
    if field == "outputs" and state.get("icap_mode", "company_defined") != "company_defined":
        top_ocs_code = (state.get("icap_candidates") or [{}])[0].get("ocs_code")
        hits = await search_outputs(
            f"{task_name} 工作產出",
            top_k=3,
            ocs_code_filter=top_ocs_code,
        )
        if hits:
            suggestions = "、".join(h["name"] for h in hits)
            icap_suggestion = f"\n\n（iCAP 參考：此類職務常見產出包含 {suggestions}，可參考或自行描述）"

    direct_question = (
        f"關於「{task_name}」，我還需要了解一個細節：\n\n"
        f"**{label}** — {question}{icap_suggestion}"
    )
    logger.debug("five_w2h: asking '%s' for task=%s", field, task_name)

    return {
        "extracted_tasks": tasks,
        "ai_response":     direct_question,
        "current_stage":   "five_w2h",
        "phase":           phase_key,
        "missing_fields":  [f for f, _, _ in missing],
    }
