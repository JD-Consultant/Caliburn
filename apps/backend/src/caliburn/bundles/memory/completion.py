"""顧問整理意圖沿 Core 完成資格，分析師另驗嚴格文字協定。"""

import json
from uuid import UUID

from langgraph.types import StateSnapshot
from openai.types.responses import Response

from caliburn.modules.agent.agent import completed_turn_id


class InvalidMemoryCompletion(ValueError):
    """分析模型未交付正式完成結果。"""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate completion property")
    return result


def require_complete(text: str) -> None:
    try:
        value = json.loads(text, object_pairs_hook=_unique_object)
    except ValueError as error:
        raise InvalidMemoryCompletion("分析師未交付有效完成 JSON") from error
    if value != {"status": "complete"}:
        raise InvalidMemoryCompletion("分析師未交付有效完成 JSON")


def final_text(response: object) -> str | None:
    """只接受單一完整最終文字；推理及中途發話不是完成證據。"""
    if not isinstance(response, Response) or response.status != "completed":
        return None
    finals = [
        item
        for item in response.output
        if item.type == "message" and item.phase != "commentary"
    ]
    if len(finals) != 1 or finals[0].status != "completed":
        return None
    parts = finals[0].content
    if not parts or any(part.type != "output_text" for part in parts):
        return None
    return "".join(part.text for part in parts if part.type == "output_text")


def completed_memory_request(snapshot: StateSnapshot) -> UUID | None:
    """回傳已完成且有整理意圖的輪次；來源上界於完成後選取。"""
    return (
        completed_turn_id(snapshot)
        if snapshot.values.get("memory_consolidation_requested") is True
        else None
    )
