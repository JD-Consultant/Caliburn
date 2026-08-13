from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.adapters.langgraph.postgres import (
    DocumentNotFound,
    PendingSourceRequiresReconciliation,
    QuoteAnchorMismatch,
    SourceConflict,
    StaleRevision,
    UnknownEvidenceSource,
    open_postgres_consultant_runtime,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedEnabler,
    ApprovedEnablerKind,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedResponsibilityRole,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    SourceProcessingStatus,
    SourceValidity,
)


def _psycopg_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "")
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_new_consultant_documents() -> AsyncIterator[None]:
    """Keep repeated local runs from accumulating random document namespaces."""
    database_url = _psycopg_url()
    if not database_url:
        yield
        return

    async def catalog_ids() -> set[UUID]:
        async with await psycopg.AsyncConnection.connect(
            database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT to_regclass('public.consultant_documents')"
                )
                row = await cursor.fetchone()
                if row is None or row[0] is None:
                    return set()
                await cursor.execute("SELECT document_id FROM consultant_documents")
                return {row[0] for row in await cursor.fetchall()}

    before = await catalog_ids()
    yield
    created = await catalog_ids() - before
    if not created:
        return
    async with open_postgres_consultant_runtime(database_url) as runtime:
        for document_id in created:
            await runtime.delete_document(document_id)
    async with await psycopg.AsyncConnection.connect(
        database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.executemany(
                "DELETE FROM consultant_documents WHERE document_id = %s",
                [(document_id,) for document_id in created],
            )


@pytest.fixture
def consultant_database_url() -> str:
    value = _psycopg_url()
    if not value:
        pytest.skip("TEST_DATABASE_URL not set; consultant PostgreSQL test skipped")
    return value


def _document(document_id: UUID, *, suffix: str = "") -> ApprovedJobDocument:
    duty_id = uuid4()
    return ApprovedJobDocument(
        document_id=document_id,
        job_title=f"採購管理專員{suffix}",
        work_description=f"負責缺料檢查與採購安排{suffix}",
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="物料供應管理",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=uuid4(),
                duty_id=duty_id,
                statement="檢查缺料並安排採購",
                action="檢查並安排",
                object="缺料與採購",
                purpose_result="確保物料按期供應",
                display_order=0,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_create_reopen_and_delete_clear_the_whole_document_namespace(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.setup()
        await runtime.setup()
        created = await runtime.create_document(document_id, title="採購職務")
        async with await psycopg.AsyncConnection.connect(
            consultant_database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT updated_at FROM consultant_documents WHERE document_id = %s",
                    (document_id,),
                )
                created_updated_at = (await cursor.fetchone())[0]
        await asyncio.sleep(0.01)
        await runtime.record_employee_source(
            document_id=document_id,
            source_id=source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="我每天先檢查缺料，再依交期安排採購。",
        )
        async with await psycopg.AsyncConnection.connect(
            consultant_database_url, autocommit=True
        ) as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "SELECT updated_at FROM consultant_documents WHERE document_id = %s",
                    (document_id,),
                )
                source_updated_at = (await cursor.fetchone())[0]

        assert created.document_id == document_id
        assert created.revision == 0
        assert source_updated_at > created_updated_at

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        reopened = await runtime.reopen_document(document_id)
        source = await runtime.get_source(document_id, source_id)

        assert reopened.revision == 1
        assert reopened.source_count == 1
        assert source.text == "我每天先檢查缺料，再依交期安排採購。"

        await runtime.delete_document(document_id)
        await runtime.delete_document(document_id)

        with pytest.raises(DocumentNotFound):
            await runtime.reopen_document(document_id)
        assert await runtime.get_source_or_none(document_id, source_id) is None
        assert (
            await runtime.graph.aget_state(runtime.graph_config(document_id))
        ).values == {}


@pytest.mark.asyncio
async def test_source_is_immutable_and_correction_supersedes_without_quote_copy(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    original_id = uuid4()
    correction_id = uuid4()
    original_text = "  我每週一整理採購需求。\n"
    correction_text = "更正：我是每天整理採購需求。"

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        first = await runtime.record_employee_source(
            document_id=document_id,
            source_id=original_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=original_text,
        )
        replay = await runtime.record_employee_source(
            document_id=document_id,
            source_id=original_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=original_text,
        )

        assert first.revision == replay.revision == 1
        with pytest.raises(SourceConflict):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=original_id,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="同一 ID 被換成別的內容",
            )

        corrected = await runtime.record_employee_source(
            document_id=document_id,
            source_id=correction_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=correction_text,
            supersedes_source_id=original_id,
        )
        original = await runtime.get_source(document_id, original_id)
        correction = await runtime.get_source(document_id, correction_id)
        raw_state = await runtime.raw_state(document_id)

        assert corrected.revision == 2
        assert corrected.source_count == 2
        assert original.text == original_text
        assert original.positions[0].start == 0
        assert original.positions[0].end == len(original_text)
        assert original.validity is SourceValidity.SUPERSEDED
        assert original.superseded_by_source_id == correction_id
        assert correction.validity is SourceValidity.CURRENT
        assert correction.supersedes_source_id == original_id
        checkpoint_json = json.dumps(raw_state, ensure_ascii=False, default=str)
        assert original_text not in checkpoint_json
        assert correction_text not in checkpoint_json


@pytest.mark.asyncio
async def test_pending_source_reconciles_both_crash_windows(
    consultant_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    before_checkpoint_document = uuid4()
    after_checkpoint_document = uuid4()
    before_source = uuid4()
    after_source = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(before_checkpoint_document, title="A")
        await runtime.create_document(after_checkpoint_document, title="B")

        async def fail_after_store(_source: EmployeeSource) -> None:
            raise RuntimeError("after-store")

        monkeypatch.setattr(runtime, "_after_source_store", fail_after_store)
        with pytest.raises(RuntimeError, match="after-store"):
            await runtime.record_employee_source(
                document_id=before_checkpoint_document,
                source_id=before_source,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="先保存再分析",
            )
        pending = await runtime.get_source(before_checkpoint_document, before_source)
        assert pending.processing_status is SourceProcessingStatus.PENDING
        assert (await runtime.reopen_document(before_checkpoint_document)).source_count == 0
        with pytest.raises(PendingSourceRequiresReconciliation):
            await runtime.record_employee_source(
                document_id=before_checkpoint_document,
                source_id=uuid4(),
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="不能越過前一筆 pending input",
            )

        monkeypatch.setattr(runtime, "_after_source_store", runtime._noop_source_hook)
        resumed = await runtime.record_employee_source(
            document_id=before_checkpoint_document,
            source_id=before_source,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="先保存再分析",
        )
        assert resumed.source_count == 1
        assert (
            await runtime.get_source(before_checkpoint_document, before_source)
        ).processing_status is SourceProcessingStatus.COMMITTED

        async def fail_after_checkpoint(_source: EmployeeSource) -> None:
            raise RuntimeError("after-checkpoint")

        monkeypatch.setattr(runtime, "_after_source_checkpoint", fail_after_checkpoint)
        with pytest.raises(RuntimeError, match="after-checkpoint"):
            await runtime.record_employee_source(
                document_id=after_checkpoint_document,
                source_id=after_source,
                kind=EmployeeSourceKind.EMPLOYEE_TURN,
                text="checkpoint 後再標記完成",
            )
        checkpointed = await runtime.reopen_document(after_checkpoint_document)
        assert checkpointed.source_count == 1
        assert (
            await runtime.get_source(after_checkpoint_document, after_source)
        ).processing_status is SourceProcessingStatus.PENDING

        monkeypatch.setattr(
            runtime, "_after_source_checkpoint", runtime._noop_source_hook
        )
        reconciled = await runtime.record_employee_source(
            document_id=after_checkpoint_document,
            source_id=after_source,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="checkpoint 後再標記完成",
        )
        assert reconciled.source_count == 1
        assert reconciled.revision == checkpointed.revision


@pytest.mark.asyncio
async def test_direct_edit_mints_only_changed_employee_text_and_exports_checkpoint(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    first_source_id = uuid4()
    second_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        first_document = _document(document_id)
        first = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=first_document,
            source_id=first_source_id,
        )
        first_source = await runtime.get_source(document_id, first_source_id)
        revised_document = first_document.model_copy(
            update={"work_description": "負責缺料預警與緊急採購協調"}
        )
        second = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=revised_document,
            source_id=second_source_id,
        )
        second_source = await runtime.get_source(document_id, second_source_id)
        exported = await runtime.export_approved_document(document_id)
        replay = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=first.revision,
            document=revised_document,
            source_id=second_source_id,
        )

        assert second.revision == first.revision + 1
        assert replay.revision == second.revision
        assert first_source.text.splitlines() == [
            "採購管理專員",
            "負責缺料檢查與採購安排",
            "物料供應管理",
            "檢查缺料並安排採購",
            "檢查並安排",
            "缺料與採購",
            "確保物料按期供應",
        ]
        assert str(document_id) not in first_source.text
        assert str(first_document.duties[0].duty_id) not in first_source.text
        assert str(first_document.tasks[0].task_id) not in first_source.text
        assert second_source.kind is EmployeeSourceKind.DIRECT_EDIT
        assert second_source.text == "負責缺料預警與緊急採購協調"
        assert [anchor.model_dump(mode="json") for anchor in second_source.positions] == [
            {
                "document_path": "/work_description",
                "start": 0,
                "end": len(second_source.text),
            }
        ]
        assert first_document.job_title not in second_source.text
        assert exported == revised_document


@pytest.mark.asyncio
async def test_direct_edit_rejects_unknown_opks_evidence_before_writing_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    direct_edit_source_id = uuid4()
    unknown_source_id = uuid4()
    document = _document(document_id)
    document = document.model_copy(
        update={
            "opks": (
                ApprovedOpksItem(
                    item_id=uuid4(),
                    kind=ApprovedOpksKind.OUTPUT,
                    text="採購安排結果",
                    display_order=0,
                    task_ids=(document.tasks[0].task_id,),
                    evidence_source_ids=(unknown_source_id,),
                ),
            )
        }
    )

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")

        with pytest.raises(UnknownEvidenceSource, match=str(unknown_source_id)):
            await runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=document,
                source_id=direct_edit_source_id,
            )

        assert (
            await runtime.get_source_or_none(document_id, direct_edit_source_id)
            is None
        )

        valid_document = document.model_copy(
            update={
                "opks": (
                    document.opks[0].model_copy(
                        update={"evidence_source_ids": (direct_edit_source_id,)}
                    ),
                )
            }
        )
        committed = await runtime.apply_direct_edit(
            document_id=document_id,
            expected_revision=initial.revision,
            document=valid_document,
            source_id=direct_edit_source_id,
        )

        assert committed.approved_document == valid_document
        assert (
            await runtime.get_source(document_id, direct_edit_source_id)
        ).text.endswith("採購安排結果")


