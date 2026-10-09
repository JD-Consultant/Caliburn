"""Render committed JD facts and allocate short locators at the model boundary."""

from caliburn.features.job_description.compound_edits import JdCompoundEditResult
from caliburn.features.job_description.item_results import (
    JdItemDeletionResult,
    JdItemMovementResult,
)
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.workflows.jd_model_references import JdModelReferences

type JdWriteResult = JdCompoundEditResult | JdItemDeletionResult | JdItemMovementResult


async def render_jd_write_result(references: JdModelReferences, result: JdWriteResult) -> str:
    match result:
        case JdCompoundEditResult(effect="created", created_item=item) if item is not None:
            canonical = jd_read_ref(item)
            assigned = await references.assign((canonical,))
            return f"created · read_ref: {assigned[canonical]}"
        case JdCompoundEditResult(effect="created"):
            raise ValueError("A created JD result requires its item identity")
        case JdCompoundEditResult(effect=effect):
            return effect
        case JdItemDeletionResult(detached_task_count=count):
            return "deleted" + (f" · {count} 項任務保留並轉為未歸屬" if count else "")
        case JdItemMovementResult(effect=effect, detached_from_area=detached):
            return effect + (
                " · 原所屬職責已解除，任務現在未歸屬" if effect == "moved" and detached else ""
            )
