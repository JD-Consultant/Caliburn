"""Deterministic validation for the real Store-backed JD working draft."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from types import MappingProxyType
from typing import Annotated, Any, Protocol, cast
from uuid import UUID

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, PrivateStateAttr
from langchain_core.messages import AIMessage
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from pydantic import ValidationError
from typing_extensions import NotRequired, override

from app.consultant.evidence_anchor import EvidenceAnchorError, resolve_evidence_reference
from app.consultant.results import AnalysisBasis, SkillId
from app.consultant.state import (
    ApprovedJobDocument,
    ApprovedOpksKind,
    EmployeeSource,
    SourceProcessingStatus,
    SourceValidity,
)
from app.consultant.verification import requires_anchored_employee_quote
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    WorkspaceDocumentDraft,
    WorkspaceDutyResource,
    WorkspaceHeaderResource,
    WorkspaceOpksResource,
    WorkspaceResourceError,
    WorkspaceTaskResource,
    parse_workspace_files,
    project_workspace_files,
    workspace_entity_id,
)
from app.consultant.workspace_state import (
    Sha256Digest,
    StoreBackedWorkspace,
    WorkspaceDiagnostic,
    WorkspaceDiagnosticSeverity,
    WorkspaceManifest,
    WorkspaceValidationStatus,
    approved_document_digest,
)


SourceLoader = Callable[[], Awaitable[Sequence[EmployeeSource]]]
_MAX_DIAGNOSTICS = 8
_OPKS_PREFIX_BY_KIND = {
    ApprovedOpksKind.OUTPUT: "o",
    ApprovedOpksKind.PERFORMANCE_INDICATOR: "p",
    ApprovedOpksKind.KNOWLEDGE: "k",
    ApprovedOpksKind.SKILL: "s",
}
_ENTITY_PATH = re.compile(
    r"^/workspace/(?:(duties)/(duty-[^/]+)|(tasks)/(task-[^/]+)|"
    r"opks/(o|p|k|s)/((?:o|p|k|s)-[^/]+))\.json$"
)


def _implicit_display_order(
    files: Mapping[str, str],
    resource_path: str,
) -> int | None:
    if resource_path.startswith("/workspace/duties/"):
        paths = sorted(
            path for path in files if path.startswith("/workspace/duties/")
        )
    elif resource_path.startswith("/workspace/tasks/"):
        paths = sorted(
            path for path in files if path.startswith("/workspace/tasks/")
        )
    elif resource_path.startswith("/workspace/opks/"):
        kind_order = {"o": 0, "p": 1, "k": 2, "s": 3}

        def opks_key(path: str) -> tuple[int, str]:
            parts = path.split("/")
            return kind_order.get(parts[3] if len(parts) > 3 else "", 99), path

        paths = sorted(
            (path for path in files if path.startswith("/workspace/opks/")),
            key=opks_key,
        )
    else:
        return None
    try:
        return paths.index(resource_path)
    except ValueError:
        return None


def _normalized_conflict_resource(
    files: Mapping[str, str],
    resource_path: str,
    value: Any,
) -> Any:
    model = _resource_schema_model(resource_path)
    if model is None:
        return value
    try:
        normalized = model.model_validate(value).model_dump(mode="json")
    except ValueError:
        return value
    normalized.pop("evidence", None)
    if normalized.get("display_order") is None:
        normalized["display_order"] = _implicit_display_order(files, resource_path)
    return normalized


@dataclass(frozen=True, slots=True)
class WorkspaceValidationSummary:
    generation: int
    status: WorkspaceValidationStatus
    resource_digest: Sha256Digest
    diagnostics: tuple[WorkspaceDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceValidationResult:
    manifest: WorkspaceManifest
    document: WorkspaceDocumentDraft | None
    diagnostics: tuple[WorkspaceDiagnostic, ...]
    revalidated: bool

    def __post_init__(self) -> None:
        exposes_document = self.manifest.validation_status in {
            WorkspaceValidationStatus.VALID,
            WorkspaceValidationStatus.CONFLICTED,
        }
        if exposes_document != (self.document is not None):
            raise ValueError(
                "only a valid or conflicted workspace may expose a parsed document"
            )

    @property
    def summary(self) -> WorkspaceValidationSummary:
        return WorkspaceValidationSummary(
            generation=self.manifest.generation,
            status=self.manifest.validation_status,
            resource_digest=self.manifest.resource_digest,
            diagnostics=self.diagnostics[:_MAX_DIAGNOSTICS],
        )


@dataclass(frozen=True, slots=True)
class WorkspacePayloadValidation:
    document: WorkspaceDocumentDraft | None
    diagnostics: tuple[WorkspaceDiagnostic, ...]
    current_sources: tuple[EmployeeSource, ...]
    evidence_by_handle: Mapping[str, tuple[AnalysisBasis, ...]]
    default_basis: AnalysisBasis | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_by_handle",
            MappingProxyType(dict(self.evidence_by_handle)),
        )


def _resource_value(
    files: Mapping[str, str],
    diagnostic_path: str,
) -> tuple[bool, Any]:
    marker = diagnostic_path.find(".json")
    if marker < 0:
        return False, None
    resource_path = diagnostic_path[: marker + len(".json")]
    raw = files.get(resource_path)
    if raw is None:
        return False, None
    pointer = diagnostic_path[marker + len(".json") :]
    try:
        value: Any = json.loads(raw)
    except json.JSONDecodeError:
        return True, raw
    if not pointer:
        return True, _normalized_conflict_resource(files, resource_path, value)
    for segment in pointer.removeprefix("/").split("/"):
        segment = segment.replace("~1", "/").replace("~0", "~")
        if isinstance(value, dict) and segment in value:
            value = value[segment]
        elif isinstance(value, list):
            try:
                value = value[int(segment)]
            except (ValueError, IndexError):
                return False, None
        else:
            return False, None
    return True, value


def active_conflict_diagnostics(
    *,
    files: Mapping[str, str],
    approved_document: ApprovedJobDocument,
    manifest: WorkspaceManifest,
) -> tuple[WorkspaceDiagnostic, ...]:
    """Keep conflict metadata until its affected Store value converges."""

    conflicts = tuple(
        diagnostic
        for diagnostic in manifest.diagnostics
        if diagnostic.code == "workspace-rebase-conflict"
    )
    if not conflicts:
        return ()
    try:
        approved_files = project_workspace_files(
            approved_document,
            handle_registry=manifest.entity_ids_by_handle,
        ).files
    except (TypeError, ValueError, WorkspaceResourceError):
        return conflicts
    active: list[WorkspaceDiagnostic] = []
    for diagnostic in conflicts:
        current_exists, current = _resource_value(files, diagnostic.path)
        approved_exists, approved = _resource_value(approved_files, diagnostic.path)
        if (current_exists, current) != (approved_exists, approved):
            active.append(diagnostic)
    return tuple(active)


def _short(value: object, *, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _diagnostic(code: str, path: str, message: object) -> WorkspaceDiagnostic:
    return WorkspaceDiagnostic(
        code=_short(code, limit=80),
        path=_short(path, limit=160),
        message=_short(message, limit=240),
        severity=WorkspaceDiagnosticSeverity.ERROR,
    )


def _workspace_path_for_handle(files: Mapping[str, str], handle: str) -> str:
    suffix = f"/{handle}.json"
    return next(
        (path for path in sorted(files) if path.endswith(suffix)),
        "/workspace",
    )


def _workspace_path_from_error(error: BaseException, files: Mapping[str, str]) -> str:
    message = str(error)
    direct = re.search(r"(/workspace/[^\s:]+)", message)
    if direct is not None:
        return direct.group(1).rstrip(".,)")
    relative = re.search(
        r"(?:resource|path):?\s+(header\.json|(?:duties|tasks|opks)/[^\s:]+\.json)",
        message,
    )
    if relative is not None:
        return "/workspace/" + relative.group(1).rstrip(".,)")
    handle = re.search(r"\b(?:duty|task|o|p|k|s)-[a-z0-9-]+\b", message)
    if handle is not None:
        value = handle.group(0)
        by_name = _workspace_path_for_handle(files, value)
        if by_name != "/workspace":
            return by_name
        return next(
            (path for path, content in sorted(files.items()) if value in content),
            "/workspace",
        )
    return "/workspace"


def _resource_error_diagnostic(
    error: BaseException,
    files: Mapping[str, str],
) -> WorkspaceDiagnostic:
    lowered = str(error).casefold()
    if "invalid json" in lowered:
        code = "json-syntax"
        safe_message = "Resource is not valid JSON."
    elif "duplicate task_handles" in lowered or "must reference" in lowered:
        code = "jd-invariant"
        safe_message = "JD relationship cardinality is invalid."
    elif (
        "unknown duty" in lowered
        or "unknown task" in lowered
        or "unknown indicator" in lowered
    ):
        code = "linkage"
        safe_message = "Resource references a missing Duty, Task, or indicator handle."
    elif "invalid resource" in lowered:
        code = "schema"
        safe_message = _safe_schema_error_message(error)
    elif "handle" in lowered or "stable id" in lowered or "collision" in lowered:
        code = "identity"
        safe_message = "Resource identity does not match its path or registry."
    else:
        code = "jd-invariant"
        safe_message = "JD resources do not form a valid document."
    return _diagnostic(
        code,
        _workspace_path_from_error(error, files),
        safe_message,
    )


def _safe_schema_error_message(error: BaseException) -> str:
    """Keep Pydantic's actionable location/type while omitting input values."""

    cause: BaseException | None = error
    while cause is not None and not isinstance(cause, ValidationError):
        cause = cause.__cause__
    if not isinstance(cause, ValidationError):
        return "Resource does not match the canonical JD schema."
    issues = cause.errors(
        include_url=False,
        include_context=False,
        include_input=False,
    )
    if not issues:
        return "Resource does not match the canonical JD schema."
    issue = issues[0]
    location = ".".join(str(part) for part in issue.get("loc", ()))[:120]
    issue_type = str(issue.get("type", "validation_error"))
    if issue_type == "extra_forbidden" and location:
        return f"Unexpected field `{location}` is not part of this resource schema; remove it."
    if issue_type == "missing" and location:
        return f"Required field `{location}` is missing."
    if location:
        return f"Field `{location}` is invalid ({issue_type})."
    return f"Resource does not match the canonical JD schema ({issue_type})."


