"""鎖定 Workspace 根並保存目前項目與發布快照。"""

from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from caliburn.modules.memory.application.errors import (
    MemoryVersionNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.modules.memory.infrastructure.persistence.codec import (
    SCHEMA_VERSION,
    ItemPayload,
    decode_current,
    decode_snapshot,
    encode_snapshot,
)
from caliburn.modules.memory.infrastructure.persistence.orm_models import (
    MemoryItemRow,
    MemorySnapshotRow,
    WorkMemoryRow,
)
from caliburn.modules.workspace.infrastructure.persistence.public_queries import (
    select_workspace_id,
)


class SqlAlchemyMemoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._loaded: dict[UUID, dict[UUID, ItemPayload] | None] = {}

    def _lock_workspace(self, *, workspace_id: UUID) -> None:
        # 鎖定父列也涵蓋首次建立；NO KEY UPDATE 仍允許訪談取得 KEY SHARE。
        if (
            self._session.scalar(
                select_workspace_id(workspace_id=workspace_id).with_for_update(
                    key_share=True
                )
            )
            is None
        ):
            raise WorkspaceNotFoundError("Workspace 不存在")

    def get_for_update(self, *, workspace_id: UUID) -> WorkMemory | None:
        self._lock_workspace(workspace_id=workspace_id)
        memory = read_current(self._session, workspace_id=workspace_id, lock=True)
        self._loaded[workspace_id] = (
            {item.id: ItemPayload.from_domain(item) for item in memory.items}
            if memory is not None
            else None
        )
        return memory

    def get_snapshot(self, *, workspace_id: UUID, version: int) -> MemorySnapshot:
        return read_snapshot(self._session, workspace_id=workspace_id, version=version)

    def save(self, memory: WorkMemory, *, snapshot: MemorySnapshot | None) -> None:
        workspace_id = memory.workspace_id
        loaded = self._loaded[workspace_id]
        values = dict(
            version=memory.version,
            published_version=memory.published_version,
            analysis=memory.analysis.model_dump(mode="json")
            if memory.analysis
            else None,
            failure=memory.failure.model_dump(mode="json") if memory.failure else None,
        )
        if loaded is None:
            self._session.add(WorkMemoryRow(workspace_id=workspace_id, **values))
            self._session.flush()
            before: dict[UUID, ItemPayload] = {}
        else:
            before = loaded
            if snapshot is not None:
                self._session.add(
                    MemorySnapshotRow(
                        workspace_id=workspace_id,
                        version=snapshot.version,
                        schema_version=SCHEMA_VERSION,
                        covered_through_message_id=snapshot.covered_through_message_id,
                        published_at=snapshot.published_at,
                        content=encode_snapshot(snapshot),
                    )
                )
                self._session.flush()
            self._session.execute(
                update(WorkMemoryRow)
                .where(WorkMemoryRow.workspace_id == workspace_id)
                .values(**values)
            )
        after = {item.id: ItemPayload.from_domain(item) for item in memory.items}
        self._save_items(workspace_id, before, after)
        self._loaded[workspace_id] = after

    def _save_items(
        self,
        workspace_id: UUID,
        before: dict[UUID, ItemPayload],
        after: dict[UUID, ItemPayload],
    ) -> None:
        removed = before.keys() - after.keys()
        if removed:
            self._session.execute(
                delete(MemoryItemRow).where(
                    MemoryItemRow.workspace_id == workspace_id,
                    MemoryItemRow.item_id.in_(removed),
                )
            )
        for item_id, item in after.items():
            old = before.get(item_id)
            if item == old:
                continue
            values = dict(
                kind=item.kind,
                title=item.title,
                description=item.description,
                body=item.body,
                source_ids=list(item.source_ids),
                changed_version=item.changed_version,
            )
            if old is None:
                self._session.add(
                    MemoryItemRow(workspace_id=workspace_id, item_id=item_id, **values)
                )
            else:
                self._session.execute(
                    update(MemoryItemRow)
                    .where(
                        MemoryItemRow.workspace_id == workspace_id,
                        MemoryItemRow.item_id == item_id,
                    )
                    .values(**values)
                )
        self._session.flush()
        # 放棄稿可能交換多個項目的名稱。完成整批再驗唯一性，仍在 COMMIT 之前。
        self._session.execute(text("SET CONSTRAINTS uq_memory_items_title IMMEDIATE"))


def read_current(
    session: Session, *, workspace_id: UUID, lock: bool
) -> WorkMemory | None:
    """呼叫者持有寫入鎖，或使用單一 REPEATABLE READ 檢視。"""
    statement = select(WorkMemoryRow).where(WorkMemoryRow.workspace_id == workspace_id)
    if lock:
        statement = statement.with_for_update()
    root = session.scalar(statement)
    if root is None:
        return None
    items = tuple(
        session.scalars(
            select(MemoryItemRow)
            .where(MemoryItemRow.workspace_id == workspace_id)
            .order_by(MemoryItemRow.item_id)
        )
    )
    return decode_current(root, items)


def read_snapshot(
    session: Session, *, workspace_id: UUID, version: int
) -> MemorySnapshot:
    row = session.get(MemorySnapshotRow, (workspace_id, version))
    if row is None:
        raise MemoryVersionNotFoundError("Workspace 沒有指定的 Memory 發布版")
    return decode_snapshot(row)
