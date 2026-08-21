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
    JsonValue,
    StringConstraints,
    model_validator,
)
from typing_extensions import Annotated

from app.consultant.document_authority import document_path_sha256
from app.consultant.document_review import (
    DocumentReviewError,
    create_document_changeset,
)
from app.consultant.evidence_anchor import (
    EvidenceAnchorError,
    resolve_evidence_reference,
)
from app.consultant.results import (
    AnalysisBasis,
    DocumentChangeOperation,
    OpksKind,
    ReviewableDocumentChange,
    SkillId,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedOpksItem,
    ApprovedOpksKind,
    ApprovedTask,
    CheckedCandidateReceipt,
    DocumentChangeSet,
    DocumentPatchAction,
    EmployeeSource,
    NonEmptyText,
    SourceProcessingStatus,
    SourceValidity,
)
from app.consultant.verification import (
    ConsultantVerificationError,
    verify_candidate_document_changes,
)
from app.consultant.workspace_resources import (
    CandidateDocumentDraft,
    CandidateReviewGroup,
    WorkspaceCatalog,
    WorkspaceResourceError,
    parse_candidate_files,
)


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
    actions: tuple[DocumentPatchAction, ...] = ()
    receipt: CheckedCandidateReceipt | None = None
    issues: tuple[str, ...] = ()
    # A check is deliberately not a review-queue mutation.  Keeping this
    # projection in the result makes that boundary explicit to callers.
    review_queue: dict[str, dict[str, Any]] = Field(default_factory=dict)


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


_HEADER_FIELDS = (
    "job_title",
    "occupation_category_name",
    "occupation_name",
    "occupation_code",
    "industry_name",
    "industry_code",
    "work_description",
    "notes",
)
_DUTY_FIELDS = ("statement",)
_TASK_FIELDS = (
    "duty_id",
    "statement",
    "action",
    "object",
    "purpose_result",
    "context",
    "frequency_text",
    "responsibility_role",
    "enablers",
)
_OPKS_FIELDS = ("text", "task_ids", "indicator_ids")
_EDITABLE_OPKS_KINDS = {
    ApprovedOpksKind.OUTPUT,
    ApprovedOpksKind.PERFORMANCE_INDICATOR,
    ApprovedOpksKind.KNOWLEDGE,
    ApprovedOpksKind.SKILL,
}


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


def _model_json(value: Any) -> dict[str, JsonValue]:
    return value.model_dump(mode="json")


def _current_sources(catalog: WorkspaceCatalog) -> tuple[EmployeeSource, ...]:
    return tuple(
        sorted(
            (
                source
                for source in catalog.sources
                if source.document_id == catalog.document_id
                and source.processing_status is SourceProcessingStatus.COMMITTED
                and source.validity is SourceValidity.CURRENT
            ),
            key=lambda source: str(source.source_id),
        )
    )


def _basis_from_sources(
    source_ids: Sequence[UUID],
    skill_ids: Sequence[SkillId],
) -> AnalysisBasis:
    unique_skill_ids = tuple(dict.fromkeys(skill_ids))
    if not unique_skill_ids:
        raise ConsultantVerificationError(
            "candidate check requires at least one loaded Skill for a semantic basis"
        )
    return AnalysisBasis(
        source_ids=tuple(dict.fromkeys(source_ids)),
        skill_ids=unique_skill_ids,
    )


def _entity_maps(document: ApprovedJobDocument) -> tuple[
    dict[UUID, ApprovedDuty],
    dict[UUID, ApprovedTask],
    dict[UUID, ApprovedOpksItem],
]:
    return (
        {item.duty_id: item for item in document.duties},
        {item.task_id: item for item in document.tasks},
        {item.item_id: item for item in document.opks},
    )


