"""App 的明示組裝接縫；資源由 lifespan 建立及關閉，不修改全域工廠。"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from openai import AsyncOpenAI
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant.configuration import ConsultantConfiguration
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES


def _create_responses_client(settings: ModelSettings) -> AsyncOpenAI:
    return create_responses_client(
        api_key=settings.api_key, timeout_seconds=settings.request_timeout_seconds
    )


@asynccontextmanager
async def _open_checkpointer(settings: DatabaseSettings) -> AsyncIterator[AsyncPostgresSaver]:
    """使用正式 serializer 及原生 setup；初始化失敗也關閉已取得的連線。"""
    dsn = make_conninfo(
        settings.sqlalchemy_url.set(drivername="postgresql").render_as_string(hide_password=False),
        options=f"-c search_path={settings.schema}",
    )
    async with AsyncPostgresSaver.from_conn_string(
        dsn, serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
    ) as native:
        await native.setup()
        yield native


@dataclass(frozen=True, slots=True)
class AppComposition:
    """替換提示或外部 I/O；業務流程、保存權限與資源所有權仍由正式 App 負責。"""

    consultant_configuration: ConsultantConfiguration = ConsultantConfiguration()
    interview_plans_enabled: bool = True
    create_responses_client: Callable[[ModelSettings], AsyncOpenAI] = _create_responses_client
    open_checkpointer: Callable[
        [DatabaseSettings], AbstractAsyncContextManager[AsyncPostgresSaver]
    ] = _open_checkpointer
