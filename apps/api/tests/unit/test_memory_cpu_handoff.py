"""The B2 parent releases database reads before doing large fixed-value comparison."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.features.work_memory.stage_changes import SituationChange, SituationRevision
from caliburn.workflows import memory_batch


@pytest.mark.asyncio
async def test_b2_comparison_releases_read_session_and_loop(monkeypatch):
    active_sessions = 0
    ticks = 0

    @asynccontextmanager
    async def sessions():
        nonlocal active_sessions
        active_sessions += 1
        try:
            yield object()
        finally:
            active_sessions -= 1

    stage = MemoryBatchPosition(
        *(uuid4() for _ in range(4)), MemoryLayer.WORK_UNDERSTANDING, uuid4()
    )
    writer = SimpleNamespace(
        scope=SimpleNamespace(job_file_id=stage.job_file_id, execution_id=stage.execution_id)
    )
    work = SimpleNamespace(writer=writer, position=stage)
    body = "".join(f"item {i % 200:03}\n" for i in range(40000))
    fixed = (
        SituationChange(
            SituationRevision(MemoryContent("title", "description", body), (2,)),
            SituationRevision(
                MemoryContent("title", "description", "unique first line\n" + body), (2, 4)
            ),
            ("understanding",),
        ),
    )

    async def read_snapshot(session, requested):
        assert active_sessions == 1 and requested == stage
        return fixed

    async def heartbeat():
        nonlocal ticks
        while True:
            ticks += 1
            await asyncio.sleep(0.01)

    class RoleReachedError(Exception):
        pass

    async def role(*args, situation_changes, **kwargs):
        assert active_sessions == 0
        assert ticks > 2, "Large diff blocked the event loop"
        assert "+unique first line" in situation_changes[0]["diff"]
        assert "訪談引用序號：2, 4" in situation_changes[0]["diff"]
        raise RoleReachedError

    monkeypatch.setattr(
        memory_batch.executions,
        "read_execution",
        AsyncMock(return_value=SimpleNamespace(status=ExecutionStatus.ACTIVE)),
    )
    monkeypatch.setattr(
        memory_batch.consolidation_requests, "read_batch_result", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        memory_batch.consolidation_requests, "list_stage_results", AsyncMock(return_value=[])
    )
    monkeypatch.setattr(memory_batch, "read_situation_handoff_snapshot", read_snapshot)
    original = memory_batch.build_situation_handoff_changes

    def compute(snapshot):
        assert active_sessions == 0, "Database session leaked into CPU work"
        return original(snapshot)

    monkeypatch.setattr(memory_batch, "build_situation_handoff_changes", compute)
    cpu = MemoryCpu()
    parent = memory_batch.MemoryBatchWorkflow(sessions, run_role=role, cpu=cpu)
    monkeypatch.setattr(parent.requests, "read_work", AsyncMock(return_value=work))
    pulse = asyncio.create_task(heartbeat())
    try:
        with pytest.raises(RoleReachedError):
            await parent.run(writer)
    finally:
        pulse.cancel()
        await asyncio.gather(pulse, return_exceptions=True)
        await cpu.aclose()
