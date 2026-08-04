"""JdHeader 進 Current State、authority CAS 與 PostgreSQL 往返（T2）。"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa

from app.adapters.job_analysis_postgres import serialization as ser
from app.adapters.job_analysis_postgres.repositories import (
    SqlAlchemyDocumentRepository,
)
from app.adapters.job_analysis_postgres.serialization import (
    PersistedJobAnalysisCorruption,
)
from app.job_analysis.application import (
    JD_HEADER_DIRECT_EDIT_SCHEMA_ID,
    DocumentRecord,
    JdHeaderDirectEditPayload,
    JobAnalysisState,
    JournalEntry,
)
from app.job_analysis.application.authority_commit import commit_authority_change
from app.job_analysis.domain import CurrentWorkModel, JdHeader


# 只有 async 測試需要 asyncio mark；serialization 那三個是純同步函式。
asyncio_test = pytest.mark.asyncio

NOW = datetime(2026, 8, 4, 9, 0, tzinfo=UTC)

FILLED = JdHeader(
    competency_name="資訊安全維運人員",
    occupation_category_name="資訊技術",
    occupation_name="資訊安全分析師",
    occupation_code="2529",
    industry_name="電腦程式設計、諮詢及相關服務業",
    industry_code="6201",
    work_description="維運企業資訊安全設備並處理資安事件。",
    competency_level=4,
    notes="本文件為客製職務說明書。",
)


def _record(document_id: UUID, *, jd_header: JdHeader) -> DocumentRecord:
    return DocumentRecord(
        document_id=document_id,
        title="資安維運",
        jd_header=jd_header,
        work_model=CurrentWorkModel(),
        active_question=None,
        authority_generation=0,
        created_at=NOW,
        updated_at=NOW,
    )


# ---- state ---------------------------------------------------------------


@asyncio_test
async def test_state_defaults_to_an_empty_header() -> None:
    state = JobAnalysisState()

    assert state.jd_header == JdHeader()
    assert state.jd_header.is_empty is True


@asyncio_test
async def test_commit_authority_change_persists_the_header() -> None:
    document_id = uuid4()
    seen: dict[str, object] = {}

    class _Documents:
        async def update_authority(self, doc_id: UUID, **kwargs: object) -> bool:
            seen.update(kwargs)
            return True

    class _Replace:
        async def replace(self, *args: object, **kwargs: object) -> None:
            return None

    class _Journal:
        async def add(self, entry: JournalEntry) -> None:
            return None

    class _Uow:
        documents = _Documents()
        tasks = _Replace()
        proposals = _Replace()
        opks = _Replace()
        opks_proposals = _Replace()
        journal = _Journal()

        async def commit(self) -> None:
            seen["committed"] = True

    await commit_authority_change(
        _Uow(),  # type: ignore[arg-type]
        record=_record(document_id, jd_header=JdHeader()),
        state=JobAnalysisState(jd_header=FILLED),
        updated_at=NOW,
    )

    assert seen["jd_header"] == FILLED
    assert seen["expected_generation"] == 0
    assert seen["committed"] is True


# ---- journal payload -----------------------------------------------------


@asyncio_test
async def test_header_direct_edit_payload_records_before_and_after() -> None:
    payload = JdHeaderDirectEditPayload(before=JdHeader(), after=FILLED)
    entry = JournalEntry(
        document_id=uuid4(),
        entry_id="idem-1",
        kind="direct_edit",
        payload_schema_id=JD_HEADER_DIRECT_EDIT_SCHEMA_ID,
        payload=payload,
        created_at=NOW,
    )

    assert entry.payload.before == JdHeader()
    assert entry.payload.after == FILLED


@asyncio_test
async def test_header_direct_edit_rejects_a_no_op_snapshot_pair() -> None:
    with pytest.raises(ValueError, match="must change"):
        JdHeaderDirectEditPayload(before=FILLED, after=FILLED)


@asyncio_test
async def test_header_direct_edit_rejects_a_mismatched_schema_id() -> None:
    with pytest.raises(ValueError, match="payload_schema_id"):
        JournalEntry(
            document_id=uuid4(),
            entry_id="idem-1",
            kind="direct_edit",
            payload_schema_id="job-analysis-direct-edit/1",
            payload=JdHeaderDirectEditPayload(before=JdHeader(), after=FILLED),
            created_at=NOW,
        )


# ---- serialization -------------------------------------------------------


def test_header_round_trips_through_the_stored_envelope() -> None:
    dumped = ser.dump_jd_header(FILLED)

    assert ser.load_jd_header(schema_id="job-analysis-jd-header/1", payload=dumped) == (
        FILLED
    )


def test_a_wrong_header_schema_id_fails_closed() -> None:
    with pytest.raises(PersistedJobAnalysisCorruption, match="schema"):
        ser.load_jd_header(schema_id="job-analysis-jd-header/99", payload={})


def test_a_broken_header_payload_fails_closed() -> None:
    with pytest.raises(PersistedJobAnalysisCorruption):
        ser.load_jd_header(
            schema_id="job-analysis-jd-header/1",
            payload={"competency_level": 9},
        )


# ---- PostgreSQL ----------------------------------------------------------


@asyncio_test
async def test_header_survives_create_and_reload(db_session) -> None:
    documents = SqlAlchemyDocumentRepository(db_session)
    document_id = uuid4()

    await documents.create(_record(document_id, jd_header=FILLED))
    await db_session.flush()
    loaded = await documents.get(document_id)

    assert loaded is not None
    assert loaded.jd_header == FILLED


@asyncio_test
async def test_update_authority_writes_the_header_under_the_same_cas(
    db_session,
) -> None:
    documents = SqlAlchemyDocumentRepository(db_session)
    document_id = uuid4()
    await documents.create(_record(document_id, jd_header=JdHeader()))
    await db_session.flush()

    updated = await documents.update_authority(
        document_id,
        expected_generation=0,
        jd_header=FILLED,
        work_model=CurrentWorkModel(),
        active_question=None,
        updated_at=NOW,
    )
    await db_session.flush()
    reloaded = await documents.get(document_id)

    assert updated is True
    assert reloaded is not None
    assert reloaded.jd_header == FILLED
    assert reloaded.authority_generation == 1

    stale = await documents.update_authority(
        document_id,
        expected_generation=0,
        jd_header=JdHeader(),
        work_model=CurrentWorkModel(),
        active_question=None,
        updated_at=NOW,
    )
    await db_session.flush()
    after_stale = await documents.get(document_id)

    assert stale is False
    assert after_stale is not None
    assert after_stale.jd_header == FILLED


@asyncio_test
async def test_documents_created_before_the_slice_load_as_an_empty_header(
    db_session,
) -> None:
    """0015 以空 header 回填既有列；舊文件必須照常載入。"""

    documents = SqlAlchemyDocumentRepository(db_session)
    document_id = uuid4()
    await documents.create(_record(document_id, jd_header=JdHeader()))
    await db_session.flush()

    loaded = await documents.get(document_id)

    assert loaded is not None
    assert loaded.jd_header == JdHeader()
    assert loaded.jd_header.is_empty is True


@asyncio_test
async def test_a_corrupt_stored_header_is_not_silently_accepted(
    db_session,
) -> None:
    documents = SqlAlchemyDocumentRepository(db_session)
    document_id = uuid4()
    await documents.create(_record(document_id, jd_header=FILLED))
    await db_session.flush()

    await db_session.execute(
        sa.text(
            "UPDATE job_analysis_documents "
            "SET jd_header_json = '{\"competency_level\": 99}'::jsonb "
            "WHERE document_id = :document_id"
        ),
        {"document_id": document_id},
    )
    db_session.expire_all()

    with pytest.raises(PersistedJobAnalysisCorruption):
        await documents.get(document_id)


# ---- the header is employee authority; AI turns must not touch it ---------


@asyncio_test
async def test_a_verified_ai_turn_preserves_the_employee_header(
    postgres_session_factory,
    cleanup_job_analysis_rows,
) -> None:
    """AI 對 header 沒有權限；一次成功的回合不得把員工填的表頭洗成空。"""

    from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
    from app.job_analysis.application import (
        commit_verified_turn,
        create_document,
        load_document,
        prepare_turn,
        put_jd_header,
    )

    from .test_job_analysis_durable_turn_postgres import (
        employee_turn,
        verified_add_result,
    )

    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="門市營運專員")
    await put_jd_header(
        uow_factory, document_id=document_id, entry_id="header-1", header=FILLED
    )

    employee = employee_turn()
    snapshot = await prepare_turn(
        uow_factory, document_id=document_id, employee_turn=employee
    )
    await commit_verified_turn(
        uow_factory,
        snapshot=snapshot,
        operation_id="operation-1",
        employee_turn=employee,
        operation_result=verified_add_result(),
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    assert loaded.state.jd_header == FILLED
    assert loaded.state.work_model.tasks  # 回合確實有做事，不是空跑


@asyncio_test
async def test_the_saved_header_reaches_the_next_task_analysis_packet(
    postgres_session_factory,
    cleanup_job_analysis_rows,
) -> None:
    """T5 的接線:員工存的 header 必須出現在下一輪送給模型的 packet 裡。"""

    from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
    from app.job_analysis.application import (
        create_document,
        prepare_turn,
        put_jd_header,
        render_context_packet,
    )

    from .test_job_analysis_durable_turn_postgres import employee_turn

    document_id = cleanup_job_analysis_rows
    uow_factory = lambda: SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory)
    await create_document(uow_factory, document_id=document_id, title="門市營運專員")
    await put_jd_header(
        uow_factory, document_id=document_id, entry_id="header-1", header=FILLED
    )

    snapshot = await prepare_turn(
        uow_factory, document_id=document_id, employee_turn=employee_turn()
    )
    overview = snapshot.packet.employee_written_overview
    rendered = render_context_packet(snapshot.packet)

    assert overview.competency_name == FILLED.competency_name
    assert overview.work_description == FILLED.work_description
    assert "維運企業資訊安全設備並處理資安事件。" in rendered
    # 只有兩個高訊號欄位過去；其餘 header 內容不得出現在送給模型的文字裡
    assert FILLED.notes is not None
    assert FILLED.notes not in rendered
    assert FILLED.occupation_code is not None
    assert FILLED.occupation_code not in rendered
