import json
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.graph.graph import get_interview_graph
from app.models import InterviewSession, JobProfile
from app.services.state_service import StateService

logger = logging.getLogger("jobintel")


def _message_kind(node_name: str, node_output: dict) -> str:
    """Classify graph node output for chat UI presentation."""
    content = (node_output.get("ai_response") or "").strip()
    if not content:
        return "status"

    if node_name in {"star", "five_w2h"} and node_output.get("phase"):
        return "question"
    if node_name == "interview":
        return "question"
    if "正在" in content and len(content) <= 80:
        return "status"
    return "summary"


class InterviewOrchestrator:
    @staticmethod
    async def stream(
        profile: JobProfile,
        phase: str,
        user_input: str,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        """Load history, run graph, stream SSE chunks, persist result."""
        profile_id = profile.id

        history_result = await db.execute(
            select(InterviewSession)
            .where(InterviewSession.job_profile_id == profile_id)
            .order_by(InterviewSession.created_at.asc())
        )
        history = [
            {"role": m.role, "content": m.content, "phase": m.phase or "general"}
            for m in history_result.scalars().all()
        ]

        initial_state = StateService.build_initial_state(profile, phase, user_input, history)
        graph = get_interview_graph()

        ai_messages: list[dict] = []
        final_stage = initial_state["current_stage"]
        accumulated = dict(initial_state)

        try:
            async for event in graph.astream(initial_state):
                for node_name, node_output in event.items():
                    if node_output.get("ai_response"):
                        chunk = node_output["ai_response"]
                        stage = node_output.get("current_stage") or accumulated.get("current_stage")
                        message = {
                            "type": "message",
                            "kind": _message_kind(node_name, node_output),
                            "stage": stage,
                            "phase": node_output.get("phase") or phase,
                            "node": node_name,
                            "content": chunk,
                        }
                        ai_messages.append(message)
                        yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                    accumulated.update(node_output)
                    if "current_stage" in node_output:
                        final_stage = node_output["current_stage"]
        except Exception as exc:
            logger.error("graph.astream error: %s", exc, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)}, ensure_ascii=False)}\n\n"
            return

        new_graph_state = StateService.extract_persistent(accumulated)

        async with AsyncSessionLocal() as new_db:
            created_at = datetime.now(timezone.utc)
            for index, message in enumerate(ai_messages):
                new_db.add(InterviewSession(
                    job_profile_id=profile_id,
                    role="ai",
                    phase=message["phase"],
                    content=message["content"],
                    extra_data={
                        "kind": message["kind"],
                        "stage": message["stage"],
                        "node": message["node"],
                    },
                    created_at=created_at + timedelta(microseconds=index),
                ))
            await StateService.persist(new_db, profile_id, final_stage, new_graph_state)

        logger.info(
            "chat done: profile=%s stage=%s tasks=%d",
            profile_id, final_stage,
            len(new_graph_state.get("extracted_tasks", [])),
        )
        yield 'data: "[DONE]"\n\n'
