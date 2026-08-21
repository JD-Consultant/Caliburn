from __future__ import annotations

import json
from collections.abc import Mapping
from uuid import UUID, uuid5
from datetime import UTC, datetime

import pytest

from app.consultant.candidate_publication import (
    CandidateCheckRequest,
    CandidatePublicationStale,
    CheckedCandidateReceipt,
    check_candidate_document,
    publish_checked_candidate,
    resource_digest,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    SourceProcessingStatus,
    RunReceipt,
    RunStatus,
    initial_thread_state,
)
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    project_candidate_files,
)


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000501")
RUN_ID = UUID("00000000-0000-0000-0000-000000000502")
OTHER_RUN_ID = UUID("00000000-0000-0000-0000-000000000503")
DUTY_ID = UUID("00000000-0000-0000-0000-000000000511")
TASK_ID = UUID("00000000-0000-0000-0000-000000000512")
OUTPUT_ID = UUID("00000000-0000-0000-0000-000000000513")
INDICATOR_ID = UUID("00000000-0000-0000-0000-000000000514")
KNOWLEDGE_ID = UUID("00000000-0000-0000-0000-000000000515")
SKILL_ID = UUID("00000000-0000-0000-0000-000000000516")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000517")

SKILLS = (
    "output",
    "performance-indicator",
    "knowledge",
    "skill",
)


def _source() -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=SOURCE_ID,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text="員工說明採購流程，核對訂單並回報結果。",
    ).model_copy(update={"processing_status": SourceProcessingStatus.COMMITTED})


def _document() -> ApprovedJobDocument:
    evidence = (SOURCE_ID,)
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購專員",
        work_description="管理採購流程。",
        duties=(
            ApprovedDuty(
                duty_id=DUTY_ID,
                statement="管理採購作業",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=TASK_ID,
                duty_id=DUTY_ID,
                statement="核對訂單",
                action="核對",
                object="訂單",
                purpose_result="避免錯誤出貨",
                display_order=0,
                competency_level=4,
            ),
        ),
        opks=(
            ApprovedOpksItem(
                item_id=OUTPUT_ID,
                kind=ApprovedOpksKind.OUTPUT,
                text="完成正確訂單",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=INDICATOR_ID,
                kind=ApprovedOpksKind.PERFORMANCE_INDICATOR,
                text="訂單錯誤率低",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=KNOWLEDGE_ID,
                kind=ApprovedOpksKind.KNOWLEDGE,
                text="訂單規則",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
            ApprovedOpksItem(
                item_id=SKILL_ID,
                kind=ApprovedOpksKind.SKILL,
                text="細節核對",
                display_order=0,
                task_ids=(TASK_ID,),
                evidence_source_ids=evidence,
            ),
        ),
    )


def _catalog() -> WorkspaceCatalog:
    return WorkspaceCatalog.from_snapshot(_document(), sources=(_source(),))


def _files() -> dict[str, str]:
    return project_candidate_files(_catalog(), run_id=RUN_ID)


def _request(
    files: Mapping[str, str],
    *,
    run_id: UUID = RUN_ID,
    baseline_revision: int = 7,
    candidate_revision: int = 1,
    loaded_skill_ids: tuple[str, ...] = SKILLS,
    check_call_id: str = "check-001",
) -> CandidateCheckRequest:
    return CandidateCheckRequest(
        document_id=DOCUMENT_ID,
        run_id=run_id,
        baseline_revision=baseline_revision,
        candidate_revision=candidate_revision,
        files=dict(files),
        check_call_id=check_call_id,
        selected_skill_ids=SKILLS,
        loaded_skill_ids=loaded_skill_ids,
    )


def _json_edit(files: dict[str, str], path: str, **updates: object) -> None:
    payload = json.loads(files[path])
    payload.update(updates)
    files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _add_evidence(payload: dict[str, object], skill_id: str) -> None:
    payload["evidence"] = [
        {
            "source_handle": "source-001",
            "quote": "核對訂單",
            "skill_ids": [skill_id],
        }
    ]


