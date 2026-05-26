"""訪談節點：引導工作者自然描述真實工作內容。"""
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.interview_readiness import compute_readiness, PARTIAL_THRESHOLD
from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState
import app.graph.prompts.interview as prompts

logger = logging.getLogger("jobintel")


async def interview_node(state: InterviewState) -> dict:
    messages = state.get("messages", [])
    prev_ready = state.get("interview_ready", False)

    readiness = compute_readiness(messages)
    score = readiness["score"]
    logger.info(
        "interview_node: readiness=%.3f ready=%s prev_ready=%s missing=%s",
        score,
        readiness["ready"],
        prev_ready,
        [s["key"] for s in readiness["missing_signals"]],
    )

    # 兩段式確認：第二段用戶已回應 → 放行至 task_extraction
    if readiness["ready"] and prev_ready:
        logger.info("interview_node: ready confirmed by user reply → task_extraction")
        return {
            "ai_response":               "",
            "current_stage":             "interview",
            "interview_readiness_score":  score,
            "interview_readiness_detail": readiness,
            "interview_ready":            True,
            "interview_ready_confirmed":  True,
        }

    system = prompts.SYSTEM.format(
        job_title=state["job_title"],
        department=state["department"],
        job_summary=state["job_summary"],
    )
    if readiness["ready"]:
        system += prompts.READY
    elif score >= PARTIAL_THRESHOLD and readiness["suggested_follow_up_question"]:
        system += prompts.TARGETED.format(
            suggested_question=readiness["suggested_follow_up_question"]
        )

    history = []
    for msg in messages[-20:]:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        else:
            history.append(AIMessage(content=msg["content"]))

    logger.debug("interview_node: %d messages in context", len(history))
    gw = LLMGateway(temperature=0.3)
    ai_text = await gw.invoke_text([SystemMessage(content=system)] + history)

    return {
        "ai_response":               ai_text,
        "current_stage":             "interview",
        "interview_readiness_score":  score,
        "interview_readiness_detail": readiness,
        "interview_ready":            readiness["ready"],
        "interview_ready_confirmed":  False,
    }
