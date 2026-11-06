"""按種類與 UUID 比較內容，忽略技術版本、實體索引與追查資料。"""

from typing import Literal

from caliburn.modules.job_description.application.content import (
    JobDescriptionContent,
)
from caliburn.modules.job_description.application.content_comparison import (
    index_content,
)
from caliburn.modules.job_description.application.errors import (
    JobDescriptionHistoryNotFoundError,
)
from caliburn.modules.job_description.application.history.results import (
    CollectionDifference,
    FieldDifference,
    ItemDifference,
    JobDescriptionDifference,
)


def compare_contents(
    before: JobDescriptionContent,
    after: JobDescriptionContent,
    *,
    before_version: int,
    after_version: int,
) -> JobDescriptionDifference:
    if before.job_description_id != after.job_description_id:
        raise JobDescriptionHistoryNotFoundError("只能比較同一份 JD 的內容")
    old = index_content(before)
    new = index_content(after)
    items: list[ItemDifference] = []
    for key in sorted(old.items.keys() | new.items.keys()):
        old_fields = old.items.get(key, {})
        new_fields = new.items.get(key, {})
        change: Literal["added", "removed", "modified"] = "modified"
        if key not in old.items:
            change = "added"
        elif key not in new.items:
            change = "removed"
        fields = tuple(
            FieldDifference(
                field=name, before=old_fields.get(name), after=new_fields.get(name)
            )
            for name in sorted(old_fields.keys() | new_fields.keys())
            if change != "modified" or old_fields.get(name) != new_fields.get(name)
        )
        if fields:
            items.append(
                ItemDifference(kind=key[0], id=key[1], change=change, fields=fields)
            )
    collections: list[CollectionDifference] = []
    for collection_key in sorted(
        old.collections.keys() | new.collections.keys(), key=str
    ):
        old_ids = old.collections.get(collection_key, ())
        new_ids = new.collections.get(collection_key, ())
        if old_ids != new_ids:
            collections.append(
                CollectionDifference(
                    collection=collection_key[0],
                    owner_id=collection_key[1],
                    group=collection_key[2],
                    before_ids=old_ids,
                    after_ids=new_ids,
                )
            )
    return JobDescriptionDifference(
        job_description_id=before.job_description_id,
        before_version=before_version,
        after_version=after_version,
        items=tuple(items),
        collections=tuple(collections),
    )
