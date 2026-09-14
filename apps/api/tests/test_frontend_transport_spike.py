from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest

import frontend_transport_spike as spike


async def _next_matching(
    events: AsyncIterator[spike.ProductEvent],
    status: spike.OperationStatus,
) -> spike.ProductEvent:
    async for event in events:
        if event.status is status:
            return event
    raise AssertionError(f"stream ended before {status}")


@pytest.mark.asyncio
async def test_disconnect_does_not_cancel_run_and_reconnect_hydrates_snapshot() -> None:
    store = spike.InMemoryOperationStore()
    transport = spike.ProductEventTransport(store)
    document_id = f"jd-{uuid4()}"
    operation_id = f"operation-{uuid4()}"
    started = asyncio.Event()
    release = asyncio.Event()

    async def run(controls: spike.RunControls) -> spike.OperationResult:
        await controls.progress(spike.VisiblePhase.UNDERSTANDING_ANSWER)
        started.set()
        await release.wait()
        return spike.OperationResult(
            document_revision=8,
            visible_message="下一步確認這項工作的成果。",
        )

    await transport.start(
        document_id=document_id,
        operation_id=operation_id,
        input_hash="sha256:answer-1",
        run=run,
    )
    events = transport.subscribe(document_id=document_id, operation_id=operation_id)
    await _next_matching(events, spike.OperationStatus.RUNNING)
    await started.wait()

    # Closing the browser stream must not own or cancel the durable run.
    await events.aclose()
    release.set()
    await transport.wait(operation_id)

    restarted_transport = spike.ProductEventTransport(store)
    snapshot = await restarted_transport.get_snapshot(
        document_id=document_id,
        operation_id=operation_id,
    )
    assert snapshot.status is spike.OperationStatus.COMPLETED
    assert snapshot.document_revision == 8
    assert snapshot.visible_message == "下一步確認這項工作的成果。"


@pytest.mark.asyncio
async def test_operation_id_is_idempotent_and_conflicting_payload_is_rejected() -> None:
    store = spike.InMemoryOperationStore()
    transport = spike.ProductEventTransport(store)
    release = asyncio.Event()
    calls = 0

    async def run(controls: spike.RunControls) -> spike.OperationResult:
        nonlocal calls
        del controls
        calls += 1
        await release.wait()
        return spike.OperationResult(document_revision=2, visible_message="完成")

    arguments = {
        "document_id": "jd-1",
        "operation_id": "operation-1",
        "input_hash": "sha256:same",
        "run": run,
    }
    first = await transport.start(**arguments)
    second = await transport.start(**arguments)
    await asyncio.sleep(0)

    assert first.operation_id == second.operation_id == "operation-1"
    assert calls == 1

    with pytest.raises(spike.IdempotencyConflict):
        await transport.start(
            document_id="jd-1",
            operation_id="operation-1",
            input_hash="sha256:different",
            run=run,
        )

    release.set()
    await transport.wait("operation-1")


@pytest.mark.asyncio
async def test_interrupt_response_requires_scope_id_and_current_revision() -> None:
    store = spike.InMemoryOperationStore()
    transport = spike.ProductEventTransport(store)
    card = spike.EmployeeInputCard(
        interrupt_id="understanding-1",
        kind="understanding_checkpoint",
        prompt="目前理解是否正確？",
        allowed_responses=("accept", "edit", "reject"),
    )

    async def run(controls: spike.RunControls) -> spike.OperationResult:
        response = await controls.wait_for_employee(card)
        return spike.OperationResult(
            document_revision=4,
            visible_message=f"收到：{response.decision}",
        )

    await transport.start(
        document_id="jd-1",
        operation_id="operation-1",
        input_hash="sha256:answer",
        run=run,
    )
    events = transport.subscribe(document_id="jd-1", operation_id="operation-1")
    waiting = await _next_matching(events, spike.OperationStatus.WAITING_FOR_EMPLOYEE)

    with pytest.raises(spike.OperationNotFound):
        await transport.respond(
            document_id="jd-other",
            operation_id="operation-1",
            interrupt_id="understanding-1",
            expected_revision=waiting.operation_revision,
            response=spike.EmployeeInputResponse(decision="accept"),
        )
    with pytest.raises(spike.StaleOperation):
        await transport.respond(
            document_id="jd-1",
            operation_id="operation-1",
            interrupt_id="understanding-1",
            expected_revision=waiting.operation_revision - 1,
            response=spike.EmployeeInputResponse(decision="accept"),
        )
    with pytest.raises(spike.InterruptNotFound):
        await transport.respond(
            document_id="jd-1",
            operation_id="operation-1",
            interrupt_id="wrong-interrupt",
            expected_revision=waiting.operation_revision,
            response=spike.EmployeeInputResponse(decision="accept"),
        )

    await transport.respond(
        document_id="jd-1",
        operation_id="operation-1",
        interrupt_id="understanding-1",
        expected_revision=waiting.operation_revision,
        response=spike.EmployeeInputResponse(decision="accept"),
    )
    await transport.wait("operation-1")
    await events.aclose()
    completed = await transport.get_snapshot(
        document_id="jd-1", operation_id="operation-1"
    )
    assert completed.status is spike.OperationStatus.COMPLETED
    assert completed.visible_message == "收到：accept"


