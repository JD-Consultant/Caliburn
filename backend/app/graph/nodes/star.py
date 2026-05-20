"""STAR 深度訪談節點：LLM slot filling，允許一次填多槽，四槽完成後寫回 extracted_tasks。"""
import logging

from langchain_core.messages import HumanMessage

from app.graph.llm_gateway import LLMGateway
from app.graph.phase import Phase
from app.graph.state import InterviewState
from app.graph.task_loop import TaskLoopManager
import app.graph.prompts.star as prompts

logger = logging.getLogger("jobintel")

_SLOT_ORDER = ["S", "T", "A", "R"]

_SLOT_LABELS = {
    "S": "情境（Situation）",
    "T": "任務目標（Task）",
    "A": "行動步驟（Action）",
    "R": "結果產出（Result）",
}

_SLOT_QUESTIONS = {
    "S": "針對「{task_name}」，最近一次遇到比較典型或複雜的情況，當時的背景是什麼？",
    "T": "在那件事中，你的目標是什麼？哪些具體事項是你負責的，哪些不是？",
    "A": "你實際怎麼一步一步處理的？用了哪些工具或系統？遇到困難怎麼解決的？",
    "R": "最後產出了什麼？有沒有達到預期目標，或避免了問題、縮短時間、改善了什麼？",
}

_SLOT_REPROMPTS = {
    "S": "能多說一點當時的情境嗎？比如時間點、觸發條件、相關人員？",
    "T": "你在那件事中的具體責任是什麼？有明確的目標或限制嗎？",
    "A": "請多描述幾個步驟，先做了什麼、再做什麼，遇到阻礙怎麼應對？",
    "R": "最終的具體產出是什麼？對方（客戶、主管）的反應或後續影響如何？",
}

_MIN_SLOT_LEN = 4


def _init_slots() -> dict:
    return {s: None for s in _SLOT_ORDER}


def _filled_count(slots: dict) -> int:
    return sum(1 for s in _SLOT_ORDER if slots.get(s))


def _next_empty_slot(slots: dict) -> str | None:
    return next((s for s in _SLOT_ORDER if not slots.get(s)), None)


def _build_completion_return(
    task_name: str,
    task_id: str,
    task_slots: dict,
    tasks: list,
    idx: int,
    all_slots: dict,
    completed_ids: list,
    phase_key: str,
) -> dict:
    slot_summary = "\n".join(
        f"- **{_SLOT_LABELS[s]}**：{(task_slots[s] or '')[:60]}"
        f"{'…' if len(task_slots[s] or '') > 60 else ''}"
        for s in _SLOT_ORDER
    )
    updated_task = dict(tasks[idx])
    updated_task["star_case"] = {
        "situation": task_slots["S"],
        "task":      task_slots["T"],
        "action":    task_slots["A"],
        "result":    task_slots["R"],
    }
    updated_tasks = list(tasks)
    updated_tasks[idx] = updated_task
    updated_completed = list(completed_ids)
    if task_id not in updated_completed:
        updated_completed.append(task_id)
    return {
        "ai_response": (
            f"「{task_name}」的 STAR 案例整理如下：\n{slot_summary}"
            "\n\n很好！接下來補充這個任務的工作細節。"
        ),
        "current_stage":          "five_w2h",
        "phase":                  phase_key,
        "extracted_tasks":        updated_tasks,
        "star_slots_by_task":     all_slots,
        "star_completed_task_ids": updated_completed,
        "current_task_index":     idx,
    }


async def _synthesize_slot(
    task_name: str,
    slot: str,
    task_slots: dict,
    user_input: str,
) -> str:
    gw = LLMGateway(temperature=0.1)
    prompt = prompts.SLOT_SYNTHESIZE.format(
        slot_label=_SLOT_LABELS[slot],
        task_name=task_name,
        user_input=user_input.strip() or "（未提供）",
        situation=task_slots.get("S") or "（未知）",
        action=task_slots.get("A") or "（未知）",
        result=task_slots.get("R") or "（未知）",
    )
    text = await gw.invoke_text([HumanMessage(content=prompt)])
    synthesized = text.strip()
    logger.info("star_node: synthesized slot %s for task=%s: '%s...'", slot, task_name, synthesized[:40])
    return synthesized


