"""訪談節點：引導工作者自然描述真實工作內容。"""
import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.graph.interview_readiness import compute_readiness, PARTIAL_THRESHOLD
from app.graph.llm import get_cheap_llm
from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState
import app.graph.prompts.interview as prompts

logger = logging.getLogger("jobintel")

_SKIP_VALIDATION: set[str] = {"開始訪談", "yes", "Yes", "確認", "是", "好", "ok", "OK"}


async def _is_on_topic(user_input: str, job_title: str, job_summary: str) -> bool:
    text = user_input.strip()
    if not text or text in _SKIP_VALIDATION or len(text) < 6:
        return True
    prompt = (
        f"你是內容過濾器。判斷以下訊息是否與「{job_title}」職務的工作訪談相關。\n"
        f"職務描述：{job_summary[:120] if job_summary else '（未提供）'}\n"
        f"訊息：{text}\n\n"
        "只回答數字 0 或 1。0 = 不相關，1 = 相關。"
    )
    llm = get_cheap_llm()
    resp = await llm.ainvoke([HumanMessage(content=prompt)])
    return "1" in resp.content.strip()


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

    # 輸入相關性過濾（只在一般訪談階段、非確認訊息時執行）
    if not prev_ready and messages:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        on_topic = await _is_on_topic(last_user, state["job_title"], state.get("job_summary", ""))
        if not on_topic:
            logger.info("interview_node: off-topic input filtered: %.40s", last_user)
            return {
                "ai_response":               "這個問題似乎和職務訪談無關。請回到工作內容的描述，例如您的主要職責、日常工作流程或工作情境。",
                "current_stage":             "interview",
                "interview_readiness_score":  score,
                "interview_readiness_detail": readiness,
                "interview_ready":            False,
                "interview_ready_confirmed":  False,
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
