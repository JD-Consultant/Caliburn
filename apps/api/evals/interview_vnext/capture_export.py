"""Read-only PostgreSQL Capture bundle export for the turn eval harness (§12).

Production has no external Capture exporter in this slice, so V3-5 exports the
already-durable rows of one finalized run to a gitignored bundle. It only
reads:it may import production persistence models/serialization, but production
never imports it. Every row is re-validated through production serialization,
the event chain is verified against the persisted manifest, and a secret /
reasoning scan runs before anything is returned — a hit fails the export.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.interview_vnext.application.operation_executor import (
    CONTEXT_ARTIFACT_KIND,
    CONTEXT_BUDGET_ARTIFACT_KIND,
    CONTEXT_MANIFEST_ARTIFACT_KIND,
    FRAME_ARTIFACT_KIND,
    TURN_INPUT_ARTIFACT_KIND,
    TURN_OUTCOME_ARTIFACT_KIND,
    TurnInterpretExecutionOutcome,
    turn_execution_uuid,
)
from app.interview_vnext.application.turn_interpret import (
    turn_interpret_input_from_context,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.llm.capture import validate_model_call_capture_closure
from app.interview_vnext.llm.context import (
    ContextBudgetReport,
    ContextSelectionManifest,
    TurnInterpretContextPacket,
)
from app.interview_vnext.llm.port import ModelCallRequest
from app.interview_vnext.llm.turn_interpret import TurnInterpretInput
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    ArtifactRef,
    ArtifactStorage,
)
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    RunManifest,
    validate_event_chain,
)
from app.interview_vnext.observability.taxonomy import resolve_execution_taxonomy
from app.interview_vnext.persistence import serialization as ser
from app.interview_vnext.persistence.models import (
    VNextArtifactRow,
    VNextExecutionEventRow,
    VNextRunRow,
)

MODEL_REQUEST_KIND = "model.request"
RUN_MANIFEST_KIND = "capture.run_manifest"

# §5.3:context packet / selection manifest / budget report 共享的 ContextIdentity
# 欄位;三者逐欄相等才算同一個 immutable context。
_CONTEXT_IDENTITY_FIELDS = (
    "operation_name",
    "operation_definition_hash",
    "context_policy_name",
    "context_policy_version",
    "context_policy_hash",
    "session_id",
    "turn_id",
    "operation_id",
    "state_hash",
    "state_version",
    "reference_snapshot_hash",
    "section_order",
)


# §12.3 secret / reasoning gate:命中任一即 harness_invalid,不得刪字串後宣稱通過。
_SECRET_PATTERNS = (
    re.compile(r"sk-or-[A-Za-z0-9]"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"Authorization\s*[:=]"),
    re.compile(r"OPENROUTER_API_KEY"),
)


class CaptureExportError(RuntimeError):
    """A Capture bundle could not be exported cleanly (harness_invalid)."""


class SecretLeakError(CaptureExportError):
    """A secret or raw reasoning payload was found in the run's artifacts."""


class _MemoryArtifactStore:
    """In-memory ArtifactStore (duck-typed) over one run's artifacts for chain validation."""

    def __init__(self, records: dict[UUID, ArtifactRecord]) -> None:
        self._records = records

    def get(self, artifact_id: UUID) -> ArtifactRecord:
        record = self._records.get(artifact_id)
        if record is None:
            raise CaptureExportError(
                f"event references an artifact absent from the run: {artifact_id}"
            )
        return record


@dataclass(frozen=True)
class CaptureBundle:
    """Validated, secret-scanned in-memory view of one run's Capture rows."""

    tenant_id: UUID
    run_id: UUID
    run: RunManifest
    events: tuple[ExecutionEvent, ...]
    artifacts: tuple[ArtifactRecord, ...]
    manifest: RunManifest

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def last_event_hash(self) -> str:
        return self.events[-1].event_hash