def _next_orders(
    document: ApprovedJobDocument,
    candidate: ApprovedJobDocument,
) -> dict[str, dict[UUID, int]]:
    """Assign new resource order per collection/OPKS axis deterministically."""

    result: dict[str, dict[UUID, int]] = {
        "duties": {},
        "tasks": {},
        "output": {},
        "indicator": {},
        "knowledge": {},
        "skill": {},
    }
    baseline_duties = {item.duty_id for item in document.duties}
    baseline_tasks = {item.task_id for item in document.tasks}
    for collection, values, baseline_ids in (
        ("duties", candidate.duties, baseline_duties),
        ("tasks", candidate.tasks, baseline_tasks),
    ):
        next_order = max(
            (item.display_order for item in getattr(document, collection)),
            default=-1,
        ) + 1
        if collection == "duties":
            new_values = (
                item for item in values if item.duty_id not in baseline_ids
            )
            key = lambda item: (item.display_order, str(item.duty_id))
        else:
            new_values = (
                item for item in values if item.task_id not in baseline_ids
            )
            key = lambda item: (item.display_order, str(item.task_id))
        for item in sorted(new_values, key=key):
            identity = item.duty_id if collection == "duties" else item.task_id
            result[collection][identity] = next_order
            next_order += 1
    for kind in _EDITABLE_OPKS_KINDS:
        key = kind.value
        baseline_values = [item for item in document.opks if item.kind is kind]
        baseline_ids = {item.item_id for item in baseline_values}
        next_order = max((item.display_order for item in baseline_values), default=-1) + 1
        new_values = sorted(
            (
                item
                for item in candidate.opks
                if item.kind is kind and item.item_id not in baseline_ids
            ),
            key=lambda item: (item.display_order, str(item.item_id)),
        )
        for item in new_values:
            result[key][item.item_id] = next_order
            next_order += 1
    return result


def _normalized_entity_after(
    value: ApprovedDuty | ApprovedTask | ApprovedOpksItem,
    *,
    baseline: ApprovedJobDocument,
    orders: Mapping[str, Mapping[UUID, int]],
) -> dict[str, JsonValue]:
    payload = _model_json(value)
    identity: UUID
    collection: str
    if isinstance(value, ApprovedDuty):
        identity = value.duty_id
        collection = "duties"
    elif isinstance(value, ApprovedTask):
        identity = value.task_id
        collection = "tasks"
    else:
        identity = value.item_id
        collection = value.kind.value
        payload.pop("evidence_source_ids", None)
    if identity not in {
        item.duty_id for item in baseline.duties
    } | {item.task_id for item in baseline.tasks} | {
        item.item_id for item in baseline.opks
    }:
        payload["display_order"] = orders[collection][identity]
    return payload


