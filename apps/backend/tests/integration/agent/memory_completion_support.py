"""Memory 來源與換窗測試共用的 Core 合法完成回應。"""

from typing import Literal

from tests.unit.modules.agent.offline_openai import message

CompletionShape = Literal["text", "refusal", "multiple_finals"]
COMPLETION_SHAPES: tuple[CompletionShape, ...] = (
    "text",
    "refusal",
    "multiple_finals",
)


def completion_messages(shape: CompletionShape, text: str) -> list[dict[str, object]]:
    final = message(text=text)
    if shape == "refusal":
        return [{**final, "content": [{"type": "refusal", "refusal": text}]}]
    if shape == "multiple_finals":
        return [
            {**message(text="先前的正式訊息"), "id": "msg_first"},
            final,
        ]
    return [final]
