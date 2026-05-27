"""任務萃取節點：從訪談對話中萃取結構化任務列表，並用 iCAP task chunks 注入 icap_task_ref。"""
import asyncio
import logging

from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState
from app.services.icap_matcher import match_icap_candidates
from app.services.icap_retriever import search_tasks

logger = logging.getLogger("jobintel")

_PURE_CONFIRM_KEYWORDS = frozenset({"確認", "好", "對", "沒問題", "ok", "OK", "可以", "繼續", "正確", "yes", "Yes"})

_TASK_LIST_FIELDS = frozenset({
    "collaborators",
    "stakeholders",
    "tools",
    "outputs",
    "workflow_steps",
    "uncertainty_fields",
})

_FIELD_LABELS = {
    "task_name": "任務名稱",
    "description": "任務描述",
    "category": "任務類型",
    "frequency": "頻率",
    "responsibility_type": "責任類型",
    "evidence_from_user": "原話證據",
    "collaborators": "協作對象",
    "stakeholders": "服務對象",
    "tools": "工具",
    "outputs": "產出",
    "workflow_steps": "流程步驟",
}


def _is_pure_confirmation(text: str) -> bool:
    """訊息是否為純確認語，不含新資訊（用於跳過 LLM 重新萃取）。"""
    cleaned = text.strip().rstrip("！!。，, ")
    return cleaned in _PURE_CONFIRM_KEYWORDS or cleaned.lower() in {"ok", "yes"}


