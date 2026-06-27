"""v3 收尾 curate 節點：fetch_ksa_pool / curate_ks（逐任務）/ curate_attitudes（全域）。
deterministic、單一 node 內 interrupt for-loop（index-based resume）。pairs() 只在
fetch_ksa_pool 打一次並快取進 state，curate_* 只讀池不重打（idempotency-on-resume）。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState, task_key
from app.graph_v3.tracing import traced_node

logger = logging.getLogger("jobintel")


def _citables_to_items(items) -> list[dict]:
    return [{"content": it.name, "source": "catalog", "icap_ref": it.code or None,
             "sources": [s.task_code for s in it.sources if s.task_code]}
            for it in items if it.name]


@traced_node("fetch_ksa_pool")
async def fetch_ksa_pool(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    ocs = state["profile"]["selected_ocs_code"]
    pool = {"knowledge": [], "skills": [], "attitudes": []}
    if ocs:
        try:
            comp = await deps.knowledge.competencies(ocs)
            pool = {"knowledge": _citables_to_items(comp.knowledge),
                    "skills": _citables_to_items(comp.skills),
                    "attitudes": _citables_to_items(comp.attitudes)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_ksa_pool: competencies() failed, empty pool: %s", exc)
    return {"ksa": {**state["ksa"], "pool": pool}, "current_step": "curate_ks"}


@traced_node("curate_ks")
async def curate_ks(state: InterviewState, config) -> dict:
    pool = state["ksa"]["pool"]
    cand = {"knowledge": pool.get("knowledge", []), "skills": pool.get("skills", [])}
    by_task = dict(state["ksa"].get("by_task") or {})
    tasks = state["tasks"]
    for idx, task in enumerate(tasks):
        key = task_key(task)
        edited = interrupt({
            "kind": "curate_ks",
            "task_index": idx, "task_total": len(tasks),
            "task_name": task["task_name"],
            "candidates": cand,
            "selected": by_task.get(key, {"knowledge": [], "skills": []}),
        })
        ks = edited.get("ks") if isinstance(edited, dict) else None
        by_task[key] = ks or {"knowledge": [], "skills": []}
    logger.info("curate_ks: %d tasks done", len(tasks))
    return {"ksa": {**state["ksa"], "by_task": by_task},
            "current_step": "curate_attitudes"}


@traced_node("curate_attitudes")
async def curate_attitudes(state: InterviewState, config) -> dict:
    pool = state["ksa"]["pool"]
    edited = interrupt({
        "kind": "curate_attitudes",
        "candidates": pool.get("attitudes", []),
        "selected": state["ksa"].get("attitudes", []),
    })
    attitudes = edited.get("attitudes") if isinstance(edited, dict) else None
    return {"ksa": {**state["ksa"], "attitudes": attitudes or []},
            "current_step": "build_doc"}
