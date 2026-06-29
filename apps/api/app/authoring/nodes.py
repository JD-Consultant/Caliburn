from langgraph.types import interrupt

from app.authoring.state import InterviewState
from app.authoring.tracing import traced_node


@traced_node("pick_profile")
async def pick_profile(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    query = state.get("job_summary") or state["job_title"]
    res = await deps.knowledge.search_occupations(query, top_k=8)
    candidates = [h.model_dump() for h in res.hits]

    selected = interrupt({"kind": "select_profile", "candidates": candidates})
    codes = _resume_to_codes(selected)          # 有序清單，順序=優先度
    primary = codes[0] if codes else None

    await deps.persist.set_selected_ocs(state["job_profile_id"], codes)
    return {
        "profile": {
            "candidates": candidates,
            "selected_ocs_codes": codes,
            "selected_ocs_code": primary,
        },
        "current_step": "task_pool",
    }


def _resume_to_codes(selected) -> list[str]:
    """容錯解析 select_profile 的 resume：
    {"ocs_codes":[...]}（複選，有序）｜{"ocs_code":"x"}（舊單選）｜純字串。"""
    if isinstance(selected, dict):
        if isinstance(selected.get("ocs_codes"), list):
            return [str(c) for c in selected["ocs_codes"] if c]
        if selected.get("ocs_code"):
            return [str(selected["ocs_code"])]
        return []
    return [str(selected)] if selected else []


def _pool_to_tasks(occ_tasks_list) -> list[dict]:
    out = []
    for occ in occ_tasks_list:
        for u in occ.units:
            for t in u.tasks:
                out.append({
                    "task_name": t.task_name,
                    "source": "catalog",
                    "indexer_ref": {"ocs_code": occ.ocs_code, "task_code": t.task_code},
                    "ocu_code": u.ocu_code,
                    "ocu_name": u.ocu_name,
                })
    return out


def _sort_by_priority(tasks: list[dict], codes: list[str]) -> list[dict]:
    """依使用者勾選的 OCS 優先度（codes 順序）穩定排序任務；未知 OCS 排最後。"""
    rank = {c: i for i, c in enumerate(codes)}
    return sorted(
        tasks,
        key=lambda t: rank.get((t.get("indexer_ref") or {}).get("ocs_code"), len(codes)),
    )


@traced_node("build_task_pool")
async def build_task_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    prof = state["profile"]
    codes = prof.get("selected_ocs_codes") or (
        [prof["selected_ocs_code"]] if prof.get("selected_ocs_code") else [])
    occ_list = [await deps.knowledge.occupation_tasks(c) for c in codes]
    proposed = _sort_by_priority(_pool_to_tasks(occ_list), codes)

    edited = interrupt({"kind": "edit_tasks", "tasks": proposed})
    tasks = edited.get("tasks", proposed) if isinstance(edited, dict) else proposed

    return {"tasks": tasks, "current_step": "deep"}
