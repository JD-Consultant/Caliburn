"""透過 Interview owner 的公開來源讀取，同交易驗證固定窗口。"""

from uuid import UUID

from sqlalchemy.orm import Session

from caliburn.modules.interview.application.errors import InterviewDataError
from caliburn.modules.interview.infrastructure.persistence.public_queries import (
    InterviewSource,
    interview_source_position,
    read_completed_interview_message_ids,
    read_completed_interview_sources,
    read_interview_sources,
)
from caliburn.modules.memory.application.errors import MemoryDataError
from caliburn.modules.memory.application.results import MemoryInterviewMessage
from caliburn.modules.memory.domain.analysis import MemorySourceWindow
from caliburn.modules.memory.domain.errors import InvalidMemorySourceError


class SqlAlchemyInterviewSourceReader:
    def __init__(self, session: Session) -> None:
        self._session = session

    def formal_message_ids(
        self,
        *,
        workspace_id: UUID,
        completed_turn_ids: frozenset[UUID],
    ) -> tuple[UUID, ...]:
        try:
            return read_completed_interview_message_ids(
                self._session,
                workspace_id=workspace_id,
                completed_turn_ids=completed_turn_ids,
                lock_turns=True,
            )
        except InterviewDataError as error:
            raise MemoryDataError("正式訪談訊息的保存資料不完整") from error

    def bind_window(
        self,
        *,
        workspace_id: UUID,
        through_message_id: UUID,
        covered_through_message_id: UUID | None,
        completed_turn_ids: frozenset[UUID],
    ) -> MemorySourceWindow | None:
        through = interview_source_position(
            self._session, workspace_id=workspace_id, message_id=through_message_id
        )
        if through is None:
            raise InvalidMemorySourceError("找不到本 Workspace 的訪談上界")
        try:
            sources = read_completed_interview_sources(
                self._session,
                workspace_id=workspace_id,
                turn_ids=completed_turn_ids,
                through=through,
            )
        except InterviewDataError as error:
            raise MemoryDataError("訪談來源損壞") from error
        if not sources or sources[-1].message.message_id != through_message_id:
            raise InvalidMemorySourceError("訪談上界須屬於已完成且有效的輪次")
        covered = None
        if covered_through_message_id is not None:
            covered = interview_source_position(
                self._session,
                workspace_id=workspace_id,
                message_id=covered_through_message_id,
            )
            if covered is None:
                raise MemoryDataError("發布版訪談涵蓋上界損壞")
            if through <= covered:
                return None
        return MemorySourceWindow(
            workspace_id=workspace_id,
            through_message_id=through_message_id,
            message_ids=tuple(source.message.message_id for source in sources),
            required_message_ids=tuple(
                source.message.message_id
                for source in sources
                if covered is None or source.position > covered
            ),
        )

    def require_sources(
        self, *, window: MemorySourceWindow, message_ids: frozenset[UUID]
    ) -> None:
        self._read_window(window=window, message_ids=message_ids, lock_turns=True)

    def list_window(
        self, window: MemorySourceWindow
    ) -> tuple[MemoryInterviewMessage, ...]:
        sources = self._read_window(
            window=window,
            message_ids=frozenset(window.message_ids),
            lock_turns=False,
        )
        return tuple(
            MemoryInterviewMessage(
                message_id=source.message.message_id,
                turn_id=source.message.turn_id,
                speaker=source.message.speaker,
                kind=source.message.kind,
                text=source.message.text,
                reply_to_message_id=source.message.reply_to_message_id,
            )
            for source in sources
        )

    def _read_window(
        self,
        *,
        window: MemorySourceWindow,
        message_ids: frozenset[UUID],
        lock_turns: bool,
    ) -> tuple[InterviewSource, ...]:
        if not message_ids:
            return ()
        checked_ids = message_ids | {window.through_message_id}
        expected = tuple(mid for mid in window.message_ids if mid in checked_ids)
        if len(expected) != len(checked_ids):
            raise InvalidMemorySourceError("來源不在固定訪談窗口")
        try:
            sources = read_interview_sources(
                self._session,
                workspace_id=window.workspace_id,
                message_ids=checked_ids,
                lock_turns=lock_turns,
            )
        except InterviewDataError as error:
            raise MemoryDataError("訪談來源損壞") from error
        if (
            tuple(source.message.message_id for source in sources) != expected
            or sources[-1].message.message_id != window.through_message_id
        ):
            raise InvalidMemorySourceError("固定窗口來源遺失、已撤回或次序不符")
        return sources
