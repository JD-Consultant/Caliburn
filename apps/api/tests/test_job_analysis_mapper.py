"""Domain/wire mapping at the greenfield job-analysis transport seam."""

from datetime import UTC, datetime
from uuid import UUID

from job_analysis_contract import (
    JdTaskWrite,
    OpksItemWrite,
    OpksProposalDecisionWrite,
)

from app.api.job_analysis_mapper import (
    to_consultation_view,
    to_jd_task_fields,
    to_opks_item_view,
    to_opks_proposal_decision,
    to_opks_write,
)
from app.job_analysis.application import (
    ActiveQuestion,
    ConversationTurn,
    DocumentRecord,
    JobAnalysisState,
    LoadedDocument,
    TurnSpeaker,
)
from app.job_analysis.domain import (
    JdHeader,
    CurrentWorkModel,
    EnablerKind,
    JdEntry,
    JdTask,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    Proposal,
    ProposalAction,
    ProposalStatus,
    ResponsibilityRole,
    SingleTaskTarget,
    SourceKind,
    SourceRef,
    SupportLink,
    Task,
)


def test_write_mapper_covers_and_normalizes_every_employee_editable_field():
    body = JdTaskWrite.model_validate(
        {
            "statement": " 每週彙整營運週報 ",
            "purpose_result": " 讓主管掌握營運狀況 ",
            "context": "   ",
            "frequency_text": " 每週一次 ",
            "responsibility_role": "primary",
            "enablers": [
                {"kind": "tool_system", "name": " Excel "},
                {"kind": "method", "name": " 交叉檢查 "},
            ],
        }
    )

    fields = to_jd_task_fields(body)

    assert fields.statement == "每週彙整營運週報"
    assert fields.purpose_result == "讓主管掌握營運狀況"
    assert fields.context is None
    assert fields.frequency_text == "每週一次"
    assert fields.responsibility_role is ResponsibilityRole.PRIMARY
    assert [(item.kind, item.name) for item in fields.enablers] == [
        (EnablerKind.TOOL_SYSTEM, "Excel"),
        (EnablerKind.METHOD, "交叉檢查"),
    ]


def test_empty_responsibility_role_normalizes_to_none():
    body = JdTaskWrite.model_validate(
        {
            "statement": "盤點耗材",
            "purpose_result": None,
            "context": None,
            "frequency_text": None,
            "responsibility_role": "",
            "enablers": [],
        }
    )

    assert to_jd_task_fields(body).responsibility_role is None


def test_opks_mapper_normalizes_employee_fields_and_exposes_only_quotes():
    body = OpksItemWrite(
        entity_kind="knowledge",
        text=" 營運資料定義 ",
        task_refs=["task-1"],
        indicator_refs=["indicator-1"],
    )

    kind, text, task_refs, indicator_refs = to_opks_write(body)

    assert kind is OpksEntityKind.KNOWLEDGE
    assert text == "營運資料定義"
    assert task_refs == ("task-1",)
    assert indicator_refs == ("indicator-1",)

    item = OpksItem(
        entity_id="knowledge-1",
        entity_kind=kind,
        text=text,
        task_refs=task_refs,
        indicator_refs=(),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="turn-secret",
                ),
                quote="我需要理解營運資料定義",
            ),
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.DIRECT_EDIT,
                    id="edit-secret",
                ),
            ),
        ),
    )
    payload = to_opks_item_view(item).model_dump(mode="json")

    assert payload["evidence_quotes"] == ["我需要理解營運資料定義"]
    assert "evidence_links" not in payload
    assert "turn-secret" not in str(payload)
    assert "edit-secret" not in str(payload)


def test_opks_proposal_decision_mapper_normalizes_optional_employee_text():
    edited = OpksProposalDecisionWrite(
        decision="edited",
        edited_text=" 員工確認的文字 ",
    )
    rejected = OpksProposalDecisionWrite(
        decision="rejected",
        reason=" 不適用於我的工作 ",
    )

    assert to_opks_proposal_decision(edited) == (
        "edited",
        "員工確認的文字",
        None,
    )
    assert to_opks_proposal_decision(rejected) == (
        "rejected",
        None,
        "不適用於我的工作",
    )


