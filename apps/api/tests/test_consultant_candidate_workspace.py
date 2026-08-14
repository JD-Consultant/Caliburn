from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.consultant.candidate_workspace import (
    CandidateDependencyError,
    CandidateRevisionConflict,
    CandidateToolCallConflict,
    CandidateWorkspace,
    VerifiedCandidateStage,
    candidate_mapping_authority,
    candidate_revision_digest,
    materialize_candidate_workspace,
)
from app.consultant.document_authority import apply_document_actions
from app.consultant.document_review import create_document_changeset
from app.consultant.results import (
    AnalysisBasis,
    DocumentChangeOperation,
    ReviewableDocumentChange,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    DocumentChangeSet,
    DocumentChangeStatus,
    DocumentPatchAction,
    DocumentPatchOperation,
    DocumentPathRead,
    RunReceipt,
    RunStatus,
    initial_thread_state,
)


def _basis(source_id: UUID) -> AnalysisBasis:
    return AnalysisBasis(
        source_ids=(source_id,),
        skill_ids=("task-boundary",),
    )


def _state(
    document_id: UUID,
    *,
    revision: int = 3,
    document: ApprovedJobDocument | None = None,
    review_queue: dict[str, dict] | None = None,
) -> dict:
    state = initial_thread_state(document_id)
    state["revision"] = revision
    state["approved_document"] = (
        document or ApprovedJobDocument(document_id=document_id)
    ).model_dump(mode="json")
    state["review_queue"] = review_queue or {}
    return state


def _change(
    source_id: UUID,
    *,
    statement: str = "管理採購作業",
    change_ref: str = "duty-change",
    depends_on_change_refs: tuple[str, ...] = (),
    depends_on_action_ids: tuple[UUID, ...] = (),
    supersedes_action_ids: tuple[UUID, ...] = (),
    atomic_group_ref: str = "",
    duty_id: UUID | None = None,
) -> ReviewableDocumentChange:
    resolved_duty_id = duty_id or uuid4()
    return ReviewableDocumentChange(
        operation=DocumentChangeOperation.ADD,
        path="/duties",
        after={
            "duty_id": str(resolved_duty_id),
            "statement": statement,
        },
        basis=_basis(source_id),
        change_ref=change_ref,
        depends_on_change_refs=depends_on_change_refs,
        depends_on_action_ids=depends_on_action_ids,
        supersedes_action_ids=supersedes_action_ids,
        atomic_group_ref=atomic_group_ref,
    )


def _stage(
    *,
    run_id: UUID,
    source_id: UUID,
    baseline_revision: int = 3,
    base_candidate_revision: int = 0,
    tool_call_id: str = "tool-call-1",
    request_sha256: str = "a" * 64,
    changes: tuple[ReviewableDocumentChange, ...] | None = None,
) -> VerifiedCandidateStage:
    return VerifiedCandidateStage(
        run_id=run_id,
        baseline_revision=baseline_revision,
        base_candidate_revision=base_candidate_revision,
        tool_call_id=tool_call_id,
        request_sha256=request_sha256,
        summary="建立可審核的候選文件。",
        changes=changes or (_change(source_id),),
        used_skill_ids=("task-boundary",),
    )


def _pending_bundle(
    document: ApprovedJobDocument,
    *,
    source_id: UUID,
    action_id: UUID,
    changeset_id: UUID | None = None,
    depends_on_action_ids: tuple[UUID, ...] = (),
    status: DocumentChangeStatus = DocumentChangeStatus.PENDING,
) -> DocumentChangeSet:
    duty_id = uuid4()
    next_display_order = max(
        (item.display_order for item in document.duties),
        default=-1,
    ) + 1
    action = DocumentPatchAction(
        action_id=action_id,
        operation=DocumentPatchOperation.ADD,
        path="/duties",
        target_key=f"pending-duty:{duty_id}",
        before=None,
        after={
            "duty_id": str(duty_id),
            "statement": "既有待審核職責",
            "display_order": next_display_order,
        },
        source_ids=(source_id,),
        read_set=(
            DocumentPathRead(
                path="/duties",
                value_sha256="0" * 64,
            ),
        ),
        depends_on_action_ids=depends_on_action_ids,
        status=status,
        rejection_reason=("員工拒絕" if status is DocumentChangeStatus.REJECTED else None),
        stale_reason=("前提失效" if status is DocumentChangeStatus.STALE else None),
    )
    return DocumentChangeSet(
        changeset_id=changeset_id or uuid4(),
        summary="既有待審核變更",
        actions=(action,),
        source_ids=(source_id,),
        created_revision=0,
        external_dependency_action_ids=depends_on_action_ids,
    )


