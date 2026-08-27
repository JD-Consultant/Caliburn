from __future__ import annotations

from uuid import UUID

import pytest

from app.consultant.document_commands import (
    CascadeDeleteDuty,
    CreateAttitude,
    CreateDuty,
    CreateOpks,
    CreateTask,
    DeleteOwnedOpks,
    DeleteSharedOpks,
    DissolveDuty,
    DocumentCommandConfirmationRequired,
    DocumentCommandError,
    LinkSharedOpks,
    MoveTask,
    ReorderEntity,
    UnlinkSharedOpks,
    DeleteTask,
    plan_document_structure_command,
    preview_document_structure_command,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000801")
DUTY_1 = UUID("00000000-0000-0000-0000-000000000802")
DUTY_2 = UUID("00000000-0000-0000-0000-000000000803")
TASK_1 = UUID("00000000-0000-0000-0000-000000000804")
TASK_2 = UUID("00000000-0000-0000-0000-000000000805")
TASK_3 = UUID("00000000-0000-0000-0000-000000000806")
OUTPUT_1 = UUID("00000000-0000-0000-0000-000000000807")
INDICATOR_1 = UUID("00000000-0000-0000-0000-000000000808")
KNOWLEDGE_1 = UUID("00000000-0000-0000-0000-000000000809")
SKILL_1 = UUID("00000000-0000-0000-0000-00000000080a")
ATTITUDE_1 = UUID("00000000-0000-0000-0000-00000000080b")
SOURCE_ID = UUID("00000000-0000-0000-0000-00000000080c")
NEW_ID = UUID("00000000-0000-0000-0000-00000000080d")


def _task(task_id: UUID, duty_id: UUID, statement: str, order: int) -> ApprovedTask:
    return ApprovedTask(
        task_id=task_id,
        duty_id=duty_id,
        statement=statement,
        action="處理",
        object=statement,
        display_order=order,
        competency_level=3,
    )


def _document() -> ApprovedJobDocument:
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        duties=(
            ApprovedDuty(duty_id=DUTY_1, statement="職責一", display_order=0),
            ApprovedDuty(duty_id=DUTY_2, statement="職責二", display_order=1),
        ),
        tasks=(
            _task(TASK_1, DUTY_1, "任務一", 0),
            _task(TASK_2, DUTY_1, "任務二", 1),
            _task(TASK_3, DUTY_2, "任務三", 2),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=OUTPUT_1,
                kind=ApprovedOpksKind.OUTPUT,
                text="產出一",
                display_order=0,
                task_ids=(TASK_1,),
                evidence_source_ids=(SOURCE_ID,),
            ),
            ApprovedOpksItem(
                item_id=INDICATOR_1,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                text="指標一",
                display_order=0,
                task_ids=(TASK_1,),
                evidence_source_ids=(SOURCE_ID,),
            ),
            ApprovedOpksItem(
                item_id=KNOWLEDGE_1,
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="知識一",
                display_order=0,
                task_ids=(TASK_1, TASK_3),
                indicator_ids=(INDICATOR_1,),
                evidence_source_ids=(SOURCE_ID,),
            ),
            ApprovedOpksItem(
                item_id=SKILL_1,
                kind=ApprovedOpksKind.SKILL,
                text="技能一",
                display_order=0,
                task_ids=(TASK_1,),
                evidence_source_ids=(SOURCE_ID,),
            ),
            ApprovedOpksItem(
                item_id=ATTITUDE_1,
                kind=ApprovedOpksKind.ATTITUDE,
                text="態度一",
                display_order=0,
                evidence_source_ids=(SOURCE_ID,),
            ),
        ),
    )


def _plan(command, *, issued_entity_id: UUID = NEW_ID):
    return plan_document_structure_command(
        _document(),
        command,
        issued_entity_id=issued_entity_id,
        employee_source_id=SOURCE_ID,
    )