def _resource_schema_model(path: str) -> type[Any] | None:
    if path == "/workspace/header.json":
        return WorkspaceHeaderResource
    match = _ENTITY_PATH.fullmatch(path)
    if match is None:
        return None
    if match.group(1) == "duties":
        return WorkspaceDutyResource
    if match.group(3) == "tasks":
        return WorkspaceTaskResource
    return WorkspaceOpksResource


def _resource_schema_diagnostics(
    files: Mapping[str, str],
) -> tuple[WorkspaceDiagnostic, ...]:
    """Preflight independent resources so one bad file cannot hide the next."""

    diagnostics: list[WorkspaceDiagnostic] = []
    for path, raw in sorted(files.items()):
        model = _resource_schema_model(path)
        if model is None:
            continue
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            diagnostics.append(
                _diagnostic("json-syntax", path, "Resource is not valid JSON.")
            )
        else:
            try:
                model.model_validate(payload)
            except ValidationError as error:
                lowered = str(error).casefold()
                if "duplicate task_handles" in lowered or "must reference" in lowered:
                    code = "jd-invariant"
                    message = "JD relationship cardinality is invalid."
                else:
                    code = "schema"
                    message = _safe_schema_error_message(error)
                diagnostics.append(
                    _diagnostic(code, path, message)
                )
        if len(diagnostics) >= _MAX_DIAGNOSTICS:
            break
    return tuple(diagnostics)


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


