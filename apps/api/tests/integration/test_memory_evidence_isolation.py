"""Damaged durable Memory evidence isolates its file without restarting healthy work."""

import asyncio
import json
import logging
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError

from caliburn.adapters.logging import SafeJsonFormatter
from caliburn.features.executions import memory_discovery
from caliburn.features.work_memory import consolidation_requests
from caliburn.features.work_memory.batch_persistence import MemoryOperationRecord
from caliburn.features.work_memory.consolidation_models import MemoryEvidenceError
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_supervisor import MemorySupervisor
from tests.integration.test_memory_batch_orchestration import complete_turn, execute, start_turn

pytestmark = pytest.mark.postgres


async def add_damaged_intent(database, writer):
    command_id = uuid4()
    await MemoryConsolidationWorkflow(database.sessions).request(writer, command_id)
    await replace_evidence(database, command_id, {"intent_source_id": uuid4()})
    return command_id


async def ready_turn(database):
    writer = await start_turn(database)
    command_id = uuid4()
    await MemoryConsolidationWorkflow(database.sessions).request(writer, command_id)
    await complete_turn(database, writer)
    return writer, command_id


async def replace_evidence(database, command_id, values):
    """Superuser corruption of this fixture schema only; restore all guards atomically."""
    async with database.sessions.begin() as session:
        shape = await session.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='memory_operations'::regclass "
                "AND conname='ck_memory_operations_evidence_shape'"
            )
        )
        shape = shape.removesuffix(" NOT VALID")
        original = (
            await session.execute(
                select(*(getattr(MemoryOperationRecord, key) for key in values)).where(
                    MemoryOperationRecord.command_id == command_id
                )
            )
        ).one()
        await session.execute(text("ALTER TABLE memory_operations DISABLE TRIGGER ALL"))
        await session.execute(
            text(
                "ALTER TABLE memory_operations DROP CONSTRAINT ck_memory_operations_evidence_shape"
            )
        )
        await session.execute(
            update(MemoryOperationRecord)
            .where(MemoryOperationRecord.command_id == command_id)
            .values(**values)
        )
        await session.execute(
            text(
                "ALTER TABLE memory_operations ADD CONSTRAINT ck_memory_operations_evidence_shape "
                + shape
                + " NOT VALID"
            )
        )
        await session.execute(text("ALTER TABLE memory_operations ENABLE TRIGGER ALL"))
    return dict(zip(values, original, strict=True))


def test_startup_isolates_damaged_file_and_dispatches_healthy_work(database_settings):
    async def scenario(database):
        requests = MemoryConsolidationWorkflow(database.sessions)
        damaged = await start_turn(database)
        await add_damaged_intent(database, damaged)
        await complete_turn(database, damaged)
        healthy = await start_turn(database)
        await requests.request(healthy, uuid4())
        await complete_turn(database, healthy)
        entered = asyncio.Event()
        seen = []

        async def leader():
            pass

        async def run(writer):
            seen.append(writer.scope.job_file_id)
            entered.set()
            await asyncio.Event().wait()

        supervisor = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=60
        )
        try:
            await supervisor.start()
            await asyncio.wait_for(entered.wait(), 5)
            assert seen == [healthy.scope.job_file_id]
            assert supervisor.failure is None
        finally:
            await supervisor.close()

    execute(database_settings, scenario)


@pytest.mark.parametrize("kind", ["consolidation_intent", "batch_failure"])
@pytest.mark.parametrize("damage", ["missing", "invalid"])
def test_malformed_disposition_blocks_only_its_file_even_with_valid_evidence(
    database_settings, kind, damage
):
    async def scenario(database):
        damaged, intent_command = await ready_turn(database)
        healthy, _ = await ready_turn(database)
        command_id = intent_command
        if kind == "consolidation_intent":
            values = {"intent_source_id": None if damage == "missing" else uuid4()}
        else:
            command_id = uuid4()
            async with database.sessions.begin() as session:
                await consolidation_requests.record_failure(
                    session,
                    job_file_id=damaged.scope.job_file_id,
                    execution_id=damaged.scope.execution_id,
                    command_id=command_id,
                    reason="synthetic",
                    frontier=3,
                )
            values = {"failure_frontier": None if damage == "missing" else -1}
        await replace_evidence(database, command_id, values)
        requests = MemoryConsolidationWorkflow(database.sessions)
        discovery = await requests.discover()
        assert discovery.ready_file_ids == (healthy.scope.job_file_id,)
        [issue] = discovery.issues
        assert issue.job_file_id == damaged.scope.job_file_id
        assert issue.command_id == command_id
        assert issue.reason == (
            ("invalid_intent_payload" if damage == "missing" else "formal_source_mismatch")
            if kind == "consolidation_intent"
            else "invalid_failure_payload"
        )
        with pytest.raises(MemoryEvidenceError) as refused:
            await requests.claim(damaged.scope.job_file_id, writer_id=uuid4())
        assert refused.value.issue == issue
        async with database.sessions() as session:
            assert await memory_discovery.list_active_memory(session) == ()

    execute(database_settings, scenario)


