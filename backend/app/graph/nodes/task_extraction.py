"""任務萃取節點：從訪談對話中萃取結構化任務列表，並用 iCAP task chunks 注入 icap_task_ref。"""
import asyncio
import logging

from langchain_core.messages import HumanMessage

from app.graph.llm import get_chat_llm
from app.graph.state import InterviewState
from app.services.icap_ksa_rag import search_tasks
from app.utils import safe_parse_json

logger = logging.getLogger("jobintel")

_PURE_CONFIRM_KEYWORDS = frozenset({"確認", "好", "對", "沒問題", "ok", "OK", "可以", "繼續", "正確", "yes", "Yes"})


def _is_pure_confirmation(text: str) -> bool:
    """訊息是否為純確認語，不含新資訊（用於跳過 LLM 重新萃取）。"""
    cleaned = text.strip().rstrip("！!。，, ")
    return cleaned in _PURE_CONFIRM_KEYWORDS or cleaned.lower() in {"ok", "yes"}


_EXTRACTION_PROMPT = """根據以下工作者的訪談內容，萃取出結構化的工作任務列表。

規則：
1. 每個任務必須有原始回答作為證據（evidence_from_user）
2. 合併相同任務，避免重複
3. 明確區分：核心職責 / 例行工作 / 協作任務 / 待確認
4. 若頻率或責任類型不明確，標記為「待確認」
5. 不得加入工作者未提到的任務
6. 對話中已識別到的工具、協作對象、產出請對應填入相關任務的欄位，不要遺漏

{signals_context}
輸出 JSON 格式（只輸出 JSON，不要其他文字）：
[
  {{
    "task_name": "任務名稱",
    "description": "簡短描述",
    "category": "核心職責|例行工作|協作任務|待確認",
    "frequency": "每日|每週|每月|專案性|臨時性|待確認",
    "responsibility_type": "主責|協作|支援|待確認",
    "evidence_from_user": "工作者原話摘錄"
  }}
]

訪談內容：
{conversation}
"""


def _build_signals_context(readiness_detail: dict) -> str:
    """從 readiness_detail 的 detected_signals 建立提示 context。"""
    detected = readiness_detail.get("detected_signals", [])
    lines = [
        f"- {s['label']}：{', '.join(s['examples'])}"
        for s in detected
        if s.get("examples")
    ]
    if not lines:
        return ""
    return "已從對話中識別到的工作資訊（請確保萃取任務時納入這些細節）：\n" + "\n".join(lines) + "\n\n"


async def _enrich_tasks_with_icap(
    tasks: list[dict],
    icap_mode: str,
    top_ocs_code: str | None,
) -> list[dict]:
    """並行查詢 iCAP task chunks，為每個任務注入 icap_task_ref。
    僅在 reference / hybrid mode 下執行。
    """
    if icap_mode == "company_defined" or not tasks:
        return tasks

    async def _search_one(task: dict) -> dict:
        task = dict(task)
        query = f"{task['task_name']} {task.get('description', '')}"
        hits = await search_tasks(query, top_k=1, ocs_code_filter=top_ocs_code)
        if hits:
            best = hits[0]
            task["icap_task_ref"] = {
                "code":      best["code"],
                "name":      best["name"],
                "ocs_code":  best["ocs_code"],
                "similarity": best["similarity"],
            }
            logger.debug(
                "task_extraction: '%s' → iCAP task %s (%.3f)",
                task["task_name"], best["code"], best["similarity"],
            )
        return task

    enriched = await asyncio.gather(*[_search_one(t) for t in tasks])
    return list(enriched)


async def task_extraction_node(state: InterviewState) -> dict:
    llm = get_chat_llm(0.0)
    prev_round = state.get("task_extraction_round", 0)
    existing_tasks = state.get("extracted_tasks", [])

    # 用戶按確認按鈕（純確認語），跳過 LLM 重新萃取直接推進
    if prev_round >= 1 and existing_tasks:
        user_msgs = [m for m in state.get("messages", []) if m.get("role") == "user"]
        if user_msgs and _is_pure_confirmation(user_msgs[-1]["content"]):
            logger.info("task_extraction_node: pure confirmation detected, skipping re-extraction")
            return {
                "extracted_tasks": existing_tasks,
                "current_stage": "task_extraction",
                "ai_response": "",
                "task_extraction_round": prev_round + 1,
            }

    conversation = "\n".join(
        f"{'工作者' if m['role'] == 'user' else 'AI'}：{m['content']}"
        for m in state["messages"]
    )

    signals_context = _build_signals_context(state.get("interview_readiness_detail", {}))
    logger.info("task_extraction_node: extracting from %d messages", len(state["messages"]))
    response = await llm.ainvoke([HumanMessage(content=_EXTRACTION_PROMPT.format(
        signals_context=signals_context,
        conversation=conversation,
    ))])

    tasks = safe_parse_json(response.content, default=[])
    logger.info("task_extraction_node: extracted %d tasks (round %d)", len(tasks), prev_round + 1)

    # 補上穩定的 task_id（後續流程以 task_id 為 key，task_name 僅供顯示）
    for i, task in enumerate(tasks, 1):
        task.setdefault("task_id", f"task_{i:03d}")

    # 多粒度 RAG：注入 iCAP task chunk 對應
    icap_mode = state.get("icap_mode", "company_defined")
    top_ocs_code = (state.get("icap_candidates") or [{}])[0].get("ocs_code")
    tasks = await _enrich_tasks_with_icap(tasks, icap_mode, top_ocs_code)

    return {
        "extracted_tasks": tasks,
        "current_stage": "task_extraction",
        "ai_response": _build_task_summary(tasks, is_revision=prev_round >= 1),
        "current_task_index": 0,
        "task_extraction_round": prev_round + 1,
    }


def _build_task_summary(tasks: list[dict], is_revision: bool = False) -> str:
    if not tasks:
        return "我還沒有足夠的資訊來整理任務，能再多描述一下你的工作嗎？"

    header = "根據你的補充，我更新了任務列表：\n" if is_revision else f"我整理出 **{len(tasks)} 項任務**，請確認是否正確：\n"
    lines = [header]
    for i, t in enumerate(tasks, 1):
        ref = t.get("icap_task_ref")
        ref_badge = f" `iCAP {ref['code']}`" if ref else ""
        lines.append(
            f"{i}. **{t['task_name']}**{ref_badge}｜{t.get('frequency', '?')}｜"
            f"{t.get('responsibility_type', '?')}｜{t.get('category', '?')}"
        )
    if is_revision:
        lines.append("\n如果這樣正確，請說「確認」，我們繼續深入訪談。如還需修改，請繼續告訴我。")
    else:
        lines.append("\n如有遺漏或分類不正確，請直接告訴我（例如：「還有一個任務是…」或「把第2項改成…」）。\n確認後請說「確認」或「好」，我們將針對每個任務深入訪談。")
    return "\n".join(lines)
