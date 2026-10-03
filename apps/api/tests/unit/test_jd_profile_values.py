"""Pure profile values preserve fields outside an explicit, validated change."""

from dataclasses import asdict
from uuid import uuid4

import pytest

from caliburn.features.job_description.models import (
    ClearProfileField,
    InvalidProfileChangeError,
    JdProfile,
    ProfileField,
    ReviseJdProfile,
    SetProfileField,
    apply_profile_changes,
)


@pytest.mark.parametrize("field", list(ProfileField))
def test_set_and_clear_one_field_preserves_other_values(field: ProfileField) -> None:
    original = JdProfile("工程師", "產品團隊", "產品主管", "交付網站前端")
    changed = apply_profile_changes(original, (SetProfileField(field, "新內容"),))
    assert asdict(changed) == {**asdict(original), field.value: "新內容"}
    assert changed is not original
    cleared = apply_profile_changes(changed, (ClearProfileField(field),))
    assert asdict(cleared) == {**asdict(original), field.value: None}
    assert original == JdProfile("工程師", "產品團隊", "產品主管", "交付網站前端")


@pytest.mark.parametrize("value", ["", " \t\n", "\u3000", "text\x00"])
def test_direct_set_intent_rejects_empty_or_unstorable_text(value: str) -> None:
    with pytest.raises(InvalidProfileChangeError):
        SetProfileField(ProfileField.PURPOSE, value)


def test_command_rejects_duplicate_fields_without_depending_on_http_validation() -> None:
    with pytest.raises(InvalidProfileChangeError):
        ReviseJdProfile(
            uuid4(),
            uuid4(),
            (
                SetProfileField(ProfileField.JOB_TITLE, "工程師"),
                ClearProfileField(ProfileField.JOB_TITLE),
            ),
        )
    with pytest.raises(InvalidProfileChangeError):
        ReviseJdProfile(uuid4(), uuid4(), ())
