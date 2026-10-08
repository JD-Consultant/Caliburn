"""Public plan projection stays explicit and never exposes saved operation identities."""

from uuid import uuid4

import pytest

from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interview_plans.models import PlanPosition, PlanSnapshot
from caliburn.transport.http.consultant_turns import turn_view
from caliburn.workflows.consultant_status import ConsultantTurnStatus


def test_legacy_turn_has_explicit_unavailable_plan_preview() -> None:
    status = ConsultantTurnStatus(uuid4(), uuid4(), ExecutionStatus.ACTIVE, "合成原話")
    wire = turn_view(status).model_dump(mode="json")
    assert "plan_preview" in wire
    assert wire["plan_preview"] is None


@pytest.mark.parametrize("body", [None, "", "## 焦點\n逐字保留。\n"])
def test_preview_projects_only_the_saved_body_without_operation_metadata(body: str | None) -> None:
    file_id, execution_id = uuid4(), uuid4()
    preview = PlanSnapshot(PlanPosition(file_id, execution_id, uuid4()), body)
    status = ConsultantTurnStatus(
        file_id, execution_id, ExecutionStatus.ACTIVE, "合成原話", plan_preview=preview
    )
    assert turn_view(status).model_dump(mode="json")["plan_preview"] == {"plan": body}
