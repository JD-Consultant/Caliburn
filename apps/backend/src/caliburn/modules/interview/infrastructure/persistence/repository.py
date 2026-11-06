"""同輪列鎖與局部追加保存。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from caliburn.modules.interview.application.errors import (
    InterviewDataError,
    WorkspaceNotFoundError,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.infrastructure.persistence.message_mapping import (
    load_message,
)
from caliburn.modules.interview.infrastructure.persistence.orm_models import (
    InterviewMessageRow,
    InterviewTurnRow,
)
from caliburn.modules.workspace.infrastructure.persistence.public_queries import (
    select_workspace_id,
)


class SqlAlchemyInterviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._loaded: dict[tuple[UUID, UUID], tuple[int, datetime | None]] = {}

    def get_or_create_for_update(self, candidate: InterviewTurn) -> InterviewTurn:
        # KEY SHARE 防止 Workspace 在建立期間被刪除，不串行其他輪次的追加。
        if (
            self._session.scalar(
                select_workspace_id(
                    workspace_id=candidate.workspace_id
                ).with_for_update(read=True, key_share=True)
            )
            is None
        ):
            raise WorkspaceNotFoundError("Workspace 不存在")
        statement = insert(InterviewTurnRow).values(
            workspace_id=candidate.workspace_id,
            turn_id=candidate.turn_id,
            kind=candidate.kind,
            created_at=candidate.created_at,
            withdrawn_at=candidate.withdrawn_at,
        )
        if candidate.kind == "opening":
            statement = statement.on_conflict_do_nothing(
                index_elements=[InterviewTurnRow.workspace_id],
                index_where=InterviewTurnRow.kind == "opening",
            )
            target = select(InterviewTurnRow).where(
                InterviewTurnRow.workspace_id == candidate.workspace_id,
                InterviewTurnRow.kind == "opening",
            )
        else:
            statement = statement.on_conflict_do_nothing(
                index_elements=[InterviewTurnRow.workspace_id, InterviewTurnRow.turn_id]
            )
            target = select(InterviewTurnRow).where(
                InterviewTurnRow.workspace_id == candidate.workspace_id,
                InterviewTurnRow.turn_id == candidate.turn_id,
            )
        inserted = self._session.scalar(statement.returning(InterviewTurnRow.turn_id))
        if inserted is not None:
            self._loaded[candidate.id] = (0, candidate.withdrawn_at)
            self.save(candidate)
            return candidate
        row = self._session.scalars(target.with_for_update()).one()
        return self._load(row)

    def get_for_update(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> InterviewTurn | None:
        row = self._session.scalar(
            select(InterviewTurnRow)
            .where(
                InterviewTurnRow.workspace_id == workspace_id,
                InterviewTurnRow.turn_id == turn_id,
            )
            .with_for_update()
        )
        return self._load(row) if row is not None else None

    def save(self, turn: InterviewTurn) -> None:
        loaded = self._loaded.get(turn.id)
        if loaded is None:
            raise RuntimeError("必須先載入並鎖定訪談輪次才能保存")
        message_count, withdrawn_at = loaded
        for message in turn.messages[message_count:]:
            self._session.add(
                InterviewMessageRow(
                    id=message.id,
                    workspace_id=turn.workspace_id,
                    turn_id=turn.turn_id,
                    position=message.position,
                    speaker=message.speaker,
                    kind=message.kind,
                    content=message.content.model_dump(mode="json"),
                    reply_to_message_id=message.reply_to_message_id,
                    created_at=message.created_at,
                )
            )
        if withdrawn_at != turn.withdrawn_at:
            self._session.execute(
                update(InterviewTurnRow)
                .where(
                    InterviewTurnRow.workspace_id == turn.workspace_id,
                    InterviewTurnRow.turn_id == turn.turn_id,
                )
                .values(withdrawn_at=turn.withdrawn_at)
            )
        self._session.flush()
        self._loaded[turn.id] = (len(turn.messages), turn.withdrawn_at)

    def _load(self, row: InterviewTurnRow) -> InterviewTurn:
        messages = self._session.scalars(
            select(InterviewMessageRow)
            .where(
                InterviewMessageRow.workspace_id == row.workspace_id,
                InterviewMessageRow.turn_id == row.turn_id,
            )
            .order_by(InterviewMessageRow.position)
        )
        try:
            turn = InterviewTurn.model_validate(
                {
                    "id": (row.workspace_id, row.turn_id),
                    "kind": row.kind,
                    "created_at": row.created_at,
                    "withdrawn_at": row.withdrawn_at,
                    "messages": tuple(load_message(message) for message in messages),
                }
            )
        except ValueError as error:
            raise InterviewDataError("訪談輪次無法依正式格式重建") from error
        self._loaded[turn.id] = (len(turn.messages), turn.withdrawn_at)
        return turn