@pytest.mark.asyncio
async def test_generic_source_entry_cannot_mint_a_direct_edit_source(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(document_id, title="採購職務")
        with pytest.raises(ValueError, match="authority command"):
            await runtime.record_employee_source(
                document_id=document_id,
                source_id=uuid4(),
                kind=EmployeeSourceKind.DIRECT_EDIT,
                text="不能繞過 direct-edit authority command",
            )


def test_only_employee_turn_and_direct_edit_can_be_evidence_sources() -> None:
    common = {
        "source_id": str(uuid4()),
        "document_id": str(uuid4()),
        "speaker": "employee",
        "text": "內容",
        "text_sha256": "0" * 64,
        "created_at": datetime.now(UTC).isoformat(),
        "processing_status": "pending",
        "validity": "current",
    }
    for forbidden in ("model_output", "accepted", "rejected", "deferred", "reference"):
        with pytest.raises(ValidationError):
            EmployeeSource.model_validate({**common, "kind": forbidden})


def test_approved_document_preserves_manual_fields_and_opks_relationships() -> None:
    document_id = uuid4()
    duty_id = uuid4()
    task_id = uuid4()
    output_id = uuid4()
    indicator_id = uuid4()
    knowledge_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(
        document_id=document_id,
        competency_level=4,
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="物料供應管理",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=task_id,
                duty_id=duty_id,
                statement="檢查缺料並安排採購",
                action="檢查並安排",
                object="缺料與採購",
                frequency_text="每日",
                responsibility_role=ApprovedResponsibilityRole.PRIMARY,
                enablers=(
                    ApprovedEnabler(
                        kind=ApprovedEnablerKind.TOOL_SYSTEM,
                        name="ERP",
                    ),
                ),
                display_order=0,
                competency_level=3,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=output_id,
                kind=ApprovedOpksKind.OUTPUT,
                text="採購安排結果",
                display_order=0,
                task_ids=(task_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=indicator_id,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                text="缺料案件於交期前完成處置",
                display_order=0,
                task_ids=(task_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=knowledge_id,
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="物料需求規則",
                display_order=0,
                task_ids=(task_id,),
                indicator_ids=(indicator_id,),
                evidence_source_ids=(source_id,),
            ),
        ),
    )

    assert document.tasks[0].frequency_text == "每日"
    assert document.tasks[0].enablers[0].name == "ERP"
    assert document.opks[1].kind.value == "indicator"

    with pytest.raises(ValidationError, match="exactly one task"):
        ApprovedOpksItem(
            item_id=uuid4(),
            kind=ApprovedOpksKind.OUTPUT,
            text="沒有 Task 的 Output",
            display_order=1,
        )
    with pytest.raises(ValidationError, match="performance indicators"):
        ApprovedJobDocument.model_validate(
            document.model_copy(
                update={
                    "opks": (
                        *document.opks,
                        ApprovedOpksItem(
                            item_id=uuid4(),
                            kind=ApprovedOpksKind.SKILL,
                            text="錯誤連到 Output",
                            display_order=0,
                            indicator_ids=(output_id,),
                            evidence_source_ids=(source_id,),
                        ),
                    )
                }
            ).model_dump(mode="json")
        )


@pytest.mark.asyncio
async def test_same_thread_writers_are_serialized_and_one_becomes_stale(
    consultant_database_url: str,
) -> None:
    document_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        initial = await runtime.create_document(document_id, title="採購職務")
        outcomes = await asyncio.gather(
            runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=_document(document_id, suffix=" A"),
                source_id=uuid4(),
            ),
            runtime.apply_direct_edit(
                document_id=document_id,
                expected_revision=initial.revision,
                document=_document(document_id, suffix=" B"),
                source_id=uuid4(),
            ),
            return_exceptions=True,
        )

        assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
        assert sum(isinstance(outcome, StaleRevision) for outcome in outcomes) == 1
        assert (await runtime.reopen_document(document_id)).revision == 1


