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
from typing_extensions import NotRequired, override

from app.consultant.evidence_anchor import EvidenceAnchorError, resolve_evidence_reference
from app.consultant.results import AnalysisBasis, SkillId
from app.consultant.state import (
    EmployeeSource,
    SourceProcessingStatus,
    SourceValidity,
)
from app.consultant.workspace_resources import (
    CandidateDocumentDraft,
    WorkspaceCatalog,
    WorkspaceResourceError,
    parse_candidate_files,
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
_COMPATIBILITY_RUN_ID = UUID("00000000-0000-0000-0000-000000000000")
_MAX_DIAGNOSTICS = 8
_ENTITY_PATH = re.compile(
    r"^/workspace/(?:(duties)/(duty-[^/]+)|(tasks)/(task-[^/]+)|"
    r"opks/(o|p|k|s)/((?:o|p|k|s)-[^/]+))\.json$"
)


@dataclass(frozen=True, slots=True)
class WorkspaceValidationSummary:
    generation: int
    status: WorkspaceValidationStatus
    resource_digest: Sha256Digest
    diagnostics: tuple[WorkspaceDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class WorkspaceValidationResult:
    manifest: WorkspaceManifest
    document: CandidateDocumentDraft | None
    diagnostics: tuple[WorkspaceDiagnostic, ...]
    revalidated: bool

    def __post_init__(self) -> None:
        if (
            self.manifest.validation_status is WorkspaceValidationStatus.VALID
        ) != (self.document is not None):
            raise ValueError("only a valid workspace may expose a parsed document")

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
    document: CandidateDocumentDraft | None
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
    candidate = re.search(r"/candidate/[^/]+/([^\s:]+)", message)
    if candidate is not None:
        return "/workspace/" + candidate.group(1).rstrip(".,)")
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
        safe_message = "Resource does not match the canonical JD schema."
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


def _compatibility_view(files: Mapping[str, str]) -> dict[str, str]:
    root = f"/candidate/{_COMPATIBILITY_RUN_ID}/"
    return {
        root + path.removeprefix("/workspace/"): content
        for path, content in files.items()
    }


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
    draft: CandidateDocumentDraft,
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
    for binding in draft.opks_evidence:
        path = _workspace_path_for_handle(files, binding.opks_handle)
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
            bindings.setdefault(binding.opks_handle, []).append(
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


def _candidate_run_id(files: Mapping[str, str]) -> UUID:
    for path in files:
        if path.startswith("/candidate/"):
            return UUID(path.split("/")[2])
    raise WorkspaceResourceError("candidate run namespace must be a UUID")


def validate_workspace_payload(
    files: Mapping[str, str],
    *,
    catalog: WorkspaceCatalog,
    selected_skill_ids: Sequence[SkillId],
    loaded_skill_ids: Sequence[SkillId],
) -> WorkspacePayloadValidation:
    """Parse and validate one workspace/candidate payload without side effects."""

    normalized = dict(sorted(files.items()))
    workspace_files = bool(normalized) and all(
        path.startswith("/workspace/") for path in normalized
    )
    parser_files = _compatibility_view(normalized) if workspace_files else normalized
    try:
        draft = parse_candidate_files(
            catalog,
            parser_files,
            run_id=(
                _COMPATIBILITY_RUN_ID
                if workspace_files
                else _candidate_run_id(parser_files)
            ),
            new_entity_namespace=("workspace" if workspace_files else "candidate"),
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
    current_ids = {source.source_id for source in current_sources}
    if any(
        set(item.evidence_source_ids) - current_ids
        for item in draft.approved_document.opks
    ):
        diagnostics = (
            *diagnostics,
            _diagnostic(
                "evidence-source-stale",
                "/workspace/opks",
                "OPKS evidence basis contains a source that is no longer current.",
            ),
        )
    diagnostics = tuple(diagnostics[:_MAX_DIAGNOSTICS])
    return WorkspacePayloadValidation(
        document=(None if diagnostics else draft),
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
        basis_digest = evidence_basis_digest(sources)
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
            fresh_catalog = WorkspaceCatalog.from_snapshot(
                self._catalog.document,
                pending=self._catalog.pending,
                sources=sources,
            )
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

        status = (
            WorkspaceValidationStatus.VALID
            if payload.document is not None
            else WorkspaceValidationStatus.INVALID
        )
        must_commit = (
            snapshot.manifest.validation_status is not status
            or snapshot.manifest.evidence_basis_digest != basis_digest
            or snapshot.manifest.diagnostics != payload.diagnostics
            or snapshot.manifest.entity_ids_by_handle != registry
        )
        manifest = snapshot.manifest
        if must_commit:
            manifest = await self._workspace.commit_validation(
                expected_resource_digest=snapshot.manifest.resource_digest,
                evidence_basis_digest=basis_digest,
                validation_status=status,
                diagnostics=payload.diagnostics,
                entity_ids_by_handle=registry,
            )
        result = WorkspaceValidationResult(
            manifest=manifest,
            document=payload.document,
            diagnostics=payload.diagnostics,
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
