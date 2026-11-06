"""不啟動 Agent 的有效訪談公開查讀。"""

from uuid import UUID

from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.interview.application.results import (
    MessageView,
    TranscriptMessage,
)


def list_messages(
    *, workspace_id: UUID, turn_id: UUID | None = None, queries: InterviewQueries
) -> tuple[TranscriptMessage, ...]:
    """依原保存次序列出有效內容；缺少內容與查詢失敗不同。"""
    return queries.list_messages(workspace_id=workspace_id, turn_id=turn_id)


def get_message(
    *, workspace_id: UUID, message_id: UUID, queries: InterviewQueries
) -> MessageView:
    """讀取指定 Workspace 的有效訊息；不存在或撤回皆為 NotFound。"""
    return queries.get_message(workspace_id=workspace_id, message_id=message_id)