def test_dissolve_duty_unassigns_tasks_and_preserves_their_full_subtrees() -> None:
    plan = _plan(DissolveDuty(duty_id=DUTY_1))

    assert [item.duty_id for item in plan.current_after.duties] == [DUTY_2]
    assert [item.duty_id for item in plan.current_after.tasks] == [None, None, DUTY_2]
    assert plan.current_after.opks == _document().opks
    assert plan.blast_radius.task_count == 2


def test_cascade_duty_requires_preview_and_respects_opks_ownership() -> None:
    command = CascadeDeleteDuty(duty_id=DUTY_1)
    preview = preview_document_structure_command(_document(), command)

    assert preview.confirmation_required is True
    assert preview.task_count == 2
    assert preview.output_count == 1
    assert preview.indicator_count == 1
    assert preview.shared_link_count == 2
    with pytest.raises(DocumentCommandConfirmationRequired):
        _plan(command)

    plan = _plan(command.model_copy(update={"preview_digest": preview.preview_digest}))
    assert [item.duty_id for item in plan.current_after.duties] == [DUTY_2]
    assert [item.task_id for item in plan.current_after.tasks] == [TASK_3]
    assert {item.item_id for item in plan.current_after.opks} == {
        KNOWLEDGE_1,
        SKILL_1,
        ATTITUDE_1,
    }
    knowledge = next(
        item for item in plan.current_after.opks if item.item_id == KNOWLEDGE_1
    )
    skill = next(item for item in plan.current_after.opks if item.item_id == SKILL_1)
    assert knowledge.task_ids == (TASK_3,)
    assert knowledge.indicator_ids == ()
    assert skill.task_ids == ()


def test_move_or_unassign_task_preserves_the_complete_subtree() -> None:
    moved = _plan(MoveTask(task_id=TASK_1, destination_duty_id=DUTY_2))
    unassigned = _plan(MoveTask(task_id=TASK_1, destination_duty_id=None))

    assert moved.current_after.tasks[0].duty_id == DUTY_2
    assert unassigned.current_after.tasks[0].duty_id is None
    assert moved.current_after.opks == _document().opks
    assert unassigned.current_after.opks == _document().opks


def test_delete_task_deletes_owned_op_and_unlinks_but_keeps_shared_ks() -> None:
    plan = _plan(DeleteTask(task_id=TASK_1))

    assert {item.task_id for item in plan.current_after.tasks} == {TASK_2, TASK_3}
    assert {item.item_id for item in plan.current_after.opks} == {
        KNOWLEDGE_1,
        SKILL_1,
        ATTITUDE_1,
    }
    knowledge = next(
        item for item in plan.current_after.opks if item.item_id == KNOWLEDGE_1
    )
    skill = next(item for item in plan.current_after.opks if item.item_id == SKILL_1)
    assert knowledge.task_ids == (TASK_3,)
    assert knowledge.indicator_ids == ()
    assert skill.task_ids == ()
    assert {
        f"/opks/{OUTPUT_1}",
        f"/opks/{INDICATOR_1}",
        f"/opks/{KNOWLEDGE_1}",
        f"/opks/{SKILL_1}",
    } <= set(plan.touched_paths)


def test_shared_ks_link_and_unlink_never_delete_the_canonical_item() -> None:
    linked = _plan(LinkSharedOpks(item_id=KNOWLEDGE_1, task_id=TASK_2))
    unlinked = _plan(UnlinkSharedOpks(item_id=SKILL_1, task_id=TASK_1))

    knowledge = next(
        item for item in linked.current_after.opks if item.item_id == KNOWLEDGE_1
    )
    skill = next(
        item for item in unlinked.current_after.opks if item.item_id == SKILL_1
    )
    assert knowledge.task_ids == (TASK_1, TASK_2, TASK_3)
    assert skill.task_ids == ()
    assert skill.item_id == SKILL_1


