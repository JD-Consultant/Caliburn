"""具名內部條目由 JD 根編修；名稱與選填補充的拒絕不變。"""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import (
    DuplicateNameError,
    InvalidNameError,
)
from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.entry_name import EntryName
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill

JD_ID = UUID(int=1)
ENTRY_ID = UUID(int=10)
type NamedEntity = Duty | Knowledge | Skill | JobTask
type Edit = Callable[[JobDescription, str, str | None], bool]

CASES: list[tuple[type[NamedEntity], str, Edit]] = [
    (
        Duty,
        "duties",
        lambda jd, name, text: jd.update_duty(duty_id=ENTRY_ID, name=name, scope=text),
    ),
    (
        Knowledge,
        "knowledge",
        lambda jd, name, text: jd.update_knowledge(
            knowledge_id=ENTRY_ID, name=name, description=text
        ),
    ),
    (
        Skill,
        "skills",
        lambda jd, name, text: jd.update_skill(
            skill_id=ENTRY_ID, name=name, description=text
        ),
    ),
    (
        JobTask,
        "tasks",
        lambda jd, name, text: jd.update_task(
            task_id=ENTRY_ID, name=name, description=text, competency_level=None
        ),
    ),
]


@pytest.mark.parametrize(("entity_type", "collection", "edit"), CASES)
def test_raw_name_factory_and_display_rename_obey_the_aggregate_boundary(
    entity_type: type[NamedEntity], collection: str, edit: Edit
) -> None:
    """模型自行建 VO；大小寫編修是變更，外部不能改欄位。"""
    entry = entity_type.create(id=ENTRY_ID, job_description_id=JD_ID, name=" SQL ")
    jd = JobDescription.model_validate(
        {"id": JD_ID, "workspace_id": UUID(int=2), collection: (entry,)}
    )
    saved_entry = getattr(jd, collection)[0]
    assert saved_entry.name.value == "SQL"
    assert saved_entry.name == EntryName(value="SQL")
    with pytest.raises(ValidationError):
        saved_entry.name = EntryName(value="繞過聚合根")
    assert saved_entry.name.value == "SQL"
    assert edit(jd, " \tSQL\n", None) is False
    assert edit(jd, "sql", None) is True
    assert saved_entry.name.value == "sql"


@pytest.mark.parametrize(("entity_type", "collection", "edit"), CASES)
def test_name_limits_use_trimmed_codepoints_on_construction_and_edit(
    entity_type: type[NamedEntity],
    collection: str,
    edit: Edit,
) -> None:
    """建立與改名都先清洗，再檢查255字元上限。"""
    name = " 😀" + "界" * 254 + " "
    entry = entity_type.create(id=ENTRY_ID, job_description_id=JD_ID, name=name)
    jd = JobDescription.model_validate(
        {"id": JD_ID, "workspace_id": UUID(int=2), collection: (entry,)}
    )
    before = jd.model_dump()
    with pytest.raises(InvalidNameError):
        entity_type.create(id=ENTRY_ID, job_description_id=JD_ID, name=name + "界")
    with pytest.raises(InvalidNameError):
        edit(jd, name + "界", None)
    assert jd.model_dump() == before
    assert edit(jd, name, None) is False


@pytest.mark.parametrize(("entity_type", "collection", "edit"), CASES)
@pytest.mark.parametrize("name", ["", "\t\n\u3000"])
def test_blank_name_rejection_preserves_the_whole_jd(
    entity_type: type[NamedEntity],
    collection: str,
    edit: Edit,
    name: str,
) -> None:
    with pytest.raises(InvalidNameError):
        entity_type.create(id=ENTRY_ID, job_description_id=JD_ID, name=name)
    jd = JobDescription.model_validate(
        {
            "id": JD_ID,
            "workspace_id": UUID(int=2),
            "job_title": "既有職稱",
            collection: (
                entity_type.create(
                    id=ENTRY_ID, job_description_id=JD_ID, name="既有名稱"
                ),
            ),
        }
    )
    before = jd.model_dump()
    with pytest.raises(InvalidNameError):
        edit(jd, name, "新補充")
    assert jd.model_dump() == before


@pytest.mark.parametrize(("entity_type", "collection", "edit"), CASES)
def test_edit_is_atomic_preserves_identity_and_can_clear_optional_text(
    entity_type: type[NamedEntity],
    collection: str,
    edit: Edit,
) -> None:
    jd = JobDescription.model_validate(
        {
            "id": JD_ID,
            "workspace_id": UUID(int=2),
            collection: (
                entity_type.create(
                    id=ENTRY_ID, job_description_id=JD_ID, name="原名稱"
                ),
            ),
        }
    )
    entry: NamedEntity = getattr(jd, collection)[0]
    original_hash = hash(entry)
    assert edit(jd, "原名稱", " 原補充\n ") is True
    before = jd.model_dump()
    with pytest.raises(ValidationError):
        edit(jd, cast(str, 123), "新補充")
    assert jd.model_dump() == before
    with pytest.raises(ValidationError):
        edit(jd, "新名稱", cast(str, 123))
    assert jd.model_dump() == before
    assert edit(jd, "原名稱", " 原補充\n ") is False
    assert edit(jd, " 新名稱 ", None) is True
    assert getattr(jd, collection)[0] is entry
    assert entry.name.value == "新名稱"
    assert entry.id == ENTRY_ID and entry.job_description_id == JD_ID
    assert hash(entry) == original_hash
    text_field = "scope" if isinstance(entry, Duty) else "description"
    assert getattr(entry, text_field) is None


@pytest.mark.parametrize(("entity_type", "collection", "edit"), CASES)
def test_same_kind_duplicate_name_is_rejected_on_construction_and_edit(
    entity_type: type[NamedEntity],
    collection: str,
    edit: Edit,
) -> None:
    entries = (
        entity_type.create(id=ENTRY_ID, job_description_id=JD_ID, name="原名稱"),
        entity_type.create(id=UUID(int=11), job_description_id=JD_ID, name="Analysis"),
    )
    jd = JobDescription.model_validate(
        {"id": JD_ID, "workspace_id": UUID(int=2), collection: entries}
    )
    before = jd.model_dump()
    with pytest.raises(DuplicateNameError):
        edit(jd, " Analysis ", "新補充")
    assert jd.model_dump() == before
    with pytest.raises(DuplicateNameError):
        JobDescription.model_validate(
            {
                "id": JD_ID,
                "workspace_id": UUID(int=2),
                collection: (
                    entries[1],
                    entity_type.create(
                        id=ENTRY_ID, job_description_id=JD_ID, name=" Analysis "
                    ),
                ),
            }
        )

    assert edit(jd, "analysis", None) is True
    assert [entry.name.value for entry in getattr(jd, collection)] == [
        "analysis",
        "Analysis",
    ]


@pytest.mark.parametrize(("entity_type", "collection", "edit"), CASES)
def test_reading_internal_entity_does_not_allow_field_assignment_or_deletion(
    entity_type: type[NamedEntity],
    collection: str,
    edit: Edit,
) -> None:
    jd = JobDescription.model_validate(
        {
            "id": JD_ID,
            "workspace_id": UUID(int=2),
            collection: (
                entity_type.create(id=ENTRY_ID, job_description_id=JD_ID, name="分析"),
            ),
        }
    )
    entry: NamedEntity = getattr(jd, collection)[0]
    before = jd.model_dump()
    for field, value in entry.model_dump().items():
        with pytest.raises(ValidationError):
            setattr(entry, field, value)
        with pytest.raises(ValidationError):
            delattr(entry, field)
    assert jd.model_dump() == before
