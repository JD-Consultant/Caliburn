"""來源引用屬於 JD 根；內容移動不改引用、刪除清目前關係。"""

from uuid import uuid4

import pytest

from caliburn.modules.job_description.domain.errors import CitationTargetNotFoundError
from caliburn.modules.job_description.domain.models.citation import InterviewReference
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def test_rehydrate_citation_keeps_fixed_source_identity() -> None:
    workspace_id, jd_id, citation_id, message_id = (uuid4() for _ in range(4))
    root = JobDescription.model_validate(
        {
            "id": jd_id,
            "workspace_id": workspace_id,
            "citations": (
                {
                    "id": citation_id,
                    "target_kind": "job_description",
                    "target_id": jd_id,
                    "source": {
                        "kind": "interview",
                        "workspace_id": workspace_id,
                        "message_id": message_id,
                    },
                    "jd_changed": False,
                },
            ),
        }
    )
    assert root.citations[0].id == citation_id
    assert isinstance(root.citations[0].source, InterviewReference)
    assert root.citations[0].source.message_id == message_id


def test_citation_rejects_target_outside_aggregate() -> None:
    workspace_id, jd_id = uuid4(), uuid4()
    with pytest.raises(CitationTargetNotFoundError):
        JobDescription.model_validate(
            {
                "id": jd_id,
                "workspace_id": workspace_id,
                "citations": (
                    {
                        "id": uuid4(),
                        "target_kind": "task",
                        "target_id": uuid4(),
                        "source": {
                            "kind": "interview",
                            "workspace_id": workspace_id,
                            "message_id": uuid4(),
                        },
                        "jd_changed": False,
                    },
                ),
            }
        )