def test_consultation_view_keeps_history_without_leaking_internal_authority():
    now = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
    effective = SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-2"),
        quote="我每週彙整營運週報",
    )
    duplicate = effective.model_copy()
    direct_edit = SupportLink(
        source_ref=SourceRef(kind=SourceKind.DIRECT_EDIT, id="edit-1")
    )
    superseded = SupportLink(
        source_ref=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-old"),
        quote="舊說法",
        superseded_by=SourceRef(kind=SourceKind.EMPLOYEE_TURN, id="turn-2"),
    )
    task = Task(
        task_id="task-1",
        statement="每週彙整營運週報",
        action="彙整",
        object="營運週報",
        support_links=(effective, duplicate, direct_edit, superseded),
    )
    jd_task = JdTask(
        task_id="task-1",
        statement=task.statement,
        display_order=0,
    )
    proposal = Proposal(
        proposal_id="proposal-1",
        target=SingleTaskTarget(action=ProposalAction.ADD, task_id="task-1"),
        jd_before=(JdEntry(task_id="task-1"),),
        jd_after=(JdEntry(task_id="task-1", value=jd_task),),
        status=ProposalStatus.STALE,
        stale_reason="Current JD 已由員工修改",
    )
    opks_item = OpksItem(
        entity_id="output-1",
        entity_kind=OpksEntityKind.OUTPUT,
        text="營運週報",
        task_refs=("task-1",),
        evidence_links=(
            OpksEvidenceLink(
                source_ref=SourceRef(
                    kind=SourceKind.EMPLOYEE_TURN,
                    id="turn-2",
                ),
                quote="我每週彙整營運週報",
            ),
        ),
    )
    opks_proposal = OpksProposal(
        proposal_id="opks-proposal-1",
        operation_id="opks-operation-1",
        entity_id=opks_item.entity_id,
        entity_kind=opks_item.entity_kind,
        action=OpksProposalAction.REVISE,
        before=opks_item,
        after=opks_item.model_copy(update={"text": "每週營運週報"}),
        base_authority_generation=7,
        created_at=now,
    )
    loaded = LoadedDocument(
        document=DocumentRecord(
            document_id=UUID("00000000-0000-0000-0000-000000000045"),
            title="門市營運專員",
            jd_header=JdHeader(),
            work_model=CurrentWorkModel(tasks=(task,)),
            active_question=ActiveQuestion(turn_id="turn-3", text="週報交給誰？"),
            authority_generation=7,
            created_at=now,
            updated_at=now,
        ),
        state=JobAnalysisState(
            work_model=CurrentWorkModel(tasks=(task,)),
            current_jd=(jd_task,),
            proposals=(proposal,),
            current_opks={"items": [opks_item]},
            opks_proposals=(opks_proposal,),
        ),
        conversation_turns=(
            ConversationTurn(
                turn_id="turn-1",
                speaker=TurnSpeaker.CONSULTANT,
                text="先說說這個職位替誰解決問題？",
            ),
            ConversationTurn(
                turn_id="turn-2",
                speaker=TurnSpeaker.EMPLOYEE,
                text="我每週彙整營運週報",
            ),
        ),
    )

    view = to_consultation_view(loaded)
    payload = view.model_dump(mode="json")

    assert [turn["speaker"] for turn in payload["conversation"]] == [
        "consultant",
        "employee",
    ]
    assert payload["active_question"]["text"] == "週報交給誰？"
    assert payload["proposals"][0]["status"] == "stale"
    assert payload["proposals"][0]["evidence_quotes"] == [
        "我每週彙整營運週報"
    ]
    assert payload["tasks"][0]["task_id"] == "task-1"
    assert payload["opks_items"][0]["text"] == "營運週報"
    assert payload["opks_proposals"][0]["operation_id"] == "opks-operation-1"
    assert payload["opks_proposals"][0]["after"]["text"] == "每週營運週報"
    assert "authority_generation" not in payload
    assert "work_model" not in payload