def test_first_candidate_revision_is_materialized_without_mutating_semantic_state() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    semantic_before = deepcopy(state)

    workspace, receipt = materialize_candidate_workspace(
        state,
        _stage(run_id=run_id, source_id=source_id),
    )

    assert workspace.run_id == run_id
    assert workspace.baseline_revision == 3
    assert workspace.candidate_revision == 1
    assert workspace.request_sha256 == "a" * 64
    assert receipt.status == "applied"
    assert receipt.candidate_revision == 1
    assert receipt.revision_digest == workspace.revision_digest
    assert tuple(receipt.action_ids) == tuple(
        action.action_id for action in workspace.changeset.actions
    )
    assert receipt.actions[0].before == workspace.changeset.actions[0].before
    assert receipt.actions[0].after == workspace.changeset.actions[0].after
    assert receipt.actions[0].depends_on_action_ids == (
        workspace.changeset.actions[0].depends_on_action_ids
    )
    assert receipt.actions[0].atomic_subgroup_id == (
        workspace.changeset.actions[0].atomic_subgroup_id
    )
    assert workspace.tool_receipts["tool-call-1"].source_ids == (
        workspace.changeset.source_ids
    )
    assert "source_ids" not in receipt.model_dump(mode="json")
    assert state == semantic_before


def test_workspace_rejects_latest_receipt_with_mismatched_source_projection() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    workspace, _ = materialize_candidate_workspace(
        state,
        _stage(run_id=run_id, source_id=source_id),
    )
    tampered = workspace.model_dump(mode="json")
    tampered["tool_receipts"]["tool-call-1"]["source_ids"] = [str(uuid4())]

    with pytest.raises(ValidationError, match="latest receipt does not match changeset"):
        CandidateWorkspace.model_validate(tampered)


def test_replacement_revision_replaces_changeset_and_retains_tool_receipts() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    first, _ = materialize_candidate_workspace(
        state,
        _stage(run_id=run_id, source_id=source_id),
    )
    state["active_candidate"] = first.model_dump(mode="json")

    second, receipt = materialize_candidate_workspace(
        state,
        _stage(
            run_id=run_id,
            source_id=source_id,
            base_candidate_revision=1,
            tool_call_id="tool-call-2",
            request_sha256="b" * 64,
            changes=(_change(source_id, statement="管理國內外採購作業"),),
        ),
    )

    assert second.candidate_revision == 2
    assert second.changeset != first.changeset
    assert set(second.tool_receipts) == {"tool-call-1", "tool-call-2"}
    assert receipt.candidate_revision == 2


def test_candidate_stage_rejects_stale_base_revision_without_writing() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    first, _ = materialize_candidate_workspace(
        state,
        _stage(run_id=run_id, source_id=source_id),
    )
    state["active_candidate"] = first.model_dump(mode="json")
    before = deepcopy(state)

    with pytest.raises(CandidateRevisionConflict, match="expected candidate revision 1"):
        materialize_candidate_workspace(
            state,
            _stage(
                run_id=run_id,
                source_id=source_id,
                base_candidate_revision=0,
                tool_call_id="tool-call-2",
                request_sha256="b" * 64,
            ),
        )

    assert state == before


def test_exact_tool_call_replay_returns_original_receipt_without_new_revision() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    stage = _stage(run_id=run_id, source_id=source_id)
    first, first_receipt = materialize_candidate_workspace(state, stage)
    state["active_candidate"] = first.model_dump(mode="json")

    replay, replay_receipt = materialize_candidate_workspace(state, stage)

    assert replay == first
    assert replay_receipt == first_receipt
    assert replay.candidate_revision == 1


