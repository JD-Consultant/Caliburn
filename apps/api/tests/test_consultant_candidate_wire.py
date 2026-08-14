from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4, uuid5

import pytest
from pydantic import ValidationError

from app.consultant.candidate_wire import (
    CandidateEditBatch,
    OutputDocumentChange,
    OutputDocumentField,
    OutputDocumentTarget,
    OutputDuty,
    OutputOpksItem,
    OutputOpksKind,
    OutputResponsibilityRole,
    OutputTask,
    map_candidate_edit_batch,
)
from app.consultant.provider_wire import OutputAnalysisBasis
from app.consultant.results import DocumentChangeOperation, GapReason


def _walk_schema(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def _basis() -> OutputAnalysisBasis:
    return OutputAnalysisBasis(
        source_ids=(uuid4(),),
        quote_anchors=(),
        skill_ids=("task-boundary",),
    )


def _change(**overrides: Any) -> OutputDocumentChange:
    values: dict[str, Any] = {
        "change_ref": "change-1",
        "depends_on_change_refs": (),
        "depends_on_action_ids": (),
        "supersedes_action_ids": (),
        "atomic_group_ref": "",
        "operation": DocumentChangeOperation.ADD,
        "target": OutputDocumentTarget.DUTY,
        "target_id": "",
        "field": OutputDocumentField.ENTITY,
        "text_value": "",
        "integer_value": -1,
        "uuid_value": "",
        "uuid_values": (),
        "enablers": (),
        "duties": (
            OutputDuty(
                duty_id="",
                entity_ref="d1",
                statement="管理採購作業",
                display_order=-1,
            ),
        ),
        "tasks": (),
        "opks_items": (),
        "target_ids": (),
        "opks_kind": OutputOpksKind.NONE,
        "task_ids": (),
        "indicator_ids": (),
        "basis_ordinal": 1,
    }
    values.update(overrides)
    return OutputDocumentChange(**values)


def _batch(*changes: OutputDocumentChange) -> CandidateEditBatch:
    return CandidateEditBatch(
        base_candidate_revision=0,
        summary="依員工原話建立可審核的 Duty、Task 與 O/P 候選。",
        analysis_bases=(_basis(),),
        replacement_changes=changes,
    )


def _task_change(**overrides: Any) -> OutputDocumentChange:
    values: dict[str, Any] = {
        "change_ref": "change-2",
        "target": OutputDocumentTarget.TASK,
        "tasks": (
            OutputTask(
                task_id="",
                duty_id="",
                entity_ref="t1",
                duty_ref="d1",
                statement="建立請購單",
                action="建立",
                object="請購單",
                purpose_result="",
                context="",
                frequency_text="",
                responsibility_role=OutputResponsibilityRole.NONE,
                enablers=(),
                display_order=-1,
            ),
        ),
        "duties": (),
    }
    values.update(overrides)
    return _change(**values)


def _opks_change(
    *,
    change_ref: str,
    entity_ref: str,
    kind: OutputOpksKind,
    **overrides: Any,
) -> OutputDocumentChange:
    return _change(
        change_ref=change_ref,
        target=OutputDocumentTarget.OPKS,
        duties=(),
        opks_items=(
            OutputOpksItem(
                item_id="",
                entity_ref=entity_ref,
                text="可審核的請購單" if kind is OutputOpksKind.OUTPUT else "退件率",
                display_order=-1,
                task_ids=(),
                indicator_ids=(),
                task_refs=("t1",),
                indicator_refs=(),
            ),
        ),
        opks_kind=kind,
        **overrides,
    )


def test_candidate_edit_wire_schema_is_closed_required_and_union_free() -> None:
    schema = CandidateEditBatch.model_json_schema()
    nodes = tuple(_walk_schema(schema))
    objects = tuple(node for node in nodes if node.get("type") == "object")

    assert objects
    assert not any("anyOf" in node or "oneOf" in node for node in nodes)
    assert all(node.get("additionalProperties") is False for node in objects)
    assert all(
        set(node.get("required", ())) == set(node.get("properties", ()))
        for node in objects
    )


def test_candidate_batch_resolves_local_document_refs_to_stable_application_uuids() -> None:
    document_id = uuid4()
    materialization_run_id = uuid4()
    batch = _batch(
        _change(),
        _task_change(depends_on_change_refs=("change-1",)),
        _opks_change(
            change_ref="change-3",
            entity_ref="o1",
            kind=OutputOpksKind.OUTPUT,
            depends_on_change_refs=("change-2",),
        ),
        _opks_change(
            change_ref="change-4",
            entity_ref="p1",
            kind=OutputOpksKind.PERFORMANCE_INDICATOR,
            depends_on_change_refs=("change-2",),
        ),
    )

    first = map_candidate_edit_batch(
        batch,
        document_id=document_id,
        materialization_run_id=materialization_run_id,
    )
    replay = map_candidate_edit_batch(
        batch,
        document_id=document_id,
        materialization_run_id=materialization_run_id,
    )
    expected_duty_id = uuid5(
        document_id, f"consultant:{materialization_run_id}:local:duty:d1"
    )
    expected_task_id = uuid5(
        document_id, f"consultant:{materialization_run_id}:local:task:t1"
    )
    expected_output_id = uuid5(
        document_id, f"consultant:{materialization_run_id}:local:opks:o1"
    )
    expected_indicator_id = uuid5(
        document_id, f"consultant:{materialization_run_id}:local:opks:p1"
    )

    assert first == replay
    assert first[0].after == {
        "duty_id": str(expected_duty_id),
        "statement": "管理採購作業",
    }
    assert first[1].after == {
        "task_id": str(expected_task_id),
        "duty_id": str(expected_duty_id),
        "statement": "建立請購單",
        "action": "建立",
        "object": "請購單",
        "enablers": [],
    }
    assert first[2].after == {
        "item_id": str(expected_output_id),
        "kind": "output",
        "text": "可審核的請購單",
        "task_ids": [str(expected_task_id)],
        "indicator_ids": [],
    }
    assert first[2].task_ids == (expected_task_id,)
    assert first[3].after == {
        "item_id": str(expected_indicator_id),
        "kind": "indicator",
        "text": "退件率",
        "task_ids": [str(expected_task_id)],
        "indicator_ids": [],
    }


@pytest.mark.parametrize(
    ("batch", "message"),
    [
        pytest.param(
            lambda: _batch(
                _change(),
                _change(change_ref="change-2", duties=(
                    OutputDuty(
                        duty_id="",
                        entity_ref="d1",
                        statement="覆寫同一 ref",
                        display_order=-1,
                    ),
                )),
            ),
            "duplicate local ref",
            id="duplicate-local-ref",
        ),
        pytest.param(
            lambda: _batch(_task_change()),
            "unknown local ref",
            id="unknown-or-cross-batch-local-ref",
        ),
        pytest.param(
            lambda: _batch(
                _change(depends_on_change_refs=("change-2",)),
                _task_change(depends_on_change_refs=("change-1",)),
            ),
            "dependency cycle",
            id="dependency-cycle",
        ),
        pytest.param(
            lambda: _batch(_change(depends_on_change_refs=("change-1",))),
            "self dependency",
            id="self-dependency",
        ),
        pytest.param(
            lambda: _batch(
                _change(
                    duties=(
                        OutputDuty(
                            duty_id=str(uuid4()),
                            entity_ref="d1",
                            statement="模型不可以編造 UUID",
                            display_order=-1,
                        ),
                    )
                )
            ),
            "application-owned ID",
            id="add-smuggles-application-uuid",
        ),
    ],
)
def test_candidate_batch_fails_closed_for_invalid_local_ref_graphs(
    batch: Any, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        map_candidate_edit_batch(
            batch(),
            document_id=uuid4(),
            materialization_run_id=uuid4(),
        )


def test_candidate_batch_rejects_duplicate_and_unknown_change_refs() -> None:
    duplicate = _batch(_change(), _task_change(change_ref="change-1"))
    unknown_dependency = _batch(_change(depends_on_change_refs=("missing",)))

    with pytest.raises(ValueError, match="duplicate change_ref"):
        map_candidate_edit_batch(
            duplicate,
            document_id=uuid4(),
            materialization_run_id=uuid4(),
        )
    with pytest.raises(ValueError, match="unknown change_ref"):
        map_candidate_edit_batch(
            unknown_dependency,
            document_id=uuid4(),
            materialization_run_id=uuid4(),
        )


def test_candidate_wire_rejects_malformed_nonempty_atomic_group_ref() -> None:
    with pytest.raises(ValidationError, match="atomic_group_ref"):
        _change(atomic_group_ref="not a short ref")


@pytest.mark.parametrize(
    "change_factory",
    [
        pytest.param(
            lambda bound, unbound: _change(
                operation=DocumentChangeOperation.REVISE,
                target=OutputDocumentTarget.TASK,
                target_id=str(unbound),
                field=OutputDocumentField.ACTION,
                text_value="修訂採購動作",
                duties=(),
            ),
            id="non-add-target-id",
        ),
        pytest.param(
            lambda bound, unbound: _change(
                operation=DocumentChangeOperation.REASSIGN,
                target=OutputDocumentTarget.TASK,
                target_id=str(bound),
                field=OutputDocumentField.DUTY_ID,
                text_value="",
                uuid_value=str(unbound),
                duties=(),
            ),
            id="non-add-uuid-value",
        ),
        pytest.param(
            lambda bound, unbound: _change(
                operation=DocumentChangeOperation.REVISE,
                target=OutputDocumentTarget.OPKS,
                target_id=str(bound),
                field=OutputDocumentField.TASK_IDS,
                text_value="",
                uuid_values=(unbound,),
                duties=(),
                opks_kind=OutputOpksKind.OUTPUT,
            ),
            id="non-add-uuid-values",
        ),
        pytest.param(
            lambda bound, unbound: _change(
                operation=DocumentChangeOperation.MERGE,
                target=OutputDocumentTarget.DUTY,
                target_id="",
                field=OutputDocumentField.ENTITY,
                text_value="",
                target_ids=(unbound,),
                duties=(
                    OutputDuty(
                        duty_id="",
                        entity_ref="",
                        statement="合併後的採購作業",
                        display_order=-1,
                    ),
                ),
            ),
            id="merge-target-ids",
        ),
        pytest.param(
            lambda bound, unbound: _task_change(
                tasks=(
                    OutputTask(
                        task_id="",
                        duty_id=str(unbound),
                        entity_ref="",
                        duty_ref="",
                        statement="建立請購單",
                        action="建立",
                        object="請購單",
                        purpose_result="",
                        context="",
                        frequency_text="",
                        responsibility_role=OutputResponsibilityRole.NONE,
                        enablers=(),
                        display_order=-1,
                    ),
                )
            ),
            id="task-duty-reference",
        ),
        pytest.param(
            lambda bound, unbound: _change(
                target=OutputDocumentTarget.OPKS,
                duties=(),
                opks_items=(
                    OutputOpksItem(
                        item_id="",
                        entity_ref="",
                        text="採購成果",
                        display_order=-1,
                        task_ids=(unbound,),
                        indicator_ids=(),
                        task_refs=(),
                        indicator_refs=(),
                    ),
                ),
                opks_kind=OutputOpksKind.OUTPUT,
                task_ids=(unbound,),
            ),
            id="opks-task-linkage",
        ),
        pytest.param(
            lambda bound, unbound: _change(
                target=OutputDocumentTarget.OPKS,
                duties=(),
                opks_items=(
                    OutputOpksItem(
                        item_id="",
                        entity_ref="",
                        text="退件率",
                        display_order=-1,
                        task_ids=(),
                        indicator_ids=(unbound,),
                        task_refs=(),
                        indicator_refs=(),
                    ),
                ),
                opks_kind=OutputOpksKind.PERFORMANCE_INDICATOR,
                indicator_ids=(unbound,),
            ),
            id="opks-indicator-linkage",
        ),
    ],
)
def test_candidate_batch_rejects_unbound_formal_entity_handles(
    change_factory: Any,
) -> None:
    bound = uuid4()
    unbound = uuid4()

    with pytest.raises(ValueError, match="unbound entity handle"):
        map_candidate_edit_batch(
            _batch(change_factory(bound, unbound)),
            document_id=uuid4(),
            materialization_run_id=uuid4(),
            allowed_entity_ids=frozenset({bound}),
        )


@pytest.mark.parametrize("field", ("depends_on_action_ids", "supersedes_action_ids"))
def test_candidate_batch_rejects_unbound_action_handles(field: str) -> None:
    action_id = uuid4()

    with pytest.raises(ValueError, match="unbound action handle"):
        map_candidate_edit_batch(
            _batch(_change(**{field: (action_id,)})),
            document_id=uuid4(),
            materialization_run_id=uuid4(),
            allowed_action_ids=frozenset(),
        )


def test_candidate_batch_accepts_authority_scoped_handles_and_local_refs() -> None:
    task_id = uuid4()
    action_id = uuid4()
    batch = _batch(
        _change(
            operation=DocumentChangeOperation.REVISE,
            target=OutputDocumentTarget.TASK,
            target_id=str(task_id),
            field=OutputDocumentField.ACTION,
            text_value="修訂採購動作",
            duties=(),
            depends_on_action_ids=(action_id,),
            supersedes_action_ids=(action_id,),
        )
    )

    mapped = map_candidate_edit_batch(
        batch,
        document_id=uuid4(),
        materialization_run_id=uuid4(),
        allowed_entity_ids=frozenset({task_id}),
        allowed_action_ids=frozenset({action_id}),
    )

    assert mapped[0].path == f"/tasks/{task_id}/action"
    assert mapped[0].depends_on_action_ids == (action_id,)
    assert mapped[0].supersedes_action_ids == (action_id,)
