"""JD Header persistence must survive every Current State reload."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.adapters.job_analysis_postgres import (
    PersistedJobAnalysisCorruption,
    SqlAlchemyJobAnalysisUnitOfWork,
)
from app.adapters.job_analysis_postgres import serialization as ser
from app.documents.authoring import load_document
from app.job_analysis.application import ActiveQuestion, DocumentRecord
from app.job_analysis.application.durable_turn import _load_state as load_turn_state
from app.opks.authoring import _locked_state
from app.opks.generation import (
    _load_state as load_opks_generation_state,
)
from app.core.domain import CurrentWorkModel, JdHeader


NOW = datetime(2026, 8, 9, 9, 0, tzinfo=UTC)
DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000052")


def _record_kwargs() -> dict[str, object]:
    return {
        "document_id": DOCUMENT_ID,
        "title": "門市營運專員",
        "work_model": CurrentWorkModel(),
        "active_question": ActiveQuestion(
            turn_id="consultant-opening",
            text="請說說這個職位最主要替誰解決什麼問題？",
        ),
        "authority_generation": 3,
        "created_at": NOW,
        "updated_at": NOW,
    }


def _record(header: JdHeader) -> DocumentRecord:
    return DocumentRecord(**_record_kwargs(), jd_header=header)


def test_document_record_requires_an_explicit_header():
    """Dropping the field must not silently create an empty authority partition."""

    with pytest.raises(TypeError, match="jd_header"):
        DocumentRecord(**_record_kwargs())


def test_document_serialization_round_trips_header_and_rejects_unknown_schema():
    header = JdHeader(
        competency_name="門市營運管理",
        work_description="負責門市日常營運與週報彙整。",
        competency_level=3,
    )
    row = SimpleNamespace(
        document_id=DOCUMENT_ID,
        title="門市營運專員",
        work_model_schema_id="job-analysis-work-model/1",
        work_model_json=CurrentWorkModel().model_dump(mode="json"),
        active_question_json=None,
        authority_generation=3,
        created_at=NOW,
        updated_at=NOW,
        jd_header_schema_id="job-analysis-jd-header/1",
        jd_header_json=header.model_dump(mode="json"),
    )

    assert ser.load_document(row).jd_header == header

    row.jd_header_schema_id = "job-analysis-jd-header/9"
    with pytest.raises(PersistedJobAnalysisCorruption, match="JD Header schema"):
        ser.load_document(row)


class _Documents:
    def __init__(self, record: DocumentRecord) -> None:
        self.record = record

    async def get(self, document_id: UUID, *, for_update: bool = False):
        assert document_id == self.record.document_id
        return self.record


class _Values:
    async def list(self, document_id: UUID):
        assert document_id == DOCUMENT_ID
        return ()


class _Duties:
    """Explicit empty Duty port for loaders that rebuild Current JD state."""

    async def list(self, document_id: UUID):
        assert document_id == DOCUMENT_ID
        return ()

    async def replace(self, document_id: UUID, duties) -> None:
        assert document_id == DOCUMENT_ID
        assert duties == ()


class _Journal:
    async def list_conversation_turns(self, document_id: UUID):
        assert document_id == DOCUMENT_ID
        return ()


class _ReadOnlyUnitOfWork:
    def __init__(self, record: DocumentRecord) -> None:
        self.documents = _Documents(record)
        self.duties = _Duties()
        self.tasks = _Values()
        self.proposals = _Values()
        self.opks = _Values()
        self.opks_proposals = _Values()
        self.journal = _Journal()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_every_current_state_loader_uses_the_persisted_header():
    header = JdHeader(
        competency_name="門市營運管理",
        work_description="負責門市日常營運與週報彙整。",
    )
    record = _record(header)
    uow = _ReadOnlyUnitOfWork(record)

    loaded = await load_document(lambda: uow, DOCUMENT_ID)
    _, opks_authoring_state = await _locked_state(uow, DOCUMENT_ID)

    assert loaded is not None
    assert loaded.state.jd_header == header
    assert (await load_turn_state(uow, record)).jd_header == header
    assert opks_authoring_state.jd_header == header
    assert (await load_opks_generation_state(uow, record)).jd_header == header


@pytest.mark.asyncio
async def test_postgres_authority_update_persists_the_header(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    initial = JdHeader(competency_name="門市營運管理")
    updated_header = initial.model_copy(
        update={
            "work_description": "負責門市日常營運與週報彙整。",
            "competency_level": 3,
        }
    )
    record = DocumentRecord(
        **{
            **_record_kwargs(),
            "document_id": document_id,
            "jd_header": initial,
        }
    )

    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        await uow.documents.create(record)
        changed = await uow.documents.update_authority(
            document_id,
            expected_generation=record.authority_generation,
            jd_header=updated_header,
            work_model=record.work_model,
            active_question=record.active_question,
            updated_at=NOW + timedelta(seconds=1),
        )
        assert changed
        await uow.commit()

    async with SqlAlchemyJobAnalysisUnitOfWork(postgres_session_factory) as uow:
        reloaded = await uow.documents.get(document_id)

    assert reloaded is not None
    assert reloaded.jd_header == updated_header
