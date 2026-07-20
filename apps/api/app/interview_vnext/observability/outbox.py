"""Outbox state machine used to deliver committed execution events."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from enum import StrEnum
from threading import RLock
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.identifiers import UtcDatetime

from .events import ExecutionEvent


class OutboxStatus(StrEnum):
    PENDING = "pending"
    LEASED = "leased"
    RETRY_WAIT = "retry_wait"
    DELIVERED = "delivered"
    DEAD_LETTER = "dead_letter"


class OutboxRecord(DomainModel):
    schema_version: Literal["capture_outbox_record.v1"] = "capture_outbox_record.v1"
    message_id: UUID
    event: ExecutionEvent
    status: OutboxStatus = OutboxStatus.PENDING
    delivery_attempts: int = Field(default=0, ge=0)
    created_at: UtcDatetime
    updated_at: UtcDatetime
    lease_owner: str | None = None
    lease_expires_at: UtcDatetime | None = None
    next_attempt_at: UtcDatetime | None = None
    delivered_at: UtcDatetime | None = None
    last_error_code: str | None = None

    @model_validator(mode="after")
    def fields_match_status(self) -> "OutboxRecord":
        if self.updated_at < self.created_at:
            raise ValueError("outbox updated_at cannot precede created_at")
        if self.message_id != self.event.event_id:
            raise ValueError("outbox message_id must equal event_id")
        if self.status == OutboxStatus.LEASED:
            if self.lease_owner is None or self.lease_expires_at is None:
                raise ValueError("leased outbox record requires owner and expiry")
        elif self.lease_owner is not None or self.lease_expires_at is not None:
            raise ValueError("only leased outbox records may carry a lease")
        if self.status == OutboxStatus.RETRY_WAIT and self.next_attempt_at is None:
            raise ValueError("retry_wait outbox record requires next_attempt_at")
        if self.status != OutboxStatus.RETRY_WAIT and self.next_attempt_at is not None:
            raise ValueError("only retry_wait outbox record may set next_attempt_at")
        if self.status in {OutboxStatus.RETRY_WAIT, OutboxStatus.DEAD_LETTER} and not (
            self.last_error_code or ""
        ).strip():
            raise ValueError("failed outbox delivery requires last_error_code")
        if self.status == OutboxStatus.DELIVERED and self.delivered_at is None:
            raise ValueError("delivered outbox record requires delivered_at")
        if self.status != OutboxStatus.DELIVERED and self.delivered_at is not None:
            raise ValueError("only delivered outbox record may set delivered_at")
        return self


class OutboxConflict(ValueError):
    pass


class OutboxLeaseConflict(ValueError):
    pass


class Outbox(Protocol):
    def enqueue(self, event: ExecutionEvent, *, occurred_at) -> OutboxRecord: ...

    def lease(
        self,
        *,
        worker_id: str,
        now,
        lease_for: timedelta,
        limit: int = 100,
    ) -> tuple[OutboxRecord, ...]: ...

    def mark_delivered(
        self,
        message_id: UUID,
        *,
        worker_id: str,
        occurred_at,
    ) -> OutboxRecord: ...

    def mark_failed(
        self,
        message_id: UUID,
        *,
        worker_id: str,
        occurred_at,
        error_code: str,
        retry_at=None,
    ) -> OutboxRecord: ...

    def get(self, message_id: UUID) -> OutboxRecord: ...


class InMemoryOutbox:
    """Thread-safe fake; database locking semantics remain a persistence concern."""

    def __init__(self, records: Iterable[OutboxRecord] = ()) -> None:
        self._records: dict[UUID, OutboxRecord] = {}
        for record in records:
            validated = OutboxRecord.model_validate(record.model_dump())
            existing = self._records.get(validated.message_id)
            if existing is not None and existing != validated:
                raise OutboxConflict(
                    f"duplicate initial outbox ID with different payload: {validated.message_id}"
                )
            self._records[validated.message_id] = validated
        self._lock = RLock()

    def enqueue(self, event: ExecutionEvent, *, occurred_at) -> OutboxRecord:
        event = ExecutionEvent.model_validate(event.model_dump())
        with self._lock:
            existing = self._records.get(event.event_id)
            if existing is not None:
                if existing.event != event:
                    raise OutboxConflict(
                        f"outbox event {event.event_id} already exists with another payload"
                    )
                return existing
            record = OutboxRecord(
                message_id=event.event_id,
                event=event,
                created_at=occurred_at,
                updated_at=occurred_at,
            )
            self._records[record.message_id] = record
            return record

    def lease(
        self,
        *,
        worker_id: str,
        now,
        lease_for: timedelta,
        limit: int = 100,
    ) -> tuple[OutboxRecord, ...]:
        if not worker_id.strip():
            raise ValueError("worker_id cannot be blank")
        if lease_for <= timedelta(0):
            raise ValueError("lease_for must be positive")
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._lock:
            eligible: list[OutboxRecord] = []
            for record in sorted(
                self._records.values(), key=lambda item: (item.created_at, str(item.message_id))
            ):
                if record.status == OutboxStatus.PENDING:
                    eligible.append(record)
                elif (
                    record.status == OutboxStatus.RETRY_WAIT
                    and record.next_attempt_at is not None
                    and record.next_attempt_at <= now
                ):
                    eligible.append(record)
                elif (
                    record.status == OutboxStatus.LEASED
                    and record.lease_expires_at is not None
                    and record.lease_expires_at <= now
                ):
                    eligible.append(record)
                if len(eligible) == limit:
                    break

            leased: list[OutboxRecord] = []
            for record in eligible:
                updated = record.model_copy(
                    update={
                        "status": OutboxStatus.LEASED,
                        "delivery_attempts": record.delivery_attempts + 1,
                        "updated_at": now,
                        "lease_owner": worker_id,
                        "lease_expires_at": now + lease_for,
                        "next_attempt_at": None,
                    }
                )
                updated = OutboxRecord.model_validate(updated.model_dump())
                self._records[record.message_id] = updated
                leased.append(updated)
            return tuple(leased)

    def mark_delivered(self, message_id: UUID, *, worker_id: str, occurred_at) -> OutboxRecord:
        with self._lock:
            record = self._require(message_id)
            if record.status == OutboxStatus.DELIVERED:
                return record
            self._assert_lease(record, worker_id)
            self._assert_transition_time(record, occurred_at)
            updated = record.model_copy(
                update={
                    "status": OutboxStatus.DELIVERED,
                    "updated_at": occurred_at,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "delivered_at": occurred_at,
                    "last_error_code": None,
                }
            )
            updated = OutboxRecord.model_validate(updated.model_dump())
            self._records[message_id] = updated
            return updated

    def mark_failed(
        self,
        message_id: UUID,
        *,
        worker_id: str,
        occurred_at,
        error_code: str,
        retry_at=None,
    ) -> OutboxRecord:
        if not error_code.strip():
            raise ValueError("error_code cannot be blank")
        with self._lock:
            record = self._require(message_id)
            self._assert_lease(record, worker_id)
            self._assert_transition_time(record, occurred_at)
            if retry_at is not None and retry_at <= occurred_at:
                raise ValueError("retry_at must be after failure time")
            target = OutboxStatus.RETRY_WAIT if retry_at is not None else OutboxStatus.DEAD_LETTER
            updated = record.model_copy(
                update={
                    "status": target,
                    "updated_at": occurred_at,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "next_attempt_at": retry_at,
                    "last_error_code": error_code,
                }
            )
            updated = OutboxRecord.model_validate(updated.model_dump())
            self._records[message_id] = updated
            return updated

    def get(self, message_id: UUID) -> OutboxRecord:
        with self._lock:
            return self._require(message_id)

    def all(self) -> tuple[OutboxRecord, ...]:
        with self._lock:
            return tuple(
                sorted(self._records.values(), key=lambda item: (item.created_at, str(item.message_id)))
            )

    def _require(self, message_id: UUID) -> OutboxRecord:
        try:
            return self._records[message_id]
        except KeyError as exc:
            raise KeyError(str(message_id)) from exc

    @staticmethod
    def _assert_lease(record: OutboxRecord, worker_id: str) -> None:
        if record.status != OutboxStatus.LEASED or record.lease_owner != worker_id:
            raise OutboxLeaseConflict(
                f"worker {worker_id!r} does not own outbox lease {record.message_id}"
            )

    @staticmethod
    def _assert_transition_time(record: OutboxRecord, occurred_at) -> None:
        if occurred_at < record.updated_at:
            raise OutboxLeaseConflict("outbox transition time cannot regress")
        if record.lease_expires_at is not None and occurred_at > record.lease_expires_at:
            raise OutboxLeaseConflict("outbox lease expired before transition")