@pytest.mark.asyncio
async def test_quote_anchor_and_uuid_namespace_are_document_scoped(
    consultant_database_url: str,
) -> None:
    first_document = uuid4()
    second_document = uuid4()
    shared_source_id = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(first_document, title="A")
        await runtime.create_document(second_document, title="B")
        await runtime.record_employee_source(
            document_id=first_document,
            source_id=shared_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text=" 每天檢查缺料並通知採購。",
        )
        await runtime.record_employee_source(
            document_id=second_document,
            source_id=shared_source_id,
            kind=EmployeeSourceKind.EMPLOYEE_TURN,
            text="每週彙整盤點差異。",
        )

        anchor = await runtime.resolve_quote(
            first_document,
            shared_source_id,
            start=3,
            end=7,
            expected_quote="檢查缺料",
        )
        leading_space_anchor = await runtime.resolve_quote(
            first_document,
            shared_source_id,
            start=0,
            end=3,
            expected_quote=" 每天",
        )
        assert anchor.quote == "檢查缺料"
        assert leading_space_anchor.quote == " 每天"
        assert (
            await runtime.get_source(first_document, shared_source_id)
        ).text != (await runtime.get_source(second_document, shared_source_id)).text
        with pytest.raises(QuoteAnchorMismatch):
            await runtime.resolve_quote(
                first_document,
                shared_source_id,
                start=3,
                end=7,
                expected_quote="彙整盤點",
            )
        with pytest.raises((TypeError, ValueError)):
            runtime.source_namespace("employee%input")


