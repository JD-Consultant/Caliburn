"""訪談插件共用的短交易建立入口；實作由 Host 提供。"""

from collections.abc import Callable

from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.interview.application.persistence import (
    InterviewQueries,
    InterviewUnitOfWork,
)
from caliburn.modules.model_references import ModelReferences

INTERVIEW_UOW_FACTORY = ServiceKey[Callable[[], InterviewUnitOfWork]](
    "interview_uow_factory"
)
INTERVIEW_QUERIES = ServiceKey[InterviewQueries]("interview_queries")
MODEL_REFERENCES = ServiceKey[ModelReferences]("model_references")
