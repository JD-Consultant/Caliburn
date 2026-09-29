"""Apply one precise source-owner edit; external source qualification stays in workflows."""

from uuid import uuid4

from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InterviewSource,
    InvalidJdSourceError,
    JdSource,
    JdSourceReference,
    RemoveJdSource,
    ReviseJdSources,
    add_source_reference,
    align_source_reference,
)


def apply_source_changes(
    references: tuple[JdSourceReference, ...], command: ReviseJdSources
) -> tuple[JdSourceReference, ...]:
    result = references
    for change in command.changes:
        if isinstance(change, AddJdSource):
            result = add_source_reference(
                result, JdSourceReference(uuid4(), command.target, change.source)
            )
            continue
        reference = next((ref for ref in result if ref.citation_id == change.citation_id), None)
        if reference is None or reference.target != command.target:
            raise InvalidJdSourceError("The citation does not belong to the selected JD target")
        if isinstance(change, RemoveJdSource):
            result = tuple(ref for ref in result if ref.citation_id != reference.citation_id)
        elif isinstance(change, AlignJdSource):
            aligned = align_source_reference(reference, change.source)
            result = tuple(
                aligned if ref.citation_id == reference.citation_id else ref for ref in result
            )
    return result


def source_change_payload(command: ReviseJdSources) -> dict[str, object]:
    """Typed command values only, with explicit actions for reliable original-result comparison."""
    changes: list[dict[str, object]] = []
    for change in command.changes:
        if isinstance(change, AddJdSource):
            changes.append({"action": "add_source", "source": _source_payload(change.source)})
        elif isinstance(change, RemoveJdSource):
            changes.append({"action": "remove_source", "citation_id": str(change.citation_id)})
        else:
            changes.append(
                {
                    "action": "confirm_reference_alignment",
                    "citation_id": str(change.citation_id),
                    "source": _source_payload(change.source),
                }
            )
    target = command.target
    return {
        "target": {
            "kind": target.kind.value,
            "item_id": str(target.item_id) if target.item_id is not None else None,
            "field": target.field.value if target.field is not None else None,
            "task_id": str(target.task_id) if target.task_id is not None else None,
        },
        "changes": changes,
    }


def _source_payload(source: JdSource) -> dict[str, str]:
    if isinstance(source, InterviewSource):
        return {"kind": "interview", "source_id": str(source.source_id)}
    return {
        "kind": source.layer.value,
        "snapshot_id": str(source.snapshot_id),
        "object_id": str(source.object_id),
        "revision_id": str(source.revision_id),
    }
