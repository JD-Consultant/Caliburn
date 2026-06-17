"""v3 深問三階段節點（interrupt 驅動）：star / five_w2h / indicator。
重用 app.graph_v3.prompts.* 與 app.graph_v3.constants（純資料模組）；控制流為新寫。"""
import json
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState
from app.graph_v3.constants import FIVE_W2H_REQUIRED, FIVE_W2H_LIST_FIELDS, INDICATOR_REQUIRED_FIELDS
from app.graph_v3.tracing import traced_node
import app.graph_v3.prompts.indicator as ind_prompts

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


@traced_node("star")
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
    if not task_id or deps.knowledge is None or task.get("outputs"):
        return task
    res = await deps.knowledge.tasks_by_id([task_id])
    detail = next((t for t in res.tasks if t.task_id == task_id), None)
    if detail and not task.get("outputs") and detail.output_pairs:
        task["outputs"] = [p.name for p in detail.output_pairs if p.name]
    return task


def _store_answer(task: dict, field: str, answer: str) -> dict:
    if field in FIVE_W2H_LIST_FIELDS:
        task[field] = [s.strip() for s in answer.replace("；", ",").replace("、", ",").replace("，", ",").split(",")
                       if s.strip()] or ([answer.strip()] if answer.strip() else [])
    else:
        task[field] = answer
    return task


@traced_node("five_w2h")
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


# ---- Indicator 節點 ----

_QUALITY_THRESHOLD = 0.60
_MAX_QUALITY_RETRIES = 1
_DIM_TO_FIELDS = {
    "has_situation": ["situation"], "has_purpose": ["purpose"],
    "has_collaborators": ["collaborators"], "has_tools": ["tools"],
    "has_action": ["workflow_steps"], "has_output": ["outputs"],
    "has_standard": ["quality_standards", "time_standards"],
}


def _score_quality(dims: dict) -> tuple[float, list[str]]:
    weak: list[str] = []
    hits = 0
    for dim, fields in _DIM_TO_FIELDS.items():
        if dims.get(dim):
            hits += 1
        else:
            weak.extend(fields)
    return round(hits / len(_DIM_TO_FIELDS), 3), weak


def _avg_quality(results: list[dict]) -> tuple[float, list[str]]:
    if not results:
        return 0.0, list({f for fs in _DIM_TO_FIELDS.values() for f in fs})
    total = 0.0
    weak: set[str] = set()
    for r in results:
        sc, wk = _score_quality(r.get("quality_dims", {}))
        total += sc
        weak.update(wk)
    return round(total / len(results), 3), list(weak)


def _build_indicator_prompt(task: dict) -> tuple[str, bool]:
    """回 (prompt, is_per_output)。catalog/iCAP 參考段落留空（檢索已外包/移除）。"""
    common = dict(
        task_name=task["task_name"], situation=task.get("situation", ""),
        purpose=task.get("purpose", ""),
        collaborators=", ".join(task.get("collaborators") or []),
        stakeholders=", ".join(task.get("stakeholders") or []),
        tools=", ".join(task.get("tools") or []),
        workflow_steps="\n".join(task.get("workflow_steps") or []),
        quality_standards=", ".join(task.get("quality_standards") or []),
        time_standards=", ".join(task.get("time_standards") or []),
        star_case=json.dumps(task.get("star_case", {}), ensure_ascii=False),
        icap_ref_section="",
    )
    outputs = task.get("outputs") or []
    if outputs:
        prompt = ind_prompts.PER_OUTPUT.format(
            outputs_numbered="\n".join(f"{i}. {o}" for i, o in enumerate(outputs, 1)),
            icap_ref_rule="", **common)
        return prompt, True
    return ind_prompts.SINGLE.format(**common), False


@traced_node("indicator")
async def indicator_node(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    idx, task, task_id = _current_task(state)
    task_name = task["task_name"]
    deep = dict(state["deep"])
    retry = dict(deep.get("retry") or {})

    # Guardrail：必填欄缺 → 退回 five_w2h
    missing = [f for f in INDICATOR_REQUIRED_FIELDS if not task.get(f)]
    if missing:
        deep["missing_fields"] = missing
        logger.warning("indicator_node: guardrail missing=%s -> five_w2h", missing)
        return {"deep": deep}

    if deps.llm is None:
        results = []
    else:
        prompt, per_output = _build_indicator_prompt(task)
        raw = await deps.llm.complete_json(prompt, role="indicator", default=[] if per_output else {})
        results = raw if per_output and isinstance(raw, list) else ([raw] if raw else [])
    score, weak = _avg_quality(results)

    if score < _QUALITY_THRESHOLD and retry.get(task_id, 0) < _MAX_QUALITY_RETRIES and deps.llm is not None:
        retry[task_id] = retry.get(task_id, 0) + 1
        for f in weak:
            task.pop(f, None)
        tasks = list(state["tasks"]); tasks[idx] = task
        deep["retry"] = retry
        deep["missing_fields"] = weak
        logger.warning("indicator_node: task=%s score=%.2f weak=%s retry#%d -> five_w2h",
                       task_name, score, weak, retry[task_id])
        return {"tasks": tasks, "deep": deep}

    status = "ok" if score >= _QUALITY_THRESHOLD else "force_accepted"
    indicators = [{
        "task_id": task_id, "task_name": task_name,
        "output_name": r.get("output_name", ""),
        "indicator_5w2h": r.get("indicator_5w2h", ""),
        "indicator_abcd": r.get("indicator_abcd", ""),
        "quality_score": score, "quality_status": status,
    } for r in results] or [{
        "task_id": task_id, "task_name": task_name, "output_name": "",
        "indicator_5w2h": "", "indicator_abcd": "",
        "quality_score": 0.0, "quality_status": "force_accepted",
    }]
    task["behavior_indicators"] = indicators
    tasks = list(state["tasks"]); tasks[idx] = task
    deep["retry"] = retry
    deep["missing_fields"] = []
    logger.info("indicator_node: task=%s accepted score=%.2f", task_name, score)
    return {"tasks": tasks, "deep": deep}


def route_after_indicator(state: InterviewState) -> str:
    """indicator 後分流：有未填弱欄 → 回 five_w2h 重補；否則 → advance（推進下一任務）。"""
    return "five_w2h" if state["deep"].get("missing_fields") else "advance"
