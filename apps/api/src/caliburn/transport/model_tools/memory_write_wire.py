"""Generated wire DTOs to typed intent, and preflight effects to compact observations."""

from caliburn.contracts.generated.tools import (
    update_work_situation_arguments as situation,
)
from caliburn.contracts.generated.tools import (
    update_work_understanding_arguments as understanding,
)
from caliburn.contracts.generated.tools.create_work_situation_arguments import (
    CreateWorkSituationArguments,
)
from caliburn.contracts.generated.tools.create_work_understanding_arguments import (
    CreateWorkUnderstandingArguments,
)
from caliburn.contracts.generated.tools.delete_memory_object_arguments import (
    DeleteMemoryObjectArguments,
)
from caliburn.contracts.generated.tools.memory_write_result import MemoryWriteResult
from caliburn.contracts.validation import parse_contract
from caliburn.features.work_memory.edit_intents import (
    CreateMemoryIntent,
    DeleteMemoryIntent,
    InterviewReferenceChange,
    InterviewSourceSelection,
    MemoryBodyChange,
    MemoryFieldChange,
    MemoryTextChange,
    MemoryWriteIntent,
    ReviseMemoryIntent,
    SituationReferenceChange,
    SituationSourceSelection,
)
from caliburn.features.work_memory.edit_preparation import MemoryStatusPreview, MemoryUpdatePreview
from caliburn.features.work_memory.models import MemoryContent


def parse_write_intent(name: str, arguments: str) -> MemoryWriteIntent:
    if name == "create_work_situation":
        created = parse_contract(CreateWorkSituationArguments, arguments)
        return CreateMemoryIntent(
            MemoryContent(created.title, created.description, created.body),
            InterviewSourceSelection(tuple(item.root for item in created.interview_references)),
        )
    if name == "create_work_understanding":
        created_understanding = parse_contract(CreateWorkUnderstandingArguments, arguments)
        return CreateMemoryIntent(
            MemoryContent(
                created_understanding.title,
                created_understanding.description,
                created_understanding.body,
            ),
            SituationSourceSelection(
                tuple(item.root for item in created_understanding.work_situation_references)
            ),
        )
    if name in ("delete_work_situation", "delete_work_understanding"):
        deleted = parse_contract(DeleteMemoryObjectArguments, arguments)
        return DeleteMemoryIntent(deleted.target_title)
    if name == "update_work_situation":
        revised = parse_contract(situation.UpdateWorkSituationArguments, arguments)
        return ReviseMemoryIntent(
            revised.target_title, tuple(_situation_change(item) for item in revised.changes)
        )
    if name == "update_work_understanding":
        revised_understanding = parse_contract(
            understanding.UpdateWorkUnderstandingArguments, arguments
        )
        return ReviseMemoryIntent(
            revised_understanding.target_title,
            tuple(_understanding_change(item) for item in revised_understanding.changes),
        )
    raise ValueError("Unknown Memory write tool")


def _situation_change(
    change: situation.MemoryTextChange
    | situation.MemoryBodyChange
    | situation.AddInterviewReferences
    | situation.RemoveInterviewReferences
    | situation.ChangeInterviewReferences,
) -> MemoryFieldChange:
    if isinstance(change, situation.MemoryTextChange):
        return MemoryTextChange(
            "title" if change.field == situation.FieldModel.TITLE else "description", change.value
        )
    if isinstance(change, situation.MemoryBodyChange):
        return MemoryBodyChange(change.diff)
    return InterviewReferenceChange(
        tuple(item.root for item in change.add)
        if isinstance(
            change, situation.AddInterviewReferences | situation.ChangeInterviewReferences
        )
        else (),
        tuple(item.root for item in change.remove)
        if isinstance(
            change, situation.RemoveInterviewReferences | situation.ChangeInterviewReferences
        )
        else (),
    )


def _understanding_change(
    change: understanding.MemoryTextChange
    | understanding.MemoryBodyChange
    | understanding.AddWorkSituationReferences
    | understanding.RemoveWorkSituationReferences
    | understanding.ChangeWorkSituationReferences,
) -> MemoryFieldChange:
    if isinstance(change, understanding.MemoryTextChange):
        return MemoryTextChange(
            "title" if change.field == understanding.FieldModel.TITLE else "description",
            change.value,
        )
    if isinstance(change, understanding.MemoryBodyChange):
        return MemoryBodyChange(change.diff)
    return SituationReferenceChange(
        tuple(item.root for item in change.add)
        if isinstance(
            change,
            understanding.AddWorkSituationReferences | understanding.ChangeWorkSituationReferences,
        )
        else (),
        tuple(item.root for item in change.remove)
        if isinstance(
            change,
            understanding.RemoveWorkSituationReferences
            | understanding.ChangeWorkSituationReferences,
        )
        else (),
    )


def render_write_preview(preview: MemoryStatusPreview | MemoryUpdatePreview) -> str:
    """Build the entire potential output before adoption; not permission to emit success."""
    if isinstance(preview, MemoryStatusPreview):
        return MemoryWriteResult.model_validate({"status": preview.status}).model_dump_json()
    changes: list[dict[str, object]] = [{"field": name} for name in preview.changed_fields]
    if preview.body_diff is not None:
        changes.append({"field": "body", "diff": preview.body_diff})
    if preview.added or preview.removed:
        references: dict[str, object] = {"field": preview.reference_field}
        if preview.added:
            references["added"] = list(preview.added)
        if preview.removed:
            references["removed"] = list(preview.removed)
        changes.append(references)
    return MemoryWriteResult.model_validate(
        {
            "status": "updated",
            "title": preview.content.title,
            "description": preview.content.description,
            "applied_changes": changes,
        }
    ).model_dump_json()
