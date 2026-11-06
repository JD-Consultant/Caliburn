"""HTTP 組裝所需的用例依賴型別。"""

from collections.abc import Callable

from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)

type JobDescriptionUoWFactory = Callable[[], JobDescriptionUnitOfWork]