@pytest.mark.parametrize("damaged_first", [False, True])
def test_a_good_intent_cannot_hide_a_damaged_intent_in_either_history_order(
    database_settings, damaged_first
):
    async def scenario(database):
        requests = MemoryConsolidationWorkflow(database.sessions)
        first = await start_turn(database)
        if damaged_first:
            await add_damaged_intent(database, first)
        else:
            await requests.request(first, uuid4())
        await complete_turn(database, first)
        second = await start_turn(database, first.scope.job_file_id)
        if damaged_first:
            await requests.request(second, uuid4())
        else:
            await add_damaged_intent(database, second)
        await complete_turn(database, second)
        discovery = await requests.discover()
        assert discovery.ready_file_ids == ()
        [issue] = discovery.issues
        assert issue.reason == "formal_source_mismatch"

    execute(database_settings, scenario)


def test_damage_does_not_cancel_healthy_runner_and_repair_recovers_without_restart(
    database_settings, caplog
):
    async def scenario(database):
        healthy, _ = await ready_turn(database)
        entered = asyncio.Event()
        cancelled = []
        seen = []

        async def leader():
            pass

        async def run(writer):
            seen.append(writer.scope.job_file_id)
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(writer.scope.job_file_id)

        supervisor = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=60
        )
        try:
            await supervisor.start()
            await asyncio.wait_for(entered.wait(), 5)
            damaged, command_id = await ready_turn(database)
            original = await replace_evidence(database, command_id, {"intent_source_id": None})
            await supervisor.scan()
            await supervisor.scan()
            assert cancelled == []
            assert seen == [healthy.scope.job_file_id]
            assert supervisor.failure is None
            [issue] = supervisor.evidence_issues
            assert issue.job_file_id == damaged.scope.job_file_id
            records = [row for row in caplog.records if row.msg == "memory.evidence_invalid"]
            [record] = records
            payload = json.loads(SafeJsonFormatter().format(record))
            assert payload["job_file_id"] == str(damaged.scope.job_file_id)
            assert payload["execution_id"] == str(damaged.scope.execution_id)
            assert payload["command_id"] == str(command_id)
            assert "execution_kind" not in payload
            assert payload["failure_kind"] == "invalid_intent_payload"
            assert "private" not in str(record.__dict__)
            assert record.exc_info is None
            entered.clear()
            await replace_evidence(database, command_id, original)
            await supervisor.scan()
            await asyncio.wait_for(entered.wait(), 5)
            assert seen == [healthy.scope.job_file_id, damaged.scope.job_file_id]
            assert cancelled == []
            assert not supervisor.evidence_issues
            assert not supervisor.failures
        finally:
            await supervisor.close()

    caplog.set_level(logging.ERROR)
    execute(database_settings, scenario)


@pytest.mark.parametrize("repair_after_claim", [False, True])
def test_claim_rechecks_damage_after_discovery_and_continues_other_files(
    database_settings, monkeypatch, caplog, repair_after_claim
):
    async def scenario(database):
        damaged, command_id = await ready_turn(database)
        healthy, _ = await ready_turn(database)
        original_claim = MemoryConsolidationWorkflow.claim

        async def race_claim(requests, file_id, *, writer_id):
            if file_id == damaged.scope.job_file_id:
                original = await replace_evidence(database, command_id, {"intent_source_id": None})
                try:
                    return await original_claim(requests, file_id, writer_id=writer_id)
                finally:
                    if repair_after_claim:
                        await replace_evidence(database, command_id, original)
            return await original_claim(requests, file_id, writer_id=writer_id)

        monkeypatch.setattr(MemoryConsolidationWorkflow, "claim", race_claim)
        entered = asyncio.Event()
        seen = []

        async def leader():
            pass

        async def run(writer):
            seen.append(writer.scope.job_file_id)
            entered.set()
            await asyncio.Event().wait()

        supervisor = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=60
        )
        try:
            await supervisor.start()
            await asyncio.wait_for(entered.wait(), 5)
            assert seen == [healthy.scope.job_file_id]
            [issue] = supervisor.evidence_issues
            assert issue.job_file_id == damaged.scope.job_file_id
            await supervisor.scan()
            await supervisor.scan()
            records = [row for row in caplog.records if row.msg == "memory.evidence_invalid"]
            assert len(records) == 1
            async with database.sessions() as session:
                [active] = await memory_discovery.list_active_memory(session)
                assert active.scope.job_file_id == healthy.scope.job_file_id
        finally:
            await supervisor.close()

    caplog.set_level(logging.ERROR)
    execute(database_settings, scenario)


@pytest.mark.parametrize("failure_at", ["leadership", "database"])
def test_global_supervision_failure_still_stops_healthy_runners(
    database_settings, monkeypatch, failure_at
):
    async def scenario(database):
        await ready_turn(database)
        entered = asyncio.Event()
        cancelled = asyncio.Event()
        failure = OperationalError("private SQL", {}, ConnectionError("private URL"))
        fail_leadership = False

        async def leader():
            if fail_leadership:
                raise failure

        async def run(writer):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def fail_discovery():
            raise failure

        supervisor = MemorySupervisor(
            database.sessions, run=run, check_leadership=leader, poll_interval_seconds=60
        )
        try:
            await supervisor.start()
            await asyncio.wait_for(entered.wait(), 5)
            if failure_at == "leadership":
                fail_leadership = True
            else:
                monkeypatch.setattr(supervisor._requests, "discover", fail_discovery)
            supervisor.notify()
            await asyncio.wait_for(asyncio.shield(supervisor._monitor), 5)
            assert cancelled.is_set()
            assert supervisor.failure is not None
            assert supervisor.failure.error_type == type(failure).__name__
            assert not supervisor.evidence_issues
        finally:
            await supervisor.close()

    execute(database_settings, scenario)