def validate_capture_bundle(bundle: CaptureBundle) -> None:
    """Revalidate an in-memory export, including model-call and turn root closure.

    Order (§6.3):artifact revalidation → manifest artifact → event chain →
    provider closure → Turn Interpreter closure → secret metadata scan.  The whole
    bundle is valid only when every step passes; any failure is a fail-closed
    ``CaptureExportError`` so no corruption survives into offline grading.
    """

    if bundle.run != bundle.manifest:
        raise CaptureExportError("capture bundle run and manifest disagree")
    if bundle.run_id != bundle.manifest.run_id:
        raise CaptureExportError("capture bundle run identity mismatch")
    records = _revalidated_records(bundle)
    _validate_manifest_artifact(bundle, records)

    taxonomy = resolve_execution_taxonomy(
        bundle.manifest.taxonomy_id, bundle.manifest.taxonomy_version
    )
    store = _MemoryArtifactStore(records)
    try:
        validate_event_chain(
            bundle.events,
            taxonomy=taxonomy,
            artifact_store=store,
            manifest=bundle.manifest,
        )
        validate_model_call_capture_closure(
            bundle.events, manifest=bundle.manifest, artifact_store=store
        )
        _validate_turn_interpret_capture_closure(bundle, records)
    except CaptureExportError:
        raise
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise CaptureExportError(f"capture bundle integrity validation failed: {exc}") from exc

    for event in bundle.events:
        _scan_secret(event.metadata_json, where=f"event {event.event_id} metadata")


def _revalidated_records(bundle: CaptureBundle) -> dict[UUID, ArtifactRecord]:
    """§6.1:rebuild every ``ArtifactRecord`` through its validator before trust.

    A caller-supplied bundle may carry records built with ``model_copy`` that never
    re-ran the after-validator, so inline bytes could disagree with the ref hash.
    Re-running ``model_validate`` re-verifies inline content hash and byte size; the
    revalidated instance is the only thing stored, scanned and closed over.
    """

    records: dict[UUID, ArtifactRecord] = {}
    for record in bundle.artifacts:
        try:
            validated = ArtifactRecord.model_validate(record.model_dump(mode="python"))
        except ValidationError as exc:
            raise CaptureExportError(
                f"bundle artifact failed revalidation: {record.ref.artifact_id}: {exc}"
            ) from exc
        artifact_id = validated.ref.artifact_id
        if artifact_id in records:
            raise CaptureExportError(f"duplicate artifact in bundle: {artifact_id}")
        if validated.run_id != bundle.run_id or validated.run_id != bundle.manifest.run_id:
            raise CaptureExportError(f"bundle artifact run scope mismatch: {artifact_id}")
        if validated.session_id != bundle.manifest.session_id:
            raise CaptureExportError(f"bundle artifact session scope mismatch: {artifact_id}")
        if validated.storage == ArtifactStorage.EXTERNAL:
            # This eval bundle never carries external bytes, so it cannot claim to
            # have verified their content — fail closed rather than trust a pointer.
            raise CaptureExportError(
                f"bundle carries an external artifact without bytes: {artifact_id}"
            )
        _scan_secret(validated.inline_content, where=f"artifact {artifact_id}")
        _scan_reasoning(validated)
        records[artifact_id] = validated
    return records


def _validate_manifest_artifact(
    bundle: CaptureBundle, records: dict[UUID, ArtifactRecord]
) -> None:
    """§6.2:exactly one inline ``capture.run_manifest`` artifact that parses back to
    ``bundle.manifest`` and is not itself a root (a pointer, never self-referential)."""

    manifest_records = [
        record for record in records.values() if record.ref.kind == RUN_MANIFEST_KIND
    ]
    if len(manifest_records) != 1:
        raise CaptureExportError(
            f"bundle must carry exactly one run manifest artifact, found {len(manifest_records)}"
        )
    manifest_record = manifest_records[0]
    if manifest_record.inline_content is None:
        raise CaptureExportError("run manifest artifact is not inline")
    root_ids = {ref.artifact_id for ref in bundle.manifest.root_artifacts}
    if manifest_record.ref.artifact_id in root_ids:
        raise CaptureExportError("run manifest artifact must not be a terminal root")
    try:
        parsed = RunManifest.model_validate_json(manifest_record.inline_content)
    except ValidationError as exc:
        raise CaptureExportError(f"run manifest artifact is invalid: {exc}") from exc
    if parsed != bundle.manifest:
        raise CaptureExportError("run manifest artifact disagrees with bundle manifest")


def _require_exact_root(
    ref: ArtifactRef | None,
    roots_by_id: dict[UUID, ArtifactRef],
    label: str,
) -> None:
    """Require ``ref`` (when present) to be an exact terminal root — full ArtifactRef
    equality, not just a matching ID (§16 correctness)."""

    if ref is None:
        return
    if roots_by_id.get(ref.artifact_id) != ref:
        raise CaptureExportError(
            f"turn closure: {label} is not an exact terminal root: {ref.artifact_id}"
        )


