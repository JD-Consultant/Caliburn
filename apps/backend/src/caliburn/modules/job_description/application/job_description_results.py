"""目前查詢及成功寫入共用的完整 JD 與單一版本。"""

from typing import Self

from pydantic import PositiveInt

from caliburn.modules.job_description.application.content import JobDescriptionContent
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


class JobDescriptionResult(JobDescriptionContent):
    version: PositiveInt

    @classmethod
    def from_job_description(
        cls, job_description: JobDescription, *, version: int
    ) -> Self:
        content = JobDescriptionContent.from_domain(job_description)
        return cls(**dict(content), version=version)
