from langgraph.graph import StateGraph, START, END

from app.graph_v3.state import InterviewState
from app.graph_v3.nodes import pick_profile, build_task_pool


def build_graph_v3(checkpointer=None):
    """v3 骨幹（Phase ②：前兩節點；深問子圖等後續 phase 接上）。"""
    g = StateGraph(InterviewState)
    g.add_node("pick_profile", pick_profile)
    g.add_node("build_task_pool", build_task_pool)
    g.add_edge(START, "pick_profile")
    g.add_edge("pick_profile", "build_task_pool")
    g.add_edge("build_task_pool", END)
    return g.compile(checkpointer=checkpointer)
