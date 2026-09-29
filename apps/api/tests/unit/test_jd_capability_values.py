"""Domain validation does not depend on HTTP, and rejected edits preserve inputs."""

from uuid import uuid4

import pytest

from caliburn.features.job_description.capabilities import (
    Capability,
    CapabilityField,
    CapabilityFieldChange,
    CapabilityInUseError,
    CapabilityKind,
    CreateCapability,
    DeleteCapability,
    InvalidCapabilityChangeError,
    ReviseCapability,
    TaskCapabilityLink,
)
from caliburn.features.job_description.capability_changes import apply_capability_change


@pytest.mark.parametrize("text", ["", "\n\t", "\u3000", "bad\x00"])
def test_blank_or_nul_definition_rejected_without_http(text: str) -> None:
    with pytest.raises(InvalidCapabilityChangeError):
        CreateCapability(CapabilityKind.KNOWLEDGE, text, None)


def test_invalid_revision_and_in_use_delete_do_not_mutate_original() -> None:
    capability = Capability(uuid4(), uuid4(), CapabilityKind.KNOWLEDGE, "資料介面", None)
    link = TaskCapabilityLink(uuid4(), capability.capability_id)
    with pytest.raises(InvalidCapabilityChangeError):
        apply_capability_change(
            (capability,),
            (link,),
            (link.task_id,),
            ReviseCapability(
                capability.capability_id,
                (CapabilityFieldChange(CapabilityField.NAME, None),),
            ),
        )
    with pytest.raises(CapabilityInUseError):
        apply_capability_change(
            (capability,), (link,), (link.task_id,), DeleteCapability(capability.capability_id)
        )
    with pytest.raises(InvalidCapabilityChangeError):
        ReviseCapability(
            capability.capability_id,
            (
                CapabilityFieldChange(CapabilityField.NAME, "甲"),
                CapabilityFieldChange(CapabilityField.NAME, "乙"),
            ),
        )
    assert capability.name == "資料介面"
