"""原生 I/O 與保存 handoff 的共同值；不擁有 Graph 路由。"""

from asyncio import CancelledError
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from openai.types.responses import Response
from openai.types.responses.response_input_item_param import FunctionCallOutput
from typing_extensions import TypedDict

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems, NativeSnapshot
from caliburn.agent_execution.request_capacity import (
    ModelCapacityLimits,
    ReceivedInputCount,
    RequestOverflow,
)


class ResponseStepState(TypedDict, total=False):
    request_id: UUID
    request_snapshot: NativeSnapshot
    response_attempt_id: UUID | None
    response_snapshot: NativeSnapshot
    operation_seed: UUID | None
    tool_results: list[FunctionCallOutput]
    next_action: Literal["continue", "deliver_answer"] | None
    completed_steps: int
    model_step_limit: int | None
    tool_call_limit: int
    capacity_limits: ModelCapacityLimits
    input_count: ReceivedInputCount | None
    compacted_request_id: UUID | None
    first_request_fits: int
    pause_enabled: bool


@dataclass(frozen=True, slots=True)
class ReceivedModelResponse:
    """The original SDK result paired with the already-admitted outbound attempt."""

    response: Response = field(repr=False)
    attempt_id: UUID


class ReceivedModelResponseCancelledError(CancelledError):
    """Cancellation carrying an intact R; it grants no authority to resume work."""

    def __init__(self, received: ReceivedModelResponse) -> None:
        self.received = received
        super().__init__("The original response is available after stream cancellation")


@dataclass(frozen=True, slots=True)
class ResponseStepRuntime:
    """Injected I/O, not persisted State. The tool owner validates its prepared command type.

    compact_window binds run_context_compaction to the same work guard and capacity
    policy. Re-entry must reconcile that boundary before any new external request;
    inactive work can settle its saved C, but cannot send, adopt or return a new window.

    fit_first_request is the data owner's pure, deterministic reduction of a counted first
    request that exceeds the hard input limit. It returns the complete replacement input
    items (never a partial edit) or raises RequestCapacityError when nothing smaller is
    legal. The loop recounts the result exactly; without this seam an oversized first
    request stays capacity-blocked.
    """

    request_model: Callable[[ResponseRequest, UUID, int], Awaitable[ReceivedModelResponse]]
    ensure_active: Callable[[], Awaitable[None]]
    account_response: Callable[[ReceivedModelResponse], Awaitable[None]]
    count_input: Callable[[ResponseRequest, UUID], Awaitable[ReceivedInputCount]]
    capacity_limits: ModelCapacityLimits
    compact_window: (
        Callable[[ResponseRequest, ReceivedInputCount, UUID], Awaitable[NativeItems]] | None
    ) = None
    fit_first_request: Callable[[ResponseRequest, RequestOverflow], NativeItems] | None = None
    inactive_errors: tuple[type[Exception], ...] = ()


@dataclass(frozen=True, slots=True)
class HeldModelResponse:
    """Process-local recovery handoff, never a replacement for a durable checkpoint.

    Only pass this object back to the same Step. Do not serialize it into logs or
    product history. Its operation seed is retained along with the exact native R.
    """

    thread_id: str
    request_id: UUID
    request_snapshot: NativeSnapshot = field(repr=False)
    update: ResponseStepState = field(repr=False)


@dataclass(frozen=True, slots=True)
class HeldInputCount:
    """Intact process-local count bound to the exact original request, not a cache."""

    thread_id: str
    request_id: UUID
    request_snapshot: NativeSnapshot = field(repr=False)
    update: ResponseStepState = field(repr=False)


class InputCountSaveError(RuntimeError):
    def __init__(self, recovery: HeldInputCount) -> None:
        super().__init__("The original input count is held; reconcile before counting again")
        self.recovery = recovery


class ResponseStepSaveError(RuntimeError):
    """No tools started from this R; the caller can retry saving the held original."""

    def __init__(self, recovery: HeldModelResponse) -> None:
        super().__init__(
            "The original model result is held; reconcile its checkpoint before retrying"
        )
        self.recovery = recovery


class ModelStepLimitError(RuntimeError):
    """The last Step is saved, but this invocation may not request another response."""


@dataclass(frozen=True, slots=True)
class ResponseLoopControls:
    """Product-owned pause request and acknowledgement; no model-visible controls."""

    read_pause_requested: Callable[[], Awaitable[bool]]
    mark_paused: Callable[[], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PausedResponseLoop:
    """A durable native interrupt, not a final answer or a failed execution."""

    interrupt_id: str
    state: ResponseStepState = field(repr=False)
