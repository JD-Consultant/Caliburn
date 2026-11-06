"""模型錯誤在開啟資料庫前明確拒絕，空批次沒有副作用。"""

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from caliburn.modules.model_references import InvalidModelReferenceError
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences


def no_database() -> Session:
    raise AssertionError("無效／空批次不應取得資料庫連線")


@pytest.mark.parametrize(
    "reference",
    [
        "",
        "task_0",
        "task_-1",
        "task_01",
        "task_+1",
        "task_１",
        "task_1.0",
        " task_1",
        "task_1\n",
        "Task_1",
        "plan_1",
        "area_1",
        "collaborator_1",
        "task_9223372036854775808",
        "task_" + "9" * 100,
        "18b7f695-aec2-4bc0-a21d-7ea193c4b1c4",
        "task_18b7f695aec24bc0a21d7ea193c4b1c4",
    ],
)
def test_invalid_model_reference_is_explicitly_rejected(reference: str) -> None:
    references = SqlAlchemyModelReferences(no_database)

    with pytest.raises(InvalidModelReferenceError) as error:
        references.resolve_refs(uuid4(), [reference])

    assert error.value.reference == reference


def test_empty_batches_do_not_access_storage() -> None:
    references = SqlAlchemyModelReferences(no_database)
    assert references.get_or_create_refs(uuid4(), []) == {}
    assert references.resolve_refs(uuid4(), []) == {}
