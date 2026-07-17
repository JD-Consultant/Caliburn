"""PostgreSQL outbox queue adapter — lease / delivered / failed (V2-B §8).

與 UoW repositories 不同,queue adapter **自己擁有短 transaction**:§8.2 要求
lease 在 transaction A commit 後才呼叫 exporter,mark_delivered/failed 是
transaction B。因此 constructor 收 ``async_sessionmaker``,每個方法一個短
transaction,絕不跨 network call 持有 connection/lock。

- lease 使用 reference §8.1 的完整 CTE(DB ``CURRENT_TIMESTAMP`` 是跨 process
  權威時間;``FOR UPDATE SKIP LOCKED`` 只用在這張 queue);同 run 只有最早的
  non-terminal message 可進行 delivery,不同 run 平行。
- at-least-once:exporter 成功但 mark 前 crash → lease 到期重送;consumer 以
  ``event_id`` 冪等。delivered/dead_letter 是 terminal,保留稽核,不 delete。
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.identifiers import Sha256, UtcDatetime

from .errors import OutboxLeaseConflict, PersistenceError

# operational config(§8.1;非 domain contract:改值要有 load test/metric 依據)
DEFAULT_LEASE_LIMIT = 100
MAX_LEASE_LIMIT = 500
DEFAULT_LEASE_SECONDS = 60
MIN_LEASE_SECONDS = 5
MAX_LEASE_SECONDS = 900

_LEASE_SQL = sa.text("""
WITH picked AS (
    SELECT o.message_id
    FROM interview_vnext_outbox AS o
    WHERE (
        o.status = 'pending'
        OR (o.status = 'retry_wait' AND o.next_attempt_at <= CURRENT_TIMESTAMP)
        OR (o.status = 'leased' AND o.lease_expires_at <= CURRENT_TIMESTAMP)
    )
      AND NOT EXISTS (
          SELECT 1
          FROM interview_vnext_outbox AS prior
          WHERE prior.tenant_id = o.tenant_id
            AND prior.run_id = o.run_id
            AND prior.event_sequence < o.event_sequence
            AND prior.status NOT IN ('delivered', 'dead_letter')
      )
    ORDER BY o.created_at, o.message_id
    FOR UPDATE OF o SKIP LOCKED
    LIMIT :limit
)
UPDATE interview_vnext_outbox AS o
SET status = 'leased',
    delivery_attempts = o.delivery_attempts + 1,
    lease_owner = :worker_id,
    lease_expires_at = CURRENT_TIMESTAMP + make_interval(secs => :lease_seconds),
    next_attempt_at = NULL,
    updated_at = CURRENT_TIMESTAMP
FROM picked
WHERE o.message_id = picked.message_id
RETURNING o.message_id, o.tenant_id, o.run_id, o.event_sequence, o.event_hash,
          o.event_json, o.status, o.delivery_attempts, o.lease_owner,
          o.lease_expires_at