def _load_inline_ref(
    ref: ArtifactRef,
    records: dict[UUID, ArtifactRecord],
    expected_kind: str,
    label: str,
) -> ArtifactRecord:
    """Load the inline record a ref points to, requiring exact ref + kind match."""

    record = records.get(ref.artifact_id)
    if record is None:
        raise CaptureExportError(f"turn closure: {label} artifact is absent: {ref.artifact_id}")
    if record.ref != ref:
        raise CaptureExportError(f"turn closure: {label} artifact ref mismatch: {ref.artifact_id}")
    if record.ref.kind != expected_kind:
        raise CaptureExportError(
            f"turn closure: {label} expected kind {expected_kind}, got {record.ref.kind}"
        )
    if record.inline_content is None:
        raise CaptureExportError(f"turn closure: {label} artifact is not inline: {ref.artifact_id}")
    return record


def _require_operation_scope(
    record: ArtifactRecord,
    *,
    run_id: UUID,
    session_id: UUID,
    operation_id: UUID,
    turn_id: UUID | None,
    label: str,
) -> None:
    """Operation-scoped artifacts must belong to this run/session/operation/turn (§6.4)."""

    if (
        record.run_id != run_id
        or record.session_id != session_id
        or record.operation_id != operation_id
    ):
        raise CaptureExportError(
            f"turn closure: {label} scope mismatch: {record.ref.artifact_id}"
        )
    if turn_id is not None and record.turn_id is not None and record.turn_id != turn_id:
        raise CaptureExportError(
            f"turn closure: {label} turn mismatch: {record.ref.artifact_id}"
        )


def _scope_authority_ref(
    ref: ArtifactRef | None,
    records: dict[UUID, ArtifactRecord],
    *,
    run_id: UUID,
    session_id: UUID,
    operation_id: UUID,
    turn_id: UUID | None,
    attempt_required: bool,
    label: str,
) -> None:
    """Load the record a checkpoint/outcome authority ref points to and require exact
    ref + operation/turn scope (§6.4); attempt-bearing authorities must carry one."""

    if ref is None:
        return
    record = records.get(ref.artifact_id)
    if record is None:
        raise CaptureExportError(f"turn closure: {label} artifact is absent: {ref.artifact_id}")
    if record.ref != ref:
        raise CaptureExportError(f"turn closure: {label} artifact ref mismatch: {ref.artifact_id}")
    _require_operation_scope(
        record, run_id=run_id, session_id=session_id,
        operation_id=operation_id, turn_id=turn_id, label=label,
    )
    if attempt_required and record.attempt_id is None:
        raise CaptureExportError(
            f"turn closure: {label} is missing attempt scope: {ref.artifact_id}"
        )


def _context_identity_tuple(model: object) -> tuple:
    return tuple(getattr(model, field) for field in _CONTEXT_IDENTITY_FIELDS)


