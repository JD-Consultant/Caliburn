from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any


class OperationStatus(StrEnum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    WAITING_FOR_EMPLOYEE = "waiting_for_employee"
    COMPLETED = "completed"
    FAILED = "failed"


class VisiblePhase(StrEnum):
    UNDERSTANDING_ANSWER = "understanding_answer"
    UPDATING_WORK_MODEL = "updating_work_model"
    PREPARING_NEXT_QUESTION = "preparing_next_question"


class IdempotencyConflict(ValueError):
    pass


class OperationNotFound(LookupError):
    pass


class InterruptNotFound(LookupError):
    pass


class StaleOperation(ValueError):
    pass


@dataclass(frozen=True)
class EmployeeInputCard:
    interrupt_id: str
    kind: str
    prompt: str
    allowed_responses: tuple[str, ...]


@dataclass(frozen=True)
class EmployeeInputResponse:
    decision: str


@dataclass(frozen=True)
class ResumeCommand:
    document_id: str
    operation_id: str
    interrupt_id: str
    expected_revision: int
    response: EmployeeInputResponse


@dataclass(frozen=True)
class OperationResult:
    document_revision: int
    visible_message: str


@dataclass(frozen=True)
class _OperationRecord:
    document_id: str
    operation_id: str
    input_hash: str
    status: OperationStatus
    operation_revision: int
    phase: VisiblePhase | None = None
    document_revision: int | None = None
    visible_message: str | None = None
    pending_input: EmployeeInputCard | None = None


@dataclass(frozen=True)
class ProductEvent:
    event_id: str
    operation_id: str
    kind: str
    status: OperationStatus
    operation_revision: int
    phase: VisiblePhase | None = None
    document_revision: int | None = None
    visible_message: str | None = None
    pending_input: EmployeeInputCard | None = None

    def to_wire(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "operation_id": self.operation_id,
            "kind": self.kind,
            "status": self.status.value,
            "operation_revision": self.operation_revision,
        }
        if self.phase is not None:
            payload["phase"] = self.phase.value
        if self.document_revision is not None:
            payload["document_revision"] = self.document_revision
        if self.visible_message is not None:
            payload["visible_message"] = self.visible_message
        if self.pending_input is not None:
            payload["pending_input"] = {
                "interrupt_id": self.pending_input.interrupt_id,
                "kind": self.pending_input.kind,
                "prompt": self.pending_input.prompt,
                "allowed_responses": list(self.pending_input.allowed_responses),
            }
        return payload


@dataclass(frozen=True)
class EditorProjection:
    draft: str
    dirty: bool
    displayed_document_revision: int
    refetch_after_clean: bool


def apply_document_event(
    editor: EditorProjection,
    event: ProductEvent,
) -> EditorProjection:
    revision = event.document_revision
    if revision is None or revision <= editor.displayed_document_revision:
        return editor
    if editor.dirty:
        return replace(editor, refetch_after_clean=True)
    return replace(
        editor,
        displayed_document_revision=revision,
        refetch_after_clean=False,
    )


class InMemoryOperationStore:
    """Represents the durable operation projection in this throwaway probe."""

    def __init__(self) -> None:
        self._records: dict[str, _OperationRecord] = {}
        self._lock = asyncio.Lock()

    async def create_or_get(
        self,
        *,
        document_id: str,
        operation_id: str,
        input_hash: str,
    ) -> tuple[_OperationRecord, bool]:
        async with self._lock:
            existing = self._records.get(operation_id)
            if existing is not None:
                if (
                    existing.document_id != document_id
                    or existing.input_hash != input_hash
                ):
                    raise IdempotencyConflict(operation_id)
                return existing, False
            record = _OperationRecord(
                document_id=document_id,
                operation_id=operation_id,
                input_hash=input_hash,
                status=OperationStatus.ACCEPTED,
                operation_revision=1,
            )
            self._records[operation_id] = record
            return record, True

    async def get(
        self,
        *,
        document_id: str,
        operation_id: str,
    ) -> _OperationRecord:
        async with self._lock:
            record = self._records.get(operation_id)
            if record is None or record.document_id != document_id:
                raise OperationNotFound(operation_id)
            return record

    async def update(
        self,
        *,
        document_id: str,
        operation_id: str,
        status: OperationStatus,
        phase: VisiblePhase | None = None,
        document_revision: int | None = None,
        visible_message: str | None = None,
        pending_input: EmployeeInputCard | None = None,
    ) -> _OperationRecord:
        async with self._lock:
            current = self._records.get(operation_id)
            if current is None or current.document_id != document_id:
                raise OperationNotFound(operation_id)
            updated = replace(
                current,
                status=status,
                operation_revision=current.operation_revision + 1,
                phase=phase,
                document_revision=document_revision,
                visible_message=visible_message,
                pending_input=pending_input,
            )
            self._records[operation_id] = updated
            return updated


RunCallable = Callable[["RunControls"], Awaitable[OperationResult]]
ResumeCallable = Callable[[ResumeCommand], Awaitable[None]]


class RunControls:
    def __init__(
        self,
        transport: "ProductEventTransport",
        *,
        document_id: str,
        operation_id: str,
    ) -> None:
        self._transport = transport
        self._document_id = document_id
        self._operation_id = operation_id

    async def progress(self, phase: VisiblePhase) -> None:
        await self._transport._transition(
            document_id=self._document_id,
            operation_id=self._operation_id,
            status=OperationStatus.RUNNING,
            phase=phase,
        )

    async def wait_for_employee(
        self,
        card: EmployeeInputCard,
    ) -> EmployeeInputResponse:
        loop = asyncio.get_running_loop()
        waiter: asyncio.Future[EmployeeInputResponse] = loop.create_future()
        self._transport._response_waiters[self._operation_id] = waiter
        await self._transport._transition(
            document_id=self._document_id,
            operation_id=self._operation_id,
            status=OperationStatus.WAITING_FOR_EMPLOYEE,
            pending_input=card,
        )
        response = await waiter
        await self._transport._transition(
            document_id=self._document_id,
            operation_id=self._operation_id,
            status=OperationStatus.RUNNING,
        )
        return response


class ProductEventTransport:
    TERMINAL = {OperationStatus.COMPLETED, OperationStatus.FAILED}

    def __init__(
        self,
        store: InMemoryOperationStore,
        *,
        resume_interrupted: ResumeCallable | None = None,
    ) -> None:
        self._store = store
        self._resume_interrupted = resume_interrupted
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[ProductEvent]]] = defaultdict(
            list
        )
        self._response_waiters: dict[
            str, asyncio.Future[EmployeeInputResponse]
        ] = {}

    @staticmethod
    def _event(record: _OperationRecord, *, kind: str) -> ProductEvent:
        return ProductEvent(
            event_id=f"{record.operation_id}:{record.operation_revision}",
            operation_id=record.operation_id,
            kind=kind,
            status=record.status,
            operation_revision=record.operation_revision,
            phase=record.phase,
            document_revision=record.document_revision,
            visible_message=record.visible_message,
            pending_input=record.pending_input,
        )

    async def start(
        self,
        *,
        document_id: str,
        operation_id: str,
        input_hash: str,
        run: RunCallable,
    ) -> ProductEvent:
        record, created = await self._store.create_or_get(
            document_id=document_id,
            operation_id=operation_id,
            input_hash=input_hash,
        )
        if created:
            self._tasks[operation_id] = asyncio.create_task(
                self._execute(
                    document_id=document_id,
                    operation_id=operation_id,
                    run=run,
                )
            )
        return self._event(record, kind="operation.accepted")

    async def _execute(
        self,
        *,
        document_id: str,
        operation_id: str,
        run: RunCallable,
    ) -> None:
        try:
            await self._transition(
                document_id=document_id,
                operation_id=operation_id,
                status=OperationStatus.RUNNING,
            )
            result = await run(
                RunControls(
                    self,
                    document_id=document_id,
                    operation_id=operation_id,
                )
            )
            await self._transition(
                document_id=document_id,
                operation_id=operation_id,
                status=OperationStatus.COMPLETED,
                document_revision=result.document_revision,
                visible_message=result.visible_message,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            await self._transition(
                document_id=document_id,
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                visible_message="顧問暫時無法完成分析，原文已保存，可安全重試。",
            )

    async def _transition(
        self,
        *,
        document_id: str,
        operation_id: str,
        status: OperationStatus,
        phase: VisiblePhase | None = None,
        document_revision: int | None = None,
        visible_message: str | None = None,
        pending_input: EmployeeInputCard | None = None,
    ) -> ProductEvent:
        record = await self._store.update(
            document_id=document_id,
            operation_id=operation_id,
            status=status,
            phase=phase,
            document_revision=document_revision,
            visible_message=visible_message,
            pending_input=pending_input,
        )
        kind = {
            OperationStatus.RUNNING: "operation.progress",
            OperationStatus.WAITING_FOR_EMPLOYEE: "input.required",
            OperationStatus.COMPLETED: "operation.completed",
            OperationStatus.FAILED: "operation.failed",
        }[status]
        event = self._event(record, kind=kind)
        for queue in tuple(self._subscribers.get(operation_id, ())):
            queue.put_nowait(event)
        return event

    async def get_snapshot(
        self,
        *,
        document_id: str,
        operation_id: str,
    ) -> ProductEvent:
        record = await self._store.get(
            document_id=document_id,
            operation_id=operation_id,
        )
        return self._event(record, kind="operation.snapshot")

    async def subscribe(
        self,
        *,
        document_id: str,
        operation_id: str,
    ) -> AsyncIterator[ProductEvent]:
        queue: asyncio.Queue[ProductEvent] = asyncio.Queue()
        subscribers = self._subscribers[operation_id]
        subscribers.append(queue)
        try:
            snapshot = await self.get_snapshot(
                document_id=document_id,
                operation_id=operation_id,
            )
            yield snapshot
            if snapshot.status in self.TERMINAL:
                return
            while True:
                event = await queue.get()
                yield event
                if event.status in self.TERMINAL:
                    return
        finally:
            subscribers.remove(queue)
            if not subscribers:
                self._subscribers.pop(operation_id, None)

    async def respond(
        self,
        *,
        document_id: str,
        operation_id: str,
        interrupt_id: str,
        expected_revision: int,
        response: EmployeeInputResponse,
    ) -> None:
        record = await self._store.get(
            document_id=document_id,
            operation_id=operation_id,
        )
        if record.operation_revision != expected_revision:
            raise StaleOperation(operation_id)
        card = record.pending_input
        if card is None or card.interrupt_id != interrupt_id:
            raise InterruptNotFound(interrupt_id)
        if response.decision not in card.allowed_responses:
            raise ValueError("response is not allowed for this interrupt")
        waiter = self._response_waiters.get(operation_id)
        if waiter is not None and not waiter.done():
            waiter.set_result(response)
            return
        if self._resume_interrupted is None:
            raise InterruptNotFound(interrupt_id)
        await self._resume_interrupted(
            ResumeCommand(
                document_id=document_id,
                operation_id=operation_id,
                interrupt_id=interrupt_id,
                expected_revision=expected_revision,
                response=response,
            )
        )

    async def wait(self, operation_id: str) -> None:
        task = self._tasks.get(operation_id)
        if task is not None:
            await task
