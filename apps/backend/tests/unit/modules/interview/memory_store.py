"""Application 測試的記憶體 I/O 替身；不證明 PG 鎖或競爭保證。"""

from types import TracebackType
from typing import Self
from uuid import UUID

from caliburn.modules.interview.application.errors import (
    InterviewMessageNotFoundError,
    InterviewPersistenceError,
)
from caliburn.modules.interview.application.persistence import InterviewUnitOfWork
from caliburn.modules.interview.application.results import (
    MessageView,
    TranscriptMessage,
    message_view,
    transcript_message,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import Question


class MemoryInterviewStore:
    def __init__(self) -> None:
        self._turns: dict[tuple[UUID, UUID], InterviewTurn] = {}
        self.fail_commit = False

    def uow_factory(self) -> InterviewUnitOfWork:
        return MemoryInterviewUnitOfWork(self)

    def list_messages(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID | None = None,
        after_message_id: UUID | None = None,
    ) -> tuple[TranscriptMessage, ...]:
        ordered_turns = tuple(
            turn for turn in self._turns.values() if turn.workspace_id == workspace_id
        )
        after_position = None
        if after_message_id is not None:
            after_position = next(
                (
                    (sequence, position)
                    for sequence, turn in enumerate(ordered_turns)
                    for position, message in enumerate(turn.messages)
                    if message.id == after_message_id
                ),
                None,
            )
            if after_position is None:
                raise InterviewMessageNotFoundError("訪談下界不存在於此 Workspace")
        result = []
        for sequence, turn in enumerate(ordered_turns):
            if turn.withdrawn_at is not None or (
                turn_id is not None and turn.turn_id != turn_id
            ):
                continue
            questions = {
                message.id: message.content
                for message in turn.messages
                if isinstance(message.content, Question)
            }
            for position, message in enumerate(turn.messages):
                if (
                    after_position is not None
                    and (sequence, position) <= after_position
                ):
                    continue
                question = (
                    questions.get(message.reply_to_message_id)
                    if message.reply_to_message_id
                    else None
                )
                result.append(
                    transcript_message(message_view(turn.turn_id, message), question)
                )
        return tuple(result)

    def get_message(self, *, workspace_id: UUID, message_id: UUID) -> MessageView:
        for turn in self._turns.values():
            if turn.workspace_id == workspace_id and turn.withdrawn_at is None:
                for message in turn.messages:
                    if message.id == message_id:
                        return message_view(turn.turn_id, message)
        raise InterviewMessageNotFoundError


class MemoryInterviewUnitOfWork:
    def __init__(self, store: MemoryInterviewStore) -> None:
        self._store = store
        self._pending: dict[tuple[UUID, UUID], InterviewTurn] = {}

    @property
    def turns(self) -> Self:
        return self

    def __enter__(self) -> Self:
        self._pending = {
            identity: turn.model_copy() for identity, turn in self._store._turns.items()
        }
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._pending = {}

    def commit(self) -> None:
        if self._store.fail_commit:
            raise InterviewPersistenceError(commit_status="not_committed")
        self._store._turns = self._pending.copy()

    def get_or_create_for_update(self, candidate: InterviewTurn) -> InterviewTurn:
        if candidate.kind == "opening":
            for turn in self._pending.values():
                if (
                    turn.workspace_id == candidate.workspace_id
                    and turn.kind == "opening"
                ):
                    return turn
        return self._pending.setdefault(candidate.id, candidate)

    def get_for_update(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> InterviewTurn | None:
        return self._pending.get((workspace_id, turn_id))

    def save(self, turn: InterviewTurn) -> None:
        self._pending[turn.id] = turn