async def _extract_slots_from_input(task_name: str, user_input: str, current_slots: dict) -> dict:
    if not user_input or not user_input.strip():
        return {}

    gw = LLMGateway(temperature=0.0)
    prompt = prompts.SLOT_EXTRACT.format(task_name=task_name, user_input=user_input.strip())
    extracted: dict = await gw.invoke_json(prompt, default={})

    result = {}
    for slot in _SLOT_ORDER:
        if current_slots.get(slot):
            continue
        val = extracted.get(slot)
        if val and isinstance(val, str) and len(val.strip()) >= _MIN_SLOT_LEN:
            result[slot] = val.strip()
    return result


async def star_node(state: InterviewState) -> dict:
    tasks = list(state.get("extracted_tasks") or [])
    completed_ids: list[str] = list(state.get("star_completed_task_ids") or [])

    loop = TaskLoopManager(tasks, state.get("current_task_index", 0)).skip_completed(completed_ids)

    if loop.is_done:
        logger.warning("star_node: all tasks done (idx=%d) — fallback to ksa", loop.index)
        return {
            "ai_response":        "所有任務的 STAR 案例已收集完畢，正在生成職能文件…",
            "current_stage":      "ksa",
            "current_task_index": loop.index,
        }

    idx = loop.index
    current_task = dict(loop.current_task)
    task_name = current_task["task_name"]
    task_id = loop.current_task_id()
    phase_key = Phase.star(task_id).to_str()

    all_slots: dict = dict(state.get("star_slots_by_task") or {})
    task_slots: dict = dict(all_slots.get(task_id) or _init_slots())

    # 只在此 phase 已有 AI 回覆時才嘗試從 user_input 填槽
    user_input: str = state.get("user_input", "")
    star_phase_ai_msgs = [
        m for m in state.get("messages", [])
        if isinstance(m, dict) and m.get("phase") == phase_key and m.get("role") == "ai"
    ]
    if not star_phase_ai_msgs:
        user_input = ""

    new_slots = await _extract_slots_from_input(task_name, user_input, task_slots)
    if new_slots:
        task_slots.update(new_slots)
        logger.debug("star_node: task=%s new_slots=%s", task_name, list(new_slots.keys()))

    all_slots[task_id] = task_slots
    next_slot = _next_empty_slot(task_slots)
    filled = _filled_count(task_slots)

    if next_slot is None:
        logger.info("star_node: task '%s' STAR complete → five_w2h", task_name)
        return _build_completion_return(
            task_name, task_id, task_slots, tasks, idx, all_slots, completed_ids, phase_key
        )

    # 重問後仍無法填槽 → synthesize
    if user_input.strip() and not new_slots.get(next_slot):
        reprompt_text = _SLOT_REPROMPTS.get(next_slot, "")
        prior_reprompts = [
            m for m in state.get("messages", [])
            if isinstance(m, dict)
            and m.get("phase") == phase_key
            and m.get("role") == "ai"
            and reprompt_text in m.get("content", "")
        ]
        if prior_reprompts:
            synthesized = await _synthesize_slot(task_name, next_slot, task_slots, user_input)
            task_slots[next_slot] = synthesized
            all_slots[task_id] = task_slots
            next_slot = _next_empty_slot(task_slots)
            filled = _filled_count(task_slots)

            if next_slot is None:
                return _build_completion_return(
                    task_name, task_id, task_slots, tasks, idx, all_slots, completed_ids, phase_key
                )

    tried_but_failed = bool(user_input.strip()) and next_slot is not None and not new_slots.get(next_slot)
    question = (
        _SLOT_REPROMPTS[next_slot]
        if tried_but_failed
        else _SLOT_QUESTIONS[next_slot].format(task_name=task_name)
    )

    progress = f"{filled}/4 已收集"
    if filled == 0 and not user_input.strip():
        intro = f"接下來針對「**{task_name}**」，我會用 STAR 框架請你分享一個真實案例（{progress}）。\n\n"
    else:
        intro = f"**{_SLOT_LABELS[next_slot]}**（{progress}）\n\n"

    logger.debug("star_node: task=%s asking=%s filled=%d/4", task_name, next_slot, filled)
    return {
        "ai_response":            intro + question,
        "current_stage":          "star",
        "phase":                  phase_key,
        "star_slots_by_task":     all_slots,
        "star_completed_task_ids": completed_ids,
    }
