"""The public source overview exposes the structured target that owns each human label."""

from dataclasses import asdict
from uuid import uuid4

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
            EvidenceEntry(uuid4(), "任務：同名", "interview", "訪談序號 2 · 員工", False, target)
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
