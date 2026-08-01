"""Employee OPKS edits share the Current JD authority transaction."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    IdempotencyConflict,
    OpksDirectEditPayload,
    OpksItemNotFound,
    add_jd_task,
    add_opks_item,
    create_document,
    delete_jd_task,
    delete_opks_item,
    edit_opks_item,
    load_document,
)
from app.job_analysis.domain import (
    JdTaskFields,
    OpksEntityKind,
    SourceKind,
    SourceRef,
)


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


async def seed_task(session_factory, document_id, *, entry_id: str, statement: str):
    uow_factory = factory(session_factory)
    await create_document(
        uow_factory,
        document_id=document_id,
        title="門市營運專員",
    )
    return await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id=entry_id,
        fields=JdTaskFields(statement=statement),
    )


async def test_add_edit_delete_reload_and_idempotent_replay(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )

    created = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-add-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task.task_id,),
    )
    replay = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-add-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task.task_id,),
    )
    assert replay == created
    assert created.entity_id == "direct-opks-add-1-output"
    assert created.evidence_links[0].source_ref == SourceRef(
        kind=SourceKind.DIRECT_EDIT,
        id="opks-add-1",
    )

    with pytest.raises(IdempotencyConflict):
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="opks-add-1",
            entity_kind=OpksEntityKind.OUTPUT,
            text="另一份產出",
            task_refs=(task.task_id,),
        )

    edited = await edit_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-edit-1",
        entity_id=created.entity_id,
        entity_kind=OpksEntityKind.OUTPUT,
        text="每週營運週報",
        task_refs=(task.task_id,),
    )
    assert edited.entity_id == created.entity_id
    assert edited.text == "每週營運週報"
    assert [link.source_ref.id for link in edited.evidence_links] == ["opks-edit-1"]

    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-delete-1",
        entity_id=created.entity_id,
    )
    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="opks-delete-1",
        entity_id=created.entity_id,
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_opks.items == ()
    assert loaded.document.authority_generation == 4

    async with uow_factory() as uow:
        add_entry = await uow.journal.get(document_id, "opks-add-1")
        edit_entry = await uow.journal.get(document_id, "opks-edit-1")
        delete_entry = await uow.journal.get(document_id, "opks-delete-1")
    assert isinstance(add_entry.payload, OpksDirectEditPayload)
    assert add_entry.payload.before is None
    assert add_entry.payload.after == created
    assert edit_entry.payload.before == created
    assert edit_entry.payload.after == edited
    assert delete_entry.payload.before == edited
    assert delete_entry.payload.after is None


async def test_invalid_manual_opks_edits_fail_before_writing(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )

    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="blank",
            entity_kind=OpksEntityKind.OUTPUT,
            text="",
            task_refs=(task.task_id,),
        )
    with pytest.raises(ValidationError, match="unknown Current JD task refs"):
        await add_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="unknown-task",
            entity_kind=OpksEntityKind.OUTPUT,
            text="週報",
            task_refs=("missing",),
        )
    with pytest.raises(OpksItemNotFound):
        await edit_opks_item(
            uow_factory,
            document_id=document_id,
            entry_id="missing-item",
            entity_id="missing",
            entity_kind=OpksEntityKind.KNOWLEDGE,
            text="報表知識",
        )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    assert loaded.state.current_opks.items == ()
    assert loaded.document.authority_generation == 1


async def test_task_delete_prunes_owned_opks_and_unlinks_shared_knowledge_skill(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    first = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )
    second = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="task-2",
        fields=JdTaskFields(statement="每月盤點門市耗材"),
    )
    output = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="output",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(first.task_id,),
    )
    indicator = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="indicator",
        entity_kind=OpksEntityKind.INDICATOR,
        text="依期限完成週報",
        task_refs=(first.task_id,),
    )
    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="knowledge",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運數據定義",
        task_refs=(first.task_id, second.task_id),
        indicator_refs=(indicator.entity_id,),
    )
    skill = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="skill",
        entity_kind=OpksEntityKind.SKILL,
        text="試算表整理",
        task_refs=(first.task_id,),
    )
    attitude = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="attitude",
        entity_kind=OpksEntityKind.ATTITUDE,
        text="主動釐清異常",
    )

    await delete_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="delete-task-1",
        task_id=first.task_id,
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    by_id = {
        item.entity_id: item for item in loaded.state.current_opks.items
    }
    assert output.entity_id not in by_id
    assert indicator.entity_id not in by_id
    assert by_id[knowledge.entity_id].task_refs == (second.task_id,)
    assert by_id[knowledge.entity_id].indicator_refs == ()
    assert by_id[skill.entity_id].task_refs == ()
    assert by_id[attitude.entity_id] == attitude


async def test_indicator_delete_unlinks_knowledge_and_skill_in_the_same_commit(
    postgres_session_factory,
    cleanup_job_analysis_rows,
):
    document_id = cleanup_job_analysis_rows
    uow_factory = factory(postgres_session_factory)
    task = await seed_task(
        postgres_session_factory,
        document_id,
        entry_id="task-1",
        statement="每週彙整營運週報",
    )
    indicator = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="indicator",
        entity_kind=OpksEntityKind.INDICATOR,
        text="依期限完成週報",
        task_refs=(task.task_id,),
    )
    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="knowledge",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運數據定義",
        indicator_refs=(indicator.entity_id,),
    )
    skill = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="skill",
        entity_kind=OpksEntityKind.SKILL,
        text="試算表整理",
        indicator_refs=(indicator.entity_id,),
    )

    await delete_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="delete-indicator",
        entity_id=indicator.entity_id,
    )
    loaded = await load_document(uow_factory, document_id)

    assert loaded is not None
    by_id = {item.entity_id: item for item in loaded.state.current_opks.items}
    assert indicator.entity_id not in by_id
    assert by_id[knowledge.entity_id].indicator_refs == ()
    assert by_id[skill.entity_id].indicator_refs == ()