def _default_basis(
    sources: Sequence[EmployeeSource],
    loaded_skill_ids: Sequence[SkillId],
) -> AnalysisBasis | None:
    skills = tuple(dict.fromkeys(loaded_skill_ids))
    if not skills:
        return None
    return AnalysisBasis(
        source_ids=tuple(source.source_id for source in sources),
        skill_ids=skills,
    )


def _resolve_evidence(
    draft: WorkspaceDocumentDraft,
    catalog: WorkspaceCatalog,
    files: Mapping[str, str],
    *,
    selected_skill_ids: Sequence[SkillId],
    loaded_skill_ids: Sequence[SkillId],
) -> tuple[
    dict[str, tuple[AnalysisBasis, ...]],
    tuple[WorkspaceDiagnostic, ...],
]:
    selected = set(selected_skill_ids)
    loaded = set(loaded_skill_ids)
    bindings: dict[str, list[AnalysisBasis]] = {}
    diagnostics: list[WorkspaceDiagnostic] = []
    for binding in draft.evidence_bindings:
        path = binding.resource_path
        for reference in binding.references:
            if set(reference.skill_ids) - selected:
                diagnostics.append(
                    _diagnostic(
                        "skill-unselected",
                        path,
                        "Evidence references a Skill outside this consultant run.",
                    )
                )
                continue
            if set(reference.skill_ids) - loaded:
                diagnostics.append(
                    _diagnostic(
                        "skill-unloaded",
                        path,
                        "Read the referenced Skill before validating this evidence.",
                    )
                )
                continue
            try:
                anchor = resolve_evidence_reference(reference, catalog)
            except EvidenceAnchorError as error:
                code = (
                    "evidence-source-stale"
                    if "superseded" in str(error).casefold()
                    or "unknown source" in str(error).casefold()
                    else "evidence-quote"
                )
                diagnostics.append(_diagnostic(code, path, str(error)))
                continue
            source = next(
                (item for item in catalog.sources if item.source_id == anchor.source_id),
                None,
            )
            if (
                source is None
                or source.processing_status is not SourceProcessingStatus.COMMITTED
                or source.validity is not SourceValidity.CURRENT
            ):
                diagnostics.append(
                    _diagnostic(
                        "evidence-source-stale",
                        path,
                        "Evidence source is not current and committed.",
                    )
                )
                continue
            bindings.setdefault(binding.resource_handle, []).append(
                AnalysisBasis(
                    source_ids=(anchor.source_id,),
                    quote_anchors=(anchor,),
                    skill_ids=reference.skill_ids,
                )
            )
    return (
        {handle: tuple(values) for handle, values in bindings.items()},
        tuple(diagnostics[:_MAX_DIAGNOSTICS]),
    )


