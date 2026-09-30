"""An unavailable settlement is not a successful rollback."""

from uuid import uuid4

import pytest

from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.workflows.execution_failures import run_with_failure_boundary


async def test_settlement_failure_propagates_without_retrying_work():
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN), uuid4()
    )
    calls = []

    async def failed_work(current):
        calls.append(current)
        raise ValueError("invalid work")

    async def unavailable_owner(current, error):
        assert current == writer
        raise ConnectionError("database unavailable")

    with pytest.raises(ConnectionError, match="database unavailable"):
        await run_with_failure_boundary(writer, run=failed_work, settle_failure=unavailable_owner)
    assert calls == [writer]
