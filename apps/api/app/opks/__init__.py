"""Public API: OPKS(O/P/K/S/A)analysis, authoring, scheduling and Proposal
decisions for one Current JD Task(ADR 0058).

`opks` owns item authoring(add／edit／delete／reorder), context packet
assembly, the one-stage generation operation, the OPKS pre-gate scheduler, and
OPKS Proposal decisions — the OPKS-equivalent of everything `task_analysis`
does for Task Proposals. It never imports the concrete OpenRouter adapter or
`app.task_analysis`—only `OpksModelPort` and whatever it needs from
`app.core`.

Only what `consultation`(Task 6)and `app.api` actually consume is re-exported
here. Names with zero consumers outside this package stay reachable via their
owning submodule(`app.opks.context`／`app.opks.generation`／
`app.opks.proposals`／`app.opks.verifier`)for tests and scripts, but are not
part of this curated surface(ADR 0058 rule 4):`OpksContextPacket`,
`OpksGenerationResult`, `OpksGenerationSnapshot`, `OpksVerificationReport`,
`remove_opks_item_and_indicator_refs`. Prompt, wire mapper and verifier
violation/gap internals stay in `app.opks.llm` / `app.opks.verifier` for the
same reason — never re-exported here. Core-owned types this feature merely
consumes(`JobAnalysisState`, `ScheduledOpks`, `OperationOutcome`,
`JobAnalysisUnitOfWorkFactory`)are not re-exported either; callers get those
straight from `app.core`.
"""

from __future__ import annotations

from .authoring import (
    add_opks_item,
    delete_opks_item,
    edit_opks_item,
    reorder_opks_items,
)
from .context import (
    OpksGroundingUnavailable,
    build_opks_context_packet,
    render_opks_context_packet,
)
from .digest import compute_analysis_input_digest, scheduled_opks_operation_id
from .errors import (
    InvalidOpksOrder,
    OpksItemNotFound,
    OpksProposalNotDecidable,
    OpksProposalNotFound,
)
from .generation import (
    commit_opks_generation,
    generate_opks_proposals,
    prepare_opks_generation,
)
from .operation import OpksOperationResult, run_opks_operation
from .ports import OpksModelPort
from .proposals import decide_opks_proposal
from .scheduler import (
    OpksTaskStatus,
    eligible_opks_candidates,
    opks_task_status,
    select_scheduled_opks,
)
from .verifier import verify_opks_result

__all__ = [
    "InvalidOpksOrder",
    "OpksGroundingUnavailable",
    "OpksItemNotFound",
    "OpksModelPort",
    "OpksOperationResult",
    "OpksProposalNotDecidable",
    "OpksProposalNotFound",
    "OpksTaskStatus",
    "add_opks_item",
    "build_opks_context_packet",
    "commit_opks_generation",
    "compute_analysis_input_digest",
    "decide_opks_proposal",
    "delete_opks_item",
    "edit_opks_item",
    "eligible_opks_candidates",
    "generate_opks_proposals",
    "opks_task_status",
    "prepare_opks_generation",
    "render_opks_context_packet",
    "reorder_opks_items",
    "run_opks_operation",
    "scheduled_opks_operation_id",
    "select_scheduled_opks",
    "verify_opks_result",
]
