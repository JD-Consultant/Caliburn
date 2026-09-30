"""Read public commentary from original native results, never from carried context."""

from dataclasses import dataclass, field

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from openai.types.responses import Response, ResponseOutputMessage

from caliburn.adapters.response_serialization import restore_response


@dataclass(frozen=True, slots=True)
class PublicCommentary:
    response_id: str
    message_id: str
    text: str = field(repr=False)


def project_commentary(response: Response) -> tuple[PublicCommentary, ...]:
    """A positive field allowlist, not serialization of provider output objects."""
    if response.status != "completed" or response.error is not None:
        return ()
    messages = []
    for item in response.output:
        if not (
            isinstance(item, ResponseOutputMessage)
            and item.role == "assistant"
            and item.phase == "commentary"
            and item.status == "completed"
        ):
            continue
        text = "\n\n".join(
            part.text if part.type == "output_text" else part.refusal for part in item.content
        )
        if text.strip():
            messages.append(PublicCommentary(response.id, item.id, text))
    return tuple(messages)


async def read_public_commentary(
    checkpointer: BaseCheckpointSaver[str], *, thread_id: str
) -> tuple[PublicCommentary, ...]:
    """Retained native history survives compaction; no Graph invocation or extra store.

    Native saver history is newest first. A saved model pending write is newer than
    its checkpoint's channel values. Only response originals are read, never input_items.
    """
    config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    seen: set[str] = set()
    groups: list[tuple[PublicCommentary, ...]] = []
    async for saved in checkpointer.alist(config):
        snapshots = [
            value
            for _task_id, channel, value in saved.pending_writes or ()
            if channel == "response_snapshot"
        ]
        snapshots.append(saved.checkpoint["channel_values"].get("response_snapshot"))
        for snapshot in snapshots:
            if not snapshot:
                continue
            if not isinstance(snapshot, dict):
                raise ValueError("A saved response original is unavailable")
            response_id = snapshot.get("id")
            if isinstance(response_id, str) and response_id in seen:
                continue
            response = restore_response(snapshot)
            seen.add(response.id)
            groups.append(project_commentary(response))
    return tuple(message for group in reversed(groups) for message in group)
