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