def _semantic_evidence_diagnostics(
    draft: WorkspaceDocumentDraft,
    baseline: ApprovedJobDocument,
    evidence_by_handle: Mapping[str, tuple[AnalysisBasis, ...]],
) -> tuple[WorkspaceDiagnostic, ...]:
    """Keep accepted Evidence rules on the persistent workspace lifecycle."""

    handle_by_id = {
        stable_id: handle for handle, stable_id in draft.handle_registry.items()
    }
    anchored_handles = {
        handle
        for handle, bases in evidence_by_handle.items()
        if any(basis.quote_anchors for basis in bases)
    }
    diagnostics: list[WorkspaceDiagnostic] = []
    seen_paths: set[str] = set()

    def add(path: str, message: str) -> None:
        if path in seen_paths or len(diagnostics) >= _MAX_DIAGNOSTICS:
            return
        seen_paths.add(path)
        diagnostics.append(_diagnostic("evidence-anchor-required", path, message))

    def require_for_risky_text(
        path: str,
        text: str | None,
        handle: str | None,
    ) -> None:
        if (
            text
            and requires_anchored_employee_quote(text)
            and (handle is None or handle not in anchored_handles)
        ):
            add(
                path,
                "Quantities, named rules, SOPs, and external claims require an exact employee quote.",
            )

    working = draft.approved_document
    for field in (
        "job_title",
        "occupation_category_name",
        "occupation_name",
        "occupation_code",
        "industry_name",
        "industry_code",
        "work_description",
        "notes",
    ):
        before = getattr(baseline, field)
        after = getattr(working, field)
        if before != after:
            require_for_risky_text("/workspace/header.json", after, "header")

    baseline_duties = {item.duty_id: item for item in baseline.duties}
    for duty in working.duties:
        before = baseline_duties.get(duty.duty_id)
        if before is None or before.statement != duty.statement:
            handle = handle_by_id.get(duty.duty_id)
            require_for_risky_text(
                f"/workspace/duties/{handle}.json" if handle else "/workspace/duties",
                duty.statement,
                handle,
            )

    baseline_tasks = {item.task_id: item for item in baseline.tasks}
    task_text_fields = (
        "statement",
        "action",
        "object",
        "purpose_result",
        "context",
        "frequency_text",
    )
    for task in working.tasks:
        before = baseline_tasks.get(task.task_id)
        handle = handle_by_id.get(task.task_id)
        path = f"/workspace/tasks/{handle}.json" if handle else "/workspace/tasks"
        for field in task_text_fields:
            before_value = getattr(before, field) if before is not None else None
            after_value = getattr(task, field)
            if before is None or before_value != after_value:
                require_for_risky_text(path, after_value, handle)
        before_enablers = before.enablers if before is not None else ()
        if before is None or before_enablers != task.enablers:
            for enabler in task.enablers:
                require_for_risky_text(path, enabler.name, handle)

    baseline_opks = {item.item_id: item for item in baseline.opks}
    for item in working.opks:
        prefix = _OPKS_PREFIX_BY_KIND.get(item.kind)
        if prefix is None:
            continue
        before = baseline_opks.get(item.item_id)
        handle = handle_by_id.get(item.item_id)
        path = (
            f"/workspace/opks/{prefix}/{handle}.json"
            if handle
            else f"/workspace/opks/{prefix}"
        )
        semantic_changed = before is None or any(
            getattr(before, field) != getattr(item, field)
            for field in ("text", "task_ids", "indicator_ids")
        )
        if (
            semantic_changed
            and item.kind in {ApprovedOpksKind.KNOWLEDGE, ApprovedOpksKind.SKILL}
            and (handle is None or handle not in anchored_handles)
        ):
            add(path, "Changed Knowledge or Skill requires an exact employee quote.")
        if before is None or before.text != item.text:
            require_for_risky_text(path, item.text, handle)

    return tuple(diagnostics)


