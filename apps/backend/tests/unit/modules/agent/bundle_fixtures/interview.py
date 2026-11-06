"""公開訪談查讀自行處理資料來源；呼叫者只傳 Workspace。"""

from collections.abc import Mapping
from uuid import UUID

from caliburn.modules.agent.plugins.contracts import AgentBundle


async def read_interview(*, workspace_id: UUID) -> str:
    return f"workspace={workspace_id.int}"


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle()
