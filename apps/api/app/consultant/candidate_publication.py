"""Application-owned publication of checked virtual-JD resources.

The model edits canonical workspace resources.  This module is the narrow
Caliburn bridge that parses those resources, resolves employee evidence,
creates the existing review changeset, and verifies the exact resource digest
again immediately before publication.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from typing_extensions import Annotated

from app.consultant.document_authority import document_path_sha256
from app.consultant.document_review import (
    DocumentReviewError,
    create_document_changeset,
)
from app.consultant.results import (
    ReviewableDocumentChange,
    SkillId,
)
from app.consultant.state import (
    ActionHandle,
    ApprovedJobDocument,
    CheckedCandidateReceipt,
    DocumentChangeSet,
    DocumentPatchAction,
    EmployeeSource,
    NonEmptyText,
)
from app.consultant.verification import (
    ConsultantVerificationError,
    verify_candidate_document_changes,
)
from app.consultant.workspace_resources import (
    CandidateReviewGroup,
    WorkspaceCatalog,
    pending_action_handles,
    workspace_entity_id,
)
from app.consultant.workspace_validation import validate_workspace_payload
from app.consultant.workspace_review import derive_semantic_changes


Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class CandidateCheckRequest(BaseModel):
    """The application inputs for one candidate resource check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: UUID
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    candidate_revision: int = Field(ge=1)
    files: dict[str, str]
    check_call_id: NonEmptyText
    selected_skill_ids: tuple[SkillId, ...]
    loaded_skill_ids: tuple[SkillId, ...]

    @model_validator(mode="after")
    def skill_receipts_are_consistent(self) -> CandidateCheckRequest:
        if len(self.selected_skill_ids) != len(set(self.selected_skill_ids)):
            raise ValueError("duplicate selected_skill_ids")
        if len(self.loaded_skill_ids) != len(set(self.loaded_skill_ids)):
            raise ValueError("duplicate loaded_skill_ids")
        if not set(self.loaded_skill_ids) <= set(self.selected_skill_ids):
            raise ValueError("loaded Skills must be selected")
        return self


class CandidatePublicationStale(RuntimeError):
    """The checked candidate no longer describes the current workspace."""


class CandidateCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["checked", "invalid"]
    run_id: UUID
    candidate_revision: int = Field(ge=1)
    resource_digest: Digest
    action_handles: tuple[ActionHandle, ...] = ()
    actions: tuple[DocumentPatchAction, ...] = ()
    receipt: CheckedCandidateReceipt | None = None
    issues: tuple[str, ...] = ()
    # A check is deliberately not a review-queue mutation.  Keeping this
    # projection in the result makes that boundary explicit to callers.
    review_queue: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def action_handles_match_actions(self) -> CandidateCheckResult:
        if len(self.action_handles) != len(set(self.action_handles)):
            raise ValueError("duplicate candidate check action handle")
        if len(self.action_handles) != len(self.actions):
            raise ValueError("candidate check action handles must match actions")
        return self


