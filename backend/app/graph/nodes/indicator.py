"""行為指標生成節點（含 Guardrail 與品質評分回退）。

逐任務、逐產出處理：每個 output 生成一個專屬指標，提升 OCS 可追溯性。
若任務無 outputs，fallback 為整任務單一指標（舊版行為）。
"""
import json
import logging

from app.graph.constants import INDICATOR_REQUIRED_FIELDS
from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState
from app.graph.task_loop import TaskLoopManager
from app.services.icap_ksa_rag import search_indicators
import app.graph.prompts.indicator as prompts

logger = logging.getLogger("jobintel")

_QUALITY_THRESHOLD = 0.60
_MAX_QUALITY_RETRIES = 1

_DIM_TO_FIELDS: dict[str, list[str]] = {
    "has_situation":     ["situation"],
    "has_purpose":       ["purpose"],
    "has_collaborators": ["collaborators"],
    "has_tools":         ["tools"],
    "has_action":        ["workflow_steps"],
    "has_output":        ["outputs"],
    "has_standard":      ["quality_standards", "time_standards"],
}


def _score_quality(quality_dims: dict) -> tuple[float, list[str]]:
    weak_fields: list[str] = []
    hits = 0
    for dim, fields in _DIM_TO_FIELDS.items():
        if quality_dims.get(dim):
            hits += 1
        else:
            weak_fields.extend(fields)
    score = hits / len(_DIM_TO_FIELDS) if _DIM_TO_FIELDS else 0.0
    return round(score, 3), weak_fields


def _avg_quality(results: list[dict]) -> tuple[float, list[str]]:
    if not results:
        return 0.0, list(_DIM_TO_FIELDS.keys())
    total = 0.0
    all_weak: set[str] = set()
    for r in results:
        score, weak = _score_quality(r.get("quality_dims", {}))
        total += score
        all_weak.update(weak)
    return round(total / len(results), 3), list(all_weak)


async def _get_icap_ref(task_name: str, purpose: str, icap_mode: str, top_ocs_code: str | None) -> str:
    if icap_mode == "company_defined":
        return ""
    query = f"{task_name} {purpose} 行為指標"
    hits = await search_indicators(query, top_k=2, ocs_code_filter=top_ocs_code)
    if not hits:
        return ""
    examples = "\n".join(f"  - {h['name']}" for h in hits)
    return f"iCAP 參考指標範例（措辭參考，勿直接複製）：\n{examples}\n"


