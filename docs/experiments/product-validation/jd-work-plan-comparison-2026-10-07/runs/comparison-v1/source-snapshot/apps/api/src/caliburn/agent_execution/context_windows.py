"""Read-only handles to native windows; eligibility is owned by the application."""

from dataclasses import dataclass, field

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple

from caliburn.adapters.response_serialization import NativeItems


@dataclass(frozen=True, slots=True)
class SavedContextWindow:
    checkpoint_id: str
    items: NativeItems = field(repr=False)


async def read_context_checkpoint(
    checkpointer: BaseCheckpointSaver[str], *, thread_id: str, checkpoint_id: str | None
) -> CheckpointTuple:
    """Read only. An explicit missing position never falls back to the latest one."""
    if not thread_id or checkpoint_id == "":
        raise ValueError("A context position needs nonempty identifiers")
    config: RunnableConfig = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    if checkpoint_id is not None:
        config["configurable"]["checkpoint_id"] = checkpoint_id
    saved = await checkpointer.aget_tuple(config)
    if saved is None:
        raise ValueError("The saved context position is unavailable")
    if checkpoint_id is not None and saved.checkpoint["id"] != checkpoint_id:
        raise ValueError("The saved context position does not match the requested checkpoint")
    return saved
