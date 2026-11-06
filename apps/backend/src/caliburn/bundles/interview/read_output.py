"""訪談工具完整結果；不截斷正文或擴大選取。"""

import json
from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from caliburn.modules.interview.application.results import TranscriptMessage


def rejection(code: str, message: str, next_action: str) -> str:
    return json.dumps(
        {
            "status": "rejected",
            "code": code,
            "message": message,
            "next_action": next_action,
        },
        ensure_ascii=False,
    )


def bounded_interview(
    messages: tuple[TranscriptMessage, ...],
    *,
    refs: Mapping[UUID, str],
    selection: Literal["messages", "range"],
    limit: int,
) -> str:
    material = {
        "data_kind": "interview",
        "messages": [
            {
                "ref": refs[message.message_id],
                "speaker": message.speaker,
                "kind": message.kind,
                "text": message.text,
                "reply_to": refs[message.reply_to_message_id]
                if message.reply_to_message_id is not None
                else None,
            }
            for message in messages
        ],
    }
    encoded = json.dumps(material, ensure_ascii=False)
    if len(encoded) <= limit:
        return encoded
    if len(messages) == 1:
        next_action = (
            "單則完整原話已超出容量，請由應用調整讀取容量；不要重試相同參數或要求截斷。"
        )
    else:
        midpoint = len(messages) // 2
        queries: list[dict[str, object]] = []
        for part in (messages[:midpoint], messages[midpoint:]):
            if selection == "range":
                query: dict[str, object] = {
                    "kind": "range",
                    "start_ref": refs[part[0].message_id],
                    "end_ref": refs[part[-1].message_id],
                }
            else:
                query = {
                    "kind": "messages",
                    "refs": [refs[message.message_id] for message in part],
                }
            queries.append({"query": query})
        next_action = "請分別呼叫 read_interview：" + json.dumps(
            queries, ensure_ascii=False
        )
    return rejection(
        "read_limit_exceeded",
        "指定訪談的完整結果超過讀取容量，未回傳部分正文。",
        next_action,
    )
