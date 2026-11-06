"""供執行取消呼叫的整輪訪談撤回；不判斷 Agent 取消資格。"""

from collections.abc import Callable
from uuid import UUID

from caliburn.modules.interview.application.persistence import InterviewUnitOfWork


def withdraw_turn(
    *,
    workspace_id: UUID,
    turn_id: UUID,
    uow_factory: Callable[[], InterviewUnitOfWork],
) -> None:
    """尚無訪談或已撤回皆無變更；固定開場拒絕撤回。"""
    with uow_factory() as uow:
        turn = uow.turns.get_for_update(workspace_id=workspace_id, turn_id=turn_id)
        if turn is not None and turn.withdraw():
            uow.turns.save(turn)
        uow.commit()
