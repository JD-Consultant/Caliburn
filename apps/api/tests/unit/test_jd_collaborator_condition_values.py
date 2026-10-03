"""Domain validation applies without HTTP; changes preserve immutable input values."""

from uuid import uuid4

import pytest

from caliburn.features.job_description.collaborators import (
    CreateCollaborator,
    InvalidCollaboratorChangeError,
)
from caliburn.features.job_description.condition_changes import apply_condition_change
from caliburn.features.job_description.conditions import (
    ConditionKind,
    ConditionKindChange,
    ConditionTextChange,
    CreateCondition,
    InvalidConditionChangeError,
    JobCondition,
    ReviseCondition,
)


@pytest.mark.parametrize("text", ["", "\t\n", "\u3000", "bad\x00"])
def test_conditions_reject_blank_or_nul_without_http(text: str) -> None:
    with pytest.raises(InvalidConditionChangeError):
        CreateCondition(ConditionKind.WORK_ENVIRONMENT, text)


@pytest.mark.parametrize("text", ["", "\t\n", "\u3000", "bad\x00"])
def test_collaborators_reject_blank_or_nul_without_http(text: str) -> None:
    with pytest.raises(InvalidCollaboratorChangeError):
        CreateCollaborator(text, None)
    with pytest.raises(InvalidCollaboratorChangeError):
        CreateCollaborator(None, text)


def test_same_kind_is_noop_and_reclassification_is_new_content_not_new_identity() -> None:
    condition = JobCondition(uuid4(), uuid4(), ConditionKind.WORK_ENVIRONMENT, "現場作業")
    original = (condition,)
    unchanged = apply_condition_change(
        original,
        ReviseCondition(
            condition.condition_id,
            (
                ConditionKindChange(condition.kind),
                ConditionTextChange(condition.text),
            ),
        ),
    )
    assert unchanged == (original, None)
    revised, content = apply_condition_change(
        original,
        ReviseCondition(
            condition.condition_id, (ConditionKindChange(ConditionKind.SCHEDULE_TRAVEL),)
        ),
    )
    assert content is not None
    assert content.condition_id == condition.condition_id
    assert content.content_revision_id != condition.content_revision_id
    assert revised == (content,)
    assert original[0].kind == ConditionKind.WORK_ENVIRONMENT


def test_duplicate_kind_changes_are_rejected_before_application() -> None:
    with pytest.raises(InvalidConditionChangeError):
        ReviseCondition(
            uuid4(),
            (
                ConditionKindChange(ConditionKind.SHARED_AUTHORITY),
                ConditionKindChange(ConditionKind.QUALIFICATION),
            ),
        )
