from langgraph.types import interrupt

from app.graph_v3.state import InterviewState


async def pick_profile(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    query = state.get("job_summary") or state["job_title"]
    res = await deps.knowledge.search(query, level="profile", top_k=8)
    candidates = [h.model_dump() for h in res.hits]

    selected = interrupt({"kind": "select_profile", "candidates": candidates})
    ocs = selected.get("ocs_code") if isinstance(selected, dict) else str(selected)

    await deps.persist.set_selected_ocs(state["job_profile_id"], ocs)
    return {
        "profile": {"candidates": candidates, "selected_ocs_code": ocs},
        "current_step": "task_pool",
    }


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


async def build_task_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pool = await deps.knowledge.task_pool([ocs] if ocs else [])
    proposed = _pool_to_tasks(pool)

    edited = interrupt({"kind": "edit_tasks", "tasks": proposed})
    tasks = edited.get("tasks", proposed) if isinstance(edited, dict) else proposed

    await deps.persist.flush_tasks(state["job_profile_id"], tasks)
    return {"tasks": tasks, "current_step": "deep"}
