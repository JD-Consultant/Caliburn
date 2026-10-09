"""Pure area membership and content transformations."""

from dataclasses import replace
from uuid import uuid4

from caliburn.features.job_description.areas import (
    AreaChange,
    AreaField,
    AreaNotFoundError,
    CreateArea,
    DeleteArea,
    ReorderArea,
    ResponsibilityArea,
    ReviseArea,
)


def apply_area_change(
    areas: tuple[ResponsibilityArea, ...], change: AreaChange
) -> tuple[tuple[ResponsibilityArea, ...], ResponsibilityArea | None]:
    """Return ordered membership and, only for changed text, one new fixed content revision."""
    if isinstance(change, CreateArea):
        created = ResponsibilityArea(uuid4(), uuid4(), change.title, change.scope_text)
        return (*areas, created), created
    target = next((area for area in areas if area.area_id == change.area_id), None)
    if target is None:
        raise AreaNotFoundError("Area is not in the selected JD")
    if isinstance(change, ReviseArea):
        title, scope_text = target.title, target.scope_text
        for item in change.changes:
            if item.field is AreaField.TITLE:
                title = item.value
            else:
                scope_text = item.value
        revised = replace(target, title=title, scope_text=scope_text)
        if revised == target:
            return areas, None
        revised = replace(revised, content_revision_id=uuid4())
        return tuple(revised if area.area_id == target.area_id else area for area in areas), revised
    remaining = tuple(area for area in areas if area.area_id != target.area_id)
    if isinstance(change, DeleteArea):
        return remaining, None
    if isinstance(change, ReorderArea):
        if change.before_area_id == target.area_id:
            return areas, None
        if change.before_area_id is None:
            return (*remaining, target), None
        for index, neighbour in enumerate(remaining):
            if neighbour.area_id == change.before_area_id:
                return (*remaining[:index], target, *remaining[index:]), None
        raise AreaNotFoundError("Ordering neighbour is not in this JD")
    raise TypeError("Unsupported area change")