@pytest.mark.asyncio
async def test_setup_is_strict_and_does_not_create_a_second_artifact_store(
    consultant_database_url: str,
) -> None:
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.setup()
        await runtime.setup()
        invariants = runtime.connection_invariants()
        assert invariants == {
            "saver_autocommit": True,
            "saver_dict_rows": True,
            "store_autocommit": True,
            "store_dict_rows": True,
            "strict_msgpack": True,
        }

    async with await psycopg.AsyncConnection.connect(
        consultant_database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name LIKE 'consultant_%'
                ORDER BY table_name
                """
            )
            assert [row[0] for row in await cursor.fetchall()] == [
                "consultant_documents"
            ]


@pytest.mark.asyncio
async def test_strict_serializer_rejects_an_unapproved_runtime_type(
    consultant_database_url: str,
) -> None:
    class UnsafeValue:
        pass

    class UnsafeState(TypedDict, total=False):
        payload: object

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        builder = StateGraph(UnsafeState)
        builder.add_node("persist", lambda state: state)
        builder.add_edge(START, "persist")
        builder.add_edge("persist", END)
        graph = builder.compile(checkpointer=runtime.saver)

        with pytest.raises(TypeError, match="not msgpack serializable"):
            await graph.ainvoke({"payload": UnsafeValue()}, config)
        await runtime.saver.adelete_thread(thread_id)


@pytest.mark.asyncio
async def test_completed_checkpoint_opens_under_an_additive_state_schema(
    consultant_database_url: str,
) -> None:
    class StateV1(TypedDict, total=False):
        document_id: str
        revision: int

    class StateV2(StateV1, total=False):
        schema_version: int
        future_projection: dict[str, str]

    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        v1_builder = StateGraph(StateV1)
        v1_builder.add_node("persist", lambda state: state)
        v1_builder.add_edge(START, "persist")
        v1_builder.add_edge("persist", END)
        v1_graph = v1_builder.compile(checkpointer=runtime.saver)
        await v1_graph.ainvoke({"document_id": thread_id, "revision": 3}, config)

        v2_builder = StateGraph(StateV2)
        v2_builder.add_node(
            "upgrade",
            lambda _state: {
                "schema_version": 2,
                "future_projection": {"status": "available"},
            },
        )
        v2_builder.add_edge(START, "upgrade")
        v2_builder.add_edge("upgrade", END)
        v2_graph = v2_builder.compile(checkpointer=runtime.saver)

        reopened = await v2_graph.aget_state(config)
        assert reopened.values == {"document_id": thread_id, "revision": 3}
        await v2_graph.ainvoke({}, config)
        upgraded = await v2_graph.aget_state(config)
        assert upgraded.values["document_id"] == thread_id
        assert upgraded.values["schema_version"] == 2
        assert upgraded.values["future_projection"] == {"status": "available"}
        await runtime.saver.adelete_thread(thread_id)


async def _storage_bytes(database_url: str, document_id: UUID) -> int:
    prefix = ".".join(("caliburn", "consultant", str(document_id), "sources"))
    thread_id = str(document_id)
    async with await psycopg.AsyncConnection.connect(
        database_url, autocommit=True
    ) as connection:
        async with connection.cursor() as cursor:
            await cursor.execute(
                """
                SELECT
                    COALESCE((SELECT SUM(pg_column_size(checkpoint) + pg_column_size(metadata))
                              FROM checkpoints WHERE thread_id = %s), 0)
                  + COALESCE((SELECT SUM(COALESCE(octet_length(blob), 0))
                              FROM checkpoint_blobs WHERE thread_id = %s), 0)
                  + COALESCE((SELECT SUM(COALESCE(octet_length(blob), 0))
                              FROM checkpoint_writes WHERE thread_id = %s), 0)
                  + COALESCE((SELECT SUM(pg_column_size(value))
                              FROM store WHERE prefix = %s), 0)
                """,
                (thread_id, thread_id, thread_id, prefix),
            )
            row = await cursor.fetchone()
            assert row is not None
            return int(row[0])


@pytest.mark.asyncio
async def test_store_owned_source_payload_has_linear_growth(
    consultant_database_url: str,
) -> None:
    short_document = uuid4()
    long_document = uuid4()

    async with open_postgres_consultant_runtime(consultant_database_url) as runtime:
        await runtime.create_document(short_document, title="短")
        await runtime.create_document(long_document, title="長")
        for document_id, count in ((short_document, 12), (long_document, 24)):
            for index in range(count):
                await runtime.record_employee_source(
                    document_id=document_id,
                    source_id=uuid4(),
                    kind=EmployeeSourceKind.EMPLOYEE_TURN,
                    text=f"{index:03d}:" + ("員工逐字工作內容。" * 80),
                )

        short_bytes = await _storage_bytes(consultant_database_url, short_document)
        long_bytes = await _storage_bytes(consultant_database_url, long_document)
        assert 1.4 < long_bytes / short_bytes < 2.6
        assert "員工逐字工作內容" not in json.dumps(
            await runtime.raw_state(long_document), ensure_ascii=False, default=str
        )

        await runtime.delete_document(short_document)
        await runtime.delete_document(long_document)
