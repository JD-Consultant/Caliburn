"""單一 kind 的 O/P/K/S/A 重排（切片 A T4）。"""

from __future__ import annotations

from uuid import UUID

import pytest

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.job_analysis.application import (
    IdempotencyConflict,
    InvalidOpksOrder,
    add_jd_task,
    add_opks_item,
    create_document,
    load_document,
    reorder_opks_items,
)
from app.job_analysis.domain import JdTaskFields, OpksEntityKind


pytestmark = pytest.mark.asyncio


def factory(session_factory):
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(session_factory)


async def seed(session_factory, document_id: UUID):
    """一份文件、一條 Task，兩個 OUTPUT 與一個 KNOWLEDGE。"""

    uow_factory = factory(session_factory)
    await create_document(uow_factory, document_id=document_id, title="門市營運專員")
    task = await add_jd_task(
        uow_factory,
        document_id=document_id,
        entry_id="task-a",
        fields=JdTaskFields(statement="每週彙整營運週報"),
    )
    first = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="o1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=(task.task_id,),
    )
    second = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="o2",
        entity_kind=OpksEntityKind.OUTPUT,
        text="異常追蹤表",
        task_refs=(task.task_id,),
    )
    knowledge = await add_opks_item(
        uow_factory,
        document_id=document_id,
        entry_id="k1",
        entity_kind=OpksEntityKind.KNOWLEDGE,
        text="營運指標定義",
        task_refs=(task.task_id,),
    )
    return uow_factory, first, second, knowledge


async def generation(uow_factory, document_id: UUID) -> int:
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id)
        assert record is not None
        return record.authority_generation


async def test_adding_items_appends_within_each_kind(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    _, first, second, knowledge = await seed(postgres_session_factory, document_id)

    assert (first.display_order, second.display_order) == (0, 1)
    # 位置在 kind 內各自從 0 起算，不跨 kind 連號
    assert knowledge.display_order == 0


async def test_reorder_renumbers_from_zero_and_survives_reload(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, first, second, _ = await seed(postgres_session_factory, document_id)

    reordered = await reorder_opks_items(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        entity_kind=OpksEntityKind.OUTPUT,
        ordered_entity_ids=(second.entity_id, first.entity_id),
    )

    assert [item.entity_id for item in reordered] == [
        second.entity_id,
        first.entity_id,
    ]
    assert [item.display_order for item in reordered] == [0, 1]
    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    outputs = [
        item
        for item in loaded.state.current_opks.items
        if item.entity_kind is OpksEntityKind.OUTPUT
    ]
    assert [item.entity_id for item in outputs] == [
        second.entity_id,
        first.entity_id,
    ]


async def test_reorder_leaves_other_kinds_untouched(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """O 只跟 O 換位置——範圍與 `display_order` 的唯一性一致。"""

    document_id = cleanup_job_analysis_rows
    uow_factory, first, second, knowledge = await seed(
        postgres_session_factory, document_id
    )

    await reorder_opks_items(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        entity_kind=OpksEntityKind.OUTPUT,
        ordered_entity_ids=(second.entity_id, first.entity_id),
    )

    loaded = await load_document(uow_factory, document_id)
    assert loaded is not None
    stored = {
        item.entity_id: item for item in loaded.state.current_opks.items
    }
    assert stored[knowledge.entity_id].display_order == 0
    assert stored[knowledge.entity_id].text == knowledge.text


async def test_reorder_replays_the_same_key(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, first, second, _ = await seed(postgres_session_factory, document_id)
    order = (second.entity_id, first.entity_id)
    reordered = await reorder_opks_items(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        entity_kind=OpksEntityKind.OUTPUT,
        ordered_entity_ids=order,
    )
    before = await generation(uow_factory, document_id)

    replayed = await reorder_opks_items(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        entity_kind=OpksEntityKind.OUTPUT,
        ordered_entity_ids=order,
    )

    assert replayed == reordered
    assert await generation(uow_factory, document_id) == before

    with pytest.raises(IdempotencyConflict):
        await reorder_opks_items(
            uow_factory,
            document_id=document_id,
            entry_id="order-1",
            entity_kind=OpksEntityKind.OUTPUT,
            ordered_entity_ids=(first.entity_id, second.entity_id),
        )


async def test_reorder_rejects_a_partial_or_repeated_order(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, first, _, _ = await seed(postgres_session_factory, document_id)

    with pytest.raises(InvalidOpksOrder):
        await reorder_opks_items(
            uow_factory,
            document_id=document_id,
            entry_id="order-1",
            entity_kind=OpksEntityKind.OUTPUT,
            ordered_entity_ids=(first.entity_id,),
        )
    with pytest.raises(InvalidOpksOrder):
        await reorder_opks_items(
            uow_factory,
            document_id=document_id,
            entry_id="order-2",
            entity_kind=OpksEntityKind.OUTPUT,
            ordered_entity_ids=(first.entity_id, first.entity_id),
        )


async def test_reorder_rejects_an_entity_from_another_kind(
    postgres_session_factory, cleanup_job_analysis_rows
):
    """拿 KNOWLEDGE 的 id 去排 OUTPUT，不能被當成合法輸入。"""

    document_id = cleanup_job_analysis_rows
    uow_factory, first, second, knowledge = await seed(
        postgres_session_factory, document_id
    )

    with pytest.raises(InvalidOpksOrder):
        await reorder_opks_items(
            uow_factory,
            document_id=document_id,
            entry_id="order-1",
            entity_kind=OpksEntityKind.OUTPUT,
            ordered_entity_ids=(second.entity_id, knowledge.entity_id),
        )


async def test_reorder_bumps_the_authority_generation(
    postgres_session_factory, cleanup_job_analysis_rows
):
    document_id = cleanup_job_analysis_rows
    uow_factory, first, second, _ = await seed(postgres_session_factory, document_id)
    before = await generation(uow_factory, document_id)

    await reorder_opks_items(
        uow_factory,
        document_id=document_id,
        entry_id="order-1",
        entity_kind=OpksEntityKind.OUTPUT,
        ordered_entity_ids=(second.entity_id, first.entity_id),
    )

    assert await generation(uow_factory, document_id) == before + 1
