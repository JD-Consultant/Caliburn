"""v3 深問三階段節點（interrupt 驅動）：star / five_w2h / indicator。
重用 app.graph.prompts.* 與 app.graph.constants（純資料模組）；控制流為新寫。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState
from app.graph.constants import FIVE_W2H_REQUIRED, FIVE_W2H_LIST_FIELDS

logger = logging.getLogger("jobintel")

# ---- STAR 槽位（domain 資料；自舊 app.graph.nodes.star 移植） ----
_SLOT_ORDER = ["S", "T", "A", "R"]
_SLOT_KEY = {"S": "situation", "T": "task", "A": "action", "R": "result"}
_SLOT_LABELS = {
    "S": "情境（Situation）", "T": "任務目標（Task）",
    "A": "行動步驟（Action）", "R": "結果產出（Result）",
}
_SLOT_QUESTIONS = {
    "S": "針對「{task_name}」，最近一次比較典型或複雜的情況，當時的背景是什麼？",
    "T": "在那件事中，你的目標是什麼？哪些具體事項是你負責的？",
    "A": "你實際怎麼一步一步處理的？用了哪些工具或系統？遇到困難怎麼解決？",
    "R": "最後產出了什麼？是否達成目標、縮短時間或改善了什麼？",
}

_STAR_REFINE = """把工作者對「{task_name}」任務的 STAR 四槽口語回答，整理成精煉的第一人稱描述。
原始回答：
- 情境(S)：{S}
- 任務(T)：{T}
- 行動(A)：{A}
- 結果(R)：{R}

只輸出 JSON（不要其他文字）：
{{"S":"精煉後情境","T":"精煉後任務","A":"精煉後行動","R":"精煉後結果"}}
規則：保留原意、勿杜撰未提及的工具/對象/數字；每槽 15〜60 字。"""


def _current_task(state: InterviewState) -> tuple[int, dict, str]:
    idx = state["deep"]["current_task_index"]
    task = dict(state["tasks"][idx])
    task_id = (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]
    return idx, task, task_id


async def star_node(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    idx, task, task_id = _current_task(state)
    task_name = task["task_name"]

    raw: dict[str, str] = {}
    for slot in _SLOT_ORDER:
        answer = interrupt({
            "kind": "ask_human", "stage": "star", "slot": slot,
            "task_id": task_id, "task_name": task_name,
            "label": _SLOT_LABELS[slot],
            "question": _SLOT_QUESTIONS[slot].format(task_name=task_name),
        })
        raw[slot] = answer if isinstance(answer, str) else str(answer)

    # deep 階 LLM 整理（best-effort；失敗或缺鍵 → 保留原答）
    refined = raw
    if deps.llm is not None:
        prompt = _STAR_REFINE.format(task_name=task_name, **raw)
        got = await deps.llm.complete_json(prompt, role="deep", default=None)
        if isinstance(got, dict) and all(got.get(s) for s in _SLOT_ORDER):
            refined = {s: str(got[s]) for s in _SLOT_ORDER}

    star_case = {_SLOT_KEY[s]: refined[s] for s in _SLOT_ORDER}
    task["star_case"] = star_case
    tasks = list(state["tasks"])
    tasks[idx] = task

    deep = dict(state["deep"])
    slots_by_task = dict(deep["slots_by_task"])
    slots_by_task[task_id] = star_case
    deep["slots_by_task"] = slots_by_task

    logger.info("star_node: task=%s STAR complete -> five_w2h", task_name)
    return {"tasks": tasks, "deep": deep}


# ---- Five W2H 節點 ----

def _prefill_from_star(task: dict) -> dict:
    """S → situation；A → workflow_steps（以「、」「；」拆分）。"""
    star = task.get("star_case") or {}
    if not task.get("situation") and star.get("situation"):
        task["situation"] = star["situation"]
    if not task.get("workflow_steps") and star.get("action"):
        action = star["action"]
        steps = [s.strip() for s in action.replace("；", "、").split("、") if s.strip()]
        task["workflow_steps"] = steps if len(steps) > 1 else [action]
    return task


async def _prefill_from_catalog(task: dict, deps) -> dict:
    """catalog k/s/output 當 just-in-time prefill：目前實填 outputs（output_pairs 名稱）。"""
    ref = task.get("indexer_ref") or {}
    task_id = ref.get("task_id")
    if not task_id or deps.knowledge is None:
        return task
    res = await deps.knowledge.tasks_by_id([task_id])
    detail = next((t for t in res.tasks if t.task_id == task_id), None)
    if detail and not task.get("outputs") and detail.output_pairs:
        task["outputs"] = [p.name for p in detail.output_pairs if p.name]
    return task


def _store_answer(task: dict, field: str, answer: str) -> dict:
    if field in FIVE_W2H_LIST_FIELDS:
        task[field] = [s.strip() for s in answer.replace("、", ",").replace("，", ",").split(",")
                       if s.strip()] or [answer]
    else:
        task[field] = answer
    return task


async def five_w2h_node(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    idx, task, _ = _current_task(state)
    task = _prefill_from_star(task)
    task = await _prefill_from_catalog(task, deps)
    task_name = task["task_name"]

    for field, (label, question) in FIVE_W2H_REQUIRED.items():
        if task.get(field):
            continue
        answer = interrupt({
            "kind": "ask_human", "stage": "five_w2h", "field": field,
            "task_name": task_name, "label": label,
            "question": f"關於「{task_name}」：{question}",
        })
        task = _store_answer(task, field, answer if isinstance(answer, str) else str(answer))

    tasks = list(state["tasks"])
    tasks[idx] = task
    logger.info("five_w2h_node: task=%s complete -> indicator", task_name)
    return {"tasks": tasks}