""")


class LeasedOutboxMessage(DomainModel):
    """Lease 結果;exporter payload 至少帶 event_id/run_id/sequence/event_hash。"""

    message_id: UUID
    tenant_id: UUID
    run_id: UUID
    event_sequence: int
    event_hash: Sha256
    event_json: str
    status: Literal["leased"] = "leased"
    delivery_attempts: int
    lease_owner: str
    lease_expires_at: UtcDatetime


class PostgresOutbox:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def lease(self, *, worker_id: str,
                    lease_seconds: int = DEFAULT_LEASE_SECONDS,
                    limit: int = DEFAULT_LEASE_LIMIT,
                    ) -> tuple[LeasedOutboxMessage, ...]:
        if not worker_id.strip():
            raise PersistenceError("worker_id cannot be blank")
        if not MIN_LEASE_SECONDS <= lease_seconds <= MAX_LEASE_SECONDS:
            raise PersistenceError(
                f"lease_seconds must be {MIN_LEASE_SECONDS}-{MAX_LEASE_SECONDS}")
        if not 1 <= limit <= MAX_LEASE_LIMIT:
            raise PersistenceError(f"limit must be 1-{MAX_LEASE_LIMIT}")
        async with self._factory() as session:
            rows = (await session.execute(_LEASE_SQL, {
                "worker_id": worker_id, "lease_seconds": lease_seconds,
                "limit": limit})).mappings().all()
            await session.commit()      # transaction A:commit 後才准呼叫 exporter
        return tuple(LeasedOutboxMessage.model_validate(dict(row)) for row in rows)

    async def mark_delivered(self, *, message_id: UUID, worker_id: str) -> None:
        async with self._factory() as session:
            status = await self._status(session, message_id)
            if status == "delivered":
                return                   # idempotent:不送出 UPDATE
            result = await session.execute(sa.text(
                "UPDATE interview_vnext_outbox SET status = 'delivered', "
                "delivered_at = CURRENT_TIMESTAMP, lease_owner = NULL, "
                "lease_expires_at = NULL, last_error_code = NULL, "
                "updated_at = CURRENT_TIMESTAMP "
                "WHERE message_id = :m AND status = 'leased' "
                "AND lease_owner = :w AND lease_expires_at >= CURRENT_TIMESTAMP "
                "RETURNING message_id"),
                {"m": str(message_id), "w": worker_id})
            if result.first() is None:
                await session.rollback()
                raise OutboxLeaseConflict(
                    "delivered precondition failed (owner/status/expiry)",
                    message_id=message_id, worker_id=worker_id)
            await session.commit()

    async def mark_failed(self, *, message_id: UUID, worker_id: str,
                          error_code: str, retry_at=None) -> None:
        if not error_code.strip():
            raise PersistenceError("error_code cannot be blank")
        async with self._factory() as session:
            if retry_at is not None:
                db_now = (await session.execute(
                    sa.text("SELECT CURRENT_TIMESTAMP"))).scalar_one()
                if retry_at <= db_now:
                    await session.rollback()
                    raise PersistenceError(
                        "retry_at must be after the failure DB time",
                        message_id=message_id)
                sql = ("UPDATE interview_vnext_outbox SET status = 'retry_wait', "
                       "next_attempt_at = :retry_at, lease_owner = NULL, "
                       "lease_expires_at = NULL, last_error_code = :err, "
                       "updated_at = CURRENT_TIMESTAMP "
                       "WHERE message_id = :m AND status = 'leased' "
                       "AND lease_owner = :w "
                       "AND lease_expires_at >= CURRENT_TIMESTAMP "
                       "RETURNING message_id")
                params = {"m": str(message_id), "w": worker_id,
                          "err": error_code, "retry_at": retry_at}
            else:
                sql = ("UPDATE interview_vnext_outbox SET status = 'dead_letter', "
                       "lease_owner = NULL, lease_expires_at = NULL, "
                       "last_error_code = :err, updated_at = CURRENT_TIMESTAMP "
                       "WHERE message_id = :m AND status = 'leased' "
                       "AND lease_owner = :w "
                       "AND lease_expires_at >= CURRENT_TIMESTAMP "
                       "RETURNING message_id")
                params = {"m": str(message_id), "w": worker_id, "err": error_code}
            result = await session.execute(sa.text(sql), params)
            if result.first() is None:
                await session.rollback()
                raise OutboxLeaseConflict(
                    "failed-transition precondition failed (owner/status/expiry)",
                    message_id=message_id, worker_id=worker_id)
            await session.commit()

    async def status(self, *, message_id: UUID) -> str:
        async with self._factory() as session:
            status = await self._status(session, message_id)
        if status is None:
            raise PersistenceError("outbox message not found", message_id=message_id)
        return status

    @staticmethod
    async def _status(session: AsyncSession, message_id: UUID) -> str | None:
        return (await session.execute(sa.text(
            "SELECT status FROM interview_vnext_outbox WHERE message_id = :m"),
            {"m": str(message_id)})).scalar_one_or_none()