def _candidate_handle_by_id(
    catalog: WorkspaceCatalog,
    files: Mapping[str, str],
    run_id: UUID,
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
            identity = uuid5(
                catalog.document.document_id,
                f"candidate:{run_id}:{kind}:{handle}",
            )
        result[identity] = handle
    return result


def _new_change(
    *,
    operation: DocumentChangeOperation,
    path: str,
    basis: AnalysisBasis,
    after: JsonValue | None = None,
    change_ref: str,
    **kwargs: Any,
) -> ReviewableDocumentChange:
    return ReviewableDocumentChange(
        operation=operation,
        path=path,
        after=after,
        basis=basis,
        change_ref=change_ref,
        **kwargs,
    )


def _opks_basis(
    *,
    item: ApprovedOpksItem,
    handle: str,
    bindings: Mapping[str, tuple[AnalysisBasis, ...]],
    default: AnalysisBasis,
    changed: bool,
) -> AnalysisBasis:
    if not changed:
        return default
    bound = bindings.get(handle, ())
    if bound:
        source_ids: list[UUID] = []
        quote_anchors = []
        skill_ids: list[SkillId] = []
        for basis in bound:
            source_ids.extend(basis.source_ids)
            quote_anchors.extend(basis.quote_anchors)
            skill_ids.extend(basis.skill_ids)
        return AnalysisBasis(
            source_ids=tuple(dict.fromkeys(source_ids)),
            quote_anchors=tuple(quote_anchors),
            skill_ids=tuple(dict.fromkeys(skill_ids)),
        )
    return default


def _pending_action_handles(
    pending: Sequence[DocumentChangeSet],
) -> dict[str, UUID]:
    handles: dict[str, UUID] = {}
    for changeset in sorted(
        pending,
        key=lambda value: (value.created_revision, str(value.changeset_id)),
    ):
        for action in changeset.actions:
            handles[f"action-{len(handles) + 1:03d}"] = action.action_id
    external = sorted(
        {
            dependency_id
            for changeset in pending
            for dependency_id in changeset.external_dependency_action_ids
            if dependency_id not in handles.values()
        },
        key=str,
    )
    for dependency_id in external:
        handles[f"action-{len(handles) + 1:03d}"] = dependency_id
    return handles


def _apply_review_groups(
    changes: Sequence[ReviewableDocumentChange],
    groups: Sequence[CandidateReviewGroup],
    *,
    pending_handles: Mapping[str, UUID],
) -> tuple[tuple[ReviewableDocumentChange, ...], tuple[UUID, ...], tuple[str, ...]]:
    offset = len(pending_handles)
    candidate_handles = {
        f"action-{offset + index + 1:03d}": change.change_ref
        for index, change in enumerate(changes)
    }
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


def _resolve_evidence(
    draft: CandidateDocumentDraft,
    catalog: WorkspaceCatalog,
    request: CandidateCheckRequest,
) -> tuple[dict[str, tuple[AnalysisBasis, ...]], tuple[str, ...]]:
    bindings: dict[str, list[AnalysisBasis]] = {}
    issues: list[str] = []
    loaded = set(request.loaded_skill_ids)
    selected = set(request.selected_skill_ids)
    for binding in draft.opks_evidence:
        for reference in binding.references:
            missing = set(reference.skill_ids) - selected
            if missing:
                issues.append(
                    f"evidence for {binding.opks_handle} uses unselected Skill(s): "
                    + ", ".join(sorted(missing))
                )
            unloaded = set(reference.skill_ids) - loaded
            if unloaded:
                issues.append(
                    f"evidence for {binding.opks_handle} uses unloaded Skill(s): "
                    + ", ".join(sorted(unloaded))
                )
            try:
                anchor = resolve_evidence_reference(reference, catalog)
            except EvidenceAnchorError as error:
                issues.append(
                    f"evidence for {binding.opks_handle} is invalid: {error}"
                )
                continue
            source = next(
                (item for item in catalog.sources if item.source_id == anchor.source_id),
                None,
            )
            if source is None or source.processing_status is not SourceProcessingStatus.COMMITTED:
                issues.append(
                    f"evidence for {binding.opks_handle} does not use a committed source"
                )
                continue
            bindings.setdefault(binding.opks_handle, []).append(
                AnalysisBasis(
                    source_ids=(anchor.source_id,),
                    quote_anchors=(anchor,),
                    skill_ids=reference.skill_ids,
                )
            )
    return (
        {handle: tuple(values) for handle, values in bindings.items()},
        tuple(issues),
    )


def _semantic_changes(
    *,
    baseline: ApprovedJobDocument,
    candidate: ApprovedJobDocument,
    catalog: WorkspaceCatalog,
    candidate_handles: Mapping[UUID, str],
    evidence: Mapping[str, tuple[AnalysisBasis, ...]],
    default_basis: AnalysisBasis,
) -> tuple[ReviewableDocumentChange, ...]:
    baseline_duties, baseline_tasks, baseline_opks = _entity_maps(baseline)
    candidate_duties, candidate_tasks, candidate_opks = _entity_maps(candidate)
    changes: list[ReviewableDocumentChange] = []

    def add(**kwargs: Any) -> None:
        changes.append(
            _new_change(
                change_ref=f"candidate-{len(changes) + 1:03d}",
                **kwargs,
            )
        )

    baseline_header = baseline.model_dump(mode="json")
    candidate_header = candidate.model_dump(mode="json")
    for field in _HEADER_FIELDS:
        if baseline_header[field] != candidate_header[field]:
            add(
                operation=DocumentChangeOperation.REVISE,
                path=f"/{field}",
                after=candidate_header[field],
                basis=default_basis,
            )

    orders = _next_orders(baseline, candidate)
    for identity in sorted(set(baseline_duties) - set(candidate_duties), key=str):
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/duties/{identity}",
            basis=default_basis,
        )
    for identity in sorted(set(candidate_duties) - set(baseline_duties), key=str):
        add(
            operation=DocumentChangeOperation.ADD,
            path="/duties",
            after=_normalized_entity_after(
                candidate_duties[identity], baseline=baseline, orders=orders
            ),
            basis=default_basis,
        )
    for identity in sorted(set(baseline_duties) & set(candidate_duties), key=str):
        before = _model_json(baseline_duties[identity])
        after = _model_json(candidate_duties[identity])
        for field in _DUTY_FIELDS:
            if before[field] != after[field]:
                add(
                    operation=DocumentChangeOperation.REVISE,
                    path=f"/duties/{identity}/{field}",
                    after=after[field],
                    basis=default_basis,
                )

    for identity in sorted(set(baseline_tasks) - set(candidate_tasks), key=str):
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/tasks/{identity}",
            basis=default_basis,
        )
    for identity in sorted(set(candidate_tasks) - set(baseline_tasks), key=str):
        add(
            operation=DocumentChangeOperation.ADD,
            path="/tasks",
            after=_normalized_entity_after(
                candidate_tasks[identity], baseline=baseline, orders=orders
            ),
            basis=default_basis,
        )
    for identity in sorted(set(baseline_tasks) & set(candidate_tasks), key=str):
        before = _model_json(baseline_tasks[identity])
        after = _model_json(candidate_tasks[identity])
        for field in _TASK_FIELDS:
            if before[field] != after[field]:
                add(
                    operation=DocumentChangeOperation.REVISE,
                    path=f"/tasks/{identity}/{field}",
                    after=after[field],
                    basis=default_basis,
                )

    for identity in sorted(set(baseline_opks) - set(candidate_opks), key=str):
        item = baseline_opks[identity]
        if item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        add(
            operation=DocumentChangeOperation.WITHDRAW,
            path=f"/opks/{identity}",
            basis=default_basis,
            opks_kind=OpksKind(item.kind.value),
        )
    for identity in sorted(set(candidate_opks) - set(baseline_opks), key=str):
        item = candidate_opks[identity]
        if item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        handle = candidate_handles.get(identity, "")
        basis = _opks_basis(
            item=item,
            handle=handle,
            bindings=evidence,
            default=default_basis,
            changed=True,
        )
        after = _normalized_entity_after(item, baseline=baseline, orders=orders)
        # The existing review factory is the single allocator for new OPKS
        # orders.  Leaving this field absent/None lets it assign the next
        # order within the axis, independent of parser file ordering.
        after["display_order"] = None
        add(
            operation=DocumentChangeOperation.ADD,
            path="/opks",
            after=after,
            basis=basis,
            opks_kind=OpksKind(item.kind.value),
            task_ids=item.task_ids,
            indicator_ids=item.indicator_ids,
        )
    for identity in sorted(set(baseline_opks) & set(candidate_opks), key=str):
        before_item = baseline_opks[identity]
        after_item = candidate_opks[identity]
        if before_item.kind not in _EDITABLE_OPKS_KINDS:
            continue
        before = _model_json(before_item)
        after = _model_json(after_item)
        handle = candidate_handles.get(identity, catalog.handle_for_id(identity))
        changed = any(before[field] != after[field] for field in _OPKS_FIELDS)
        basis = _opks_basis(
            item=after_item,
            handle=handle,
            bindings=evidence,
            default=default_basis,
            changed=changed,
        )
        for field in _OPKS_FIELDS:
            if before[field] != after[field]:
                add(
                    operation=DocumentChangeOperation.REVISE,
                    path=f"/opks/{identity}/{field}",
                    after=after[field],
                    basis=basis,
                    opks_kind=OpksKind(after_item.kind.value),
                    task_ids=after_item.task_ids,
                    indicator_ids=after_item.indicator_ids,
                )
    return tuple(changes)


