"""以一次短交易保存開場、原輸入及本輪訊息，提交後才回結果。"""

from collections.abc import Callable, Sequence
from uuid import UUID

from caliburn.modules.interview.application.errors import InterviewTurnNotFoundError
from caliburn.modules.interview.application.persistence import (
    InterviewRepository,
    InterviewUnitOfWork,
)
from caliburn.modules.interview.application.results import MessageView, message_view
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)


def record_opening(
    *, workspace_id: UUID, text: str, uow_factory: Callable[[], InterviewUnitOfWork]
) -> MessageView:
    with uow_factory() as uow:
        result = prepare_opening(workspace_id=workspace_id, text=text, turns=uow.turns)
        uow.commit()
    return result


def prepare_opening(
    *, workspace_id: UUID, text: str, turns: InterviewRepository
) -> MessageView:
    """共用開場規則與同文查回；回傳尚待呼叫端提交，不管理交易。"""
    candidate = InterviewTurn.create_opening(workspace_id=workspace_id, text=text)
    turn = turns.get_or_create_for_update(candidate)
    return message_view(turn.turn_id, turn.record_opening(text))


def record_turn_input(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    text: str,
    uow_factory: Callable[[], InterviewUnitOfWork],
) -> MessageView:
    candidate = InterviewTurn.create_conversation(
        workspace_id=workspace_id, turn_id=turn_id, text=text
    )
    with uow_factory() as uow:
        turn = uow.turns.get_or_create_for_update(candidate)
        result = message_view(turn.turn_id, turn.record_input(text))
        uow.commit()
    return result


def record_consultant_message(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    text: str,
    uow_factory: Callable[[], InterviewUnitOfWork],
) -> MessageView:
    with uow_factory() as uow:
        turn = _load_turn(uow, workspace_id=workspace_id, turn_id=turn_id)
        result = message_view(turn_id, turn.record_text("consultant", text))
        uow.turns.save(turn)
        uow.commit()
    return result


def record_questions(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    questions: Sequence[Question],
    uow_factory: Callable[[], InterviewUnitOfWork],
) -> tuple[MessageView, ...]:
    with uow_factory() as uow:
        turn = _load_turn(uow, workspace_id=workspace_id, turn_id=turn_id)
        result = tuple(
            message_view(turn_id, message)
            for message in turn.record_questions(questions)
        )
        uow.turns.save(turn)
        uow.commit()
    return result


def record_answers(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    answers: Sequence[AnswerInput],
    uow_factory: Callable[[], InterviewUnitOfWork],
) -> tuple[MessageView, ...]:
    with uow_factory() as uow:
        turn = _load_turn(uow, workspace_id=workspace_id, turn_id=turn_id)
        result = tuple(
            message_view(turn_id, message) for message in turn.record_answers(answers)
        )
        uow.turns.save(turn)
        uow.commit()
    return result


def _load_turn(
    uow: InterviewUnitOfWork, *, workspace_id: UUID, turn_id: UUID
) -> InterviewTurn:
    turn = uow.turns.get_for_update(workspace_id=workspace_id, turn_id=turn_id)
    if turn is None:
        raise InterviewTurnNotFoundError("指定訪談輪次不存在")
    return turn
