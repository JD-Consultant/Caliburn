"""複合命令沿用原 JD 欄位驗證，不因合併保存邊界放寬規則。"""

from uuid import uuid4

import pytest

from caliburn.features.job_description.compound_edits import ReviseProfileWithSources
from caliburn.features.job_description.models import (
    InvalidProfileChangeError,
    ProfileField,
    SetProfileField,
)


def test_compound_profile_rejects_changing_the_same_field_twice() -> None:
    with pytest.raises(InvalidProfileChangeError, match="each field once"):
        ReviseProfileWithSources(
            uuid4(),
            uuid4(),
            (
                SetProfileField(ProfileField.JOB_TITLE, "第一個意圖"),
                SetProfileField(ProfileField.JOB_TITLE, "重複意圖"),
            ),
            (),
        )
