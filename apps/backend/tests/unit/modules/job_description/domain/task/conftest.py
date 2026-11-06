"""Task 案例的完整 JD；每個測試取得獨立物件圖。"""

from uuid import UUID

import pytest

from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)


@pytest.fixture
def jd() -> JobDescription:
    return JobDescription(
        id=UUID(int=100),
        workspace_id=UUID(int=200),
        job_title="分析師",
        duties=(
            Duty.create(id=UUID(int=2), job_description_id=UUID(int=100), name="分析"),
        ),
        knowledge=tuple(
            Knowledge.create(
                id=UUID(int=i), job_description_id=UUID(int=100), name=f"知識{i}"
            )
            for i in (20, 21, 22)
        ),
        skills=tuple(
            Skill.create(
                id=UUID(int=i), job_description_id=UUID(int=100), name=f"技能{i}"
            )
            for i in (30, 31, 32)
        ),
        tasks=(
            JobTask.create(
                id=UUID(int=1),
                job_description_id=UUID(int=100),
                name="整理查詢需求",
                outcomes=(TaskOutcome(id=UUID(int=10), text="查詢清單"),),
                requirements=(TaskRequirement(id=UUID(int=11), text="確認資料權限"),),
                knowledge_ids=(UUID(int=20),),
                skill_ids=(UUID(int=30),),
            ),
        ),
    )
