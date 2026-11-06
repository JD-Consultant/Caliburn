"""訪談查讀只使用 SQL 投影，不重建整份訪談聚合。"""

from uuid import UUID

from sqlalchemy import Engine, Select, and_, select
from sqlalchemy.orm import Session

from caliburn.modules.interview.application.errors import (
    InterviewDataError,
    InterviewMessageNotFoundError,
    InterviewQueryError,
    WorkspaceNotFoundError,
)
from caliburn.modules.interview.application.results import (
    MessageView,
    TranscriptMessage,
    message_view,
    transcript_message,
)
from caliburn.modules.interview.domain.models.message_content import Question
from caliburn.modules.interview.infrastructure.persistence.message_mapping import (
    load_message,
)
from caliburn.modules.interview.infrastructure.persistence.orm_models import (
    InterviewMessageRow,
    InterviewTurnRow,
)
from caliburn.modules.interview.infrastructure.persistence.public_queries import (
    interview_source_position,
)
from caliburn.modules.workspace.infrastructure.persistence.public_queries import (
    select_workspace_id,
)


class SqlAlchemyInterviewQueries:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list_messages(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID | None = None,
        after_message_id: UUID | None = None,
    ) -> tuple[TranscriptMessage, ...]:
        workspace = select_workspace_id(workspace_id=workspace_id).subquery()
        turn_scope = [
            InterviewTurnRow.workspace_id == workspace.c.id,
            InterviewTurnRow.withdrawn_at.is_(None),
        ]
        if turn_id is not None:
            turn_scope.append(InterviewTurnRow.turn_id == turn_id)
        statement = (
            select(workspace.c.id, InterviewTurnRow.sequence, InterviewMessageRow)
            .select_from(workspace)
            .outerjoin(InterviewTurnRow, and_(*turn_scope))
            .outerjoin(
                InterviewMessageRow,
                and_(
                    InterviewMessageRow.workspace_id == InterviewTurnRow.workspace_id,
                    InterviewMessageRow.turn_id == InterviewTurnRow.turn_id,
                ),
            )
            .order_by(InterviewTurnRow.sequence, InterviewMessageRow.position)
        )
        try:
            with Session(self._engine) as session:
                rows = session.execute(statement).all()
                if not rows:
                    raise WorkspaceNotFoundError("Workspace 不存在")
                after_position = None
                if after_message_id is not None:
                    after_position = interview_source_position(
                        session,
                        workspace_id=workspace_id,
                        message_id=after_message_id,
                    )
                    if after_position is None:
                        raise InterviewMessageNotFoundError(
                            "訪談下界不存在於此 Workspace"
                        )
                messages = tuple(
                    (
                        (sequence, row.position),
                        message_view(row.turn_id, load_message(row)),
                    )
                    for _, sequence, row in rows
                    if row is not None
                )
                questions = {
                    message.message_id: message.content
                    for _, message in messages
                    if isinstance(message.content, Question)
                }
                return tuple(
                    transcript_message(
                        message,
                        questions.get(message.reply_to_message_id)
                        if message.reply_to_message_id is not None
                        else None,
                    )
                    for position, message in messages
                    if after_position is None or position > after_position
                )
        except (
            WorkspaceNotFoundError,
            InterviewMessageNotFoundError,
            InterviewDataError,
        ):
            raise
        except Exception as error:
            raise InterviewQueryError("訪談查詢或資源釋放失敗") from error

    def get_message(self, *, workspace_id: UUID, message_id: UUID) -> MessageView:
        statement = self._messages(workspace_id=workspace_id).where(
            InterviewMessageRow.id == message_id
        )
        try:
            with Session(self._engine) as session:
                row = session.scalar(statement)
                if row is None:
                    raise InterviewMessageNotFoundError("指定有效訪談訊息不存在")
                return message_view(row.turn_id, load_message(row))
        except InterviewMessageNotFoundError, InterviewDataError:
            raise
        except Exception as error:
            raise InterviewQueryError("訪談查詢或資源釋放失敗") from error

    @staticmethod
    def _messages(*, workspace_id: UUID) -> Select[InterviewMessageRow]:
        return (
            select(InterviewMessageRow)
            .join(
                InterviewTurnRow,
                and_(
                    InterviewMessageRow.workspace_id == InterviewTurnRow.workspace_id,
                    InterviewMessageRow.turn_id == InterviewTurnRow.turn_id,
                ),
            )
            .where(
                InterviewTurnRow.workspace_id == workspace_id,
                InterviewTurnRow.withdrawn_at.is_(None),
            )
        )
