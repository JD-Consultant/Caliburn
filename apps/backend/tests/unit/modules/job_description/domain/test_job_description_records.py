"""JD 內部記載的身分、受控編修、分類及拒絕不變。"""

from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import (
    CollaborationNotFoundError,
    DuplicateIdentityError,
    InvalidCollaborationNameError,
    InvalidJobDescriptionRecordOrderError,
    InvalidTextError,
    JobConditionNotFoundError,
)
from caliburn.modules.job_description.domain.models import job_description as root_model
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def test_root_accepts_complete_owned_records_and_preserves_original_text() -> None:
    root = JobDescription.model_validate(
        {
            "id": UUID(int=1),
            "workspace_id": UUID(int=2),
            "collaborations": (
                {"id": UUID(int=3), "collaborator_name": " 顧問 " * 100, "scope": None},
                {"id": UUID(int=4), "collaborator_name": " 顧問 " * 100, "scope": ""},
            ),
            "conditions": (
                {
                    "id": UUID(int=5),
                    "kind": ConditionKind.QUALIFICATION,
                    "text": " 相同 ",
                },
                {
                    "id": UUID(int=6),
                    "kind": ConditionKind.QUALIFICATION,
                    "text": " 相同 ",
                },
            ),
        }
    )
    assert root.collaborations[0].collaborator_name == " 顧問 " * 100
    assert tuple(item.text for item in root.conditions) == (" 相同 ", " 相同 ")
    with pytest.raises(ValidationError):
        root.collaborations[0].__setattr__("scope", "禁止直接修改")


def _root() -> JobDescription:
    return JobDescription(
        id=UUID(int=1),
        workspace_id=UUID(int=2),
        collaborations=tuple(
            CollaborationEntry(
                id=UUID(int=number), collaborator_name="顧問", scope="原範圍"
            )
            for number in (3, 4, 5)
        ),
        conditions=tuple(
            JobCondition(id=UUID(int=number), kind=kind, text="原文")
            for number, kind in (
                (6, ConditionKind.WORK_ENVIRONMENT),
                (7, ConditionKind.WORK_ENVIRONMENT),
                (8, ConditionKind.QUALIFICATION),
                (9, ConditionKind.QUALIFICATION),
            )
        ),
    )


@pytest.mark.parametrize("invalid", [42, True, [], object()])
def test_late_invalid_collaboration_field_leaves_existing_entity_unchanged(
    invalid: Any,
) -> None:
    root = _root()
    before = root.model_dump()
    existing = root.collaborations[0]
    with pytest.raises(ValidationError):
        root.update_collaboration(
            collaboration_id=existing.id, collaborator_name="新名稱", scope=invalid
        )
    assert root.model_dump() == before
    assert root.collaborations[0] is existing


def test_controlled_update_preserves_entity_identity_and_recognizes_noop() -> None:
    root = _root()
    existing = root.collaborations[0]
    assert root.update_collaboration(
        collaboration_id=existing.id, collaborator_name="新對象", scope=None
    )
    assert root.collaborations[0] is existing
    assert existing.collaborator_name == "新對象" and existing.scope is None
    assert not root.update_collaboration(
        collaboration_id=existing.id, collaborator_name="新對象", scope=None
    )
    with pytest.raises(InvalidCollaborationNameError):
        root.update_collaboration(
            collaboration_id=existing.id, collaborator_name=" \n", scope=None
        )


def test_append_rejects_duplicate_record_identity_without_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _root()
    before = root.model_dump()
    monkeypatch.setattr(root_model, "uuid7", lambda: UUID(int=3))
    with pytest.raises(DuplicateIdentityError):
        root.add_collaboration(collaborator_name="另一份", scope=None)
    assert root.model_dump() == before
    monkeypatch.setattr(root_model, "uuid7", lambda: UUID(int=6))
    with pytest.raises(DuplicateIdentityError):
        root.add_condition(kind=ConditionKind.QUALIFICATION, text="另一條件")
    assert root.model_dump() == before
    for collection in ("collaborations", "conditions"):
        payload = root.model_dump()
        payload[collection] = (*payload[collection], payload[collection][0])
        with pytest.raises(DuplicateIdentityError):
            JobDescription.model_validate(payload)


def test_reclassification_retains_id_text_and_appends_only_to_new_kind() -> None:
    root = _root()
    item = root.conditions[0]
    assert root.reclassify_condition(
        condition_id=item.id, kind=ConditionKind.QUALIFICATION
    )
    assert tuple(x.id.int for x in root.conditions) == (7, 8, 9, 6)
    assert root.conditions[-1] is item and item.text == "原文"
    assert not root.reclassify_condition(
        condition_id=UUID(int=8), kind=ConditionKind.QUALIFICATION
    )
    assert tuple(x.id.int for x in root.conditions) == (7, 8, 9, 6)
    before = root.model_dump()
    invalid: Any = "not_a_kind"
    with pytest.raises(ValidationError):
        root.reclassify_condition(condition_id=item.id, kind=invalid)
    with pytest.raises(InvalidTextError):
        root.update_condition(condition_id=item.id, text=" \n")
    assert root.model_dump() == before


def test_ordering_retains_entities_and_rejects_invalid_anchors() -> None:
    root = _root()
    identities = {x.id: x for x in root.collaborations}
    assert root.move_collaboration(collaboration_id=UUID(int=5), before_id=UUID(int=3))
    assert tuple(x.id.int for x in root.collaborations) == (5, 3, 4)
    assert all(identities[x.id] is x for x in root.collaborations)
    assert not root.move_collaboration(collaboration_id=UUID(int=4), before_id=None)
    assert root.move_condition(condition_id=UUID(int=7), before_id=UUID(int=6))
    assert tuple(x.id.int for x in root.conditions) == (7, 6, 8, 9)
    before = root.model_dump()
    for anchor in (UUID(int=7), UUID(int=8), UUID(int=99)):
        with pytest.raises(InvalidJobDescriptionRecordOrderError):
            root.move_condition(condition_id=UUID(int=7), before_id=anchor)
        assert root.model_dump() == before
    with pytest.raises(InvalidJobDescriptionRecordOrderError):
        root.move_collaboration(collaboration_id=UUID(int=3), before_id=UUID(int=3))
    assert root.model_dump() == before


def test_deletion_only_removes_target_and_missing_target_rejects() -> None:
    root = _root()
    root.remove_collaboration(collaboration_id=UUID(int=4))
    root.remove_condition(condition_id=UUID(int=8))
    assert tuple(x.id.int for x in root.collaborations) == (3, 5)
    assert tuple(x.id.int for x in root.conditions) == (6, 7, 9)
    before = root.model_dump()
    with pytest.raises(CollaborationNotFoundError):
        root.remove_collaboration(collaboration_id=UUID(int=4))
    with pytest.raises(JobConditionNotFoundError):
        root.remove_condition(condition_id=UUID(int=8))
    assert root.model_dump() == before