def test_preserved_workspace_baseline_allows_replay_and_replacement_after_metadata_revisions() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    first_stage = _stage(run_id=run_id, source_id=source_id)
    first, first_receipt = materialize_candidate_workspace(state, first_stage)
    state["active_candidate"] = first.model_dump(mode="json")
    state["revision"] = 5

    replayed, replay_receipt = materialize_candidate_workspace(state, first_stage)
    replacement, replacement_receipt = materialize_candidate_workspace(
        state,
        _stage(
            run_id=run_id,
            source_id=source_id,
            baseline_revision=3,
            base_candidate_revision=1,
            tool_call_id="tool-call-2",
            request_sha256="b" * 64,
            changes=(
                _change(source_id, statement="管理國內外採購作業"),
            ),
        ),
    )

    assert replayed == first
    assert replay_receipt == first_receipt
    assert replacement.baseline_revision == 3
    assert replacement.candidate_revision == 2
    assert replacement_receipt.candidate_revision == 2


def test_tool_call_id_reuse_with_another_digest_is_a_conflict() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    first, _ = materialize_candidate_workspace(
        state,
        _stage(run_id=run_id, source_id=source_id),
    )
    state["active_candidate"] = first.model_dump(mode="json")

    with pytest.raises(CandidateToolCallConflict, match="tool-call-1"):
        materialize_candidate_workspace(
            state,
            _stage(
                run_id=run_id,
                source_id=source_id,
                base_candidate_revision=1,
                request_sha256="c" * 64,
            ),
        )


def test_invalid_replacement_preserves_previous_successful_workspace() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    state = _state(document_id)
    first, _ = materialize_candidate_workspace(
        state,
        _stage(run_id=run_id, source_id=source_id),
    )
    state["active_candidate"] = first.model_dump(mode="json")
    before = deepcopy(state)
    invalid = ReviewableDocumentChange(
        operation=DocumentChangeOperation.REVISE,
        path=f"/duties/{uuid4()}/statement",
        after="不存在的 Duty",
        basis=_basis(source_id),
        change_ref="invalid-change",
    )

    with pytest.raises(ValueError, match="valid review state"):
        materialize_candidate_workspace(
            state,
            _stage(
                run_id=run_id,
                source_id=source_id,
                base_candidate_revision=1,
                tool_call_id="tool-call-2",
                request_sha256="b" * 64,
                changes=(invalid,),
            ),
        )

    assert state == before


def test_revision_digest_is_stable_for_canonical_changeset_payload() -> None:
    document_id = uuid4()
    source_id = uuid4()
    workspace, _ = materialize_candidate_workspace(
        _state(document_id),
        _stage(run_id=uuid4(), source_id=source_id),
    )
    payload = workspace.changeset.model_dump(mode="json")
    reordered = dict(reversed(tuple(payload.items())))

    assert candidate_revision_digest(workspace.changeset) == candidate_revision_digest(
        DocumentChangeSet.model_validate(reordered)
    )


def test_explicit_external_dependency_builds_conditional_baseline_and_full_closure() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    root_id = uuid4()
    leaf_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    root = _pending_bundle(document, source_id=source_id, action_id=root_id)
    conditional = apply_document_actions(document, root.actions)
    leaf = _pending_bundle(
        conditional,
        source_id=source_id,
        action_id=leaf_id,
        depends_on_action_ids=(root_id,),
    )
    leaf_duty_id = UUID(str(leaf.actions[0].after["duty_id"]))  # type: ignore[index]
    queue = {
        str(root.changeset_id): root.model_dump(mode="json"),
        str(leaf.changeset_id): leaf.model_dump(mode="json"),
    }
    dependent = ReviewableDocumentChange(
        operation=DocumentChangeOperation.REVISE,
        path=f"/duties/{leaf_duty_id}/statement",
        after="依條件式前提修訂職責",
        basis=_basis(source_id),
        change_ref="dependent-change",
        depends_on_action_ids=(leaf_id,),
    )

    workspace, _ = materialize_candidate_workspace(
        _state(document_id, document=document, review_queue=queue),
        _stage(
            run_id=run_id,
            source_id=source_id,
            changes=(dependent,),
        ),
    )

    assert workspace.changeset.external_dependency_action_ids == (root_id, leaf_id)
    assert set(workspace.changeset.actions[0].depends_on_action_ids) == {
        root_id,
        leaf_id,
    }


