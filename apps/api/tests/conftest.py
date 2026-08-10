import asyncio
import os
import sys
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")


@pytest_asyncio.fixture
async def db_session():
    """每測試一條交易，結束 rollback；需設 TEST_DATABASE_URL。"""
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    engine = create_async_engine(TEST_DATABASE_URL)
    conn = await engine.connect()
    trans = await conn.begin()
    session_factory = async_sessionmaker(
        bind=conn,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    session = session_factory()
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
def require_postgres():
    if not TEST_DATABASE_URL:
        if os.getenv("CI"):
            pytest.fail("TEST_DATABASE_URL must be set in CI")
        pytest.skip("TEST_DATABASE_URL not set; PostgreSQL test skipped")


@pytest_asyncio.fixture
async def postgres_session_factory(require_postgres):
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    finally:
        await engine.dispose()


@pytest.fixture
def job_analysis_document_id() -> UUID:
    return uuid4()


@pytest_asyncio.fixture
async def cleanup_job_analysis_rows(
    postgres_session_factory,
    job_analysis_document_id: UUID,
):
    yield job_analysis_document_id
    async with postgres_session_factory() as session:
        exists = await session.scalar(
            text(
                "SELECT EXISTS ("
                " SELECT 1 FROM information_schema.tables"
                " WHERE table_schema = 'public'"
                " AND table_name = 'job_analysis_documents'"
                ")"
            )
        )
        if exists:
            params = {"document_id": str(job_analysis_document_id)}
            for table in (
                "job_analysis_journal",
                "job_analysis_opks_proposals",
                "job_analysis_opks_items",
                "job_analysis_proposals",
                "job_analysis_jd_tasks",
                "job_analysis_jd_duties",
                "job_analysis_documents",
            ):
                await session.execute(
                    text(f"DELETE FROM {table} WHERE document_id = :document_id"),  # noqa: S608
                    params,
                )
            await session.commit()
