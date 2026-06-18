from langgraph.types import interrupt

from app.graph_v3.state import InterviewState
from app.graph_v3.tracing import traced_node


@traced_node("pick_profile")
async def pick_profile(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    query = state.get("job_summary") or state["job_title"]
    res = await deps.knowledge.search(query, level="profile", top_k=8)
    candidates = [h.model_dump() for h in res.hits]

    selected = interrupt({"kind": "select_profile", "candidates": candidates})
    codes = _resume_to_codes(selected)          # 有序清單，順序=優先度
    primary = codes[0] if codes else None

    await deps.persist.set_selected_ocs(state["job_profile_id"], primary)
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


def _pool_to_tasks(pool) -> list[dict]:
    out = []
    for g in pool.groups:
        for u in g.units:
            for t in u.tasks:
                out.append({
                    "task_name": t.task_title,
                    "source": "catalog",
                    "indexer_ref": {"ocs_code": g.ocs_code, "task_id": t.task_id},
                    "unit_id": u.unit_id,
                    "unit_title": u.unit_title,
                    "activity_examples": t.activity_examples,
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
    pool = await deps.knowledge.task_pool(codes)
    proposed = _sort_by_priority(_pool_to_tasks(pool), codes)

    edited = interrupt({"kind": "edit_tasks", "tasks": proposed})
    tasks = edited.get("tasks", proposed) if isinstance(edited, dict) else proposed

    await deps.persist.flush_tasks(state["job_profile_id"], tasks)
    return {"tasks": tasks, "current_step": "deep"}
