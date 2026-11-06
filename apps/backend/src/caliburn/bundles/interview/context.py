"""既有訪談的讀取、模型投影及一次預載；不保存第二份正文。"""

import asyncio
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from langgraph.runtime import Runtime
from openai.types.responses.response_input_param import ResponseInputParam

from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.interview.application.queries import list_messages
from caliburn.modules.interview.application.results import TranscriptMessage


@dataclass(frozen=True, slots=True)
class InterviewContextMessage:
    message: TranscriptMessage
    supporting_question: bool = False


class InterviewContextSelectionError(ValueError):
    """選取含本輪或不可用的來源；呼叫者須修正範圍，不能視為空訪談。"""

    def __init__(
        self,
        message_id: UUID,
        *,
        reason: Literal["unavailable", "current_turn", "missing_question"],
    ) -> None:
        self.message_id = message_id
        self.reason = reason
        super().__init__(f"無法選取訪談來源 {message_id}：{reason}")


def select_interview_context(
    transcript: tuple[TranscriptMessage, ...],
    *,
    turn_id: UUID,
    message_ids: tuple[UUID, ...] | None = None,
) -> tuple[InterviewContextMessage, ...]:
    """從同一 Workspace 的有序 Transcript 選取；None 全選、空 tuple 不預載。

    排除目前輪次；指定 ID 不可用或所需原題缺失時明確失敗。補題不計入主要選取。
    """
    by_id = {message.message_id: message for message in transcript}
    if message_ids is not None:
        for message_id in message_ids:
            message = by_id.get(message_id)
            if message is None:
                raise InterviewContextSelectionError(message_id, reason="unavailable")
            if message.turn_id == turn_id:
                raise InterviewContextSelectionError(message_id, reason="current_turn")
    selected_ids = (
        set(message_ids)
        if message_ids is not None
        else {
            message.message_id for message in transcript if message.turn_id != turn_id
        }
    )
    question_ids = {
        message.reply_to_message_id
        for message in transcript
        if message.message_id in selected_ids and message.kind == "answer"
    }
    for question_id in question_ids:
        if question_id is None:
            raise ValueError("訪談答案必須指向原題")
        question = by_id.get(question_id)
        if question is None:
            raise InterviewContextSelectionError(question_id, reason="missing_question")
        if question.turn_id == turn_id:
            raise InterviewContextSelectionError(question_id, reason="current_turn")
    return tuple(
        InterviewContextMessage(
            message, supporting_question=message.message_id not in selected_ids
        )
        for message in transcript
        if message.message_id in selected_ids or message.message_id in question_ids
    )


def load_interview_context(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    queries: InterviewQueries,
    message_ids: tuple[UUID, ...] | None = None,
) -> tuple[InterviewContextMessage, ...]:
    """一次查讀可信 Workspace 的有效訪談，查詢錯誤直接傳出。"""
    transcript = list_messages(workspace_id=workspace_id, queries=queries)
    return select_interview_context(
        transcript, turn_id=turn_id, message_ids=message_ids
    )


def project_interview_context(
    messages: tuple[InterviewContextMessage, ...],
    *,
    refs: Mapping[UUID, str],
) -> OpenAIItems:
    """來源保持 user-role；ref 與題答關係沿已提交的持久模型定位。"""
    if not messages:
        return []
    material = {
        "source": "interview",
        "messages": [
            {
                "ref": refs[source.message.message_id],
                "speaker": source.message.speaker,
                "kind": source.message.kind,
                "text": source.message.text,
                "reply_to": (
                    refs[source.message.reply_to_message_id]
                    if source.message.reply_to_message_id is not None
                    else None
                ),
                "supporting_question": source.supporting_question,
            }
            for source in messages
        ],
    }
    return [{"role": "user", "content": json.dumps(material, ensure_ascii=False)}]


def project_employee_input_reference(ref: str) -> OpenAIItems:
    """本輪輸入已由原生 request 保留，此處只提供正式來源定位。"""
    return [
        {
            "role": "user",
            "content": json.dumps(
                {"data_kind": "employee_input_reference", "ref": ref}
            ),
        }
    ]


def insert_interview_context(
    items: OpenAIItems, material: OpenAIItems, *, position: int
) -> OpenAIItems:
    """在 0 到 len(items) 的指定位置插入，保留其他原生 items 與其順序。"""
    if not 0 <= position <= len(items):
        raise ValueError("訪談來源插入位置超出目前 input")
    return [*items[:position], *material, *items[position:]]


async def preload_interview_context(
    state: AgentState, *, runtime: Runtime[AgentContext]
) -> dict[str, object]:
    sources = await asyncio.to_thread(
        load_interview_context,
        workspace_id=state["workspace_id"],
        turn_id=state["turn_id"],
        queries=runtime.context.services.require(INTERVIEW_QUERIES),
    )
    refs = await asyncio.to_thread(
        message_refs,
        workspace_id=state["workspace_id"],
        message_ids=tuple(source.message.message_id for source in sources),
        references=runtime.context.services.require(MODEL_REFERENCES),
    )
    request = state["model_request"]
    items = insert_interview_context(
        request_items(request),
        project_interview_context(sources, refs=refs),
        position=0,
    )
    return {"model_request": {**request, "input": cast(ResponseInputParam, items)}}