def _add_resource(
    files: dict[str, str],
    *,
    kind: str,
    handle: str,
    text: str,
    skill_id: str,
) -> None:
    payload: dict[str, object] = {
        "handle": handle,
        "kind": kind,
        "text": text,
        "task_handles": ["task-001"],
        "indicator_handles": [],
    }
    _add_evidence(payload, skill_id)
    prefix = {"output": "o", "indicator": "p", "knowledge": "k", "skill": "s"}[kind]
    files[f"/candidate/{RUN_ID}/opks/{prefix}/{handle}.json"] = (
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


def _add_duty(files: dict[str, str], handle: str) -> None:
    files[f"/candidate/{RUN_ID}/duties/{handle}.json"] = json.dumps(
        {"handle": handle, "statement": "新增職責"},
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _add_task(files: dict[str, str], handle: str) -> None:
    files[f"/candidate/{RUN_ID}/tasks/{handle}.json"] = json.dumps(
        {
            "handle": handle,
            "duty_handle": "duty-001",
            "statement": "新增工作",
            "action": "處理",
            "object": "採購資料",
            "purpose_result": "完成工作",
            "context": None,
            "frequency_text": None,
            "responsibility_role": "primary",
            "enablers": [],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _checked(files: Mapping[str, str]) -> CheckedCandidateReceipt:
    result = check_candidate_document(
        _request(files),
        catalog=_catalog(),
        existing_review_queue={},
        interview_work={},
    )
    assert result.status == "checked", result.issues
    assert result.receipt is not None
    return result.receipt


def test_header_edit_emits_one_reviewable_revise_action() -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked"
    assert [(action.operation.value, action.path, action.after) for action in result.actions] == [
        ("revise", "/job_title", "資深採購專員")
    ]


@pytest.mark.parametrize(
    ("resource", "updates", "expected_path"),
    [
        ("duties/duty-001.json", {"statement": "管理國際採購作業"}, "/duties/" + str(DUTY_ID) + "/statement"),
        ("tasks/task-001.json", {"statement": "核對國際訂單"}, "/tasks/" + str(TASK_ID) + "/statement"),
        ("opks/o/o-001.json", {"text": "完成國際正確訂單"}, "/opks/" + str(OUTPUT_ID) + "/text"),
        ("opks/p/p-001.json", {"text": "國際訂單錯誤率低"}, "/opks/" + str(INDICATOR_ID) + "/text"),
        ("opks/k/k-001.json", {"text": "國際訂單規則"}, "/opks/" + str(KNOWLEDGE_ID) + "/text"),
        ("opks/s/s-001.json", {"text": "國際細節核對"}, "/opks/" + str(SKILL_ID) + "/text"),
    ],
)
def test_existing_duty_task_and_opks_edit_emits_fixed_semantic_path(
    resource: str,
    updates: dict[str, object],
    expected_path: str,
) -> None:
    files = _files()
    path = f"/candidate/{RUN_ID}/{resource}"
    _json_edit(files, path, **updates)
    if path.startswith(f"/candidate/{RUN_ID}/opks/"):
        payload = json.loads(files[path])
        _add_evidence(payload, {"o": "output", "p": "performance-indicator", "k": "knowledge", "s": "skill"}[path.split("/")[-2]])
        files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked", result.issues
    assert expected_path in [action.path for action in result.actions]


@pytest.mark.parametrize(
    ("kind", "handle", "skill_id"),
    [
        ("output", "o-101", "output"),
        ("indicator", "p-101", "performance-indicator"),
        ("knowledge", "k-101", "knowledge"),
        ("skill", "s-101", "skill"),
    ],
)
def test_new_opks_create_gets_application_uuid_and_axis_order(
    kind: str, handle: str, skill_id: str
) -> None:
    files = _files()
    _add_resource(
        files,
        kind=kind,
        handle=handle,
        text=f"新增{kind}內容",
        skill_id=skill_id,
    )

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked", result.issues
    added = [action for action in result.actions if action.operation.value == "add"]
    assert len(added) == 1
    expected_id = uuid5(DOCUMENT_ID, f"candidate:{RUN_ID}:{kind}:{handle}")
    assert added[0].after["item_id"] == str(expected_id)
    assert added[0].after["display_order"] == 1


@pytest.mark.parametrize(
    ("kind", "handle", "path", "identity_key"),
    [
        ("duty", "duty-101", "duties", "duty_id"),
        ("task", "task-101", "tasks", "task_id"),
    ],
)
def test_new_duty_and_task_create_get_application_uuid_and_axis_order(
    kind: str,
    handle: str,
    path: str,
    identity_key: str,
) -> None:
    files = _files()
    if kind == "duty":
        _add_duty(files, handle)
    else:
        _add_task(files, handle)

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked", result.issues
    added = [action for action in result.actions if action.operation.value == "add"]
    assert len(added) == 1
    expected_id = uuid5(DOCUMENT_ID, f"candidate:{RUN_ID}:{kind}:{handle}")
    assert added[0].after[identity_key] == str(expected_id)
    assert added[0].after["display_order"] == 1


@pytest.mark.parametrize(
    "resource",
    [
        "duties/duty-001.json",
        "tasks/task-001.json",
        "opks/o/o-001.json",
        "opks/p/p-001.json",
        "opks/k/k-001.json",
        "opks/s/s-001.json",
    ],
)
def test_entity_delete_emits_withdraw_action(resource: str) -> None:
    files = _files()
    path = f"/candidate/{RUN_ID}/{resource}"
    del files[path]
    if resource.startswith("duties/"):
        del files[f"/candidate/{RUN_ID}/tasks/task-001.json"]
        for prefix in ("o", "p", "k", "s"):
            del files[f"/candidate/{RUN_ID}/opks/{prefix}/{prefix}-001.json"]
    elif resource.startswith("tasks/"):
        for prefix in ("o", "p", "k", "s"):
            del files[f"/candidate/{RUN_ID}/opks/{prefix}/{prefix}-001.json"]

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked", result.issues
    assert any(action.operation.value == "withdraw" for action in result.actions)


def test_task_split_is_general_atomic_resource_diff() -> None:
    files = _files()
    del files[f"/candidate/{RUN_ID}/tasks/task-001.json"]
    for handle, statement in (("task-101", "核對國內訂單"), ("task-102", "核對國際訂單")):
        files[f"/candidate/{RUN_ID}/tasks/{handle}.json"] = json.dumps(
            {
                "handle": handle,
                "duty_handle": "duty-001",
                "statement": statement,
                "action": "核對",
                "object": "訂單",
                "purpose_result": "避免錯誤出貨",
                "context": None,
                "frequency_text": None,
                "responsibility_role": "primary",
                "enablers": [],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n"
    for resource, skill_id in (
        ("o/o-001.json", "output"),
        ("p/p-001.json", "performance-indicator"),
        ("k/k-001.json", "knowledge"),
        ("s/s-001.json", "skill"),
    ):
        path = f"/candidate/{RUN_ID}/opks/{resource}"
        payload = json.loads(files[path])
        payload["task_handles"] = ["task-101", "task-102"] if resource[0] in {"k", "s"} else ["task-101"]
        _add_evidence(payload, skill_id)
        files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked", result.issues
    assert {action.operation.value for action in result.actions} == {
        "add",
        "revise",
        "withdraw",
    }
    groups = {
        action.atomic_subgroup_id
        for action in result.actions
        if action.atomic_subgroup_id is not None
    }
    assert len(groups) == 1
    assert len(result.actions) >= 7


def test_invalid_linkage_returns_issues_without_a_receipt() -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/tasks/task-001.json", duty_handle="duty-999")

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "invalid"
    assert result.receipt is None
    assert any("duty" in issue.lower() for issue in result.issues)


def test_invalid_evidence_returns_issues_without_a_receipt() -> None:
    files = _files()
    path = f"/candidate/{RUN_ID}/opks/o/o-001.json"
    payload = json.loads(files[path])
    payload["text"] = "需要新的輸出標準"
    payload["evidence"] = [
        {
            "source_handle": "source-001",
            "quote": "不存在的原話",
            "skill_ids": ["output"],
        }
    ]
    files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "invalid"
    assert result.receipt is None
    assert any("quote" in issue.lower() for issue in result.issues)


def test_unloaded_skill_returns_issues_without_a_receipt() -> None:
    files = _files()
    path = f"/candidate/{RUN_ID}/opks/o/o-001.json"
    payload = json.loads(files[path])
    payload["text"] = "需要輸出標準"
    _add_evidence(payload, "output")
    files[path] = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    result = check_candidate_document(
        _request(
            files,
            loaded_skill_ids=(),
        ),
        catalog=_catalog(),
        existing_review_queue={},
        interview_work={},
    )

    assert result.status == "invalid"
    assert result.receipt is None
    assert any("skill" in issue.lower() for issue in result.issues)


def test_unknown_review_group_handle_returns_issues_without_a_receipt() -> None:
    files = _files()
    files[f"/candidate/{RUN_ID}/review-groups.json"] = json.dumps(
        {
            "groups": [
                {
                    "handle": "review-001",
                    "action_handles": ["action-999"],
                    "depends_on_handles": [],
                }
            ]
        },
        ensure_ascii=False,
    )
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "invalid"
    assert result.receipt is None
    assert any("action" in issue.lower() and "known" in issue.lower() for issue in result.issues)


def test_successful_check_persists_only_exact_receipt_fields_and_not_review_items() -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")

    result = check_candidate_document(
        _request(files), catalog=_catalog(), existing_review_queue={}, interview_work={}
    )

    assert result.status == "checked"
    assert result.review_queue == {}
    assert result.receipt is not None
    assert set(result.receipt.model_dump(mode="json")) == {
        "run_id",
        "baseline_revision",
        "candidate_revision",
        "resource_digest",
        "check_call_id",
        "used_skill_ids",
        "changeset",
    }
    assert result.receipt.resource_digest == resource_digest(files)


def test_publication_rejects_any_candidate_digest_change_before_queue_mutation() -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")
    receipt = _checked(files)
    mutated = dict(files)
    _json_edit(mutated, f"/candidate/{RUN_ID}/header.json", notes="後續修改")

    with pytest.raises(CandidatePublicationStale, match="digest"):
        publish_checked_candidate(
            receipt,
            current_run_id=RUN_ID,
            current_baseline_revision=7,
            current_document=_document(),
            current_files=mutated,
            current_source_ids=(SOURCE_ID,),
        )


def test_publication_rejects_changed_document_read_set_before_queue_mutation() -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")
    receipt = _checked(files)
    changed_document = _document().model_copy(update={"job_title": "員工修正標題"})

    with pytest.raises(CandidatePublicationStale, match="read-set"):
        publish_checked_candidate(
            receipt,
            current_run_id=RUN_ID,
            current_baseline_revision=7,
            current_document=changed_document,
            current_files=files,
            current_source_ids=(SOURCE_ID,),
        )


def test_publication_rejects_changed_source_set_before_queue_mutation() -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")
    receipt = _checked(files)

    with pytest.raises(CandidatePublicationStale, match="source"):
        publish_checked_candidate(
            receipt,
            current_run_id=RUN_ID,
            current_baseline_revision=7,
            current_document=_document(),
            current_files=files,
            current_source_ids=(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("current_run_id", OTHER_RUN_ID),
        ("current_baseline_revision", 8),
    ],
)
def test_publication_rejects_old_run_or_baseline_before_queue_mutation(
    field: str, value: object
) -> None:
    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")
    receipt = _checked(files)
    kwargs: dict[str, object] = {
        "current_run_id": RUN_ID,
        "current_baseline_revision": 7,
        "current_document": _document(),
        "current_files": files,
        "current_source_ids": (SOURCE_ID,),
    }
    kwargs[field] = value

    with pytest.raises(CandidatePublicationStale):
        publish_checked_candidate(receipt, **kwargs)  # type: ignore[arg-type]


def test_graph_check_then_publication_moves_exact_receipt_atomically() -> None:
    from app.consultant.graph import _apply_command

    files = _files()
    _json_edit(files, f"/candidate/{RUN_ID}/header.json", job_title="資深採購專員")
    receipt = _checked(files)
    state = initial_thread_state(DOCUMENT_ID)
    state.update(
        {
            "revision": 7,
            "approved_document": _document().model_dump(mode="json"),
            "latest_run": RunReceipt(
                run_id=RUN_ID,
                status=RunStatus.SOURCE_SAVED,
                source_id=SOURCE_ID,
                started_at=datetime(2026, 8, 22, tzinfo=UTC),
            ).model_dump(mode="json"),
        }
    )

    class Runtime:
        def __init__(self, context: dict[str, object]) -> None:
            self.context = context

    checked = _apply_command(
        state,
        Runtime(
            {
                "action": "check_candidate_document",
                "document_id": str(DOCUMENT_ID),
                "expected_revision": 7,
                "checked_candidate": receipt.model_dump(mode="json"),
            }
        ),
    )
    assert checked["checked_candidate"] == receipt.model_dump(mode="json")
    assert checked.get("review_queue") is None

    published = _apply_command(
        {**state, **checked},
        Runtime(
            {
                "action": "publish_checked_candidate",
                "document_id": str(DOCUMENT_ID),
                "expected_revision": 7,
                "run_id": str(RUN_ID),
            }
        ),
    )
    assert published["revision"] == 8
    assert published["checked_candidate"] is None
    assert set(published["review_queue"]) == {str(receipt.changeset.changeset_id)}
