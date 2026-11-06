"""用例所需的短交易、輪次儲存與唯讀查詢契約。"""

from typing import Protocol
from uuid import UUID

from caliburn.modules.interview.application.results import (
    MessageView,
    TranscriptMessage,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.shared.application.base_unit_of_work import BaseUnitOfWork


class InterviewRepository(Protocol):
    def get_or_create_for_update(self, candidate: InterviewTurn) -> InterviewTurn:
        """原生衝突處理後鎖同一根；新建含首則原文，既有原文由根核對。"""
        ...

    def get_for_update(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> InterviewTurn | None:
        """只載入並鎖定指定範圍；不存在回 None。"""
        ...

    def save(self, turn: InterviewTurn) -> None:
        """只追加新訊息及更新撤回時間，不重寫已保存原文或隱式提交。"""
        ...


class InterviewUnitOfWork(BaseUnitOfWork, Protocol):
    @property
    def turns(self) -> InterviewRepository: ...


class InterviewQueries(Protocol):
    def list_messages(
        self,
        *,
        workspace_id: UUID,
        turn_id: UUID | None = None,
        after_message_id: UUID | None = None,
    ) -> tuple[TranscriptMessage, ...]:
        """依保存次序列出有效訪談，無資料回空 tuple。

        after_message_id 是同 Workspace 的嚴格下界，撤回後仍保留座標；
        不存在或跨 Workspace 拋 InterviewMessageNotFoundError。
        """
        ...

    def get_message(self, *, workspace_id: UUID, message_id: UUID) -> MessageView:
        """指定範圍的有效訊息；缺少或撤回拋 InterviewMessageNotFoundError。"""
        ...