def validate_workspace_payload(
    files: Mapping[str, str],
    *,
    catalog: WorkspaceCatalog,
    selected_skill_ids: Sequence[SkillId],
    loaded_skill_ids: Sequence[SkillId],
) -> WorkspacePayloadValidation:
    """Parse and validate one persistent workspace payload without side effects."""

    normalized = dict(sorted(files.items()))
    schema_diagnostics = _resource_schema_diagnostics(normalized)
    if schema_diagnostics:
        return WorkspacePayloadValidation(
            document=None,
            diagnostics=schema_diagnostics,
            current_sources=_current_sources(catalog),
            evidence_by_handle={},
            default_basis=None,
        )
    try:
        draft = parse_workspace_files(
            catalog.document_id,
            normalized,
            handle_registry=catalog.handle_to_stable,
            baseline_document=catalog.document,
        )
    except (ValueError, WorkspaceResourceError) as error:
        return WorkspacePayloadValidation(
            document=None,
            diagnostics=(_resource_error_diagnostic(error, normalized),),
            current_sources=_current_sources(catalog),
            evidence_by_handle={},
            default_basis=None,
        )

    current_sources = _current_sources(catalog)
    if not current_sources:
        return WorkspacePayloadValidation(
            document=None,
            diagnostics=(
                _diagnostic(
                    "evidence-basis-empty",
                    "/workspace",
                    "No current committed employee source can support this draft.",
                ),
            ),
            current_sources=(),
            evidence_by_handle={},
            default_basis=None,
        )
    evidence, diagnostics = _resolve_evidence(
        draft,
        catalog,
        normalized,
        selected_skill_ids=selected_skill_ids,
        loaded_skill_ids=loaded_skill_ids,
    )
    diagnostics = (
        *diagnostics,
        *_semantic_evidence_diagnostics(draft, catalog.document, evidence),
    )
    current_ids = {source.source_id for source in current_sources}
    handles_by_id = {
        stable_id: handle for handle, stable_id in draft.handle_registry.items()
    }
    for item in draft.approved_document.opks:
        if not set(item.evidence_source_ids) - current_ids:
            continue
        handle = handles_by_id.get(item.item_id)
        prefix = _OPKS_PREFIX_BY_KIND.get(item.kind)
        path = (
            f"/workspace/opks/{prefix}/{handle}.json"
            if prefix is not None and handle is not None
            else "/workspace/opks"
        )
        diagnostics = (
            *diagnostics,
            _diagnostic(
                "evidence-source-stale",
                path,
                "OPKS evidence basis contains a source that is no longer current.",
            ),
        )
    diagnostics = tuple(diagnostics[:_MAX_DIAGNOSTICS])
    recoverable_source_correction = bool(diagnostics) and all(
        diagnostic.code == "evidence-source-stale" for diagnostic in diagnostics
    )
    return WorkspacePayloadValidation(
        document=(
            draft if not diagnostics or recoverable_source_correction else None
        ),
        diagnostics=diagnostics,
        current_sources=current_sources,
        evidence_by_handle=evidence,
        default_basis=_default_basis(current_sources, loaded_skill_ids),
    )


