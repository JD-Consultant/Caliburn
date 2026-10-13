"""Public DTOs project explicit internal values without publishing internal additions."""

from dataclasses import dataclass
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.features.job_description.models import JdProfile, JdProfileRevision
from caliburn.transport.http.jd_profile import read_profile
from caliburn.workflows.job_description.manual_editing import JdEditingWorkflow


@dataclass(frozen=True, slots=True)
class InternalProfile(JdProfile):
    private_note: str = "synthetic internal note"


@dataclass(frozen=True, slots=True)
class InternalRevision(JdProfileRevision):
    private_note: str = "synthetic revision note"


async def test_nested_internal_attributes_do_not_expand_the_public_profile() -> None:
    revision_id = uuid4()
    workflow = create_autospec(JdEditingWorkflow, instance=True)
    workflow.read_profile.return_value = InternalRevision(
        revision_id,
        InternalProfile(job_title="合成職務", purpose="保留原文\n第二行"),
    )

    result = await read_profile(uuid4(), workflow)

    assert result.model_dump(mode="json") == {
        "revision_id": str(revision_id),
        "profile": {
            "job_title": "合成職務",
            "organization_unit": None,
            "reports_to": None,
            "purpose": "保留原文\n第二行",
        },
    }


@dataclass(frozen=True, slots=True)
class InvalidProfile:
    job_title: int = 123
    organization_unit: None = None
    reports_to: None = None
    purpose: None = None


@dataclass(frozen=True, slots=True)
class InvalidRevision:
    revision_id: str
    profile: InvalidProfile


@pytest.mark.parametrize("revision_id", ["not-a-uuid", str(uuid4())])
async def test_declared_nested_fields_still_require_the_public_types(revision_id: str) -> None:
    workflow = create_autospec(JdEditingWorkflow, instance=True)
    workflow.read_profile.return_value = InvalidRevision(revision_id, InvalidProfile())

    with pytest.raises(ValidationError) as caught:
        await read_profile(uuid4(), workflow)

    assert ("profile", "job_title") in {error["loc"] for error in caught.value.errors()}
