from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.interview_vnext.application.noop_result import OperationNoopResult
from app.interview_vnext.observability.artifacts import build_inline_artifact


NOW = datetime(2026, 7, 17, 8, 0, tzinfo=UTC)
STATE_HASH = "sha256:" + "1" * 64


def verification_ref():
    return build_inline_artifact(
        artifact_id=uuid4(),
        kind="operation.verification",
        media_type="application/json",
        payload={"accepted": [], "dropped": [{"reason": "off_topic"}]},
        run_id=uuid4(),
        session_id=uuid4(),
        operation_id=uuid4(),
        created_at=NOW,
        contains_test_data=True,
    ).ref


def test_noop_result_requires_zero_accepts_and_unchanged_state() -> None:
    result = OperationNoopResult(
        operation_id=uuid4(),
        completion_event_id=uuid4(),
        reason_code="no_domain_mutation",
        state_before_hash=STATE_HASH,
        state_after_hash=STATE_HASH,
        dropped_count=1,
        verification_artifact=verification_ref(),
    )
    assert result.accepted_count == 0
    assert result.schema_version == "operation_noop_result.v1"

    with pytest.raises(ValidationError, match="accepted_count"):
        OperationNoopResult.model_validate(
            {**result.model_dump(), "accepted_count": 1}
        )
    with pytest.raises(ValidationError, match="identical before/after"):
        OperationNoopResult.model_validate(
            {**result.model_dump(), "state_after_hash": "sha256:" + "2" * 64}
        )


def test_noop_result_rejects_invalid_reason_and_drop_count() -> None:
    base = {
        "operation_id": uuid4(),
        "completion_event_id": uuid4(),
        "reason_code": "no_domain_mutation",
        "state_before_hash": STATE_HASH,
        "state_after_hash": STATE_HASH,
        "dropped_count": 0,
        "verification_artifact": verification_ref(),
    }
    with pytest.raises(ValidationError, match="reason_code"):
        OperationNoopResult.model_validate({**base, "reason_code": "not valid"})
    with pytest.raises(ValidationError, match="dropped_count"):
        OperationNoopResult.model_validate({**base, "dropped_count": -1})