async def indicator_generation_node(state: InterviewState) -> dict:
    tasks = state.get("extracted_tasks", [])
    indicators = list(state.get("behavior_indicators", []))
    retry_counts = dict(state.get("indicator_retry_counts", {}))

    loop = TaskLoopManager(tasks, state.get("current_task_index", 0))
    processed_task_ids = {ind.get("task_id", ind["task_name"]) for ind in indicators}

    if loop.is_done:
        return {
            "current_stage":       "ksa",
            "ai_response":         "所有任務的行為指標已生成完畢，接下來整理知識、技能與態度（K/S/A）。",
            "behavior_indicators": indicators,
        }

    idx = loop.index
    task = tasks[idx]
    task_name = task["task_name"]
    task_id   = loop.current_task_id()

    # Resume 重入防呆：此任務已有指標，直接推進
    if task_id in processed_task_ids:
        next_loop = loop.advance()
        if not next_loop.is_done:
            next_task_name = tasks[next_loop.index]["task_name"]
            logger.info("indicator_node: task '%s' already done → star idx=%d", task_name, next_loop.index)
            return {
                "current_stage":       "star",
                "current_task_index":  next_loop.index,
                "ai_response":         "",
                "behavior_indicators": indicators,
            }
        return {
            "current_stage":       "ksa",
            "current_task_index":  next_loop.index,
            "ai_response":         "所有任務的行為指標已生成完畢，接下來整理 K/S/A。",
            "behavior_indicators": indicators,
        }

    gw = LLMGateway(temperature=0.2)
    icap_mode    = state.get("icap_mode", "company_defined")
    top_ocs_code = (state.get("icap_candidates") or [{}])[0].get("ocs_code")

    # Guardrail：必填欄位檢查
    missing = [f for f in INDICATOR_REQUIRED_FIELDS if not task.get(f)]
    if missing:
        logger.warning("indicator guardrail: task=%s missing=%s", task_name, missing)
        return {
            "current_stage":       "five_w2h",
            "current_task_index":  idx,
            "ai_response":         (
                f"「{task_name}」還缺少 {', '.join(missing)} 的資訊，"
                "必須補齊後才能生成行為指標。"
            ),
            "missing_fields":      missing,
            "behavior_indicators": indicators,
        }

    icap_ref_section = await _get_icap_ref(task_name, task.get("purpose", ""), icap_mode, top_ocs_code)
    retry_counts.setdefault(task_id, retry_counts.pop(task_name, 0))
    icap_ref_rule = (
        "- 若有 iCAP 參考指標，可參考其措辭風格，但內容必須以工作者的真實描述為主\n"
        if icap_ref_section else ""
    )

    outputs: list[str] = task.get("outputs") or []

    if outputs:
        outputs_numbered = "\n".join(f"{i}. {o}" for i, o in enumerate(outputs, 1))
        prompt = prompts.PER_OUTPUT.format(
            task_name=task_name,
            situation=task.get("situation", ""),
            purpose=task.get("purpose", ""),
            collaborators=", ".join(task.get("collaborators") or []),
            stakeholders=", ".join(task.get("stakeholders") or []),
            tools=", ".join(task.get("tools") or []),
            workflow_steps="\n".join(task.get("workflow_steps") or []),
            quality_standards=", ".join(task.get("quality_standards") or []),
            time_standards=", ".join(task.get("time_standards") or []),
            star_case=json.dumps(task.get("star_case", {}), ensure_ascii=False),
            outputs_numbered=outputs_numbered,
            icap_ref_section=icap_ref_section,
            icap_ref_rule=icap_ref_rule,
        )
        logger.info("indicator_node: per-output generation for task=%s (%d outputs)", task_name, len(outputs))
        results: list[dict] = await gw.invoke_json(prompt, default=[])
        if not isinstance(results, list):
            results = []

        quality_score, weak_fields = _avg_quality(results)
        task_retry = retry_counts.get(task_id, 0)

        if quality_score < _QUALITY_THRESHOLD and task_retry < _MAX_QUALITY_RETRIES:
            improved_tasks = list(tasks)
            task_copy = dict(improved_tasks[idx])
            for field in weak_fields:
                task_copy.pop(field, None)
            improved_tasks[idx] = task_copy
            retry_counts[task_id] = task_retry + 1
            logger.warning(
                "indicator quality: task=%s avg_score=%.2f weak=%s retry#%d → five_w2h",
                task_name, quality_score, weak_fields, task_retry + 1,
            )
            return {
                "extracted_tasks":        improved_tasks,
                "behavior_indicators":    indicators,
                "indicator_retry_counts": retry_counts,
                "current_stage":          "five_w2h",
                "current_task_index":     idx,
                "missing_fields":         weak_fields,
                "ai_response":            (
                    f"「{task_name}」的行為指標還不夠具體（品質評分 {quality_score:.0%}），"
                    f"我需要再了解幾個細節：{', '.join(weak_fields)}。"
                ),
            }

        if quality_score < _QUALITY_THRESHOLD:
            logger.warning("indicator quality: task=%s avg_score=%.2f — force accepted", task_name, quality_score)

        quality_status = "ok" if quality_score >= _QUALITY_THRESHOLD else "force_accepted"
        for r in results:
            indicators.append({
                "task_id":        task_id,
                "task_name":      task_name,
                "output_name":    r.get("output_name", ""),
                "indicator_5w2h": r.get("indicator_5w2h", ""),
                "indicator_abcd": r.get("indicator_abcd", ""),
                "quality_score":  quality_score,
                "quality_status": quality_status,
            })

        if not results:
            indicators.append({
                "task_id":        task_id,
                "task_name":      task_name,
                "output_name":    "",
                "indicator_5w2h": "",
                "indicator_abcd": "",
                "quality_score":  0.0,
                "quality_status": "force_accepted",
            })

        ai_lines = [f"**「{task_name}」行為指標已生成**（{len(results)} 個產出，品質評分 {quality_score:.0%}）\n"]
        for r in results[:3]:
            ai_lines.append(f"**產出：{r.get('output_name', '')}**")
            ai_lines.append(r.get("indicator_5w2h", ""))
        if len(results) > 3:
            ai_lines.append(f"…（共 {len(results)} 個指標）")
        ai_response = "\n".join(ai_lines)

    else:
        # Fallback：無 outputs，整任務單一指標
        prompt = prompts.SINGLE.format(
            task_name=task_name,
            situation=task.get("situation", ""),
            purpose=task.get("purpose", ""),
            collaborators=", ".join(task.get("collaborators") or []),
            stakeholders=", ".join(task.get("stakeholders") or []),
            tools=", ".join(task.get("tools") or []),
            workflow_steps="\n".join(task.get("workflow_steps") or []),
            quality_standards=", ".join(task.get("quality_standards") or []),
            time_standards=", ".join(task.get("time_standards") or []),
            star_case=json.dumps(task.get("star_case", {}), ensure_ascii=False),
            icap_ref_section=icap_ref_section,
        )
        logger.info("indicator_node: single fallback for task=%s (no outputs)", task_name)
        result = await gw.invoke_json(prompt, default={})

        quality_score, weak_fields = _score_quality(result.get("quality_dims", {}))
        task_retry = retry_counts.get(task_id, 0)

        if quality_score < _QUALITY_THRESHOLD and task_retry < _MAX_QUALITY_RETRIES:
            improved_tasks = list(tasks)
            task_copy = dict(improved_tasks[idx])
            for field in weak_fields:
                task_copy.pop(field, None)
            improved_tasks[idx] = task_copy
            retry_counts[task_id] = task_retry + 1
            logger.warning(
                "indicator quality (single): task=%s score=%.2f weak=%s retry#%d → five_w2h",
                task_name, quality_score, weak_fields, task_retry + 1,
            )
            return {
                "extracted_tasks":        improved_tasks,
                "behavior_indicators":    indicators,
                "indicator_retry_counts": retry_counts,
                "current_stage":          "five_w2h",
                "current_task_index":     idx,
                "missing_fields":         weak_fields,
                "ai_response":            (
                    f"「{task_name}」的行為指標還不夠具體（品質評分 {quality_score:.0%}），"
                    f"我需要再了解幾個細節：{', '.join(weak_fields)}。"
                ),
            }

        quality_status = "ok" if quality_score >= _QUALITY_THRESHOLD else "force_accepted"
        indicators.append({
            "task_id":        task_id,
            "task_name":      task_name,
            "output_name":    "",
            "indicator_5w2h": result.get("indicator_5w2h", ""),
            "indicator_abcd": result.get("indicator_abcd", ""),
            "quality_score":  quality_score,
            "quality_status": quality_status,
        })

        ai_response = (
            f"**「{task_name}」行為指標已生成**（品質評分 {quality_score:.0%}）\n\n"
            f"**5W2H 版**：\n{result.get('indicator_5w2h', '')}\n\n"
            f"**ABCD 版**：\n{result.get('indicator_abcd', '')}"
        )

    next_loop = loop.advance()
    retry_counts.setdefault(task_id, 0)

    if not next_loop.is_done:
        next_task_name = tasks[next_loop.index]["task_name"]
        logger.info("indicator_node: task '%s' done → star for next='%s'", task_name, next_task_name)
        return {
            "behavior_indicators":    indicators,
            "indicator_retry_counts": retry_counts,
            "current_stage":          "star",
            "current_task_index":     next_loop.index,
            "missing_fields":         [],
            "ai_response":            ai_response,
        }

    logger.info("indicator_node: all tasks done → ksa")
    return {
        "behavior_indicators":    indicators,
        "indicator_retry_counts": retry_counts,
        "current_stage":          "ksa",
        "current_task_index":     next_loop.index,
        "missing_fields":         [],
        "ai_response":            ai_response + "\n\n所有任務的行為指標已生成完畢，接下來整理 K/S/A。",
    }