_EXTRACTION_PROMPT = """你是任務萃取 Agent。你的工作是把訪談中的口語描述整理成「待使用者確認的工作任務清單」。
這一階段只做整理與確認，不做 STAR 深問，不生成正式職能文件。

規則：
1. 每個任務必須有工作者原始回答作為證據（evidence_from_user）
2. 合併相同任務，避免重複
3. 明確區分：核心職責 / 例行工作 / 協作任務 / 待確認
4. 若頻率或責任類型不明確，標記為「待確認」
5. 不得加入工作者未提到的任務
6. 對話中已識別到的工具、協作對象、產出請對應填入相關任務的欄位，不要遺漏
7. AI 提示與先前整理只能當作脈絡，不能當作事實來源；事實必須來自工作者回答
8. 如果使用者正在修正上一版任務清單，請依照最新修正更新清單，而不是直接進入下一階段
9. 不確定的欄位放進 uncertainty_fields，不要硬猜

{previous_tasks_context}

{signals_context}
輸出 JSON 格式（只輸出 JSON，不要其他文字）：
[
  {{
    "task_name": "任務名稱",
    "description": "簡短描述",
    "category": "核心職責|例行工作|協作任務|待確認",
    "frequency": "每日|每週|每月|專案性|臨時性|待確認",
    "responsibility_type": "主責|協作|支援|待確認",
    "evidence_from_user": "工作者原話摘錄",
    "collaborators": ["協作對象或部門，沒有就空陣列"],
    "stakeholders": ["服務或影響對象，沒有就空陣列"],
    "tools": ["系統、工具、表單或平台，沒有就空陣列"],
    "outputs": ["文件、報表、資料、通知等產出，沒有就空陣列"],
    "workflow_steps": ["已知流程步驟，沒有就空陣列"],
    "uncertainty_fields": ["需要使用者確認的欄位，例如 frequency、responsibility_type、outputs"]
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


def _build_previous_tasks_context(existing_tasks: list[dict]) -> str:
    if not existing_tasks:
        return ""
    lines = ["上一版任務清單（若使用者提出修正，請在此基礎上更新）："]
    for i, task in enumerate(existing_tasks, 1):
        lines.append(
            f"{i}. {task.get('task_name', '')}｜"
            f"{task.get('frequency', '待確認')}｜"
            f"{task.get('responsibility_type', '待確認')}｜"
            f"{task.get('category', '待確認')}"
        )
    return "\n".join(lines) + "\n\n"


def _as_list(value) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        normalized = value.replace("、", ",").replace("，", ",")
        return [v.strip() for v in normalized.split(",") if v.strip()]
    return [str(value).strip()]


def _normalize_tasks(tasks: list, existing_tasks: list[dict]) -> list[dict]:
    if not isinstance(tasks, list):
        return []

    existing_task_ids = {
        task.get("task_name"): task.get("task_id")
        for task in existing_tasks
        if task.get("task_name") and task.get("task_id")
    }
    normalized = []
    seen_names: set[str] = set()

    for raw in tasks:
        if not isinstance(raw, dict):
            continue
        task_name = str(raw.get("task_name", "")).strip()
        if not task_name or task_name in seen_names:
            continue
        seen_names.add(task_name)

        task = dict(raw)
        task["task_name"] = task_name
        task["description"] = str(task.get("description", "")).strip()
        task["category"] = task.get("category") or "待確認"
        task["frequency"] = task.get("frequency") or "待確認"
        task["responsibility_type"] = task.get("responsibility_type") or "待確認"
        task["evidence_from_user"] = str(task.get("evidence_from_user", "")).strip()

        uncertainty_fields = set(_as_list(task.get("uncertainty_fields")))
        for field in ("category", "frequency", "responsibility_type"):
            if task.get(field) == "待確認":
                uncertainty_fields.add(field)
        if not task["evidence_from_user"]:
            uncertainty_fields.add("evidence_from_user")

        for field in _TASK_LIST_FIELDS:
            task[field] = _as_list(task.get(field))
        task["uncertainty_fields"] = sorted(uncertainty_fields)
        task["task_id"] = existing_task_ids.get(task_name) or f"task_{len(normalized) + 1:03d}"
        normalized.append(task)

    return normalized


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
    prompt = _EXTRACTION_PROMPT.format(
        previous_tasks_context=_build_previous_tasks_context(existing_tasks),
        signals_context=signals_context,
        conversation=conversation,
    )
    raw_tasks = await LLMGateway(temperature=0.0).invoke_json(prompt, default=[])
    tasks = _normalize_tasks(raw_tasks, existing_tasks)
    logger.info("task_extraction_node: extracted %d tasks (round %d)", len(tasks), prev_round + 1)

    # 任務萃取後重新比對 iCAP，讓任務、產出、工具等細節也參與候選排序。
    icap_match = await match_icap_candidates(
        job_title=state["job_title"],
        department=state.get("department", ""),
        job_summary=state.get("job_summary", ""),
        readiness_detail=state.get("interview_readiness_detail", {}),
        tasks=tasks,
    )
    icap_mode = icap_match["icap_mode"]
    top_ocs_code = (icap_match["candidates"] or [{}])[0].get("ocs_code")
    tasks = await _enrich_tasks_with_icap(tasks, icap_mode, top_ocs_code)

    return {
        "extracted_tasks": tasks,
        "icap_candidates": icap_match["candidates"],
        "icap_hit": icap_match["icap_hit"],
        "icap_mode": icap_mode,
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
        uncertainty = t.get("uncertainty_fields") or []
        uncertainty_text = (
            f"\n   待確認：{'、'.join(_FIELD_LABELS.get(f, f) for f in uncertainty)}"
            if uncertainty
            else ""
        )
        evidence = t.get("evidence_from_user", "")
        evidence_text = f"\n   依據：「{evidence[:45]}{'…' if len(evidence) > 45 else ''}」" if evidence else ""
        lines.append(
            f"{i}. **{t['task_name']}**{ref_badge}｜{t.get('frequency', '?')}｜"
            f"{t.get('responsibility_type', '?')}｜{t.get('category', '?')}"
            f"{evidence_text}{uncertainty_text}"
        )
    if is_revision:
        lines.append("\n如果這樣正確，請說「確認」，接著我會整理主要職責分組。如還需修改，請繼續告訴我。")
    else:
        lines.append("\n如有遺漏或分類不正確，請直接告訴我（例如：「還有一個任務是…」或「把第2項改成…」）。\n確認後請說「確認」或「好」，我會先整理主要職責分組。")
    return "\n".join(lines)