def _validate_turn_interpret_capture_closure(
    bundle: CaptureBundle, records: dict[UUID, ArtifactRecord]
) -> None:
    """Turn Interpreter-specific closure (§5.2/§5.3/§5.5).

    Runs only when the terminal manifest roots a turn-interpret execution outcome;
    other runs are already closed by the generic event/provider validators.  Uses
    the persisted typed authorities directly — no parallel dict schema, no
    re-rendering of prompt or re-building of context.
    """

    manifest = bundle.manifest
    roots_by_id = {ref.artifact_id: ref for ref in manifest.root_artifacts}
    run_id = manifest.run_id
    session_id = manifest.session_id

    # Parse every rooted model.request first: a run is a turn-interpret run when a
    # rooted request declares operation_name "turn.interpret" (§16). Keying off the
    # request means an outcome that was itself unrooted or deleted cannot disguise a
    # turn run as a non-turn run and skip closure.
    request_refs = tuple(
        ref for ref in manifest.root_artifacts if ref.kind == MODEL_REQUEST_KIND
    )
    parsed_requests: list[tuple[ArtifactRef, ArtifactRecord, ModelCallRequest]] = []
    for request_ref in request_refs:
        request_record = _load_inline_ref(
            request_ref, records, MODEL_REQUEST_KIND, "model request"
        )
        parsed_requests.append(
            (
                request_ref,
                request_record,
                ModelCallRequest.model_validate_json(request_record.inline_content),
            )
        )

    is_turn_run = any(
        request.operation_name == "turn.interpret" for _, _, request in parsed_requests
    )
    outcome_present = any(
        record.ref.kind == TURN_OUTCOME_ARTIFACT_KIND for record in records.values()
    )
    if not is_turn_run and not outcome_present:
        return

    outcome_roots = tuple(
        ref for ref in manifest.root_artifacts if ref.kind == TURN_OUTCOME_ARTIFACT_KIND
    )
    # A turn-interpret run always carries exactly one rooted execution outcome; an
    # outcome that exists only as a record, or not at all, is corruption once the
    # rooted request marks this a turn run.
    if len(outcome_roots) != 1:
        raise CaptureExportError(
            "turn closure: expected exactly one rooted execution outcome"
        )
    outcome_record = _load_inline_ref(
        outcome_roots[0], records, TURN_OUTCOME_ARTIFACT_KIND, "execution outcome"
    )
    outcome = TurnInterpretExecutionOutcome.model_validate_json(
        outcome_record.inline_content
    )
    checkpoint = outcome.checkpoint
    operation_id = checkpoint.operation_id
    turn_id = checkpoint.turn_id
    _require_operation_scope(
        outcome_record, run_id=run_id, session_id=session_id,
        operation_id=operation_id, turn_id=turn_id, label="execution outcome",
    )

    # §5.5 + §6.4:every non-null checkpoint/outcome ref must be an exact terminal
    # root, and its record must be scoped to this run/session/operation/turn.  The
    # attempt-bearing provider authorities must additionally carry an attempt id.
    attempt_scoped = {
        "checkpoint.attempt_result",
        "checkpoint.provider_result",
        "checkpoint.provider_execution_evidence",
        "checkpoint.provider_conformance",
        "outcome.provider_result",
    }
    checkpoint_refs = (
        ("checkpoint.request", checkpoint.request_artifact),
        *(
            ("checkpoint.attempt_result", ref)
            for ref in checkpoint.attempt_result_artifacts
        ),
        ("checkpoint.provider_result", checkpoint.provider_result_artifact),
        (
            "checkpoint.provider_execution_evidence",
            checkpoint.provider_execution_evidence_artifact,
        ),
        ("checkpoint.provider_conformance", checkpoint.provider_conformance_artifact),
        ("checkpoint.verification", checkpoint.verification_artifact),
        ("checkpoint.domain_result", checkpoint.domain_result_artifact),
        ("checkpoint.response", checkpoint.response_artifact),
        ("checkpoint.failure", checkpoint.failure_artifact),
    )
    outcome_refs = (
        ("outcome.context_packet", outcome.context_packet_ref),
        ("outcome.input", outcome.input_ref),
        ("outcome.provider_result", outcome.provider_result_ref),
        ("outcome.verification_report", outcome.verification_report_ref),
        ("outcome.interpretation_record", outcome.interpretation_record_ref),
        ("outcome.domain_command", outcome.domain_command_ref),
        ("outcome.reduction_result", outcome.reduction_result_ref),
        ("outcome.turn_output", outcome.turn_output_ref),
        ("outcome.failure", outcome.failure_ref),
        ("outcome.response", outcome.response_artifact),
    )
    for label, ref in (*checkpoint_refs, *outcome_refs):
        _require_exact_root(ref, roots_by_id, label)
        _scope_authority_ref(
            ref, records, run_id=run_id, session_id=session_id,
            operation_id=operation_id, turn_id=turn_id,
            attempt_required=label in attempt_scoped, label=label,
        )

    # §5.2:每個 rooted model.request 的四個 content dependency 都要 rooted、scoped，
    # 且送出的 bytes 與 artifact 一致（不重新 render，只比 persisted authority）。
    if not parsed_requests:
        raise CaptureExportError("turn closure: terminal manifest has no rooted model.request")
    for request_ref, request_record, request in parsed_requests:
        _require_operation_scope(
            request_record, run_id=run_id, session_id=session_id,
            operation_id=operation_id, turn_id=turn_id, label="model request",
        )
        if request_record.attempt_id is None:
            raise CaptureExportError(
                f"turn closure: model request missing attempt scope: {request_ref.artifact_id}"
            )
        if (
            request.run_id != run_id
            or request.session_id != session_id
            or request.operation_id != operation_id
        ):
            raise CaptureExportError(
                f"turn closure: request scope mismatch: {request_ref.artifact_id}"
            )
        for label, ref in (
            ("request.prompt", request.prompt_artifact),
            ("request.output_schema", request.output_schema_artifact),
            ("request.context", request.context_artifact),
            ("request.selection_manifest", request.selection_manifest_artifact),
        ):
            _require_exact_root(ref, roots_by_id, label)
        prompt_record = _load_inline_ref(
            request.prompt_artifact, records, "prompt.template", "prompt"
        )
        _require_operation_scope(
            prompt_record, run_id=run_id, session_id=session_id,
            operation_id=operation_id, turn_id=turn_id, label="prompt",
        )
        if prompt_record.inline_content != request.instructions:
            raise CaptureExportError(
                "turn closure: prompt artifact bytes differ from request instructions"
            )
        schema_record = _load_inline_ref(
            request.output_schema_artifact, records, "schema.output", "output schema"
        )
        _require_operation_scope(
            schema_record, run_id=run_id, session_id=session_id,
            operation_id=operation_id, turn_id=turn_id, label="output schema",
        )
        if request.output_schema_artifact.schema_id != request.output_schema_id:
            raise CaptureExportError(
                "turn closure: output schema ref id differs from request output_schema_id"
            )
        if request.context_artifact != outcome.context_packet_ref:
            raise CaptureExportError(
                "turn closure: request context artifact does not match outcome context packet"
            )
        # attempt 1 的第一個 user message 逐字等於持久化 TurnInterpretInput 的 canonical JSON。
        if request.attempt == 1:
            input_record = _load_inline_ref(
                outcome.input_ref, records, TURN_INPUT_ARTIFACT_KIND, "turn input"
            )
            if not request.messages or request.messages[0].text != input_record.inline_content:
                raise CaptureExportError(
                    "turn closure: attempt-1 user message differs from persisted turn input"
                )

    # §5.3:context packet / selection manifest / budget / turn input / frame closure。
    packet_record = _load_inline_ref(
        outcome.context_packet_ref, records, CONTEXT_ARTIFACT_KIND, "context packet"
    )
    _require_operation_scope(
        packet_record, run_id=run_id, session_id=session_id,
        operation_id=operation_id, turn_id=turn_id, label="context packet",
    )
    packet = TurnInterpretContextPacket.model_validate_json(packet_record.inline_content)

    authoritative_request_record = _load_inline_ref(
        checkpoint.request_artifact, records, MODEL_REQUEST_KIND, "checkpoint request"
    )
    authoritative_request = ModelCallRequest.model_validate_json(
        authoritative_request_record.inline_content
    )
    selection_record = _load_inline_ref(
        authoritative_request.selection_manifest_artifact,
        records,
        CONTEXT_MANIFEST_ARTIFACT_KIND,
        "context selection manifest",
    )
    _require_operation_scope(
        selection_record, run_id=run_id, session_id=session_id,
        operation_id=operation_id, turn_id=turn_id, label="context selection manifest",
    )
    selection = ContextSelectionManifest.model_validate_json(
        selection_record.inline_content
    )

    budget_id = turn_execution_uuid(operation_id, "context-budget")
    budget_record = records.get(budget_id)
    if budget_record is None:
        raise CaptureExportError("turn closure: context budget artifact is absent")
    _require_exact_root(budget_record.ref, roots_by_id, "context budget")
    if budget_record.ref.kind != CONTEXT_BUDGET_ARTIFACT_KIND:
        raise CaptureExportError(
            f"turn closure: context budget kind is {budget_record.ref.kind}"
        )
    _require_operation_scope(
        budget_record, run_id=run_id, session_id=session_id,
        operation_id=operation_id, turn_id=turn_id, label="context budget",
    )
    budget = ContextBudgetReport.model_validate_json(budget_record.inline_content)

    input_record = _load_inline_ref(
        outcome.input_ref, records, TURN_INPUT_ARTIFACT_KIND, "turn input"
    )
    _require_operation_scope(
        input_record, run_id=run_id, session_id=session_id,
        operation_id=operation_id, turn_id=turn_id, label="turn input",
    )
    turn_input = TurnInterpretInput.model_validate_json(input_record.inline_content)

    if packet.question_frame is not None:
        frame_id = turn_execution_uuid(operation_id, "question-frame-snapshot")
        frame_record = records.get(frame_id)
        if frame_record is None:
            raise CaptureExportError(
                "turn closure: eligible question frame has no snapshot artifact"
            )
        _require_exact_root(frame_record.ref, roots_by_id, "question frame snapshot")
        if frame_record.ref.kind != FRAME_ARTIFACT_KIND:
            raise CaptureExportError(
                f"turn closure: frame snapshot kind is {frame_record.ref.kind}"
            )
        _require_operation_scope(
            frame_record, run_id=run_id, session_id=session_id,
            operation_id=operation_id, turn_id=turn_id, label="question frame snapshot",
        )
        if frame_record.ref.content_hash != canonical_hash(packet.question_frame.frame):
            raise CaptureExportError(
                "turn closure: frame snapshot content differs from the packet frame"
            )

    identities = (
        _context_identity_tuple(packet),
        _context_identity_tuple(selection),
        _context_identity_tuple(budget),
    )
    if identities[0] != identities[1] or identities[0] != identities[2]:
        raise CaptureExportError(
            "turn closure: context identity fields disagree across packet/selection/budget"
        )

    if turn_interpret_input_from_context(packet) != turn_input:
        raise CaptureExportError(
            "turn closure: turn input is not the deterministic projection of the context packet"
        )


