"""Host 提供目前 Plan 查詢與短交易 factory。"""

from collections.abc import Callable

from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.plan.application.persistence import PlanUnitOfWork
from caliburn.modules.plan.application.queries import PlanQueries

PLAN_QUERIES = ServiceKey[PlanQueries]("plan_queries")
PLAN_UOW_FACTORY = ServiceKey[Callable[[], PlanUnitOfWork]]("plan_uow_factory")