def test_pending_review_action_is_never_implicitly_mixed_into_candidate_baseline() -> None:
    document_id = uuid4()
    source_id = uuid4()
    pending_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    pending = _pending_bundle(document, source_id=source_id, action_id=pending_id)
    pending_duty_id = UUID(str(pending.actions[0].after["duty_id"]))  # type: ignore[index]
    state = _state(
        document_id,
        document=document,
        review_queue={str(pending.changeset_id): pending.model_dump(mode="json")},
    )
    unbound = ReviewableDocumentChange(
        operation=DocumentChangeOperation.REVISE,
        path=f"/duties/{pending_duty_id}/statement",
        after="不可偷渡 pending baseline",
        basis=_basis(source_id),
        change_ref="unbound-change",
    )

    with pytest.raises(ValueError, match="valid review state"):
        materialize_candidate_workspace(
            state,
            _stage(run_id=uuid4(), source_id=source_id, changes=(unbound,)),
        )


@pytest.mark.parametrize(
    "status",
    (DocumentChangeStatus.REJECTED, DocumentChangeStatus.STALE),
)
def test_rejected_or_stale_external_dependency_is_rejected(
    status: DocumentChangeStatus,
) -> None:
    document_id = uuid4()
    source_id = uuid4()
    action_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    bundle = _pending_bundle(
        document,
        source_id=source_id,
        action_id=action_id,
        status=status,
    )

    with pytest.raises(CandidateDependencyError, match=status.value):
        materialize_candidate_workspace(
            _state(
                document_id,
                document=document,
                review_queue={
                    str(bundle.changeset_id): bundle.model_dump(mode="json")
                },
            ),
            _stage(
                run_id=uuid4(),
                source_id=source_id,
                changes=(
                    _change(
                        source_id,
                        depends_on_action_ids=(action_id,),
                    ),
                ),
            ),
        )


def test_pending_external_dependency_accepts_already_applied_ancestor() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    ancestor_id = uuid4()
    root_id = uuid4()
    original = ApprovedJobDocument(document_id=document_id)
    ancestor = _pending_bundle(
        original,
        source_id=source_id,
        action_id=ancestor_id,
    )
    approved = apply_document_actions(original, ancestor.actions)
    accepted_ancestor = ancestor.model_copy(
        update={
            "actions": (
                ancestor.actions[0].model_copy(
                    update={"status": DocumentChangeStatus.ACCEPTED}
                ),
            )
        }
    )
    root = _pending_bundle(
        approved,
        source_id=source_id,
        action_id=root_id,
        depends_on_action_ids=(ancestor_id,),
    )
    root_duty_id = UUID(str(root.actions[0].after["duty_id"]))  # type: ignore[index]
    queue = {
        str(accepted_ancestor.changeset_id): accepted_ancestor.model_dump(mode="json"),
        str(root.changeset_id): root.model_dump(mode="json"),
    }
    dependent = ReviewableDocumentChange(
        operation=DocumentChangeOperation.REVISE,
        path=f"/duties/{root_duty_id}/statement",
        after="依待審前提修訂職責",
        basis=_basis(source_id),
        change_ref="dependent-change",
        depends_on_action_ids=(root_id,),
    )

    workspace, _ = materialize_candidate_workspace(
        _state(document_id, document=approved, review_queue=queue),
        _stage(
            run_id=run_id,
            source_id=source_id,
            changes=(dependent,),
        ),
    )

    assert workspace.changeset.external_dependency_action_ids == (root_id,)
    assert workspace.changeset.actions[0].depends_on_action_ids == (root_id,)


