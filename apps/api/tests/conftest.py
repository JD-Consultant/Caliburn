import asyncio
import os
import sys
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


# psycopg3 async cannot use ProactorEventLoop on Windows; switch to SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


@pytest_asyncio.fixture
async def db_session():
    """每測試一條交易，結束 rollback；需設 TEST_DATABASE_URL 指向測試 Postgres。"""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(TEST_DATABASE_URL)
    conn = await engine.connect()
    trans = await conn.begin()
    Session = async_sessionmaker(bind=conn, expire_on_commit=False, class_=AsyncSession)
    session = Session()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


# ── vNext V2-B PostgreSQL integration fixtures（durable persistence plan §3.3）──
# outer-transaction `db_session` 無法測「commit 後另一 session 看見」；outbox/crash
# recovery tests 需要 transaction A commit 後讓 transaction B 讀到，因此另建真 commit
# 的 session factory + 逐 case 依 ID 清理（不 truncate 共享 DB）。

@pytest.fixture
def require_postgres():
    """CI 未設 TEST_DATABASE_URL 直接 fail（skip 不得當通過）；local 缺 DB 標明原因 skip。"""
    if not TEST_DATABASE_URL:
        if os.getenv("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI for PostgreSQL integration tests")
        pytest.skip("TEST_DATABASE_URL not set; PostgreSQL integration test skipped (local)")


@pytest_asyncio.fixture
async def postgres_session_factory(require_postgres):
    """真 commit 的 async_sessionmaker：每個 AsyncSession 各自獨立 transaction，
    commit 後其他 session 可見（AsyncSession 一 task 一 session，不跨 task 共用）。"""
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    finally:
        await engine.dispose()


@dataclass(frozen=True)
class VNextIds:
    """每 case 唯一的 vNext identity；tenant_id 獨立產生，絕不拿 user_id 充當。"""

    tenant_id: UUID
    user_id: UUID
    profile_id: UUID
    session_id: UUID
    run_id: UUID


@pytest.fixture
def vnext_ids() -> VNextIds:
    return VNextIds(
        tenant_id=uuid4(),
        user_id=uuid4(),
        profile_id=uuid4(),
        session_id=uuid4(),
        run_id=uuid4(),
    )


# vNext 八張表（0010）：cleanup 依 FK 反向順序刪；表在 V2-B-2 才建，先以
# introspection 容忍缺表，讓 V2-B-0/1 的 fixture 測試不需等 migration。
_VNEXT_TABLES_REVERSE_ORDER = (
    "interview_vnext_operation_attempts",
    "interview_vnext_operation_checkpoints",
    "interview_vnext_outbox",
    "interview_vnext_execution_events",
    "interview_vnext_commands",
    "interview_vnext_artifacts",
    "interview_vnext_runs",
    "interview_vnext_sessions",
)


@pytest_asyncio.fixture
async def cleanup_vnext_rows(postgres_session_factory, vnext_ids):
    """只清本 case IDs：先把 run manifest／session initial-state 指標設 null
    （斷開 circular FK），Authoring 先按 proposal → revision leaves → document
    清除，再依 attempts → … → sessions → profile/user 反向刪除。"""
    yield vnext_ids
    async with postgres_session_factory() as session:
        rows = await session.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND (table_name LIKE 'interview_vnext_%' "
            "OR table_name LIKE 'job_authoring_%')"
        ))
        existing = {name for (name,) in rows.all()}
        params = {"tenant_id": str(vnext_ids.tenant_id)}
        if "job_authoring_proposals" in existing:
            await session.execute(text(
                "DELETE FROM job_authoring_proposals WHERE tenant_id = :tenant_id"
            ), params)
        if "job_authoring_revisions" in existing:
            while True:
                deleted = await session.execute(text(
                    "DELETE FROM job_authoring_revisions AS revision "
                    "WHERE revision.tenant_id = :tenant_id "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM job_authoring_revisions AS child "
                    "  WHERE child.tenant_id = revision.tenant_id "
                    "  AND child.parent_revision_id = revision.revision_id"
                    ") RETURNING revision.revision_id"
                ), params)
                deleted_count = len(deleted.all())
                if deleted_count == 0:
                    remaining = await session.scalar(text(
                        "SELECT count(*) FROM job_authoring_revisions "
                        "WHERE tenant_id = :tenant_id"
                    ), params)
                    if remaining:
                        raise RuntimeError(
                            "authoring revision cleanup made no progress"
                        )
                    break
        if "job_authoring_documents" in existing:
            await session.execute(text(
                "DELETE FROM job_authoring_documents WHERE tenant_id = :tenant_id"
            ), params)
        if "interview_vnext_runs" in existing:
            await session.execute(text(
                "UPDATE interview_vnext_runs SET manifest_artifact_id = NULL "
                "WHERE tenant_id = :tenant_id"), params)
        if "interview_vnext_sessions" in existing:
            await session.execute(text(
                "UPDATE interview_vnext_sessions SET initial_state_artifact_id = NULL "
                "WHERE tenant_id = :tenant_id"), params)
        for table in _VNEXT_TABLES_REVERSE_ORDER:
            if table in existing:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE tenant_id = :tenant_id"), params)  # noqa: S608
        await session.execute(text("DELETE FROM job_profiles WHERE id = :profile_id"),
                              {"profile_id": str(vnext_ids.profile_id)})
        await session.execute(text("DELETE FROM users WHERE id = :user_id"),
                              {"user_id": str(vnext_ids.user_id)})
        await session.commit()


@pytest_asyncio.fixture
async def vnext_profile(postgres_session_factory, cleanup_vnext_rows):
    """最小 User/JobProfile fixture（vNext sessions.profile_id 的 FK 前提）。
    回傳 VNextIds；tenant_id 與 user_id 是兩個獨立 UUID（§2.3 tenant seam）。"""
    from app.models import JobProfile, User

    ids = cleanup_vnext_rows
    async with postgres_session_factory() as session:
        session.add(User(id=ids.user_id, email=f"vnext-{ids.user_id}@test.local",
                         name="vNext 整合測試使用者"))
        session.add(JobProfile(id=ids.profile_id, user_id=ids.user_id,
                               job_title="vNext 整合測試職務"))
        await session.commit()
    return ids