@pytest.mark.asyncio
async def test_interrupt_can_resume_through_durable_graph_port_after_server_restart() -> None:
    store = spike.InMemoryOperationStore()
    card = spike.EmployeeInputCard(
        interrupt_id="understanding-1",
        kind="understanding_checkpoint",
        prompt="目前理解是否正確？",
        allowed_responses=("accept", "edit", "reject"),
    )
    await store.create_or_get(
        document_id="jd-1",
        operation_id="operation-1",
        input_hash="sha256:answer",
    )
    await store.update(
        document_id="jd-1",
        operation_id="operation-1",
        status=spike.OperationStatus.WAITING_FOR_EMPLOYEE,
        pending_input=card,
    )

    async def resume(command: spike.ResumeCommand) -> None:
        # This stands in for the already-proven LangGraph Command(resume=...)
        # port and makes the externally visible durable state change real.
        await store.update(
            document_id=command.document_id,
            operation_id=command.operation_id,
            status=spike.OperationStatus.COMPLETED,
            document_revision=9,
            visible_message=f"恢復完成：{command.response.decision}",
        )

    restarted_transport = spike.ProductEventTransport(
        store,
        resume_interrupted=resume,
    )
    waiting = await restarted_transport.get_snapshot(
        document_id="jd-1", operation_id="operation-1"
    )
    await restarted_transport.respond(
        document_id="jd-1",
        operation_id="operation-1",
        interrupt_id="understanding-1",
        expected_revision=waiting.operation_revision,
        response=spike.EmployeeInputResponse(decision="edit"),
    )

    completed = await restarted_transport.get_snapshot(
        document_id="jd-1", operation_id="operation-1"
    )
    assert completed.status is spike.OperationStatus.COMPLETED
    assert completed.document_revision == 9
    assert completed.visible_message == "恢復完成：edit"


@pytest.mark.asyncio
async def test_wire_events_expose_product_status_not_internal_agent_state() -> None:
    store = spike.InMemoryOperationStore()
    transport = spike.ProductEventTransport(store)

    async def run(controls: spike.RunControls) -> spike.OperationResult:
        await controls.progress(spike.VisiblePhase.PREPARING_NEXT_QUESTION)
        return spike.OperationResult(
            document_revision=3,
            visible_message="請描述完成這項工作後會交付什麼。",
        )

    await transport.start(
        document_id="jd-1",
        operation_id="operation-1",
        input_hash="sha256:employee-raw-text-is-not-an-event",
        run=run,
    )
    await transport.wait("operation-1")
    event = await transport.get_snapshot(
        document_id="jd-1", operation_id="operation-1"
    )

    assert event.to_wire() == {
        "event_id": event.event_id,
        "operation_id": "operation-1",
        "kind": "operation.snapshot",
        "status": "completed",
        "operation_revision": event.operation_revision,
        "document_revision": 3,
        "visible_message": "請描述完成這項工作後會交付什麼。",
    }
    serialized = str(event.to_wire())
    assert "input_hash" not in serialized
    assert "employee-raw-text" not in serialized
    assert "skill" not in serialized.lower()
    assert "tool" not in serialized.lower()
    assert "current_jd" not in serialized


def test_document_revision_event_preserves_dirty_draft_and_defers_refetch() -> None:
    dirty = spike.EditorProjection(
        draft="員工尚未儲存的修改",
        dirty=True,
        displayed_document_revision=7,
        refetch_after_clean=False,
    )
    clean = spike.EditorProjection(
        draft="伺服器版本",
        dirty=False,
        displayed_document_revision=7,
        refetch_after_clean=False,
    )
    completed = spike.ProductEvent(
        event_id="operation-1:4",
        operation_id="operation-1",
        kind="operation.completed",
        status=spike.OperationStatus.COMPLETED,
        operation_revision=4,
        document_revision=8,
        visible_message="完成",
    )

    dirty_after = spike.apply_document_event(dirty, completed)
    clean_after = spike.apply_document_event(clean, completed)

    assert dirty_after.draft == "員工尚未儲存的修改"
    assert dirty_after.displayed_document_revision == 7
    assert dirty_after.refetch_after_clean is True
    assert clean_after.draft == "伺服器版本"
    assert clean_after.displayed_document_revision == 8
    assert clean_after.refetch_after_clean is False
