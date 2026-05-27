"""5W2H 補洞節點：逐欄位追問缺漏，並把回答存回 extracted_tasks。"""
import logging

from app.graph.constants import FIVE_W2H_LIST_FIELDS, FIVE_W2H_REQUIRED
from app.graph.phase import Phase
from app.graph.state import InterviewState
from app.graph.task_loop import TaskLoopManager
from app.services.icap_retriever import (
    search_indicators,
    search_knowledge,
    search_outputs,
    search_skills,
    search_tasks,
)

logger = logging.getLogger("jobintel")

_ICAP_SUGGESTION_FIELDS = frozenset({
    "workflow_steps",
    "tools",
    "outputs",
    "quality_standards",
})


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


def _unique_names(hits: list[dict], limit: int = 3) -> list[str]:
    names = []
    seen = set()
    for hit in hits:
        name = (hit.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


async def _icap_suggestion(field: str, task_name: str, state: InterviewState) -> str:
    if field not in _ICAP_SUGGESTION_FIELDS:
        return ""
    if state.get("icap_mode", "company_defined") == "company_defined":
        return ""

    top_ocs_code = (state.get("icap_candidates") or [{}])[0].get("ocs_code")
    if not top_ocs_code:
        return ""

    if field == "outputs":
        hits = await search_outputs(f"{task_name} 工作產出", top_k=3, ocs_code_filter=top_ocs_code)
        names = _unique_names(hits)
        hint = f"這類任務常見產出包含：{'、'.join(names)}。" if names else ""
    elif field == "workflow_steps":
        hits = await search_tasks(f"{task_name} 工作流程 步驟", top_k=3, ocs_code_filter=top_ocs_code)
        names = _unique_names(hits)
        hint = f"iCAP 中相近任務包含：{'、'.join(names)}。" if names else ""
    elif field == "quality_standards":
        hits = await search_indicators(f"{task_name} 品質 標準 行為指標", top_k=3, ocs_code_filter=top_ocs_code)
        names = _unique_names(hits)
        hint = f"相近指標常提到：{'、'.join(names)}。" if names else ""
    else:  # tools
        skill_hits = await search_skills(f"{task_name} 工具 系統 方法", top_k=2, ocs_code_filter=top_ocs_code)
        knowledge_hits = await search_knowledge(f"{task_name} 工具 系統 方法", top_k=2, ocs_code_filter=top_ocs_code)
        names = _unique_names(skill_hits + knowledge_hits)
        hint = f"相關職能常見知識或技能包含：{'、'.join(names)}。" if names else ""

    if not hint:
        return ""

    return (
        f"iCAP 參考提示：{hint}\n\n"
        "這只是參考，不一定適用；請以你的實際工作為準，沒有符合也可以直接忽略。"
    )


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

    icap_suggestion = await _icap_suggestion(field, task_name, state)
    direct_question = (
        f"關於「{task_name}」，我還需要了解一個細節：\n\n"
        f"**{label}** — {question}"
    )
    logger.debug("five_w2h: asking '%s' for task=%s", field, task_name)

    ai_messages = []
    if icap_suggestion:
        ai_messages.append({"kind": "reference", "content": icap_suggestion})
    ai_messages.append({"kind": "question", "content": direct_question})

    return {
        "extracted_tasks": tasks,
        "ai_response":     direct_question,
        "ai_messages":     ai_messages,
        "current_stage":   "five_w2h",
        "phase":           phase_key,
        "missing_fields":  [f for f, _, _ in missing],
    }