def check_candidate_document(
    request: CandidateCheckRequest,
    *,
    catalog: WorkspaceCatalog,
    existing_review_queue: Mapping[str, dict[str, Any]],
    interview_work: Mapping[str, dict[str, Any]],
) -> CandidateCheckResult:
    """Parse, verify, and materialize one candidate without queue mutation."""

    digest = resource_digest(request.files)
    if request.document_id != catalog.document_id:
        return _invalid(request, digest, ("candidate document scope does not match",))
    if not request.selected_skill_ids:
        return _invalid(request, digest, ("candidate check requires selected Skills",))
    current_sources = _current_sources(catalog)
    if not current_sources:
        return _invalid(
            request,
            digest,
            ("candidate check requires at least one current committed employee source",),
        )
    try:
        draft = parse_candidate_files(catalog, request.files, run_id=request.run_id)
    except (ValueError, WorkspaceResourceError) as error:
        return _invalid(request, digest, (f"candidate resources are invalid: {error}",))

    try:
        default_basis = _basis_from_sources(
            [source.source_id for source in current_sources],
            request.loaded_skill_ids,
        )
    except ConsultantVerificationError as error:
        return _invalid(request, digest, (f"candidate verification failed: {error}",))
    evidence, evidence_issues = _resolve_evidence(draft, catalog, request)
    if evidence_issues:
        return _invalid(request, digest, evidence_issues)
    try:
        changes = _semantic_changes(
            baseline=catalog.document,
            candidate=draft.approved_document,
            catalog=catalog,
            candidate_handles=_candidate_handle_by_id(
                catalog, request.files, request.run_id
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

    pending_handles = _pending_action_handles(catalog.pending)
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
        changeset=changeset,
    )
    return CandidateCheckResult(
        status="checked",
        run_id=request.run_id,
        candidate_revision=request.candidate_revision,
        resource_digest=digest,
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