def _scan_secret(text: str | None, *, where: str) -> None:
    if not text:
        return
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise SecretLeakError(f"possible secret in {where}: pattern {pattern.pattern}")


def _scan_reasoning(record: ArtifactRecord) -> None:
    """Raw provider reasoning may only survive as redacted metadata (§12.3)."""

    if "reasoning" in record.ref.kind and record.redaction_status != "applied":
        raise SecretLeakError(
            f"raw reasoning artifact is not redacted: {record.ref.artifact_id}"
        )


async def export_run_bundle(
    session_factory: async_sessionmaker, *, tenant_id: UUID, run_id: UUID
) -> CaptureBundle:
    """Load, revalidate and secret-scan one finalized run's Capture rows."""

    async with session_factory() as session:
        run_row = (
            await session.execute(
                sa.select(VNextRunRow).where(
                    VNextRunRow.tenant_id == tenant_id,
                    VNextRunRow.run_id == run_id,
                )
            )
        ).scalar_one_or_none()
        if run_row is None:
            raise CaptureExportError(f"run does not exist: {run_id}")
        if run_row.manifest_artifact_id is None:
            raise CaptureExportError("cannot export a non-finalized run")

        event_rows = (
            await session.execute(
                sa.select(VNextExecutionEventRow)
                .where(
                    VNextExecutionEventRow.tenant_id == tenant_id,
                    VNextExecutionEventRow.run_id == run_id,
                )
                .order_by(VNextExecutionEventRow.sequence)
            )
        ).scalars().all()
        artifact_rows = (
            await session.execute(
                sa.select(VNextArtifactRow)
                .where(
                    VNextArtifactRow.tenant_id == tenant_id,
                    VNextArtifactRow.run_id == run_id,
                )
                .order_by(VNextArtifactRow.created_at, VNextArtifactRow.artifact_id)
            )
        ).scalars().all()

    events = tuple(
        ser.load_event(
            row.event_json, row.event_hash,
            event_id=row.event_id, run_id=row.run_id, sequence=row.sequence,
        )
        for row in event_rows
    )
    if not events:
        raise CaptureExportError("finalized run has no events")

    records: dict[UUID, ArtifactRecord] = {}
    ordered_records: list[ArtifactRecord] = []
    for row in artifact_rows:
        record = ser.load_artifact(row)  # re-verifies inline hash/byte size
        _scan_secret(record.inline_content, where=f"artifact {record.ref.artifact_id}")
        _scan_reasoning(record)
        records[record.ref.artifact_id] = record
        ordered_records.append(record)

    manifest_record = records.get(run_row.manifest_artifact_id)
    if manifest_record is None or manifest_record.inline_content is None:
        raise CaptureExportError("run manifest artifact is missing or external")
    manifest = RunManifest.model_validate_json(manifest_record.inline_content)

    bundle = CaptureBundle(
        tenant_id=tenant_id,
        run_id=run_id,
        run=manifest,
        events=events,
        artifacts=tuple(ordered_records),
        manifest=manifest,
    )
    # Event chain, root existence/hash, model-call closure and redaction are one
    # export gate so re-export and offline regrade share identical integrity rules.
    validate_capture_bundle(bundle)
    return bundle
