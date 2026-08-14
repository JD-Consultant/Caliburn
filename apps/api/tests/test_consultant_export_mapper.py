from uuid import uuid4

from app.api.consultant_export_mapper import assemble_approved_export_document
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
)


def test_new_approved_document_projects_to_the_retained_xlsx_shape() -> None:
    document_id = uuid4()
    source_id = uuid4()
    duty_id = uuid4()
    assigned_id = uuid4()
    orphan_id = uuid4()
    indicator_id = uuid4()
    document = ApprovedJobDocument(
        document_id=document_id,
        job_title="採購專員",
        occupation_name="採購人員",
        occupation_code="EMPLOYEE-CLASSIFICATION",
        competency_level=3,
        duties=(
            ApprovedDuty(duty_id=duty_id, statement="採購作業", display_order=0),
        ),
        tasks=(
            ApprovedTask(
                task_id=assigned_id,
                duty_id=duty_id,
                statement="整理採購需求",
                action="整理",
                object="採購需求",
                display_order=0,
                competency_level=2,
            ),
            ApprovedTask(
                task_id=orphan_id,
                duty_id=None,
                statement="追蹤緊急缺料",
                action="追蹤",
                object="緊急缺料",
                display_order=1,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=uuid4(),
                kind=ApprovedOpksKind.OUTPUT,
                text="採購需求清單",
                display_order=0,
                task_ids=(assigned_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=indicator_id,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                text="需求內容完整",
                display_order=0,
                task_ids=(assigned_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=uuid4(),
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="採購流程知識",
                display_order=0,
                task_ids=(assigned_id,),
                indicator_ids=(indicator_id,),
                evidence_source_ids=(source_id,),
            ),
            ApprovedOpksItem(
                item_id=uuid4(),
                kind=ApprovedOpksKind.SKILL,
                text="需求彙整技能",
                display_order=0,
                task_ids=(assigned_id,),
                evidence_source_ids=(source_id,),
            ),
        ),
    )

    exported = assemble_approved_export_document(document, title="採購職務")

    task = exported.duties[0].tasks[0]
    assert exported.header.competency_name == "採購專員"
    assert exported.header.occupation_code == "EMPLOYEE-CLASSIFICATION"
    assert task.position_code == "T1.1"
    assert task.competency_level == 2
    assert task.outputs[0].position_code == "O1.1.1"
    assert task.indicators[0].position_code == "P1.1.1"
    assert task.knowledge[0].position_code == "K01"
    assert task.skills[0].position_code == "S01"
    assert exported.unassigned_tasks[0].task_id == str(orphan_id)
    assert exported.unassigned_tasks[0].position_code is None
