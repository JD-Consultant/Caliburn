from langgraph.graph import StateGraph, START, END

from app.authoring.state import InterviewState
from app.authoring.nodes import pick_profile, build_task_pool
from app.authoring.deep_nodes import (
    star_node, five_w2h_node, indicator_node, route_after_indicator)
from app.authoring.curate_nodes import fetch_ksa_pool, curate_ks, curate_attitudes
from app.authoring.build_doc import build_doc


def route_deep(state: InterviewState) -> str:
    """還有未處理任務 → 進 star（深問）；否則 → 收尾。"""
    if state["deep"]["current_task_index"] < len(state["tasks"]):
        return "star"
    return "finish_deep"


def advance_deep(state: InterviewState) -> dict:
    """一任務深問完成：標記 completed + index 前進。"""
    idx = state["deep"]["current_task_index"]
    deep = dict(state["deep"])
    completed = list(deep.get("completed_task_ids") or [])
    task = state["tasks"][idx]
    task_id = (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]
    if task_id not in completed:
        completed.append(task_id)
    deep["completed_task_ids"] = completed
    deep["current_task_index"] = idx + 1
    deep["missing_fields"] = []
    return {"deep": deep}


def finish_deep(state: InterviewState) -> dict:
    """全部任務深問完 → 交棒 Phase ④（fetch_ksa_pool）。"""
    return {"current_step": "fetch_ksa_pool"}


def build_graph(checkpointer=None):
    """骨幹 + 逐任務深問迴圈（單層 node loop，interrupt 驅動）。
    finish_deep → fetch_ksa_pool → curate_ks → curate_attitudes → build_doc → END。"""
    g = StateGraph(InterviewState)
    g.add_node("pick_profile", pick_profile)
    g.add_node("build_task_pool", build_task_pool)
    g.add_node("star", star_node)
    g.add_node("five_w2h", five_w2h_node)
    g.add_node("indicator", indicator_node)
    g.add_node("advance_deep", advance_deep)
    g.add_node("finish_deep", finish_deep)
    g.add_node("fetch_ksa_pool", fetch_ksa_pool)
    g.add_node("curate_ks", curate_ks)
    g.add_node("curate_attitudes", curate_attitudes)
    g.add_node("build_doc", build_doc)

    g.add_edge(START, "pick_profile")
    g.add_edge("pick_profile", "build_task_pool")
    g.add_conditional_edges("build_task_pool", route_deep,
                            {"star": "star", "finish_deep": "finish_deep"})
    g.add_edge("star", "five_w2h")
    g.add_edge("five_w2h", "indicator")
    g.add_conditional_edges("indicator", route_after_indicator,
                            {"five_w2h": "five_w2h", "advance": "advance_deep"})
    g.add_conditional_edges("advance_deep", route_deep,
                            {"star": "star", "finish_deep": "finish_deep"})
    g.add_edge("finish_deep", "fetch_ksa_pool")
    g.add_edge("fetch_ksa_pool", "curate_ks")
    g.add_edge("curate_ks", "curate_attitudes")
    g.add_edge("curate_attitudes", "build_doc")
    g.add_edge("build_doc", END)
    return g.compile(checkpointer=checkpointer)