def test_owned_opks_delete_prunes_indicator_dependencies() -> None:
    plan = _plan(DeleteOwnedOpks(item_id=INDICATOR_1))

    assert INDICATOR_1 not in {item.item_id for item in plan.current_after.opks}
    knowledge = next(
        item for item in plan.current_after.opks if item.item_id == KNOWLEDGE_1
    )
    assert knowledge.indicator_ids == ()


def test_permanent_shared_ks_delete_requires_preview_when_linked() -> None:
    command = DeleteSharedOpks(item_id=KNOWLEDGE_1)
    preview = preview_document_structure_command(_document(), command)

    assert preview.confirmation_required is True
    assert preview.shared_link_count == 2
    with pytest.raises(DocumentCommandConfirmationRequired):
        _plan(command)
    plan = _plan(command.model_copy(update={"preview_digest": preview.preview_digest}))
    assert KNOWLEDGE_1 not in {item.item_id for item in plan.current_after.opks}


def test_create_commands_use_application_identity_and_correct_axis_ownership() -> None:
    duty = _plan(CreateDuty(name="新職責"))
    task = _plan(
        CreateTask(
            duty_id=None,
            statement="整理法規更新",
            action="整理",
            object="法規更新",
            competency_level=3,
        )
    )
    output = _plan(
        CreateOpks(
            task_id=TASK_1,
            kind=ApprovedOpksKind.OUTPUT,
            text="法規摘要",
        )
    )
    knowledge = _plan(
        CreateOpks(
            task_id=TASK_1,
            kind=ApprovedOpksKind.KNOWLEDGE,
            text="勞動法規知識",
        )
    )
    attitude = _plan(CreateAttitude(text="審慎"))

    assert duty.current_after.duties[-1].duty_id == NEW_ID
    assert task.current_after.tasks[-1].task_id == NEW_ID
    assert task.current_after.tasks[-1].duty_id is None
    assert output.current_after.opks[-1].task_ids == (TASK_1,)
    assert knowledge.current_after.opks[-1].task_ids == (TASK_1,)
    assert attitude.current_after.opks[-1].task_ids == ()
    for plan in (output, knowledge, attitude):
        assert plan.current_after.opks[-1].item_id == NEW_ID
        assert plan.current_after.opks[-1].evidence_source_ids == (SOURCE_ID,)


def test_reorder_changes_only_same_level_orders_and_preserves_identity() -> None:
    duties = _plan(
        ReorderEntity(
            entity_kind="duty",
            entity_id=DUTY_2,
            parent_id=None,
            before_entity_id=DUTY_1,
        )
    )
    tasks = _plan(
        ReorderEntity(
            entity_kind="task",
            entity_id=TASK_2,
            parent_id=DUTY_1,
            before_entity_id=TASK_1,
        )
    )

    assert [(item.duty_id, item.display_order) for item in duties.current_after.duties] == [
        (DUTY_2, 0),
        (DUTY_1, 1),
    ]
    assert [(item.task_id, item.display_order) for item in tasks.current_after.tasks] == [
        (TASK_2, 0),
        (TASK_1, 1),
        (TASK_3, 2),
    ]
    assert tasks.current_after.opks == _document().opks
    assert {f"/tasks/{TASK_1}", f"/tasks/{TASK_2}"} <= set(
        tasks.touched_paths
    )


def test_reorder_rejects_moving_an_entity_before_itself_as_a_typed_error() -> None:
    with pytest.raises(DocumentCommandError, match="before itself"):
        _plan(
            ReorderEntity(
                entity_kind="task",
                entity_id=TASK_1,
                parent_id=DUTY_1,
                before_entity_id=TASK_1,
            )
        )


def test_every_plan_carries_one_bounded_inverse_and_touched_stable_scope() -> None:
    plan = _plan(MoveTask(task_id=TASK_1, destination_duty_id=DUTY_2))

    assert plan.inverse_command["operation"] == "restore_documents"
    assert plan.inverse_command["current_document"]["document_id"] == str(DOCUMENT_ID)
    assert f"/tasks/{TASK_1}" in plan.touched_paths
