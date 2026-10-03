"""The public source overview exposes the structured target that owns each human label."""

from dataclasses import asdict
from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.contracts.generated.jd_source_changes_view import JdSourceChangesView
from caliburn.contracts.generated.jd_sources_view import JdSourcesView
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import JdSourceTarget, SourceTargetKind
from caliburn.workflows.jd_evidence import EvidenceEntry, EvidenceOverview


def test_every_target_shape_reaches_the_http_view_by_identity_not_label() -> None:
    task_id, item_id = uuid4(), uuid4()
    targets = (
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        JdSourceTarget(SourceTargetKind.AREA, item_id),
        JdSourceTarget(SourceTargetKind.TASK, task_id),
        JdSourceTarget(SourceTargetKind.DETAIL, item_id, task_id=task_id),
        JdSourceTarget(SourceTargetKind.CAPABILITY, item_id),
        JdSourceTarget(SourceTargetKind.COLLABORATOR, item_id),
        JdSourceTarget(SourceTargetKind.CONDITION, item_id),
        JdSourceTarget(SourceTargetKind.TASK_CAPABILITY, item_id, task_id=task_id),
    )
    # Two entries share one human label on purpose: only the target tells them apart.
    overview = EvidenceOverview(
        uuid4(),
        tuple(
            EvidenceEntry(
                uuid4(), "任務：同名", "interview", "訪談序號 2 · 員工", False, target, False, False
            )
            for target in targets
        ),
    )

    body = JdSourcesView.model_validate(asdict(overview)).model_dump(mode="json")

    assert [reference["target"]["kind"] for reference in body["references"]] == [
        target.kind.value for target in targets
    ]
    assert body["references"][0]["target"] == {
        "kind": "profile_field",
        "field": "purpose",
        "item_id": None,
        "task_id": None,
    }
    assert body["references"][3]["target"] == {
        "kind": "detail",
        "field": None,
        "item_id": str(item_id),
        "task_id": str(task_id),
    }


def test_changes_exposes_two_sides_and_requires_explicit_null_for_interviews() -> None:
    payload = {
        "revision_id": str(uuid4()),
        "citation_id": str(uuid4()),
        "jd_markdown": "JD 差異",
        "source_markdown": None,
    }
    assert JdSourceChangesView.model_validate(payload).model_dump(mode="json") == payload
    with pytest.raises(ValidationError):
        JdSourceChangesView.model_validate(
            {k: v for k, v in payload.items() if k != "source_markdown"}
        )


def test_overview_requires_separate_change_flags() -> None:
    reference = {
        "citation_id": str(uuid4()),
        "target_label": "職務名稱",
        "source_kind": "interview",
        "source_label": "訪談序號 2 · 員工",
        "needs_recheck": True,
        "jd_changed": True,
        "source_changed": False,
    }
    payload = {"revision_id": str(uuid4()), "references": [reference]}
    assert JdSourcesView.model_validate(payload).references[0].jd_changed is True
    for missing in ("jd_changed", "source_changed"):
        with pytest.raises(ValidationError):
            JdSourcesView.model_validate(
                {**payload, "references": [{k: v for k, v in reference.items() if k != missing}]}
            )