def evidence_basis_digest(sources: Sequence[EmployeeSource]) -> Sha256Digest:
    payload = [
        {
            "source_id": str(source.source_id),
            "text_sha256": source.text_sha256,
            "processing_status": source.processing_status.value,
            "validity": source.validity.value,
            "supersedes_source_id": (
                str(source.supersedes_source_id)
                if source.supersedes_source_id is not None
                else None
            ),
            "superseded_by_source_id": (
                str(source.superseded_by_source_id)
                if source.superseded_by_source_id is not None
                else None
            ),
        }
        for source in sorted(sources, key=lambda item: str(item.source_id))
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return cast(Sha256Digest, sha256(encoded).hexdigest())


def _entity_registry(
    *,
    files: Mapping[str, str],
    document_id: UUID,
    manifest: WorkspaceManifest,
    catalog: WorkspaceCatalog,
) -> tuple[dict[str, UUID], WorkspaceDiagnostic | None]:
    registry = dict(manifest.entity_ids_by_handle)
    for handle, stable_id in catalog.handle_to_stable.items():
        if handle.startswith(("duty-", "task-", "o-", "p-", "k-", "s-")):
            known = registry.get(handle)
            if known is not None and known != stable_id:
                return registry, _diagnostic(
                    "identity",
                    _workspace_path_for_handle(files, handle),
                    "Workspace handle no longer matches its stable identity.",
                )
            registry.setdefault(handle, stable_id)
    kind_by_prefix = {
        "duty-": "duty",
        "task-": "task",
        "o-": "output",
        "p-": "indicator",
        "k-": "knowledge",
        "s-": "skill",
    }
    for path in sorted(files):
        match = _ENTITY_PATH.fullmatch(path)
        if match is None:
            continue
        handle = next(value for value in match.groups()[1::2] if value is not None)
        kind = next(
            value
            for prefix, value in kind_by_prefix.items()
            if handle.startswith(prefix)
        )
        stable_id = workspace_entity_id(
            document_id,
            handle,
            kind,
            handle_registry=registry,
        )
        registry.setdefault(handle, stable_id)
    return registry, None


def _approved_registry_issue(
    *,
    files: Mapping[str, str],
    document: ApprovedJobDocument,
    manifest: WorkspaceManifest,
) -> WorkspaceDiagnostic | None:
    """Reject a manifest that forgot an already-approved editable identity."""

    expected = project_workspace_files(document, handle_registry={}).handle_registry
    actual_handle_by_id = {
        stable_id: handle
        for handle, stable_id in manifest.entity_ids_by_handle.items()
    }
    for expected_handle, stable_id in expected.items():
        actual_handle = actual_handle_by_id.get(stable_id)
        if actual_handle is None:
            return _diagnostic(
                "identity",
                _workspace_path_for_handle(files, expected_handle),
                "Workspace registry no longer contains an approved stable identity.",
            )
        expected_prefix = expected_handle.split("-", maxsplit=1)[0]
        if not actual_handle.startswith(f"{expected_prefix}-"):
            return _diagnostic(
                "identity",
                _workspace_path_for_handle(files, actual_handle),
                "Workspace handle no longer matches its approved entity kind.",
            )
    return None


class WorkspaceValidationService:
    def __init__(
        self,
        *,
        workspace: StoreBackedWorkspace,
        catalog: WorkspaceCatalog,
        source_loader: SourceLoader,
        selected_skill_ids: tuple[SkillId, ...],
    ) -> None:
        self._workspace = workspace
        self._catalog = catalog
        self._source_loader = source_loader
        self._selected_skill_ids = selected_skill_ids
        self._last_result: WorkspaceValidationResult | None = None
        self._last_loaded_skill_ids: tuple[SkillId, ...] = ()

    async def validate_current(
        self,
        *,
        loaded_skill_ids: tuple[SkillId, ...],
    ) -> WorkspaceValidationResult:
        sources = tuple(await self._source_loader())
        basis_digest = evidence_basis_digest(
            tuple(
                source
                for source in sources
                if source.processing_status is SourceProcessingStatus.COMMITTED
                and source.validity is SourceValidity.CURRENT
            )
        )
        snapshot = await self._workspace.read_snapshot()
        baseline_digest = approved_document_digest(self._catalog.document)
        last = self._last_result
        same_content = (
            last is not None
            and last.manifest.resource_digest == snapshot.manifest.resource_digest
            and last.manifest.evidence_basis_digest == basis_digest
            and snapshot.manifest.approved_baseline_digest == baseline_digest
            and last.manifest.approved_baseline_digest == baseline_digest
            and last.manifest.validation_status
            is snapshot.manifest.validation_status
            and last.manifest.diagnostics == snapshot.manifest.diagnostics
            and last.manifest.entity_ids_by_handle
            == snapshot.manifest.entity_ids_by_handle
            and loaded_skill_ids == self._last_loaded_skill_ids
        )
        if same_content:
            return WorkspaceValidationResult(
                manifest=snapshot.manifest,
                document=last.document,
                diagnostics=last.diagnostics,
                revalidated=False,
            )

        if snapshot.manifest.approved_baseline_digest != baseline_digest:
            payload = WorkspacePayloadValidation(
                document=None,
                diagnostics=(
                    _diagnostic(
                        "approved-basis-stale",
                        "/workspace",
                        "Workspace approved baseline no longer matches this document.",
                    ),
                ),
                current_sources=(),
                evidence_by_handle={},
                default_basis=None,
            )
            registry = dict(snapshot.manifest.entity_ids_by_handle)
        else:
            approved_identity_issue = _approved_registry_issue(
                files=snapshot.files,
                document=self._catalog.document,
                manifest=snapshot.manifest,
            )
            if approved_identity_issue is not None:
                registry = dict(snapshot.manifest.entity_ids_by_handle)
                payload = WorkspacePayloadValidation(
                    document=None,
                    diagnostics=(approved_identity_issue,),
                    current_sources=(),
                    evidence_by_handle={},
                    default_basis=None,
                )
            else:
                try:
                    fresh_catalog = WorkspaceCatalog.from_snapshot(
                        self._catalog.document,
                        sources=sources,
                        handle_registry=snapshot.manifest.entity_ids_by_handle,
                    )
                except (TypeError, ValueError, WorkspaceResourceError) as error:
                    registry = dict(snapshot.manifest.entity_ids_by_handle)
                    payload = WorkspacePayloadValidation(
                        document=None,
                        diagnostics=(
                            _resource_error_diagnostic(error, snapshot.files),
                        ),
                        current_sources=(),
                        evidence_by_handle={},
                        default_basis=None,
                    )
                else:
                    registry, identity_issue = _entity_registry(
                        files=snapshot.files,
                        document_id=self._workspace.document_id,
                        manifest=snapshot.manifest,
                        catalog=fresh_catalog,
                    )
                    payload = (
                        WorkspacePayloadValidation(
                            document=None,
                            diagnostics=(identity_issue,),
                            current_sources=(),
                            evidence_by_handle={},
                            default_basis=None,
                        )
                        if identity_issue is not None
                        else validate_workspace_payload(
                            snapshot.files,
                            catalog=fresh_catalog,
                            selected_skill_ids=self._selected_skill_ids,
                            loaded_skill_ids=loaded_skill_ids,
                        )
                    )

        conflict_diagnostics = active_conflict_diagnostics(
            files=snapshot.files,
            approved_document=self._catalog.document,
            manifest=snapshot.manifest,
        )
        status = (
            (
                WorkspaceValidationStatus.CONFLICTED
                if payload.diagnostics or conflict_diagnostics
                else WorkspaceValidationStatus.VALID
            )
            if payload.document is not None
            else WorkspaceValidationStatus.INVALID
        )
        diagnostics_list = list(payload.diagnostics)
        for diagnostic in conflict_diagnostics:
            if diagnostic not in diagnostics_list:
                diagnostics_list.append(diagnostic)
        diagnostics = tuple(diagnostics_list)
        must_commit = (
            snapshot.manifest.validation_status is not status
            or snapshot.manifest.evidence_basis_digest != basis_digest
            or snapshot.manifest.diagnostics != diagnostics
            or snapshot.manifest.entity_ids_by_handle != registry
        )
        manifest = snapshot.manifest
        if must_commit:
            manifest = await self._workspace.commit_validation(
                expected_resource_digest=snapshot.manifest.resource_digest,
                evidence_basis_digest=basis_digest,
                validation_status=status,
                diagnostics=diagnostics,
                entity_ids_by_handle=registry,
            )
        result = WorkspaceValidationResult(
            manifest=manifest,
            document=payload.document,
            diagnostics=diagnostics,
            revalidated=True,
        )
        self._last_result = result
        self._last_loaded_skill_ids = loaded_skill_ids
        return result


class LoadedSkillReceipt(Protocol):
    @property
    def loaded_skill_ids(self) -> tuple[SkillId, ...]: ...


class WorkspaceValidationState(AgentState):
    workspace_validation_repair_requested: NotRequired[
        Annotated[bool, UntrackedValue, PrivateStateAttr]
    ]


class WorkspaceValidationMiddleware(AgentMiddleware[WorkspaceValidationState, Any]):
    """Validate the complete Store after-state between tool waves and model calls."""

    state_schema = WorkspaceValidationState

    def __init__(
        self,
        *,
        validator: WorkspaceValidationService,
        skill_backend: LoadedSkillReceipt,
    ) -> None:
        self._validator = validator
        self._skill_backend = skill_backend

    @override
    async def abefore_model(
        self,
        state: WorkspaceValidationState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        del state
        if runtime.context is None:
            return None
        result = await self._validator.validate_current(
            loaded_skill_ids=self._skill_backend.loaded_skill_ids,
        )
        runtime.context.workspace_validation = result.summary
        return None

    @override
    async def aafter_model(
        self,
        state: WorkspaceValidationState,
        runtime: Runtime[Any],
    ) -> dict[str, Any] | None:
        if runtime.context is None:
            return None
        summary = getattr(runtime.context, "workspace_validation", None)
        if summary is None or summary.status is not WorkspaceValidationStatus.INVALID:
            return None
        last_ai = next(
            (
                message
                for message in reversed(state.get("messages", ()))
                if isinstance(message, AIMessage)
            ),
            None,
        )
        if last_ai is None or last_ai.tool_calls:
            return None
        if state.get("workspace_validation_repair_requested", False):
            return None
        return {
            "workspace_validation_repair_requested": True,
            "jump_to": "model",
        }
