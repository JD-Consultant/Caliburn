"""Host 注入同一公版查詢實例與有界推論 worker。"""

from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.model_references.contracts import ModelReferences
from caliburn.modules.occupation_reference.application.execution import SearchRunner
from caliburn.modules.occupation_reference.application.search import ReferenceSearch

REFERENCE_SEARCH = ServiceKey[ReferenceSearch]("occupation_reference_search")
REFERENCE_RUNNER = ServiceKey[SearchRunner]("occupation_reference_runner")
REFERENCE_IDS = ServiceKey[ModelReferences]("occupation_reference_ids")
