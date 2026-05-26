"""
LangGraph 訪談狀態機主體。

節點流程（逐任務）：
  START
    → icap_rag          （iCAP RAG 檢索）
    → interview         （一般訪談）
    → task_extraction   （萃取任務）
    → [per task loop]:
        star            （STAR 深度追問，四槽 slot filling）
        → five_w2h      （5W2H 補洞，9 欄）
        → indicator     （行為指標生成 + 品質評分）
        → [更多任務 → 回 star] or [全部完成 → ksa]
    → ksa               （K/S/A 對齊，OCS 文件生成）
    → END

條件邊：
  - star      → star（繼續追問）或 five_w2h（四槽完成，同任務接 5W2H）
  - five_w2h  → five_w2h（補洞中）或 indicator（當前任務補齊）
  - indicator → five_w2h（Guardrail/品質退回）或 star（下一個任務）或 ksa（全部完成）
  - preview   → END（terminal state，不再 route 到任何節點）
"""
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.icap_rag import icap_rag_node
from app.graph.nodes.indicator import indicator_generation_node
from app.graph.nodes.interview import interview_node
from app.graph.nodes.ocs_builder import ocs_builder_node
from app.graph.nodes.star import star_node
from app.graph.nodes.task_extraction import task_extraction_node
from app.graph.nodes.five_w2h import five_w2h_node
from app.graph.state import InterviewState


# ── 條件函式 ─────────────────────────────────────────────────

_CONFIRM_KEYWORDS = {"確認", "好", "對", "沒問題", "ok", "OK", "可以", "繼續", "正確", "yes", "Yes"}


def _is_pure_confirmation(text: str) -> bool:
    cleaned = text.strip().rstrip("！!。，, ")
    return cleaned in _CONFIRM_KEYWORDS or cleaned.lower() in {"ok", "yes"}


def route_after_task_extraction(state: InterviewState) -> str:
    """
    第一輪：萃取後展示給用戶，停在 task_extraction 等確認。
    第二輪起：
      - 用戶說確認/好/OK → 進 STAR
      - 否則重新萃取（含用戶修正）再等一次確認
    """
    round_count = state.get("task_extraction_round", 0)
    if round_count <= 1:
        # 第一次萃取，等用戶回應
        return END

    # 看最後一條 user 訊息是否為確認語
    user_msgs = [m for m in state.get("messages", []) if m.get("role") == "user"]
    if user_msgs:
        last_user = user_msgs[-1]["content"]
        if _is_pure_confirmation(last_user):
            return "star"

    # 用戶提出修正，重新萃取後再等確認
    return END


def route_after_interview(state: InterviewState) -> str:
    """訪談成熟度 ready=True 才進入任務萃取；需等用戶回應過渡訊息後才放行。"""
    if not state.get("interview_ready", False):
        return "interview"
    # 兩段式：interview_node 第一段只顯示過渡訊息（confirmed=False）；
    # 用戶回應後第二段設 confirmed=True，才路由至 task_extraction。
    if not state.get("interview_ready_confirmed", False):
        return "interview"
    user_msgs = [
        m for m in state.get("messages", [])
        if isinstance(m, dict) and m.get("role") == "user"
    ]
    if len(user_msgs) < 2:
        return "interview"
    return "task_extraction"


def route_after_star(state: InterviewState) -> str:
    """Slot filling 完成後節點自行設 current_stage='five_w2h'；否則繼續 STAR。"""
    if state.get("current_stage") == "five_w2h":
        return "five_w2h"
    return "star"


def route_after_five_w2h(state: InterviewState) -> str:
    """若還有缺漏欄位就繼續補洞，否則生成行為指標。"""
    if state.get("missing_fields"):
        return "five_w2h"
    return "indicator"


def route_after_indicator(state: InterviewState) -> str:
    """Guardrail 退回補洞，或前往下一任務 STAR，或前往 K/S/A。"""
    stage = state.get("current_stage")
    if stage == "five_w2h":
        return "five_w2h"
    if stage == "star":
        return "star"
    return "ksa"


_STAGE_TO_NODE: dict[str, str] = {
    "basic_info":      "icap_rag",
    "icap_ref":        "icap_rag",
    "interview":       "interview",
    "task_extraction": "task_extraction",
    "star":            "star",
    "five_w2h":        "five_w2h",
    "indicator":       "indicator",
    "ksa":             "ksa",
    # "preview" は terminal state — entry_router handles it → END
}

_TERMINAL_STAGES = frozenset({"preview"})


def entry_router(state: InterviewState) -> str:
    """每次 API call 根據 current_stage 跳到正確的節點，不從頭執行。
    preview 為 terminal state，直接路由到 END，不再執行任何節點。
    """
    stage = state.get("current_stage", "basic_info")
    if stage in _TERMINAL_STAGES:
        return END
    return _STAGE_TO_NODE.get(stage, "icap_rag")


# ── 建立 Graph ────────────────────────────────────────────────

def build_interview_graph() -> StateGraph:
    graph = StateGraph(InterviewState)

    # 加入節點
    graph.add_node("icap_rag", icap_rag_node)
    graph.add_node("interview", interview_node)
    graph.add_node("task_extraction", task_extraction_node)
    graph.add_node("star", star_node)
    graph.add_node("five_w2h", five_w2h_node)
    graph.add_node("indicator", indicator_generation_node)
    graph.add_node("ksa", ocs_builder_node)

    # 起始邊：根據 current_stage 決定入口節點
    # END 必須在 mapping 中，讓 preview terminal state 可以直接結束
    graph.add_conditional_edges(
        START,
        entry_router,
        {**{node: node for node in _STAGE_TO_NODE.values()}, END: END},
    )
    graph.add_edge("icap_rag", "interview")

    # 訪談 → 萃取 or END（每次 API call 只跑一輪 interview，不循環）
    graph.add_conditional_edges(
        "interview",
        route_after_interview,
        {"interview": END, "task_extraction": "task_extraction"},
    )

    # 萃取完 → 等確認 or 重萃取 or 進 STAR
    graph.add_conditional_edges(
        "task_extraction",
        route_after_task_extraction,
        {"star": "star", END: END},
    )

    # STAR → END（繼續追問）or 5W2H（完成移下一任務）
    graph.add_conditional_edges(
        "star",
        route_after_star,
        {"star": END, "five_w2h": "five_w2h"},
    )

    # 5W2H → END（仍有缺漏）or 生成指標（全部齊全）
    graph.add_conditional_edges(
        "five_w2h",
        route_after_five_w2h,
        {"five_w2h": END, "indicator": "indicator"},
    )

    # 指標生成 → Guardrail退回 or 下一任務STAR or K/S/A
    graph.add_conditional_edges(
        "indicator",
        route_after_indicator,
        {"five_w2h": "five_w2h", "star": "star", "ksa": "ksa"},
    )

    # K/S/A → 結束
    graph.add_edge("ksa", END)

    return graph.compile()


@lru_cache(maxsize=1)
def get_interview_graph():
    """編譯一次後快取，所有 API call 共用同一個 compiled graph。"""
    return build_interview_graph()