def resource_digest(files: Mapping[str, str | bytes]) -> str:
    """Hash exact path/content pairs, including harmless-looking formatting."""

    payload = {
        str(path): raw.decode("utf-8") if isinstance(raw, bytes) else raw
        for path, raw in files.items()
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _invalid(
    request: CandidateCheckRequest,
    digest: str,
    issues: Sequence[str],
) -> CandidateCheckResult:
    normalized = tuple(issue.strip() for issue in issues if issue.strip())
    if not normalized:
        normalized = ("candidate check failed without an actionable issue",)
    return CandidateCheckResult(
        status="invalid",
        run_id=request.run_id,
        candidate_revision=request.candidate_revision,
        resource_digest=digest,
        issues=normalized,
        review_queue={},
    )


def _candidate_handle_by_id(
    catalog: WorkspaceCatalog,
    files: Mapping[str, str],
    run_id: UUID,
    *,
    new_entity_namespace: Literal["candidate", "workspace"],
) -> dict[UUID, str]:
    """Recover local handles for new entities without storing another mapping."""

    result: dict[UUID, str] = {}
    for path in files:
        parts = path.strip("/").split("/")
        if len(parts) < 4 or parts[0] != "candidate" or parts[1] != str(run_id):
            continue
        if parts[2] == "duties" and len(parts) == 4:
            handle = parts[3][:-5] if parts[3].endswith(".json") else ""
            kind = "duty"
        elif parts[2] == "tasks" and len(parts) == 4:
            handle = parts[3][:-5] if parts[3].endswith(".json") else ""
            kind = "task"
        elif parts[2] == "opks" and len(parts) == 5:
            handle = parts[4][:-5] if parts[4].endswith(".json") else ""
            kind = {
                "o": "output",
                "p": "indicator",
                "k": "knowledge",
                "s": "skill",
            }.get(parts[3], "")
        else:
            continue
        if not handle or not kind:
            continue
        try:
            identity = catalog.id_for_handle(handle)
        except KeyError:
            identity = (
                workspace_entity_id(
                    catalog.document.document_id,
                    handle,
                    kind,
                    handle_registry=catalog.handle_to_stable,
                )
                if new_entity_namespace == "workspace"
                else uuid5(
                    catalog.document.document_id,
                    f"candidate:{run_id}:{kind}:{handle}",
                )
            )
        result[identity] = handle
    return result


def _candidate_action_handles(
    changes: Sequence[ReviewableDocumentChange],
    *,
    pending_handles: Mapping[str, UUID],
) -> dict[ActionHandle, str]:
    offset = len(pending_handles)
    return {
        f"action-{offset + index + 1:03d}": change.change_ref
        for index, change in enumerate(changes)
    }


def _apply_review_groups(
    changes: Sequence[ReviewableDocumentChange],
    groups: Sequence[CandidateReviewGroup],
    *,
    pending_handles: Mapping[str, UUID],
) -> tuple[tuple[ReviewableDocumentChange, ...], tuple[UUID, ...], tuple[str, ...]]:
    candidate_handles = _candidate_action_handles(
        changes,
        pending_handles=pending_handles,
    )
    known_handles = set(pending_handles) | set(candidate_handles)
    issues: list[str] = []
    updates: dict[str, dict[str, Any]] = {}
    external_ids: set[UUID] = set()
    for group in groups:
        referenced = (*group.action_handles, *group.depends_on_handles)
        unknown = sorted(set(referenced) - known_handles)
        if unknown:
            issues.append(
                f"review group {group.handle} references unknown action handle(s): "
                + ", ".join(unknown)
            )
            continue
        members = [
            candidate_handles[handle]
            for handle in group.action_handles
            if handle in candidate_handles
        ]
        dependencies = [
            candidate_handles[handle]
            for handle in group.depends_on_handles
            if handle in candidate_handles
        ]
        pending_dependencies = [
            pending_handles[handle]
            for handle in group.depends_on_handles
            if handle in pending_handles
        ]
        external_ids.update(pending_dependencies)
        for change_ref in members:
            update = updates.setdefault(change_ref, {})
            update["atomic_group_ref"] = group.handle
            update["depends_on_change_refs"] = tuple(
                dict.fromkeys(
                    (*update.get("depends_on_change_refs", ()), *dependencies)
                )
            )
            update["depends_on_action_ids"] = tuple(
                dict.fromkeys(
                    (*update.get("depends_on_action_ids", ()), *pending_dependencies)
                )
            )
    if issues:
        return tuple(changes), tuple(sorted(external_ids, key=str)), tuple(issues)
    return (
        tuple(
            change.model_copy(update=updates.get(change.change_ref, {}))
            for change in changes
        ),
        tuple(sorted(external_ids, key=str)),
        (),
    )


def _candidate_compatibility_view(
    files: Mapping[str, str],
    run_id: UUID,
) -> dict[str, str]:
    """Adapt the persistent workspace root to the pre-Task-6 check parser."""

    workspace_prefix = "/workspace/"
    candidate_prefix = f"/candidate/{run_id}/"
    return {
        (
            f"{candidate_prefix}{path.removeprefix(workspace_prefix)}"
            if path.startswith(workspace_prefix)
            else path
        ): content
        for path, content in files.items()
    }


def check_candidate_document(
    request: CandidateCheckRequest,
    *,
    catalog: WorkspaceCatalog,
    existing_review_queue: Mapping[str, dict[str, Any]],
    interview_work: Mapping[str, dict[str, Any]],
) -> CandidateCheckResult:
    """Parse, verify, and materialize one candidate without queue mutation."""

    digest = resource_digest(request.files)
    new_entity_namespace: Literal["candidate", "workspace"] = (
        "workspace"
        if request.files
        and all(path.startswith("/workspace/") for path in request.files)
        else "candidate"
    )
    candidate_files = _candidate_compatibility_view(request.files, request.run_id)
    if request.document_id != catalog.document_id:
        return _invalid(request, digest, ("candidate document scope does not match",))
    if not request.selected_skill_ids:
        return _invalid(request, digest, ("candidate check requires selected Skills",))
    validation = validate_workspace_payload(
        request.files,
        catalog=catalog,
        selected_skill_ids=request.selected_skill_ids,
        loaded_skill_ids=request.loaded_skill_ids,
    )
    if validation.diagnostics:
        return _invalid(
            request,
            digest,
            tuple(
                f"{item.code} {item.path}: {item.message}"
                for item in validation.diagnostics
            ),
        )
    draft = validation.document
    if draft is None:
        return _invalid(request, digest, ("candidate resources are invalid",))
    current_sources = validation.current_sources
    default_basis = validation.default_basis
    if default_basis is None:
        return _invalid(
            request,
            digest,
            (
                "candidate verification failed: candidate check requires at least "
                "one loaded Skill for a semantic basis",
            ),
        )
    evidence = validation.evidence_by_handle
    try:
        changes = derive_semantic_changes(
            baseline=catalog.document,
            candidate=draft.approved_document,
            candidate_handles=_candidate_handle_by_id(
                catalog,
                candidate_files,
                request.run_id,
                new_entity_namespace=new_entity_namespace,
            ),
            evidence=evidence,
            default_basis=default_basis,
        )
    except (ValueError, KeyError) as error:
        return _invalid(request, digest, (f"candidate semantic diff is invalid: {error}",))
    if not changes:
        return _invalid(request, digest, ("candidate check found no document change",))

    try:
        used_skill_ids = verify_candidate_document_changes(
            changes,
            document_id=request.document_id,
            selected_skill_ids=request.selected_skill_ids,
            loaded_skill_ids=request.loaded_skill_ids,
            employee_sources=current_sources,
        )
    except ConsultantVerificationError as error:
        return _invalid(request, digest, (f"candidate verification failed: {error}",))

    pending_handles = {
        handle: action_id
        for action_id, handle in pending_action_handles(catalog.pending).items()
    }
    changes, external_ids, group_issues = _apply_review_groups(
        changes,
        draft.review_groups.groups,
        pending_handles=pending_handles,
    )
    if group_issues:
        return _invalid(request, digest, group_issues)
    try:
        changeset = create_document_changeset(
            document_id=request.document_id,
            run_id=request.run_id,
            summary="Verified virtual JD candidate",
            read_revision=request.baseline_revision,
            document=catalog.document,
            changes=changes,
            existing_review_queue=existing_review_queue,
            interview_work=interview_work,
            external_dependency_action_ids=external_ids,
        )
    except (DocumentReviewError, ValueError) as error:
        return _invalid(request, digest, (f"candidate review changeset is invalid: {error}",))

    # Every semantic action has a declared basis.  The default basis is the
    # actually loaded method set; explicit OPKS anchors may narrow it.
    receipt = CheckedCandidateReceipt(
        run_id=request.run_id,
        baseline_revision=request.baseline_revision,
        candidate_revision=request.candidate_revision,
        resource_digest=digest,
        check_call_id=request.check_call_id,
        used_skill_ids=used_skill_ids,
        action_handles=tuple(
            _candidate_action_handles(
                changes,
                pending_handles=pending_handles,
            )
        ),
        changeset=changeset,
    )
    return CandidateCheckResult(
        status="checked",
        run_id=request.run_id,
        candidate_revision=request.candidate_revision,
        resource_digest=digest,
        action_handles=receipt.action_handles,
        actions=changeset.actions,
        receipt=receipt,
        review_queue={},
    )


def _validate_read_set(
    changeset: DocumentChangeSet,
    document: ApprovedJobDocument,
) -> tuple[str, ...]:
    issues: list[str] = []
    for action in changeset.actions:
        for read in action.read_set:
            actual = document_path_sha256(document, read.path)
            if actual != read.value_sha256:
                issues.append(f"document read-set changed at {read.path}")
    return tuple(issues)


def publish_checked_candidate(
    receipt: CheckedCandidateReceipt,
    *,
    current_run_id: UUID,
    current_baseline_revision: int,
    current_document: ApprovedJobDocument,
    current_files: Mapping[str, str | bytes],
    current_source_ids: Sequence[UUID],
) -> DocumentChangeSet:
    """Validate the exact checked receipt before the graph queue transition."""

    if receipt.run_id != current_run_id:
        raise CandidatePublicationStale("candidate publication run is stale")
    if receipt.baseline_revision != current_baseline_revision:
        raise CandidatePublicationStale("candidate publication baseline revision is stale")
    if receipt.resource_digest != resource_digest(current_files):
        raise CandidatePublicationStale("candidate publication resource digest is stale")
    missing_sources = set(receipt.changeset.source_ids) - set(current_source_ids)
    if missing_sources:
        raise CandidatePublicationStale(
            "candidate publication source read-set is stale: "
            + ", ".join(sorted(str(item) for item in missing_sources))
        )
    read_issues = _validate_read_set(receipt.changeset, current_document)
    if read_issues:
        raise CandidatePublicationStale("; ".join(read_issues))
    return receipt.changeset
