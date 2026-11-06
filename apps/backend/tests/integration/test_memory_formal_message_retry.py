"""失敗後六則資格計入已完成的正式題答，尚可取消的內容不算。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.interview.application.recording import (
    record_answers,
    record_consultant_message,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.memory.application.errors import MemoryFailureBlockedError
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.modules.memory.infrastructure.persistence.unit_of_work import (
    SqlAlchemyMemoryUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.test_memory_persistence import CompletedTurns


def test_six_completed_messages_include_questions_answers_and_skips(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    interview = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    original_turn, analysis_id = uuid4(), uuid4()
    original = record_turn_input(
        workspace_id=jd_workspace_id,
        turn_id=original_turn,
        text="原始工作說明",
        uow_factory=interview,
    )
    record_consultant_message(
        workspace_id=jd_workspace_id,
        turn_id=original_turn,
        text="原輪完成",
        uow_factory=interview,
    )
    completed = CompletedTurns(frozenset({original_turn}))
    service = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, sessions), completed_turns=completed
    )
    service.start(
        MemoryWriteContext(jd_workspace_id, 0, analysis_id),
        through_message_id=original.message_id,
    )
    service.discard(
        MemoryWriteContext(jd_workspace_id, 1, analysis_id), reason="invalid_completion"
    )
    retry = MemoryWriteContext(jd_workspace_id, 2, uuid4())

    def dialogue(turn_id: UUID) -> tuple[UUID, ...]:
        source = record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            text="補充核對工作",
            uow_factory=interview,
        )
        questions = record_questions(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            questions=(
                Question(question="如何核對？"),
                Question(question="多久一次？"),
            ),
            uow_factory=interview,
        )
        answers = record_answers(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            answers=(
                AnswerInput(
                    question_message_id=questions[0].message_id, custom="逐筆比對"
                ),
                AnswerInput(question_message_id=questions[1].message_id),
            ),
            uow_factory=interview,
        )
        final = record_consultant_message(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            text="已保留回答與略過",
            uow_factory=interview,
        )
        return (
            source.message_id,
            *(q.message_id for q in questions),
            *(a.message_id for a in answers),
            final.message_id,
        )

    cancelled = uuid4()
    dialogue(cancelled)
    withdraw_turn(
        workspace_id=jd_workspace_id, turn_id=cancelled, uow_factory=interview
    )
    completed.ids |= {cancelled}
    with pytest.raises(MemoryFailureBlockedError):
        service.start(retry, through_message_id=original.message_id)

    pending = uuid4()
    new_ids = dialogue(pending)
    assert len(new_ids) == 6
    # 內容已保存（含末句），尚無 Agent 完成證據，仍不得重開。
    with pytest.raises(MemoryFailureBlockedError):
        service.start(retry, through_message_id=original.message_id)
    completed.ids |= {pending}
    assert service.start(retry, through_message_id=original.message_id).changed
    current = SqlAlchemyMemoryQueries(pg_engine).get_current(
        workspace_id=jd_workspace_id
    )
    assert current.analysis is not None
    assert current.analysis.source_window.message_ids == (original.message_id,)