def test_external_atomic_subgroup_expands_complete_conditional_baseline() -> None:
    document_id = uuid4()
    run_id = uuid4()
    source_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    external = create_document_changeset(
        document_id=document_id,
        run_id=uuid4(),
        summary="不可拆分的外部前提。",
        read_revision=3,
        document=document,
        changes=(
            _change(
                source_id,
                statement="管理採購作業",
                change_ref="external-first",
                atomic_group_ref="external-group",
            ),
            _change(
                source_id,
                statement="管理供應商作業",
                change_ref="external-second",
                atomic_group_ref="external-group",
            ),
        ),
        existing_review_queue={},
        interview_work={},
    )
    first_action, sibling_action = external.actions
    sibling_duty_id = UUID(str(sibling_action.after["duty_id"]))  # type: ignore[index]
    state = _state(
        document_id,
        document=document,
        review_queue={
            str(external.changeset_id): external.model_dump(mode="json")
        },
    )
    dependent = ReviewableDocumentChange(
        operation=DocumentChangeOperation.REVISE,
        path=f"/duties/{sibling_duty_id}/statement",
        after="修訂完整原子前提中的職責",
        basis=_basis(source_id),
        change_ref="dependent-change",
        depends_on_action_ids=(first_action.action_id,),
    )

    allowed_entities, allowed_actions = candidate_mapping_authority(
        state,
        depends_on_action_ids=(first_action.action_id,),
        supersedes_action_ids=(),
    )
    workspace, _ = materialize_candidate_workspace(
        state,
        _stage(
            run_id=run_id,
            source_id=source_id,
            changes=(dependent,),
        ),
    )

    expected_action_ids = {first_action.action_id, sibling_action.action_id}
    assert allowed_actions == expected_action_ids
    assert sibling_duty_id in allowed_entities
    assert set(workspace.changeset.external_dependency_action_ids) == expected_action_ids
    assert set(workspace.changeset.actions[0].depends_on_action_ids) == expected_action_ids


def test_local_dependencies_and_explicit_atomic_group_become_review_metadata() -> None:
    document_id = uuid4()
    source_id = uuid4()
    first = _change(
        source_id,
        change_ref="first",
        atomic_group_ref="group-1",
        duty_id=uuid4(),
    )
    second = _change(
        source_id,
        statement="管理供應商作業",
        change_ref="second",
        depends_on_change_refs=("first",),
        atomic_group_ref="group-1",
        duty_id=uuid4(),
    )

    workspace, _ = materialize_candidate_workspace(
        _state(document_id),
        _stage(
            run_id=uuid4(),
            source_id=source_id,
            changes=(first, second),
        ),
    )

    first_action, second_action = workspace.changeset.actions
    assert first_action.atomic_subgroup_id is not None
    assert second_action.atomic_subgroup_id == first_action.atomic_subgroup_id
    assert second_action.depends_on_action_ids == (first_action.action_id,)


def test_supersession_handle_is_carried_without_mutating_old_review_action() -> None:
    document_id = uuid4()
    source_id = uuid4()
    old_action_id = uuid4()
    document = ApprovedJobDocument(document_id=document_id)
    old_bundle = _pending_bundle(
        document,
        source_id=source_id,
        action_id=old_action_id,
    )
    state = _state(
        document_id,
        document=document,
        review_queue={
            str(old_bundle.changeset_id): old_bundle.model_dump(mode="json")
        },
    )

    workspace, _ = materialize_candidate_workspace(
        state,
        _stage(
            run_id=uuid4(),
            source_id=source_id,
            changes=(
                _change(source_id, supersedes_action_ids=(old_action_id,)),
            ),
        ),
    )

    assert workspace.changeset.actions[0].supersedes_action_ids == (old_action_id,)
    persisted_old = DocumentChangeSet.model_validate(
        state["review_queue"][str(old_bundle.changeset_id)]
    )
    assert persisted_old.actions[0].status is DocumentChangeStatus.PENDING
