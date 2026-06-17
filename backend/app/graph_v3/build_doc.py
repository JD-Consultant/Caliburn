"""v3 build_doc：deterministic 組裝 OCS 文件（D13）。
OCU 分組用 catalog unit 結構；編碼 T/P/O/K/S/A 全程式化；不用 LLM、不 import 舊 ocs_builder。"""
import logging

from langgraph.types import interrupt

from app.graph_v3.state import InterviewState
from app.graph_v3.tracing import traced_node

logger = logging.getLogger("jobintel")


def _group_units(tasks: list[dict]) -> list[dict]:
    """依 unit_id 保序分組；無 unit_id 者歸入 '_'。"""
    order: list[str] = []
    by_unit: dict[str, dict] = {}
    for t in tasks:
        uid = t.get("unit_id") or "_"
        if uid not in by_unit:
            order.append(uid)
            by_unit[uid] = {"unit_title": t.get("unit_title") or "其他工作任務", "tasks": []}
        by_unit[uid]["tasks"].append(t)
    return [{"unit_id": uid, **by_unit[uid]} for uid in order]


def _assemble(state: InterviewState) -> dict:
    units_grouped = _group_units(state["tasks"])
    ocu_units = []
    for u_idx, unit in enumerate(units_grouped, 1):
        tasks_out = []
        for t_idx, task in enumerate(unit["tasks"], 1):
            inds = task.get("behavior_indicators") or []
            indicators = [{"code": f"P{u_idx}.{t_idx}.{p}", "text": ind.get("indicator_5w2h", "")}
                          for p, ind in enumerate(inds, 1) if ind.get("indicator_5w2h")]
            # outputs：優先用 indicator 的 output_name，否則 task["outputs"]
            out_names = [ind["output_name"] for ind in inds if ind.get("output_name")] \
                or [o for o in (task.get("outputs") or []) if o]
            outputs = [{"code": f"O{u_idx}.{t_idx}.{o}", "name": name}
                       for o, name in enumerate(out_names, 1)]
            tasks_out.append({"task_code": f"T{u_idx}.{t_idx}",
                              "task_name": task.get("task_name", ""),
                              "indicators": indicators, "outputs": outputs})
        ocu_units.append({"ocu_code": f"T{u_idx}", "ocu_name": unit["unit_title"], "tasks": tasks_out})

    ksa = state.get("ksa") or {"knowledge": [], "skills": [], "attitudes": []}
    def _coded(items, prefix):
        out = []
        i = 0
        for it in items:
            content = (it.get("content") or "").strip()
            if not content:
                continue
            i += 1
            out.append({"code": it.get("icap_ref") or f"{prefix}{i:02d}", "name": content,
                        "source": it.get("source", "company"), "icap_ref": it.get("icap_ref")})
        return out

    return {
        "ocs_profile": {
            "ocs_code": (state["profile"].get("selected_ocs_code") or ""),
            "occupation_name": state.get("job_title", ""),
            "job_description": state.get("job_summary", ""),
        },
        "ocs_content": {"ocu_units": ocu_units},
        "ocs_ksa": {
            "knowledge": _coded(ksa.get("knowledge", []), "K"),
            "skills": _coded(ksa.get("skills", []), "S"),
            "attitudes": _coded(ksa.get("attitudes", []), "A"),
        },
    }


@traced_node("build_doc")
async def build_doc(state: InterviewState, config) -> dict:
    deps = config["configurable"]["deps"]
    doc = _assemble(state)
    interrupt({"kind": "preview", "document": doc})   # 人確認預覽
    await deps.persist.save_document(state["job_profile_id"], doc)
    logger.info("build_doc: assembled %d OCU units", len(doc["ocs_content"]["ocu_units"]))
    return {"document": doc, "current_step": "done"}
