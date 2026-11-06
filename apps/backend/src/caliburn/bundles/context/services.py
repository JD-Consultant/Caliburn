"""上下文策略使用組裝方管理的同一個 OpenAI client。"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from langgraph.types import StateSnapshot
from openai import AsyncOpenAI
from openai.types.responses import CompactedResponse
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.modules.agent.plugins.services import ServiceCollection, ServiceKey

WINDOW_CONTRIBUTIONS = ServiceCollection[WindowContribution]("window_contributions")
HISTORY_COMPACTION = ServiceCollection[
    Callable[[ResponseCreateParamsBase], Awaitable[CompactedResponse | None]]
]("history_compaction")

COMPACTION_CLIENT = ServiceKey[AsyncOpenAI]("compaction-client")

PREVIOUS_WINDOW = ServiceKey[Callable[[UUID, UUID], Awaitable[StateSnapshot | None]]](
    "previous_completed_window"
)
COMPLETED_TURNS = ServiceKey[Callable[[UUID], Awaitable[frozenset[UUID]]]](
    "context_completed_turns"
)
