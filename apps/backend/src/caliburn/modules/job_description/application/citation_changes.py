"""比較 JD 引用的固定 Memory 圖；同名新 UUID 不接替被刪來源。"""

from dataclasses import dataclass
from uuid import UUID

from caliburn.modules.job_description.application.errors import CitationSourceDataError
from caliburn.modules.job_description.domain.models.citation import MemoryReference
from caliburn.modules.memory.application.errors import MemoryVersionNotFoundError
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.modules.memory.domain.items import (
    MemoryItem,
    WorkSituation,
    same_memory_item,
)
from caliburn.modules.memory.domain.snapshot import MemorySnapshot


@dataclass(frozen=True)
class MemoryCitationContent:
    item: MemoryItem
    situations: tuple[WorkSituation, ...]


@dataclass(frozen=True)
class CitationSourceComparison:
    before: MemoryCitationContent
    after: MemoryCitationContent | None
    source_changed: bool


def compare_memory_citation(
    *,
    source: MemoryReference,
    published_version: int,
    queries: MemoryQueries,
) -> CitationSourceComparison:
    before_snapshot = _read_snapshot(
        queries, source.workspace_id, source.published_version
    )
    after_snapshot = (
        before_snapshot
        if source.published_version == published_version
        else _read_snapshot(queries, source.workspace_id, published_version)
    )
    before = _content(before_snapshot, source.item_id)
    if before is None:
        raise CitationSourceDataError("固定 Memory 項目已遺失")
    after = _content(after_snapshot, source.item_id)
    if after is None:
        return CitationSourceComparison(before=before, after=None, source_changed=True)
    if before.item.kind != after.item.kind:
        raise CitationSourceDataError("同一 Memory 身分的種類不一致")
    old_situations = {item.id: item for item in before.situations}
    new_situations = {item.id: item for item in after.situations}
    same_chain = old_situations.keys() == new_situations.keys() and all(
        same_memory_item(old_situations[item_id], new_situations[item_id])
        for item_id in old_situations
    )
    return CitationSourceComparison(
        before=before,
        after=after,
        source_changed=not (same_memory_item(before.item, after.item) and same_chain),
    )


def _read_snapshot(
    queries: MemoryQueries, workspace_id: UUID, version: int
) -> MemorySnapshot:
    try:
        snapshot = queries.get_published(
            workspace_id=workspace_id, published_version=version
        )
    except MemoryVersionNotFoundError as error:
        raise CitationSourceDataError("固定 Memory 發布版已遺失") from error
    if (
        snapshot is None
        or snapshot.workspace_id != workspace_id
        or snapshot.version != version
    ):
        raise CitationSourceDataError("固定 Memory 發布版不符")
    return snapshot


def _content(snapshot: MemorySnapshot, item_id: UUID) -> MemoryCitationContent | None:
    by_id = {item.id: item for item in snapshot.items}
    item = by_id.get(item_id)
    if item is None:
        return None
    situations = []
    if not isinstance(item, WorkSituation):
        for source_id in item.situation_ids:
            source = by_id.get(source_id)
            if not isinstance(source, WorkSituation):
                raise CitationSourceDataError("固定 Memory 來源圖不完整")
            situations.append(source)
    return MemoryCitationContent(item=item, situations=tuple(situations))
