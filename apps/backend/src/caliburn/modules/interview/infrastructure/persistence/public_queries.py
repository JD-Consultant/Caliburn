"""訪談 owner 公開的同交易來源讀取；呼叫端管理交易。"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.elements import ColumnElement

from caliburn.modules.interview.application.errors import InterviewDataError
from caliburn.modules.interview.application.results import (
    TranscriptMessage,
    message_view,
    transcript_message,
)
from caliburn.modules.interview.domain.errors import InvalidAnswerError
from caliburn.modules.interview.domain.models.message_content import Question
from caliburn.modules.interview.infrastructure.persistence.message_mapping import (
    load_message,
)
from caliburn.modules.interview.infrastructure.persistence.orm_models import (
    InterviewMessageRow,
    InterviewTurnRow,
)

type SourcePosition = tuple[int, int]


@dataclass(frozen=True, slots=True)
class InterviewSource:
    position: SourcePosition
    message: TranscriptMessage


def interview_source_position(
    session: Session, *, workspace_id: UUID, message_id: UUID
) -> SourcePosition | None:
    """只回同 Workspace 保存座標，包含已撤回的歷史涵蓋上界。"""
    row = session.execute(
        select(InterviewTurnRow.sequence, InterviewMessageRow.position)
        .join(InterviewMessageRow, _turn_scope())
        .where(
            InterviewTurnRow.workspace_id == workspace_id,
            InterviewMessageRow.id == message_id,
        )
    ).one_or_none()
    if row is None:
        return None
    return row.sequence, row.position


def read_completed_interview_sources(
    session: Session,
    *,
    workspace_id: UUID,
    turn_ids: frozenset[UUID],
    through: SourcePosition,
) -> tuple[InterviewSource, ...]:
    """只讀呼叫端證明已完成的有效輪次，並持有 FOR SHARE 到交易結束。"""
    if not turn_ids:
        return ()
    sequence, position = through
    return _read_sources(
        session,
        workspace_id=workspace_id,
        lock_turns=True,
        criteria=(
            InterviewTurnRow.turn_id.in_(turn_ids),
            or_(
                InterviewTurnRow.sequence < sequence,
                and_(
                    InterviewTurnRow.sequence == sequence,
                    InterviewMessageRow.position <= position,
                ),
            ),
        ),
    )


def read_interview_sources(
    session: Session,
    *,
    workspace_id: UUID,
    message_ids: frozenset[UUID],
    lock_turns: bool,
) -> tuple[InterviewSource, ...]:
    """只讀指定且有效的來源；呼叫端比對所需 ID 是否全數存在。"""
    if not message_ids:
        return ()
    return _read_sources(
        session,
        workspace_id=workspace_id,
        lock_turns=lock_turns,
        criteria=(InterviewMessageRow.id.in_(message_ids),),
    )


def read_completed_interview_message_ids(
    session: Session,
    *,
    workspace_id: UUID,
    completed_turn_ids: frozenset[UUID],
    lock_turns: bool,
) -> tuple[UUID, ...]:
    """依正式順序回已完成有效 conversation 的全部訊息，含題答與略過。

    完成集合由呼叫端證明；借用 Session，不提交、不關閉。
    lock_turns=True 時以 FOR SHARE 阻止來源輪撤回，直到呼叫端交易結束。
    """
    if not completed_turn_ids:
        return ()
    statement = (
        select(InterviewMessageRow.id)
        .select_from(InterviewTurnRow)
        .join(InterviewMessageRow, _turn_scope())
        .where(
            InterviewTurnRow.workspace_id == workspace_id,
            InterviewTurnRow.turn_id.in_(completed_turn_ids),
            InterviewTurnRow.kind == "conversation",
            InterviewTurnRow.withdrawn_at.is_(None),
        )
        .order_by(InterviewTurnRow.sequence, InterviewMessageRow.position)
    )
    if lock_turns:
        statement = statement.with_for_update(read=True, of=InterviewTurnRow)
    return tuple(session.scalars(statement))


def _read_sources(
    session: Session,
    *,
    workspace_id: UUID,
    lock_turns: bool,
    criteria: tuple[ColumnElement[bool], ...],
) -> tuple[InterviewSource, ...]:
    original = aliased(InterviewMessageRow)
    statement = (
        select(InterviewTurnRow.sequence, InterviewMessageRow, original)
        .join(InterviewMessageRow, _turn_scope())
        .outerjoin(original, InterviewMessageRow.reply_to_message_id == original.id)
        .where(
            InterviewTurnRow.workspace_id == workspace_id,
            InterviewTurnRow.withdrawn_at.is_(None),
            *criteria,
        )
        .order_by(InterviewTurnRow.sequence, InterviewMessageRow.position)
    )
    if lock_turns:
        # 只鎖可撤回的輪次，不鎖 outer join 的可空原題。
        statement = statement.with_for_update(read=True, of=InterviewTurnRow)
    return tuple(
        InterviewSource(
            position=(sequence, row.position),
            message=_transcript(row, question),
        )
        for sequence, row, question in session.execute(statement)
    )


def _turn_scope() -> ColumnElement[bool]:
    return and_(
        InterviewMessageRow.workspace_id == InterviewTurnRow.workspace_id,
        InterviewMessageRow.turn_id == InterviewTurnRow.turn_id,
    )


def _transcript(
    row: InterviewMessageRow, question_row: InterviewMessageRow | None
) -> TranscriptMessage:
    question = load_message(question_row).content if question_row is not None else None
    if question is not None and not isinstance(question, Question):
        raise InterviewDataError("答案參照的訊息不是原題")
    try:
        return transcript_message(
            message_view(row.turn_id, load_message(row)), question
        )
    except InvalidAnswerError as error:
        raise InterviewDataError("答案不符合保存的原題") from error
