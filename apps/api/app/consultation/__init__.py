"""Public API: one synchronous, durable consultant turn per employee message.

`consultation` is the orchestrator ADR 0058 carves out last: it coordinates
exactly one Task Proposal analysis turn (`app.task_analysis`) with at most one
scheduled OPKS child analysis (`app.opks`) for a single `/turns` request —
provider call before the write transaction, idempotency-key replay, and the
"one primary consultant + at most one OPKS child" invariant (ADR 0054
decisions 7-9, 32, 34) all live here.

`consultation` is the *only* module allowed to import both `app.task_analysis`
and `app.opks` (ADR 0058 rule 2's one named exception) — and only their root
public APIs, never sibling implementation files inside either package. It
never imports the concrete `OpenRouterAdapter`; `submit_employee_turn` takes
`TaskAnalysisModelPort` and `OpksModelPort` as two explicitly typed
parameters, so the composition root may hand the same adapter instance to
both without `consultation` depending on which concrete class satisfies them.

Only what `app.api` actually consumes is re-exported here. `_require_verified`,
`_load_state`, and other private `durable_turn` helpers stay reachable via
`app.consultation.durable_turn` for tests, but are not part of this curated
surface (ADR 0058 rule 4).
"""

from __future__ import annotations

from .durable_turn import (
    CommittedTurn,
    TransitionCommitRejected,
    TurnSnapshot,
    UncommittableOperationResult,
    commit_verified_turn,
    prepare_turn,
)
from .turn import submit_employee_turn

__all__ = [
    "CommittedTurn",
    "TransitionCommitRejected",
    "TurnSnapshot",
    "UncommittableOperationResult",
    "commit_verified_turn",
    "prepare_turn",
    "submit_employee_turn",
]
